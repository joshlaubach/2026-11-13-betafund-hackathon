"""Model calls, the SymPy equivalence check, and call budgets for worksheet grading.

AnswerSolver.solve() answers a statement and never sees a student's answer; judge() sees both.
LiveSolver is the only class that reaches the network, and only through call_model. FakeSolver is
scripted and records every call. compare_answers and compare_to_expression are the SymPy
equivalence check, and LaTeX is read only through core.latex_reader. CallBudget and CallLedger
count model calls for a worksheet and for one item.
"""

from __future__ import annotations

import math
import os
import threading
from collections.abc import Mapping
from typing import NamedTuple, Optional, TypeVar

import anthropic
import sympy as sp
from pydantic import BaseModel

from core.derivative_checker import ABS_FLOOR, MIN_COMPARABLE_POINTS, REL_TOLERANCE, SAMPLE_POINTS, X
from core.drafter import (
    AUTH_MESSAGE,
    DEFAULT_EFFORT,
    DEFAULT_MODEL,
    MAX_TOKENS,
    OUTPUT_CONFIG_ARG,
    SOURCE_FAKE,
    SOURCE_LIVE,
)
from core.input_boundary import BoundaryError
from core.latex_reader import read_latex
from core.worksheet_types import GradeMethod, Verdict

ENV_API_KEY = "ANTHROPIC_API_KEY"
WORKSHEET_CALL_BUDGET = 40
ITEM_CALL_CAP = 3
BUDGET_REASON = "call budget reached"
ITEM_CAP_REASON = "item call limit reached"
RATE_LIMIT_MESSAGE = "rate limited by the model service; try again later"
CONNECTION_MESSAGE = "could not reach the model service"
REFUSAL_MESSAGE = "the model declined to read the worksheet"
EMPTY_MESSAGE = "the model returned no reading"
EQUAL = "equal"
DIFFERENT = "different"
UNKNOWN = "unknown"
CONSTANT_EXPLANATION = "answers differ by a constant; check for + C"
UNCOMPARED_EXPLANATION = (
    "SymPy could not compare the student's answer with the verified key, so this mark is unsure."
)
JUDGE_FAILED_EXPLANATION = "the AI judge could not give a verdict, so this mark is unsure."
SOLVE_SYSTEM_PROMPT = (
    "You solve calculus problems for Echo. Give the final answer only, as LaTeX that uses only "
    "digits, x, + and -, ^ for powers (write x^{3}), \\frac{a}{b}, \\sqrt{...}, \\sqrt[n]{...}, "
    "\\ln, \\sin, \\cos, \\tan, \\exp, \\pi, braces, and parentheses. Do not write '+ C'. "
    "Return only the structured output requested."
)
JUDGE_SYSTEM_PROMPT = (
    "You judge a student's written answer to a calculus problem for Echo. Reply correct or "
    "incorrect only when you are sure; reply unsure when you cannot tell. "
    "Return only the structured output requested."
)

ModelT = TypeVar("ModelT", bound=BaseModel)


class SolveReply(BaseModel):
    final_answer_latex: str


class JudgeReply(BaseModel):
    verdict: Verdict


class SourceError(Exception):
    """A reading source or a solver could not answer. The message is shown to the user."""


class Comparison(NamedTuple):
    status: str  # EQUAL, DIFFERENT, or UNKNOWN
    points: int = 0
    constant_offset: bool = False


class Mark(NamedTuple):
    """A verdict, how it was made, and the answer shown beside the student's."""

    verdict: Verdict
    method: GradeMethod
    explanation: str
    reference: Optional[str] = None


class Attempt(NamedTuple):
    """One solve. answer is None when the solver failed; refusal is set when no call was made."""

    answer: Optional[str] = None
    refusal: Optional[str] = None


class CallBudget:
    """How many model calls a worksheet may still make. take() is thread-safe."""

    def __init__(self, total: int = WORKSHEET_CALL_BUDGET) -> None:
        self._remaining = total
        self._lock = threading.Lock()

    @property
    def remaining(self) -> int:
        with self._lock:
            return self._remaining

    def take(self) -> bool:
        """Spend one call. Returns False, and spends nothing, when the budget is empty."""
        with self._lock:
            if self._remaining <= 0:
                return False
            self._remaining -= 1
            return True


class CallLedger:
    """Calls made for one item: at most ITEM_CALL_CAP, each also spent from the worksheet budget."""

    def __init__(self, budget: CallBudget) -> None:
        self._budget = budget
        self._spent = 0

    def take(self) -> Optional[str]:
        """Reserve one call. Returns None when the call may be made, else the reason it may not."""
        if self._spent >= ITEM_CALL_CAP:
            return ITEM_CAP_REASON
        if not self._budget.take():
            return BUDGET_REASON
        self._spent += 1
        return None


class AnswerSolver:
    """Base for solvers. solve() never sees a student's answer; judge() does.

    effort None means the solver's own default. source is "live" or "fake".
    """

    name: str = "solver"
    source: str = ""
    last_usage: Optional[dict] = None

    def solve(self, statement: str, effort: Optional[str] = None) -> str:
        raise NotImplementedError

    def judge(
        self, statement: str, student_answer: str, effort: Optional[str] = None
    ) -> JudgeReply:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Model calls
# ---------------------------------------------------------------------------


def _model_error_message(error: anthropic.APIError) -> str:
    if isinstance(error, anthropic.AuthenticationError):
        return AUTH_MESSAGE
    if isinstance(error, anthropic.RateLimitError):
        return RATE_LIMIT_MESSAGE
    if isinstance(error, anthropic.APIConnectionError):
        return CONNECTION_MESSAGE
    if isinstance(error, anthropic.APIStatusError):
        return f"the model service returned HTTP {error.status_code}"
    return "the model service could not complete the request"


def _parse_once(client: anthropic.Anthropic, request: dict, effort: str) -> object:
    """One structured call. Retries once without output_config on older SDKs."""
    try:
        return client.messages.parse(**request, output_config={"effort": effort})
    except TypeError as error:
        if OUTPUT_CONFIG_ARG not in str(error):
            raise
        return client.messages.parse(**request)


def _usage_of(response: object) -> Optional[dict]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    return {
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
    }


def call_model(
    model: str,
    effort: str,
    system: str,
    content: object,
    output_model: type[ModelT],
) -> tuple[ModelT, Optional[dict]]:
    """Ask the model for a structured reply. Raises SourceError for every failure."""
    if not os.environ.get(ENV_API_KEY, "").strip():
        raise SourceError(AUTH_MESSAGE)
    request = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "system": system,
        "messages": [{"role": "user", "content": content}],
        "output_format": output_model,
    }
    try:
        response = _parse_once(anthropic.Anthropic(), request, effort)
    except anthropic.APIError as error:
        raise SourceError(_model_error_message(error)) from error
    if response.stop_reason == "refusal":  # type: ignore[attr-defined]
        raise SourceError(REFUSAL_MESSAGE)
    if response.parsed_output is None:  # type: ignore[attr-defined]
        raise SourceError(EMPTY_MESSAGE)
    return response.parsed_output, _usage_of(response)  # type: ignore[attr-defined]


class LiveSolver(AnswerSolver):
    source = SOURCE_LIVE

    def __init__(self, model: str = DEFAULT_MODEL, effort: str = DEFAULT_EFFORT) -> None:
        self.model = model
        self.effort = effort
        self.name = f"live ({model}, effort {effort})"

    def solve(self, statement: str, effort: Optional[str] = None) -> str:
        reply, self.last_usage = call_model(
            self.model,
            effort or self.effort,
            SOLVE_SYSTEM_PROMPT,
            f"Problem: {statement}\nGive the final answer only.",
            SolveReply,
        )
        return reply.final_answer_latex

    def judge(
        self, statement: str, student_answer: str, effort: Optional[str] = None
    ) -> JudgeReply:
        prompt = (
            f"Problem: {statement}\n"
            f"Student's written answer: {student_answer}\n"
            "Reply with a verdict: correct, incorrect, or unsure."
        )
        reply, self.last_usage = call_model(
            self.model, effort or self.effort, JUDGE_SYSTEM_PROMPT, prompt, JudgeReply
        )
        return reply


class FakeSolver(AnswerSolver):
    """Scripted solver for tests and fake mode. Records every call; never touches the network."""

    name = "fake"
    source = SOURCE_FAKE

    def __init__(
        self,
        answers: Optional[Mapping[str, str]] = None,
        verdict: Verdict = "unsure",
        error: Optional[str] = None,
    ) -> None:
        self._answers = dict(answers or {})
        self._verdict = verdict
        self._error = error
        self._solve_calls: list[tuple[str, Optional[str]]] = []
        self._judge_calls: list[tuple[str, str, Optional[str]]] = []

    @property
    def solve_calls(self) -> tuple[tuple[str, Optional[str]], ...]:
        """Each solve call as (statement, effort). The student's answer is never passed."""
        return tuple(self._solve_calls)

    @property
    def judge_calls(self) -> tuple[tuple[str, str, Optional[str]], ...]:
        return tuple(self._judge_calls)

    def solve(self, statement: str, effort: Optional[str] = None) -> str:
        self._solve_calls.append((statement, effort))
        if self._error is not None:
            raise SourceError(self._error)
        if statement not in self._answers:
            raise SourceError("no scripted answer for this statement")
        return self._answers[statement]

    def judge(
        self, statement: str, student_answer: str, effort: Optional[str] = None
    ) -> JudgeReply:
        self._judge_calls.append((statement, student_answer, effort))
        if self._error is not None:
            raise SourceError(self._error)
        return JudgeReply(verdict=self._verdict)


def ask_solve(
    solver: AnswerSolver, statement: str, ledger: CallLedger, effort: Optional[str]
) -> Attempt:
    """One blind solve, counted against the ledger. A solver failure is an Attempt with no answer."""
    refusal = ledger.take()
    if refusal is not None:
        return Attempt(refusal=refusal)
    try:
        return Attempt(answer=solver.solve(statement, effort))
    except Exception:  # a solver failure is a missing answer, never a crash
        return Attempt()


# ---------------------------------------------------------------------------
# SymPy equivalence check
# ---------------------------------------------------------------------------


def _real_value(expr: sp.Basic) -> Optional[float]:
    """Return expr as a finite real float, or None if it is not one."""
    try:
        value = complex(sp.N(expr))
    except (TypeError, ValueError, ArithmeticError):
        return None
    if value.imag != 0 or not math.isfinite(value.real):
        return None
    return value.real


def _value_at(expr: sp.Basic, point: float) -> Optional[float]:
    try:
        return _real_value(expr.subs(X, sp.Float(point)))
    except (TypeError, ValueError, ArithmeticError):
        return None


def _values_agree(left: float, right: float) -> bool:
    scale = max(abs(left), abs(right))
    return abs(left - right) <= REL_TOLERANCE * scale + ABS_FLOOR


def _depends_on_x(expr: sp.Basic) -> bool:
    return any(symbol.name == X.name for symbol in expr.free_symbols)


def _comparable_pairs(reference: sp.Basic, student: sp.Basic) -> list[tuple[float, float]]:
    pairs: list[tuple[float, float]] = []
    for point in SAMPLE_POINTS:
        reference_value = _value_at(reference, point)
        student_value = _value_at(student, point)
        if reference_value is not None and student_value is not None:
            pairs.append((reference_value, student_value))
    return pairs


def _is_constant_offset(pairs: list[tuple[float, float]]) -> bool:
    """True when student minus reference is the same nonzero number at every sample point."""
    first = pairs[0][0] - pairs[0][1]
    if _values_agree(first, 0.0):
        return False
    return all(_values_agree(reference - student, first) for reference, student in pairs)


def compare_expressions(reference: sp.Basic, student: sp.Basic) -> Comparison:
    """Compare two SymPy expressions at fixed non-grid points in x, with the derivative checker's tolerance.

    Needs MIN_COMPARABLE_POINTS comparable points. A nonzero constant difference is reported as
    constant_offset when an answer depends on x (the "+ C" case); two constants that differ are
    simply different.
    """
    pairs = _comparable_pairs(reference, student)
    if len(pairs) < MIN_COMPARABLE_POINTS:
        return Comparison(UNKNOWN, len(pairs))
    if all(_values_agree(reference_value, student_value) for reference_value, student_value in pairs):
        return Comparison(EQUAL, len(pairs))
    depends = _depends_on_x(reference) or _depends_on_x(student)
    if depends and _is_constant_offset(pairs):
        return Comparison(UNKNOWN, len(pairs), constant_offset=True)
    return Comparison(DIFFERENT, len(pairs))


def compare_to_expression(reference: sp.Basic, student_latex: str) -> Comparison:
    """Compare a SymPy expression with a student's LaTeX answer. UNKNOWN when the LaTeX cannot be read."""
    try:
        student = read_latex(student_latex)
    except BoundaryError:
        return Comparison(UNKNOWN)
    return compare_expressions(reference, student)


def compare_answers(reference_latex: str, student_latex: str) -> Comparison:
    """Compare two LaTeX answers. UNKNOWN when either cannot be read. See compare_expressions."""
    try:
        reference = read_latex(reference_latex)
    except BoundaryError:
        return Comparison(UNKNOWN)
    return compare_to_expression(reference, student_latex)


def answers_equivalent(a_latex: str, b_latex: str) -> str:
    """Return "equal", "different", or "unknown" for two LaTeX answers. See compare_answers."""
    return compare_answers(a_latex, b_latex).status


def is_readable(latex: str) -> bool:
    """True when core.latex_reader can read the LaTeX, so SymPy can compare it."""
    try:
        read_latex(latex)
    except BoundaryError:
        return False
    return True


def comparison_mark(
    comparison: Comparison,
    student: str,
    reference: str,
    method: GradeMethod,
    source_phrase: str,
) -> Optional[Mark]:
    """A mark from a comparison, or None when SymPy could not compare the answers."""
    if comparison.constant_offset:
        return Mark("unsure", method, CONSTANT_EXPLANATION, reference)
    if comparison.status == EQUAL:
        explanation = (
            f"The student's answer {student} matches {source_phrase} {reference} "
            f"at {comparison.points} sample points, checked by SymPy."
        )
        return Mark("correct", method, explanation, reference)
    if comparison.status == DIFFERENT:
        explanation = (
            f"The student's answer {student} does not match {source_phrase} {reference}: "
            "SymPy found different values at a sample point."
        )
        return Mark("incorrect", method, explanation, reference)
    return None
