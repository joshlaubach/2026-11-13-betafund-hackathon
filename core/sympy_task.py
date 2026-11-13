"""Compute the answer to a derivative or limit statement with SymPy, then mark the student.

parse_task reads the statement by shape only; no AI translates it. SymPy runs in a spawned child
process that is terminated after SYMPY_TIMEOUT_S seconds, so a hung computation cannot stall
grading. Every failure returns None, and None sends the item to the AI ladder. The one blind
cross-check solve never sees the student's answer, and it never changes a verdict: it can only
confirm the SymPy mark or make it unsure.
"""

from __future__ import annotations

import multiprocessing
import queue
import re
from typing import Any, NamedTuple, Optional

import sympy as sp

from core.derivative_checker import X, parse_derivative_statement
from core.latex_reader import read_latex
from core.solvers import (
    EQUAL,
    AnswerSolver,
    CallLedger,
    Mark,
    ask_solve,
    comparison_mark,
    compare_to_expression,
    is_readable,
)
from core.worksheet_types import GradeMethod

SYMPY_TIMEOUT_S = 5.0  # hard limit on the SymPy computation itself, after the child is ready
STARTUP_TIMEOUT_S = 60.0  # bound on a child that never starts; interpreter start-up is not timed
READY = "ready"
SYMPY_METHOD: GradeMethod = "sympy_computed"
UNSURE = "unsure"
DERIVATIVE = "derivative"
LIMIT = "limit"
SOURCE_PHRASE = "SymPy's computed answer"
CROSS_CHECK_AGREES = "An independent AI solve agreed with SymPy's answer."
NO_CROSS_CHECK = "No independent AI cross-check was available, so SymPy's mark stands alone."
CROSS_CHECK_DISAGREES = (
    "SymPy computed {computed}, but an independent AI solve gave {ai}. The problem may have been "
    "read wrongly, so this mark is unsure."
)
NON_FINITE = (sp.nan, sp.zoo, sp.oo, -sp.oo, sp.I, sp.Limit)
_NUMBER = r"-?\d+(?:\.\d+)?"
_LIMIT_SHAPE = re.compile(
    r"(?:Evaluate )?\\lim_\{x\s*\\to\s*(" + _NUMBER + r")\}\s*(.+?)\.?(?: Give an exact answer\.)?"
)
_CONTEXT = multiprocessing.get_context("spawn")


class Task(NamedTuple):
    """A derivative f'(x) or f'(a), or a limit at a number. point_latex is None for f'(x)."""

    kind: str
    function_latex: str
    point_latex: Optional[str]


class Computed(NamedTuple):
    answer: sp.Basic
    mark: Mark


_TEXT_WRAPPER = re.compile(r"\\(?:text|mathrm|textbf)\{([^{}]*)\}")


def _cleaned_limit_text(statement: str) -> str:
    """Drop $ signs, \\displaystyle and \\text{...} wrappers, and collapse whitespace.

    The reading model sometimes wraps the words of a statement in \\text{...} and sometimes
    delimits the math with $; both must reach the same plain shape.
    """
    unwrapped = _TEXT_WRAPPER.sub(r" \1 ", statement.replace("$", " ").replace("\\displaystyle", " "))
    return " ".join(unwrapped.split())


_ASK = r"(?:Find|Compute|Determine|Calculate|Evaluate)"
_GIVEN = r"(?:for|if|when|where|given)"
_FUNCTION = r"(?:f\(x\)|y)\s*=\s*"
# Worksheet wordings of a derivative, after $ and \displaystyle are removed. The function text
# still goes through core.latex_reader, which refuses anything ambiguous, so a loose shape here
# can only send an item to the AI ladder, never produce a wrong SymPy answer.
_DERIVATIVE_SHAPES = (
    (re.compile(_ASK + r" f'\((" + _NUMBER + r")\) " + _GIVEN + r" " + _FUNCTION + r"(.+?)\.?"), True),
    (re.compile(_ASK + r" f'\(x\) " + _GIVEN + r" " + _FUNCTION + r"(.+?)\.?"), False),
    (re.compile(_ASK + r" (?:\\frac\{dy\}\{dx\}|dy/dx) " + _GIVEN + r" y\s*=\s*(.+?)\.?"), False),
    (re.compile(_ASK + r" the derivative of (?:" + _FUNCTION + r")?(.+?)\.?"), False),
    (re.compile(r"Differentiate (?:" + _FUNCTION + r")?(.+?)\.?"), False),
)


def _worksheet_derivative(statement: str) -> Optional[Task]:
    text = _cleaned_limit_text(statement)
    for shape, has_point in _DERIVATIVE_SHAPES:
        match = shape.fullmatch(text)
        if match is None:
            continue
        function = match.group(2 if has_point else 1).strip()
        if not is_readable(function):  # prose or an ambiguous form: let the AI ladder handle it
            return None
        return Task(DERIVATIVE, function, match.group(1) if has_point else None)
    return None


def parse_task(statement: object) -> Optional[Task]:
    """The task for a derivative or limit statement, read by shape only. None for anything else."""
    if not isinstance(statement, str):
        return None
    derivative = parse_derivative_statement(statement)
    if derivative is not None:
        return Task(DERIVATIVE, derivative["function_latex"], derivative["at"])
    worksheet_derivative = _worksheet_derivative(statement)
    if worksheet_derivative is not None:
        return worksheet_derivative
    limit = _LIMIT_SHAPE.fullmatch(_cleaned_limit_text(statement))
    if limit is None:
        return None
    return Task(LIMIT, limit.group(2).strip(), limit.group(1))


def _finite_or_none(result: object) -> Optional[sp.Basic]:
    if not isinstance(result, sp.Basic) or result.has(*NON_FINITE):
        return None
    return result


def compute_task(task: Task) -> Optional[sp.Basic]:
    """SymPy's answer for a task, or None when it is not a finite value or expression."""
    function = read_latex(task.function_latex)
    if task.kind == LIMIT:
        result = sp.limit(function, X, read_latex(task.point_latex or ""))
    else:
        result = sp.diff(function, X)
        if task.point_latex is not None:
            result = result.subs(X, read_latex(task.point_latex))
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


def compute_answer(task: Task) -> Optional[sp.Basic]:
    """SymPy's answer, computed in a child process. None on timeout, error, or a non-finite result."""
    outbox = _CONTEXT.Queue()
    child = _CONTEXT.Process(target=_child_compute, args=(task, outbox), daemon=True)
    child.start()
    try:
        if outbox.get(timeout=STARTUP_TIMEOUT_S) != READY:
            return None
        answer = outbox.get(timeout=SYMPY_TIMEOUT_S)
    except queue.Empty:  # the child never started, or the computation ran past its limit
        return None
    finally:
        _stop(child)
    return answer if isinstance(answer, sp.Basic) else None


def _computed(task: Task, student: str) -> Optional[Computed]:
    """SymPy's answer and the student's SymPy-only mark. None when SymPy cannot grade it."""
    if not is_readable(student):
        return None
    answer = compute_answer(task)
    if answer is None:
        return None
    reference = sp.latex(answer)
    comparison = compare_to_expression(answer, student)
    mark = comparison_mark(comparison, student, reference, SYMPY_METHOD, SOURCE_PHRASE)
    return None if mark is None else Computed(answer, mark)


def deterministic_mark(statement: str, student: str) -> Optional[Mark]:
    """The SymPy-only mark for a derivative or limit statement. No AI call. None when SymPy cannot grade it."""
    task = parse_task(statement)
    if task is None:
        return None
    computed = _computed(task, student)
    return None if computed is None else computed.mark


def _cross_check(
    statement: str, computed: Computed, fast: AnswerSolver, ledger: CallLedger
) -> Optional[Mark]:
    attempt = ask_solve(fast, statement, ledger, None)
    if attempt.refusal is not None:
        return None  # the AI ladder reports the same refusal for this item
    mark = computed.mark
    if attempt.answer is None:
        return mark._replace(explanation=f"{mark.explanation} {NO_CROSS_CHECK}")
    if compare_to_expression(computed.answer, attempt.answer).status == EQUAL:
        return mark._replace(explanation=f"{mark.explanation} {CROSS_CHECK_AGREES}")
    explanation = CROSS_CHECK_DISAGREES.format(computed=mark.reference, ai=attempt.answer)
    return Mark(UNSURE, SYMPY_METHOD, explanation, mark.reference)


def sympy_mark(
    statement: str, student: str, fast: AnswerSolver, ledger: CallLedger
) -> Optional[Mark]:
    """The SymPy mark with one blind Haiku cross-check, or None when SymPy cannot grade this item."""
    task = parse_task(statement)
    if task is None:
        return None
    computed = _computed(task, student)
    if computed is None:
        return None
    if computed.mark.verdict == UNSURE:
        return computed.mark
    return _cross_check(statement, computed, fast, ledger)
