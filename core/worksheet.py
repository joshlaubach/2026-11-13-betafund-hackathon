"""Read a worksheet photo into problems and the student's answers, then grade each answer.

Reading follows core/photo_reader.py: LiveWorksheetSource (Claude vision),
ReplayWorksheetSource (a saved reading matched by image SHA-256; the image is never
saved), and FakeWorksheetSource (scripted). read_worksheet() checks the image bytes
before any source runs and never raises for a source failure.

Grading tries three tiers in order. bank_key: the statement matches an eligible bank
problem, and the student's answer is compared with the verified key by SymPy.
ai_solve_sympy: an independent solver answers the statement without ever seeing the
student's answer, and SymPy compares the two answers. ai_judgment: a model judges the
written answer when neither answer can be read by SymPy. Every answer is read by
core.latex_reader only.
"""

from __future__ import annotations

import base64
import json
import math
import os
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple, Optional, TypeVar

import anthropic
import sympy as sp
from pydantic import BaseModel

from core.bank_fallback import BANK_PATH
from core.derivative_checker import (
    ABS_FLOOR,
    MIN_COMPARABLE_POINTS,
    REL_TOLERANCE,
    SAMPLE_POINTS,
    X,
)
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
from core.photo_reader import (
    SHA256_HEX_PATTERN,
    bank_topic_ids,
    check_image,
    sha256_hex,
)
from core.worksheet_types import (
    GRADE_LABELS,
    Grade,
    GradedItem,
    GradeMethod,
    Verdict,
    WorksheetItem,
    WorksheetReading,
)
from scripts.audit_bank import classify, load_bank

MAX_ITEMS = 20
REGRADE_EFFORT = "high"
ENV_API_KEY = "ANTHROPIC_API_KEY"
STATUS_OK = "ok"
STATUS_ERROR = "error"
STATUS_UNREADABLE = "unreadable"
READING_SOURCES = (SOURCE_LIVE, SOURCE_FAKE)
BANK_METHOD: GradeMethod = "bank_key"
SOLVE_METHOD: GradeMethod = "ai_solve_sympy"
JUDGE_METHOD: GradeMethod = "ai_judgment"
EQUAL = "equal"
DIFFERENT = "different"
UNKNOWN = "unknown"
NO_ANSWER_EXPLANATION = "no answer written"
CONSTANT_EXPLANATION = "answers differ by a constant; check for + C"
UNCOMPARED_EXPLANATION = (
    "SymPy could not compare the student's answer with the verified key, so this mark is unsure."
)
JUDGE_FAILED_EXPLANATION = "the AI judge could not give a verdict, so this mark is unsure."
DIFFERENT_PHOTO_MESSAGE = "saved reading is for a different photo"
UNREADABLE_MESSAGE = "no problems were read from the worksheet"
REFUSAL_MESSAGE = "the model declined to read the worksheet"
EMPTY_MESSAGE = "the model returned no reading"
RATE_LIMIT_MESSAGE = "rate limited by the model service; try again later"
CONNECTION_MESSAGE = "could not reach the model service"
ITEM_CAP_NOTE = "the worksheet has {total} problems; only the first {kept} were kept"
BLANK_DROPPED_NOTE = "{count} blank problem(s) dropped"
TOPIC_CLEARED_NOTE = "topic guess {guess!r} is not a bank topic, so it was cleared"

WORKSHEET_SYSTEM_PROMPT = (
    "You transcribe a student's handwritten or printed calculus worksheet for Echo. "
    "For every numbered problem, write statement_latex with exactly what is written, and "
    "student_answer_latex with exactly the student's written answer, or null when no answer "
    "is written. Do not solve, simplify, complete, or correct anything, even when it is wrong. "
    "If any part is illegible, cut off, or ambiguous, say which part in notes and lower "
    "confidence. Choose topic_guess only from the topic ids given in the request, or null if "
    "none fits. Return only the structured output requested."
)
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


# ---------------------------------------------------------------------------
# Reading sources
# ---------------------------------------------------------------------------


class WorksheetSource:
    """Base for worksheet sources. source is "live" or "fake"; name is for display."""

    name: str = "source"
    source: str = ""
    last_usage: Optional[dict] = None

    def get_reading(
        self, image: bytes, media_type: str, topics: tuple[str, ...]
    ) -> WorksheetReading:
        raise NotImplementedError


FAKE_READING = WorksheetReading(
    items=(
        WorksheetItem(
            number=1,
            statement_latex="Find $f'(x)$ for $f(x) = 3x^{4} + 2x$.",
            student_answer_latex="12x^{3}+2",
            topic_guess="power_rule",
            confidence="high",
        ),
        WorksheetItem(
            number=2,
            statement_latex=(
                "Evaluate $\\displaystyle \\lim_{x \\to 1} \\frac{- \\frac{1}{2} + \\frac{1}{x + 1}}"
                "{x^{2} - 1}$. Give an exact answer."
            ),
            student_answer_latex="-\\frac{1}{8}",
            topic_guess="algebraic",
            confidence="high",
        ),
    ),
    notes="scripted reading; no model read this photo",
)


class FakeWorksheetSource(WorksheetSource):
    name = "fake"
    source = SOURCE_FAKE

    def __init__(self, reading: WorksheetReading = FAKE_READING) -> None:
        self._reading = reading

    def get_reading(
        self, image: bytes, media_type: str, topics: tuple[str, ...]
    ) -> WorksheetReading:
        return self._reading


class ReplayWorksheetSource(WorksheetSource):
    """Plays back a saved reading for the same photo. The original source is exposed as source."""

    def __init__(self, path: Path | str) -> None:
        saved = load_worksheet_reading(path)
        self._saved = saved
        self.source = saved["source"]
        self.saved_at = saved.get("saved_at", "unknown time")
        self.name = f"replay (saved {self.source} reading)"

    def get_reading(
        self, image: bytes, media_type: str, topics: tuple[str, ...]
    ) -> WorksheetReading:
        if sha256_hex(image) != self._saved["image_sha256"]:
            raise SourceError(DIFFERENT_PHOTO_MESSAGE)
        return self._saved["reading"]


class LiveWorksheetSource(WorksheetSource):
    source = SOURCE_LIVE

    def __init__(self, model: str = DEFAULT_MODEL, effort: str = DEFAULT_EFFORT) -> None:
        self.model = model
        self.effort = effort
        self.name = f"live ({model}, effort {effort})"

    def get_reading(
        self, image: bytes, media_type: str, topics: tuple[str, ...]
    ) -> WorksheetReading:
        content = _image_content(image, media_type, build_worksheet_prompt(topics))
        reading, self.last_usage = _call_model(
            self.model, self.effort, WORKSHEET_SYSTEM_PROMPT, content, WorksheetReading
        )
        return reading


def _image_content(image: bytes, media_type: str, prompt: str) -> list[dict]:
    """The image block comes before the text block, as the vision API expects."""
    encoded = base64.standard_b64encode(image).decode("ascii")
    return [
        {
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": encoded},
        },
        {"type": "text", "text": prompt},
    ]


def build_worksheet_prompt(topics: tuple[str, ...]) -> str:
    return "\n".join(
        [
            "Transcribe every numbered problem on the worksheet in the photo, "
            "with the student's written answer to each.",
            "topic_guess must be one of these topic ids, or null: " + ", ".join(topics),
        ]
    )


# ---------------------------------------------------------------------------
# Model calls shared by the live reader and the live solver
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


def _call_model(
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


# ---------------------------------------------------------------------------
# Reading the worksheet
# ---------------------------------------------------------------------------


def _digest(image: object) -> Optional[str]:
    if not isinstance(image, (bytes, bytearray)):
        return None
    return sha256_hex(bytes(image))


def _tokens(source: WorksheetSource) -> Optional[dict]:
    usage = getattr(source, "last_usage", None)
    return dict(usage) if usage else None


def _join_notes(existing: str, extra: str) -> str:
    return " ".join(part for part in (existing.strip(), extra) if part)


def _topic_ids(topics: Optional[Sequence[str]]) -> tuple[str, ...]:
    if topics is None:
        return bank_topic_ids()
    return tuple(sorted(set(topics)))


def _normalized_item(item: WorksheetItem, topics: tuple[str, ...]) -> WorksheetItem:
    """Strip the text, make a blank answer None, and clear a topic guess that is not a bank topic."""
    answer = (item.student_answer_latex or "").strip() or None
    update: dict = {"statement_latex": item.statement_latex.strip(), "student_answer_latex": answer}
    if item.topic_guess is not None and item.topic_guess not in topics:
        update["topic_guess"] = None
        update["notes"] = _join_notes(item.notes, TOPIC_CLEARED_NOTE.format(guess=item.topic_guess))
    return item.model_copy(update=update)


def _normalized(reading: WorksheetReading, topics: tuple[str, ...]) -> WorksheetReading:
    """Drop blank problems, keep the first MAX_ITEMS, and record each change in the notes."""
    usable = [
        _normalized_item(item, topics)
        for item in reading.items
        if item.statement_latex.strip()
    ]
    notes = reading.notes
    dropped = len(reading.items) - len(usable)
    if dropped:
        notes = _join_notes(notes, BLANK_DROPPED_NOTE.format(count=dropped))
    if len(usable) > MAX_ITEMS:
        notes = _join_notes(notes, ITEM_CAP_NOTE.format(total=len(usable), kept=MAX_ITEMS))
        usable = usable[:MAX_ITEMS]
    return reading.model_copy(update={"items": tuple(usable), "notes": notes})


def _result(
    status: str,
    source_name: str,
    digest: Optional[str],
    error: Optional[str] = None,
    reading: Optional[WorksheetReading] = None,
    tokens: Optional[dict] = None,
) -> dict:
    return {
        "status": status,
        "source": source_name,
        "reading": reading.model_dump(mode="json") if reading is not None else None,
        "image_sha256": digest,
        "error": error,
        "tokens": tokens,
    }


def read_worksheet(
    image: bytes, source: WorksheetSource, topics: Optional[Sequence[str]] = None
) -> dict:
    """Read a worksheet photo with source. Never raises for bad input or source failures."""
    digest = _digest(image)
    media_type, image_error = check_image(image)
    if image_error is not None:
        return _result(STATUS_ERROR, source.name, digest, error=image_error)
    try:
        allowed = _topic_ids(topics)
        raw = WorksheetReading.model_validate(
            source.get_reading(bytes(image), media_type, allowed)
        )
    except Exception as error:  # a reading-source failure must not crash the caller
        return _result(STATUS_ERROR, source.name, digest, error=str(error) or type(error).__name__)
    reading = _normalized(raw, allowed)
    if not reading.items:
        return _result(
            STATUS_UNREADABLE, source.name, digest, error=UNREADABLE_MESSAGE,
            reading=reading, tokens=_tokens(source),
        )
    return _result(STATUS_OK, source.name, digest, reading=reading, tokens=_tokens(source))


def _is_sha256_hex(value: object) -> bool:
    return isinstance(value, str) and SHA256_HEX_PATTERN.fullmatch(value) is not None


def save_worksheet_reading(
    path: Path | str, image_sha256: str, reading: WorksheetReading, source: str
) -> None:
    """Write a reading to a JSON file. The image itself is never written."""
    if source not in READING_SOURCES:
        raise ValueError(f"source must be one of {READING_SOURCES}, got {source!r}")
    if not _is_sha256_hex(image_sha256):
        raise ValueError("image_sha256 must be a 64-character lowercase hex digest")
    payload = {
        "source": source,
        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "image_sha256": image_sha256,
        "reading": reading.model_dump(mode="json"),
    }
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def load_worksheet_reading(path: Path | str) -> dict:
    """Read a saved reading. Raises ValueError when the file is not a valid saved reading."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("source") not in READING_SOURCES:
        raise ValueError(f"{path} is not a saved Echo worksheet reading")
    if not _is_sha256_hex(data.get("image_sha256")):
        raise ValueError(f"{path} is missing its image_sha256")
    if not isinstance(data.get("reading"), dict):
        raise ValueError(f"{path} is missing its reading")
    reading = WorksheetReading.model_validate(data["reading"])
    return {**data, "reading": reading}


# ---------------------------------------------------------------------------
# Solvers
# ---------------------------------------------------------------------------


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


class LiveSolver(AnswerSolver):
    source = SOURCE_LIVE

    def __init__(self, model: str = DEFAULT_MODEL, effort: str = DEFAULT_EFFORT) -> None:
        self.model = model
        self.effort = effort
        self.name = f"live ({model}, effort {effort})"

    def solve(self, statement: str, effort: Optional[str] = None) -> str:
        reply, self.last_usage = _call_model(
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
        reply, self.last_usage = _call_model(
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


def compare_answers(reference_latex: str, student_latex: str) -> Comparison:
    """Compare two LaTeX answers at fixed non-grid points in x, with the derivative checker's tolerance.

    Needs MIN_COMPARABLE_POINTS comparable points. A nonzero constant difference is reported as
    constant_offset when an answer depends on x (the "+ C" case); two constants that differ are
    simply different.
    """
    try:
        reference = read_latex(reference_latex)
        student = read_latex(student_latex)
    except BoundaryError:
        return Comparison(UNKNOWN)
    pairs = _comparable_pairs(reference, student)
    if len(pairs) < MIN_COMPARABLE_POINTS:
        return Comparison(UNKNOWN, len(pairs))
    if all(_values_agree(reference_value, student_value) for reference_value, student_value in pairs):
        return Comparison(EQUAL, len(pairs))
    depends = _depends_on_x(reference) or _depends_on_x(student)
    if depends and _is_constant_offset(pairs):
        return Comparison(UNKNOWN, len(pairs), constant_offset=True)
    return Comparison(DIFFERENT, len(pairs))


def answers_equivalent(a_latex: str, b_latex: str) -> str:
    """Return "equal", "different", or "unknown" for two LaTeX answers. See compare_answers."""
    return compare_answers(a_latex, b_latex).status


# ---------------------------------------------------------------------------
# Grading
# ---------------------------------------------------------------------------


def _statement_key(text: str) -> str:
    """Normalized statement for bank matching: no $ signs, no \\displaystyle, no whitespace."""
    return "".join(text.replace("$", "").replace("\\displaystyle", "").split())


def _eligible_bank() -> tuple[dict, ...]:
    """Bank problems that pass the audit. Raises ValueError when the bank cannot be read."""
    return tuple(problem for problem in load_bank(BANK_PATH) if classify(problem) is None)


def _bank_match(item: WorksheetItem, problems: tuple[dict, ...]) -> Optional[dict]:
    key = _statement_key(item.statement_latex)
    matches = [
        problem
        for problem in problems
        if _statement_key(problem["statement"]) == key
        and (item.topic_guess is None or problem["topic"] == item.topic_guess)
    ]
    if not matches:
        return None
    return min(matches, key=lambda problem: (problem["topic"], str(problem["id"])))


def _reference_latex(problem: dict) -> str:
    return str((problem.get("answer") or {}).get("latex", ""))


def _answer_text(item: WorksheetItem) -> Optional[str]:
    text = (item.student_answer_latex or "").strip()
    return text or None


def _grade(
    verdict: Verdict,
    method: GradeMethod,
    explanation: str,
    reference: Optional[str] = None,
    bank_problem: Optional[dict] = None,
) -> Grade:
    return Grade(
        verdict=verdict,
        method=method,
        label=GRADE_LABELS[method],
        reference_answer_latex=reference,
        explanation=explanation,
        bank_topic=bank_problem["topic"] if bank_problem is not None else None,
        bank_id=str(bank_problem["id"]) if bank_problem is not None else None,
    )


def _from_comparison(
    comparison: Comparison,
    student: str,
    reference: str,
    method: GradeMethod,
    source_phrase: str,
    bank_problem: Optional[dict] = None,
) -> Optional[Grade]:
    """A grade from a comparison, or None when SymPy could not compare the answers."""
    if comparison.constant_offset:
        return _grade("unsure", method, CONSTANT_EXPLANATION, reference, bank_problem)
    if comparison.status == EQUAL:
        explanation = (
            f"The student's answer {student} matches {source_phrase} {reference} "
            f"at {comparison.points} sample points, checked by SymPy."
        )
        return _grade("correct", method, explanation, reference, bank_problem)
    if comparison.status == DIFFERENT:
        explanation = (
            f"The student's answer {student} does not match {source_phrase} {reference}: "
            "SymPy found different values at a sample point."
        )
        return _grade("incorrect", method, explanation, reference, bank_problem)
    return None


def _bank_grade(problem: dict, student: str) -> Grade:
    reference = _reference_latex(problem)
    comparison = compare_answers(reference, student)
    grade = _from_comparison(
        comparison, student, reference, BANK_METHOD, "the verified key", problem
    )
    if grade is None:
        return _grade("unsure", BANK_METHOD, UNCOMPARED_EXPLANATION, reference, problem)
    return grade


def _no_answer_grade(problem: Optional[dict]) -> Grade:
    if problem is None:
        return _grade("unsure", JUDGE_METHOD, NO_ANSWER_EXPLANATION)
    return _grade(
        "unsure", BANK_METHOD, NO_ANSWER_EXPLANATION, _reference_latex(problem), problem
    )


def _solved_grade(
    statement: str, student: str, solver: AnswerSolver, effort: Optional[str]
) -> Optional[Grade]:
    try:
        reference = solver.solve(statement, effort)
    except Exception:  # a solver failure falls to the judgment tier, never a crash
        return None
    comparison = compare_answers(reference, student)
    return _from_comparison(
        comparison, student, reference, SOLVE_METHOD, "the independent AI answer"
    )


def _judged_grade(
    statement: str, student: str, solver: AnswerSolver, effort: Optional[str]
) -> Grade:
    try:
        verdict = solver.judge(statement, student, effort).verdict
    except Exception:  # a judge failure is an unsure mark, never a crash
        return _grade("unsure", JUDGE_METHOD, JUDGE_FAILED_EXPLANATION)
    explanation = (
        f"The student's answer {student} could not be checked by SymPy, so the AI judge "
        f"marked it {verdict} from the statement alone."
    )
    return _grade(verdict, JUDGE_METHOD, explanation)


def _ai_grade(
    statement: str, student: str, solver: AnswerSolver, effort: Optional[str]
) -> Grade:
    grade = _solved_grade(statement, student, solver, effort)
    if grade is not None:
        return grade
    return _judged_grade(statement, student, solver, effort)


def grade_item(
    item: WorksheetItem,
    solver: AnswerSolver,
    bank: Optional[Sequence[dict]] = None,
    effort: Optional[str] = None,
) -> Grade:
    """Grade one item: bank_key, then ai_solve_sympy, then ai_judgment. Never raises for a solver failure."""
    problems = _eligible_bank() if bank is None else tuple(bank)
    problem = _bank_match(item, problems)
    student = _answer_text(item)
    if student is None:
        return _no_answer_grade(problem)
    if problem is not None:
        return _bank_grade(problem, student)
    return _ai_grade(item.statement_latex, student, solver, effort)


def grade_worksheet(
    reading: WorksheetReading,
    solver: AnswerSolver,
    bank: Optional[Sequence[dict]] = None,
) -> list[GradedItem]:
    problems = _eligible_bank() if bank is None else tuple(bank)
    return [
        GradedItem(item=item, grade=grade_item(item, solver, bank=problems))
        for item in reading.items
    ]


def regrade_item(
    graded: GradedItem,
    solver: AnswerSolver,
    bank: Optional[Sequence[dict]] = None,
) -> GradedItem:
    """Grade again. Bank grades are recomputed; AI grades get a fresh solve at REGRADE_EFFORT."""
    fresh = grade_item(graded.item, solver, bank=bank, effort=REGRADE_EFFORT)
    is_ai = graded.grade.method != BANK_METHOD
    changed = is_ai and fresh.verdict != graded.grade.verdict
    return GradedItem(
        item=graded.item,
        grade=fresh,
        regraded=True,
        changed_on_regrade=changed,
    )
