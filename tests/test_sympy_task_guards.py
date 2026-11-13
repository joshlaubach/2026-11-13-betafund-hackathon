"""Guards in core/sympy_task.py: one-sided limits, kinks in derivatives, child exits, and the cross-check budget.

SymPy runs in a spawned child process, as in production. Offline only: no model call, no network.
"""

import os
import sys
import time
from pathlib import Path

import sympy as sp

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core import sympy_task  # noqa: E402
from core.derivative_checker import X  # noqa: E402
from core.ladder import Rungs  # noqa: E402
from core.solvers import CallBudget, FakeSolver  # noqa: E402
from core.sympy_task import NO_CROSS_CHECK, compute_answer, compute_task, parse_task  # noqa: E402
from core.worksheet import grade_item  # noqa: E402
from core.worksheet_types import WorksheetItem  # noqa: E402

ONE_SIDED_DISAGREE = "\\lim_{x\\to 0} \\frac{|x|}{x}"
SQRT_AT_ZERO = "\\lim_{x\\to 0} \\sqrt{x}"
REMOVABLE = "\\lim_{x\\to 3} \\frac{x^2-9}{x-3}"
ABS_DERIVATIVE_AT_ZERO = "Compute $f'(0)$ when $f(x) = |x|$."
ABS_DERIVATIVE = "Find $f'(x)$ for $f(x) = |x|$."
DERIVATIVE = "Find $f'(x)$ for $f(x) = 5x^{7} - 3x^{2} + 11$."
DERIVATIVE_ANSWER = "35x^{6} - 6x"
EXIT_TIME_LIMIT_S = 10.0  # far below STARTUP_TIMEOUT_S, so a dead child is not waited out


def _item(statement: str, student: str) -> WorksheetItem:
    return WorksheetItem(number=1, statement_latex=statement, student_answer_latex=student)


def _parsed(statement: str):
    task = parse_task(statement)
    assert task is not None, statement
    return task


# ---------------------------------------------------------------------------
# Two-sided limits
# ---------------------------------------------------------------------------


def test_limit_whose_sides_disagree_is_not_computed() -> None:
    task = _parsed(ONE_SIDED_DISAGREE)
    assert compute_task(task) is None
    assert compute_answer(task) is None


def test_limit_of_sqrt_at_zero_is_not_computed() -> None:
    assert compute_answer(_parsed(SQRT_AT_ZERO)) is None


def test_limit_that_exists_on_both_sides_is_still_six() -> None:
    assert compute_answer(_parsed(REMOVABLE)) == sp.Integer(6)


def test_unfit_limit_falls_through_to_the_ai_ladder_and_is_not_sympy_computed() -> None:
    rungs = Rungs(FakeSolver(), FakeSolver(), FakeSolver())
    grade = grade_item(_item(ONE_SIDED_DISAGREE, "0"), rungs)
    assert grade.method != "sympy_computed"


# ---------------------------------------------------------------------------
# Derivatives at kinks
# ---------------------------------------------------------------------------


def test_derivative_of_abs_at_zero_is_not_graded_as_zero() -> None:
    assert compute_answer(_parsed(ABS_DERIVATIVE_AT_ZERO)) is None


def test_derivative_of_abs_everywhere_is_not_computed() -> None:
    assert compute_answer(_parsed(ABS_DERIVATIVE)) is None


def test_abs_derivative_at_zero_falls_through_to_the_ai_ladder() -> None:
    rungs = Rungs(FakeSolver(), FakeSolver(), FakeSolver())
    grade = grade_item(_item(ABS_DERIVATIVE_AT_ZERO, "0"), rungs)
    assert grade.method != "sympy_computed"


def test_ordinary_derivative_is_still_computed() -> None:
    answer = compute_answer(_parsed(DERIVATIVE))
    assert answer is not None
    assert sp.simplify(answer - (35 * X**6 - 6 * X)) == 0


# ---------------------------------------------------------------------------
# Child process that exits at once
# ---------------------------------------------------------------------------


class _ExitingContext:
    """Stands in for the spawn context. Its child exits at once and sends nothing."""

    def __init__(self, real: object) -> None:
        self._real = real

    def Queue(self) -> object:  # noqa: N802 - mirrors the multiprocessing API
        return self._real.Queue()

    def Process(self, target: object, args: tuple, daemon: bool) -> object:  # noqa: N802
        return self._real.Process(target=os._exit, args=(0,), daemon=daemon)


def test_child_that_exits_at_once_gives_none_without_waiting_out_the_timeout(monkeypatch) -> None:
    monkeypatch.setattr(sympy_task, "_CONTEXT", _ExitingContext(sympy_task._CONTEXT))
    started = time.monotonic()
    assert compute_answer(_parsed(REMOVABLE)) is None
    assert time.monotonic() - started < EXIT_TIME_LIMIT_S


# ---------------------------------------------------------------------------
# Cross-check refused by the budget
# ---------------------------------------------------------------------------


def test_cross_check_refused_for_budget_keeps_the_sympy_mark_with_a_note() -> None:
    fast = FakeSolver({DERIVATIVE: DERIVATIVE_ANSWER})
    rungs = Rungs(fast, FakeSolver(), FakeSolver())
    grade = grade_item(_item(DERIVATIVE, DERIVATIVE_ANSWER), rungs, budget=CallBudget(0))
    assert grade.method == "sympy_computed"
    assert grade.verdict == "correct"
    assert NO_CROSS_CHECK in grade.explanation
    assert fast.solve_calls == ()
