"""Compute the answer to a derivative, limit, value, or integral statement with SymPy, then mark the student.

parse_task and parse_tasks read the statement by shape only; no AI translates it. A named function
such as v(t) = 1 - e^{-t} comes from the part's shared setup (core/definitions.py). A part that asks
several things becomes several tasks, and each one is compared with its own final answer. SymPy runs in
a spawned child process that is terminated after SYMPY_TIMEOUT_S seconds, so a hung computation cannot
stall grading. Every failure returns None, and None sends the item to the AI ladder. The one blind
cross-check solve never sees the student's answer, and it never changes a verdict: it can only
confirm the SymPy mark or make it unsure.
"""

from __future__ import annotations

import math
import multiprocessing
import queue
import re
import time
from typing import Any, NamedTuple, Optional

import sympy as sp

from core.definitions import (
    ASK_VERBS,
    Definition,
    ask_label,
    parse_definitions,
    plain_text,
    split_asks,
)
from core.derivative_checker import X, parse_derivative_statement
from core.input_boundary import BoundaryError
from core.latex_reader import read_latex
from core.solvers import (
    DIFFERENT,
    DOMAIN_DIFFERS,
    EQUAL,
    AnswerSolver,
    CallLedger,
    Comparison,
    Mark,
    ask_solve,
    compare_expressions,
    comparison_mark,
)
from core.worksheet_types import GradeMethod, Verdict, join_statement

SYMPY_TIMEOUT_S = 5.0  # hard limit on the SymPy computation itself, after the child is ready
STARTUP_TIMEOUT_S = 60.0  # bound on a child that never starts; interpreter start-up is not timed
POLL_INTERVAL_S = 0.05  # how often the parent checks that the child is still alive
LIMIT_PROBE = sp.Rational(1, 10**6)  # distance either side of a limit point where f must be real
NOT_DIFFERENTIABLE = (sp.sign, sp.Abs, sp.Piecewise, sp.Heaviside, sp.DiracDelta)
NON_FINITE = (sp.nan, sp.zoo, sp.oo, -sp.oo, sp.I, sp.Limit, sp.Integral)
READY = "ready"
SYMPY_METHOD: GradeMethod = "sympy_computed"
UNSURE: Verdict = "unsure"
DERIVATIVE = "derivative"
LIMIT = "limit"
VALUE = "value"
INTEGRAL = "integral"
DEFAULT_VARIABLE = "x"
ROUNDING_REL_TOLERANCE = 1e-3  # a decimal this close to an exact answer is a rounded decimal
SOURCE_PHRASE = "SymPy's computed answer"
CROSS_CHECK_AGREES = "An independent AI solve agreed with SymPy's answer."
NO_CROSS_CHECK = "No independent AI cross-check was available, so SymPy's mark stands alone."
CROSS_CHECK_DISAGREES = (
    "SymPy computed {computed}, but an independent AI solve gave {ai}. The problem may have been "
    "read wrongly, so this mark is unsure."
)
ROUNDED_EXPLANATION = "Looks like a rounded decimal of the exact answer; the exact form was expected."
_NUMBER = r"-?\d+(?:\.\d+)?"
_DECIMAL = re.compile(r"-?\d+\.\d+")
_LIMIT_SHAPE = re.compile(
    r"(?:Evaluate )?\\lim_\{x\s*\\to\s*(" + _NUMBER + r")\}\s*(.+?)\.?(?: Give an exact answer\.)?"
)
_LABEL = re.compile(r"^\s*[A-Za-z]'*\s*\(\s*[A-Za-z0-9]+\s*\)\s*=\s*")
_CONTEXT = multiprocessing.get_context("spawn")
_NAMED_DERIVATIVE_AT = re.compile(ASK_VERBS + r" ([A-Za-z])'\((" + _NUMBER + r")\)")
_NAMED_DERIVATIVE = re.compile(ASK_VERBS + r" ([A-Za-z])'\(([A-Za-z])\)")
_NAMED_VALUE = re.compile(ASK_VERBS + r" ([A-Za-z])\((" + _NUMBER + r")\)")
_NAMED_INTEGRAL = re.compile(
    ASK_VERBS + r" \\int_\{?(" + _NUMBER + r")\}?\^\{?(" + _NUMBER + r")\}?\s*(.+?)\s*(?:\\[,;!]\s*)?d([A-Za-z])"
)
_INTEGRAND_CALL = re.compile(r"([A-Za-z])\(([A-Za-z])\)")


class Task(NamedTuple):
    """One thing SymPy computes.

    kind is DERIVATIVE, LIMIT, VALUE, or INTEGRAL. point_latex is the derivative point, the limit
    point, the value point, or the lower limit of an integral; upper_latex is the upper limit. variable
    is the letter the function is written in (x unless a named function says otherwise).
    """

    kind: str
    function_latex: str
    point_latex: Optional[str]
    variable: str = DEFAULT_VARIABLE
    upper_latex: Optional[str] = None


class Computed(NamedTuple):
    """The tasks, SymPy's value for each, and the mark for the whole part."""

    tasks: tuple[Task, ...]
    values: tuple[sp.Basic, ...]
    mark: Mark


# ---------------------------------------------------------------------------
# Parsing the statement by shape
# ---------------------------------------------------------------------------


def _worksheet_derivative_shapes() -> tuple[tuple[re.Pattern[str], bool], ...]:
    given = r"(?:for|if|when|where|given)"
    function = r"(?:f\(x\)|y)\s*=\s*"
    # Worksheet wordings of a derivative, after $ and \displaystyle are removed. The function text
    # still goes through core.latex_reader, which refuses anything ambiguous, so a loose shape here
    # can only send an item to the AI ladder, never produce a wrong SymPy answer.
    return (
        (re.compile(ASK_VERBS + r" f'\((" + _NUMBER + r")\) " + given + r" " + function + r"(.+?)\.?"), True),
        (re.compile(ASK_VERBS + r" f'\(x\) " + given + r" " + function + r"(.+?)\.?"), False),
        (re.compile(ASK_VERBS + r" (?:\\frac\{dy\}\{dx\}|dy/dx) " + given + r" y\s*=\s*(.+?)\.?"), False),
        (re.compile(ASK_VERBS + r" the derivative of (?:" + function + r")?(.+?)\.?"), False),
        (re.compile(r"Differentiate (?:" + function + r")?(.+?)\.?"), False),
    )


_DERIVATIVE_SHAPES = _worksheet_derivative_shapes()


def _worksheet_derivative(statement: str) -> Optional[Task]:
    text = plain_text(statement)
    for shape, has_point in _DERIVATIVE_SHAPES:
        match = shape.fullmatch(text)
        if match is None:
            continue
        function = match.group(2 if has_point else 1).strip()
        if not _readable(function):  # prose or an ambiguous form: let the AI ladder handle it
            return None
        return Task(DERIVATIVE, function, match.group(1) if has_point else None)
    return None


def _derivative_at_point(match: re.Match[str], definitions: dict[str, Definition]) -> Optional[Task]:
    definition = definitions.get(match.group(1))
    if definition is None:
        return None
    return Task(DERIVATIVE, definition.body_latex, match.group(2), definition.variable)


def _derivative_named(match: re.Match[str], definitions: dict[str, Definition]) -> Optional[Task]:
    definition = definitions.get(match.group(1))
    if definition is None or definition.variable != match.group(2):
        return None
    return Task(DERIVATIVE, definition.body_latex, None, definition.variable)


def _value_at_point(match: re.Match[str], definitions: dict[str, Definition]) -> Optional[Task]:
    definition = definitions.get(match.group(1))
    if definition is None:
        return None
    return Task(VALUE, definition.body_latex, match.group(2), definition.variable)


def _integral_task(match: re.Match[str], definitions: dict[str, Definition]) -> Optional[Task]:
    lower, upper, integrand, variable = match.group(1), match.group(2), match.group(3).strip(), match.group(4)
    call = _INTEGRAND_CALL.fullmatch(integrand)
    if call is None:  # a bare expression, read in the integration variable
        return Task(INTEGRAL, integrand, lower, variable, upper)
    definition = definitions.get(call.group(1))
    if definition is None or definition.variable != variable or call.group(2) != variable:
        return None
    return Task(INTEGRAL, definition.body_latex, lower, variable, upper)


_NAMED_SHAPES = (
    (_NAMED_DERIVATIVE_AT, _derivative_at_point),
    (_NAMED_DERIVATIVE, _derivative_named),
    (_NAMED_VALUE, _value_at_point),
    (_NAMED_INTEGRAL, _integral_task),
)


def _named_task(statement: str, context: str) -> Optional[Task]:
    """A task about a function named in the shared setup, or None when the setup does not define it."""
    text = plain_text(statement).rstrip(". ")
    definitions = parse_definitions(context)
    for shape, build in _NAMED_SHAPES:
        match = shape.fullmatch(text)
        if match is not None:
            return build(match, definitions)
    return None


def parse_task(statement: object, context: str = "") -> Optional[Task]:
    """The task for one ask, read by shape only. context is the part's shared setup. None for anything else."""
    if not isinstance(statement, str):
        return None
    derivative = parse_derivative_statement(statement)
    if derivative is not None:
        return Task(DERIVATIVE, derivative["function_latex"], derivative["at"])
    worksheet_derivative = _worksheet_derivative(statement)
    if worksheet_derivative is not None:
        return worksheet_derivative
    limit = _LIMIT_SHAPE.fullmatch(plain_text(statement))
    if limit is not None:
        return Task(LIMIT, limit.group(2).strip(), limit.group(1))
    return _named_task(statement, context)


def parse_tasks(statement: object, context: str = "") -> Optional[tuple[Task, ...]]:
    """The tasks for a part: one, or several when the part asks for more than one thing.

    None when any ask is refused, so the whole part goes to the AI ladder.
    """
    single = parse_task(statement, context)
    if single is not None:
        return (single,)
    if not isinstance(statement, str):
        return None
    found = [parse_task(ask, context) for ask in split_asks(statement)]
    if not found or any(task is None for task in found):
        return None
    return tuple(task for task in found if task is not None)


def _readable(latex: str) -> bool:
    try:
        read_latex(latex)
    except BoundaryError:
        return False
    return True


# ---------------------------------------------------------------------------
# Reading expressions and comparing them
# ---------------------------------------------------------------------------


def strip_label(answer: str) -> str:
    """The answer without a leading label such as "v'(t) =" or "v(0) =". Only one label is removed."""
    return _LABEL.sub("", answer, count=1).strip()


def _in_x(expr: sp.Basic, variable: str) -> sp.Basic:
    """The expression with its variable replaced by the shared X symbol, so the existing checks apply."""
    return expr.subs(sp.Symbol(variable, real=True), X)


def _read_in_x(latex: str, variable: str) -> Optional[sp.Basic]:
    """latex read in its variable and returned in X, or None when the reader cannot read it."""
    try:
        return _in_x(read_latex(latex, (variable,)), variable)
    except BoundaryError:
        return None


def _displayed(value: sp.Basic, variable: str) -> str:
    """The answer as LaTeX in the statement's own variable, with the terms in their natural order (4 + e^{-5})."""
    return sp.latex(value.subs(X, sp.Symbol(variable, real=True)), order="none")


def _finite_or_none(result: object) -> Optional[sp.Basic]:
    if not isinstance(result, sp.Basic) or result.has(*NON_FINITE):
        return None
    return result


def _real_at(expr: sp.Basic, value: sp.Basic) -> bool:
    """True when expr is a finite real number at value."""
    try:
        number = complex(sp.N(expr.subs(X, value)))
    except (TypeError, ValueError, ArithmeticError):
        return False
    return number.imag == 0 and math.isfinite(number.real)


def _real_on_both_sides(function: sp.Basic, point: sp.Basic) -> bool:
    return all(_real_at(function, point + side * LIMIT_PROBE) for side in (-1, 1))


def _limit(function: sp.Basic, point: sp.Basic) -> Optional[sp.Basic]:
    """The two-sided limit, or None when the function is not real on both sides or the sides disagree."""
    if not _real_on_both_sides(function, point):
        return None  # e.g. sqrt(x) at 0: SymPy's left limit is not a real value
    try:
        return sp.limit(function, X, point, dir="+-")
    except ValueError:  # SymPy raises when the left and right limits do not agree
        return None


def _derivative(function: sp.Basic, point_latex: Optional[str]) -> Optional[sp.Basic]:
    """f'(x) or f'(a), or None when f has a kink or jump, where a derivative value is not defined."""
    derivative = sp.diff(function, X)
    if derivative.has(*NOT_DIFFERENTIABLE):
        return None  # e.g. f = |x| gives sign(x), whose value at 0 is not f'(0)
    if point_latex is None:
        return derivative
    return derivative.subs(X, read_latex(point_latex))


def _integral(function: sp.Basic, lower: sp.Basic, upper: sp.Basic) -> sp.Basic:
    """The definite integral over [lower, upper]. An unevaluated integral is refused by _finite_or_none."""
    return sp.integrate(function, (X, lower, upper))


def _task_value(task: Task) -> Optional[sp.Basic]:
    function = _read_in_x(task.function_latex, task.variable)
    if function is None:
        return None
    if task.kind == LIMIT:
        return _limit(function, read_latex(task.point_latex or ""))
    if task.kind == DERIVATIVE:
        return _derivative(function, task.point_latex)
    if task.kind == VALUE:
        return function.subs(X, read_latex(task.point_latex or ""))
    return _integral(function, read_latex(task.point_latex or ""), read_latex(task.upper_latex or ""))


def compute_task(task: Task) -> Optional[sp.Basic]:
    """SymPy's answer for a task, or None when it is not a finite value or expression."""
    try:
        result = _task_value(task)
    except BoundaryError:
        return None
    return _finite_or_none(result)


def _child_compute(task: Task, outbox: Any) -> None:
    """Runs in the child process: announce readiness, then send the answer or None on any failure."""
    outbox.put(READY)
    try:
        answer = compute_task(task)
    except Exception:  # any SymPy or reader failure is a missing answer, never a crash
        answer = None
    outbox.put(answer)


def _stop(child: Any) -> None:
    if child.is_alive():
        child.terminate()
    child.join()


def _await_message(child: Any, outbox: Any, timeout_s: float) -> Any:
    """The child's next message. Raises queue.Empty on timeout, or once the child has exited with nothing queued."""
    deadline = time.monotonic() + timeout_s
    while True:
        wait = min(POLL_INTERVAL_S, deadline - time.monotonic())
        try:
            return outbox.get(timeout=max(wait, 0.0))
        except queue.Empty:
            if deadline - time.monotonic() <= 0:
                raise
            if not child.is_alive():
                return outbox.get(timeout=POLL_INTERVAL_S)  # a message sent just before exit still counts


def compute_answer(task: Task) -> Optional[sp.Basic]:
    """SymPy's answer, computed in a child process. None on timeout, child exit, error, or a non-finite result."""
    outbox = _CONTEXT.Queue()
    child = _CONTEXT.Process(target=_child_compute, args=(task, outbox), daemon=True)
    child.start()
    try:
        if _await_message(child, outbox, STARTUP_TIMEOUT_S) != READY:
            return None
        answer = _await_message(child, outbox, SYMPY_TIMEOUT_S)
    except queue.Empty:  # the child never started, exited silently, or ran past its limit
        return None
    finally:
        _stop(child)
        outbox.close()
        outbox.join_thread()
    return answer if isinstance(answer, sp.Basic) else None


# ---------------------------------------------------------------------------
# Marks
# ---------------------------------------------------------------------------


def _sub_answers(count: int, answers: tuple[str, ...]) -> Optional[tuple[str, ...]]:
    """The student's answers without labels, one per task. None when the counts differ."""
    stripped = tuple(strip_label(answer) for answer in answers)
    if len(stripped) != count or not all(stripped):
        return None
    return stripped


def _is_rounded_decimal(value: sp.Basic, student: str, comparison: Comparison) -> bool:
    """True when two constants differ but the student's decimal is within the rounding tolerance."""
    if comparison.status != DIFFERENT or value.free_symbols or not _DECIMAL.fullmatch(student):
        return False
    try:
        exact = float(sp.N(value))
    except (TypeError, ValueError):
        return False
    return exact != 0 and abs(float(student) - exact) <= ROUNDING_REL_TOLERANCE * abs(exact)


def _sub_verdict(comparison: Comparison) -> Optional[Verdict]:
    """The verdict for one sub-answer, or None when SymPy could not compare it at all."""
    if comparison.constant_offset or comparison.status == DOMAIN_DIFFERS:
        return UNSURE
    if comparison.status == EQUAL:
        return "correct"
    if comparison.status == DIFFERENT:
        return "incorrect"
    return None


def _sub_mark(
    task: Task, value: sp.Basic, student: str, label: str, single: bool
) -> Optional[Mark]:
    """The mark for one sub-answer, or None when SymPy cannot compare it with the student's answer."""
    reference = _displayed(value, task.variable)
    student_value = _read_in_x(student, task.variable)
    if student_value is None:
        return None
    comparison = compare_expressions(value, student_value)
    if _is_rounded_decimal(value, student, comparison):
        return Mark(UNSURE, SYMPY_METHOD, ROUNDED_EXPLANATION, reference)
    if single:
        return comparison_mark(comparison, student, reference, SYMPY_METHOD, SOURCE_PHRASE)
    verdict = _sub_verdict(comparison)
    if verdict is None:
        return None
    explanation = f"{label}: SymPy computes {reference}; the student wrote {student}."
    return Mark(verdict, SYMPY_METHOD, explanation, reference)


def _combined_mark(marks: list[Mark]) -> Mark:
    """One part's mark: incorrect if any sub-answer is, correct only if all are, unsure otherwise."""
    if len(marks) == 1:
        return marks[0]
    verdicts = {mark.verdict for mark in marks}
    if "incorrect" in verdicts:
        verdict: Verdict = "incorrect"
    elif verdicts == {"correct"}:
        verdict = "correct"
    else:
        verdict = UNSURE
    explanation = " ".join(mark.explanation for mark in marks)
    reference = "; ".join(mark.reference or "" for mark in marks)
    return Mark(verdict, SYMPY_METHOD, explanation, reference)


def _computed(
    tasks: tuple[Task, ...], answers: tuple[str, ...], labels: tuple[str, ...]
) -> Optional[Computed]:
    """SymPy's values and the part's mark. None when any answer cannot be computed or matched."""
    students = _sub_answers(len(tasks), answers)
    if students is None:
        return None
    values: list[sp.Basic] = []
    for task in tasks:
        value = compute_answer(task)
        if value is None:
            return None
        values.append(value)
    single = len(tasks) == 1
    marks: list[Mark] = []
    for task, value, student, label in zip(tasks, values, students, labels):
        mark = _sub_mark(task, value, student, label, single)
        if mark is None:
            return None
        marks.append(mark)
    return Computed(tasks, tuple(values), _combined_mark(marks))


def _labels(statement: str, count: int) -> tuple[str, ...]:
    if count == 1:
        return ("",)
    return tuple(ask_label(ask) for ask in split_asks(statement))


def deterministic_mark(statement: str, student: str, context: str = "") -> Optional[Mark]:
    """The SymPy-only mark for a statement. No AI call. None when SymPy cannot grade it."""
    tasks = parse_tasks(statement, context)
    if tasks is None:
        return None
    computed = _computed(tasks, (student,), _labels(statement, len(tasks)))
    return None if computed is None else computed.mark


def _reply_parts(reply: str, count: int) -> Optional[tuple[str, ...]]:
    """The cross-check reply split into one answer per task, or None when the counts differ."""
    if count == 1:
        return (strip_label(reply),)
    parts = tuple(strip_label(piece) for piece in reply.split(";"))
    return parts if len(parts) == count and all(parts) else None


def _agrees(task: Task, value: sp.Basic, reply: str) -> bool:
    expr = _read_in_x(reply, task.variable)
    return expr is not None and compare_expressions(value, expr).status == EQUAL


def _cross_check(full: str, computed: Computed, fast: AnswerSolver, ledger: CallLedger) -> Mark:
    mark = computed.mark
    attempt = ask_solve(fast, full, ledger, None)
    if attempt.refusal is not None or attempt.answer is None:  # no cross-check ran: keep the SymPy mark
        return mark._replace(explanation=f"{mark.explanation} {NO_CROSS_CHECK}")
    replies = _reply_parts(attempt.answer, len(computed.tasks))
    if replies is None:
        return mark._replace(explanation=f"{mark.explanation} {NO_CROSS_CHECK}")
    pairs = zip(computed.tasks, computed.values, replies)
    if all(_agrees(task, value, reply) for task, value, reply in pairs):
        return mark._replace(explanation=f"{mark.explanation} {CROSS_CHECK_AGREES}")
    explanation = CROSS_CHECK_DISAGREES.format(computed=mark.reference, ai=attempt.answer)
    return Mark(UNSURE, SYMPY_METHOD, explanation, mark.reference)


def sympy_mark(
    statement: str,
    answers: tuple[str, ...],
    fast: AnswerSolver,
    ledger: CallLedger,
    context: str = "",
) -> Optional[Mark]:
    """The SymPy mark with one blind Haiku cross-check, or None when SymPy cannot grade this part.

    statement is the part's own question, context its shared setup, and answers the student's final
    answers (or the whole written answer when none was read).
    """
    tasks = parse_tasks(statement, context)
    if tasks is None:
        return None
    computed = _computed(tasks, answers, _labels(statement, len(tasks)))
    if computed is None:
        return None
    if computed.mark.verdict == UNSURE:
        return computed.mark
    return _cross_check(join_statement(context, statement), computed, fast, ledger)
