"""The brief's worksheet lines, graded end to end: scripted reading, shared setup copied in, SymPy marks.

Offline only: scripted reading sources and FakeSolvers, no network, no API key. SymPy runs in the spawned
child process, as in production. Each row is one part of the worksheet, with the answer the student wrote.
"""

import struct
import sys
import zlib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core import sympy_task  # noqa: E402
from core.solvers import CallBudget, CallLedger, FakeSolver  # noqa: E402
from core.sympy_task import ROUNDED_EXPLANATION, parse_task  # noqa: E402
from core.worksheet import (  # noqa: E402
    STATUS_OK,
    FakeWorksheetSource,
    grade_worksheet,
    read_worksheet,
)
from core.worksheet_types import (  # noqa: E402
    Grade,
    WorksheetItem,
    WorksheetReading,
    join_statement,
)

FUNCTION_SETUP = r"f(x) = x^3 - 3x^2 + 2"
CURVE_SETUP = r"The curve is y^2 = x^3 - 3x + 3."
CROSS_CHECK_AGREES = sympy_task.CROSS_CHECK_AGREES
TANGENT = r"Write the equation of the tangent line at $x=1$."
CRITICAL = r"Find all critical points where $f'(x)=0$."
INCREASING = r"On what intervals is $f$ increasing?"
INTEGRAL_THREE_OVER_X = r"Find $\int \frac{3}{x}\,dx$."
EXACT_INTEGRAL = r"Compute $\int_0^1 e^x\,dx$."
SOLVE_SQUARE = r"Solve $x^2 = 2$."
HORIZONTAL = r"Find all points where the tangent line is horizontal."


def _chunk(kind: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(kind + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)


def _png() -> bytes:
    """A valid 1x1 RGB PNG, so the image checks pass."""
    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    pixel = zlib.compress(bytes([0, 255, 0, 0]))
    return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", header) + _chunk(b"IDAT", pixel) + _chunk(b"IEND", b"")


def _reading(setup: str, parts: list) -> WorksheetReading:
    items = tuple(
        WorksheetItem(
            number=index + 1,
            part_label="abcdefghij"[index],
            statement_latex=statement,
            student_answer_latex="; ".join(finals),
            final_answers_latex=tuple(finals),
            explanation_text="",
        )
        for index, (statement, finals) in enumerate(parts)
    )
    return WorksheetReading(shared_context=setup, items=items)


def _grade(setup: str, parts: list, solver: FakeSolver | None = None) -> list[Grade]:
    """Read the scripted worksheet through the normal path, then grade every part with no bank."""
    result = read_worksheet(_png(), FakeWorksheetSource(_reading(setup, parts)), topics=())
    assert result["status"] == STATUS_OK
    graded = WorksheetReading.model_validate(result["reading"])
    return [entry.grade for entry in grade_worksheet(graded, solver or FakeSolver(), bank=())]


def _grade_one(setup: str, statement: str, finals: tuple, solver: FakeSolver | None = None) -> Grade:
    return _grade(setup, [(statement, finals)], solver)[0]


# ---------------------------------------------------------------------------
# Worksheet 1: f(x) = x^3 - 3x^2 + 2
# ---------------------------------------------------------------------------

WORKSHEET_ONE = [
    # (a) f'(x) and (b) f'(1): handled before this change, kept as a regression
    pytest.param(r"Find $f'(x)$.", ("3x(x-2)",), "correct", id="a-derivative"),
    pytest.param(r"Compute $f'(1)$.", (r"-3\pi",), "incorrect", id="b-value"),
    # (c) tangent line at x = 1: the true line is y = -3x + 3
    pytest.param(TANGENT, ("y=-3x-3",), "incorrect", id="c-wrong-intercept"),
    pytest.param(TANGENT, ("y-0=-3(x-1)",), "correct", id="c-point-slope"),
    pytest.param(TANGENT, ("y=-3x+3",), "correct", id="c-slope-intercept"),
    pytest.param(TANGENT, ("3x+y=3",), "correct", id="c-standard"),
    # (d) critical points: {0, 2}
    pytest.param(CRITICAL, ("0; -2",), "incorrect", id="d-wrong-element"),
    pytest.param(CRITICAL, ("0; 2",), "correct", id="d-correct"),
    pytest.param(CRITICAL, ("2", "0"), "correct", id="d-two-answers"),
    pytest.param(CRITICAL, ("0; 2; 3",), "incorrect", id="d-extra-element"),
    pytest.param(CRITICAL, ("0",), "incorrect", id="d-missing-element"),
    # (e) increasing: x < 0 or x > 2
    pytest.param(INCREASING, ("0>x", "x>2"), "correct", id="e-two-final-answers"),
    pytest.param(INCREASING, (r"(-\infty,0)\cup(2,\infty)",), "correct", id="e-interval-union"),
    pytest.param(INCREASING, ("(0,2)",), "incorrect", id="e-open-interval"),
    # (g) indefinite integral of 3/x
    pytest.param(INTEGRAL_THREE_OVER_X, (r"3\ln|x| + C",), "correct", id="g-ln-abs"),
    pytest.param(INTEGRAL_THREE_OVER_X, (r"3\ln x + C",), "unsure", id="g-ln-x-domain"),
    pytest.param(INTEGRAL_THREE_OVER_X, (r"3\ln|x|",), "unsure", id="g-missing-plus-c"),
    # (h) exact integral: handled before this change, kept as a regression
    pytest.param(EXACT_INTEGRAL, ("1.718",), "unsure", id="h-rounded-decimal"),
    pytest.param(EXACT_INTEGRAL, ("e-1",), "correct", id="h-exact"),
    pytest.param(EXACT_INTEGRAL, ("1.7",), "incorrect", id="h-wrong-decimal"),
    # (i) solve x^2 = 2
    pytest.param(SOLVE_SQUARE, (r"x=\pm\sqrt{2}",), "correct", id="i-both-roots"),
    pytest.param(SOLVE_SQUARE, (r"x=\sqrt{2}",), "incorrect", id="i-positive-root-only"),
]


@pytest.mark.parametrize("statement, finals, verdict", WORKSHEET_ONE)
def test_worksheet_one_part_is_marked_as_the_brief_requires(statement: str, finals: tuple, verdict: str) -> None:
    grade = _grade_one(FUNCTION_SETUP, statement, finals)
    assert grade.verdict == verdict
    assert grade.method == "sympy_computed"


def test_domain_unsure_names_the_answer_that_is_right_for_both_signs() -> None:
    grade = _grade_one(FUNCTION_SETUP, INTEGRAL_THREE_OVER_X, (r"3\ln x + C",))
    assert grade.verdict == "unsure"
    assert "Agrees only for x>0; the answer should be 3 ln|x| + C" in grade.explanation


def test_missing_plus_c_is_unsure_and_says_add_plus_c() -> None:
    grade = _grade_one(FUNCTION_SETUP, INTEGRAL_THREE_OVER_X, (r"3\ln|x|",))
    assert grade.verdict == "unsure"
    assert "add + C" in grade.explanation


def test_rounded_decimal_of_the_exact_integral_is_unsure_not_correct() -> None:
    grade = _grade_one(FUNCTION_SETUP, EXACT_INTEGRAL, ("1.718",))
    assert grade.verdict == "unsure"
    assert grade.explanation == ROUNDED_EXPLANATION


def test_wrong_critical_point_explanation_names_the_sympy_set_and_the_student_answer() -> None:
    grade = _grade_one(FUNCTION_SETUP, CRITICAL, ("0; -2",))
    assert r"\left\{0, 2\right\}" in grade.explanation
    assert "0; -2" in grade.explanation


def test_wrong_tangent_explanation_names_the_sympy_line_and_the_student_line() -> None:
    grade = _grade_one(FUNCTION_SETUP, TANGENT, ("y=-3x-3",))
    assert "y = 3 - 3 x" in grade.explanation
    assert "y=-3x-3" in grade.explanation


def test_lim_abs_x_over_x_stays_on_the_ai_path() -> None:
    grade = _grade_one(FUNCTION_SETUP, r"Evaluate $\lim_{x\to 0} \frac{|x|}{x}$.", ("DNE",))
    assert grade.method.startswith("ai_")
    assert grade.method != "sympy_computed"


def test_one_sided_limit_guard_still_refuses_the_two_sided_limit() -> None:
    task = parse_task(r"Evaluate $\lim_{x\to 0} \frac{|x|}{x}$.")
    assert task is not None
    assert sympy_task.compute_answer(task) is None


def test_sympy_mark_for_the_one_sided_limit_is_none() -> None:
    mark = sympy_task.sympy_mark(
        r"Evaluate $\lim_{x\to 0} \frac{|x|}{x}$.", ("DNE",), FakeSolver(), CallLedger(CallBudget()), ""
    )
    assert mark is None


def test_timeout_sends_an_integral_to_the_ai_ladder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sympy_task, "SYMPY_TIMEOUT_S", 1e-6)
    grade = _grade_one(FUNCTION_SETUP, INTEGRAL_THREE_OVER_X, (r"3\ln|x| + C",))
    assert grade.method.startswith("ai_")


# ---------------------------------------------------------------------------
# Worksheet 2: y^2 = x^3 - 3x + 3
# ---------------------------------------------------------------------------

SLOPE = r"Find the slope of the tangent to the curve at $(-2,1)$."
CURVE_LINE = r"Find the equation of the tangent line at $(-2,1)$."
TRUE_POINTS = r"(1,1),(1,-1),(-1,\sqrt{5}),(-1,-\sqrt{5})"
WORKSHEET_TWO = [
    (SLOPE, (r"\frac{9}{2}",), "correct"),
    (CURVE_LINE, (r"y-1=\frac{9}{2}(x+2)",), "correct"),
    (HORIZONTAL, ("(-1,0),(1,0)",), "incorrect"),
    (HORIZONTAL, (TRUE_POINTS,), "correct"),
]


@pytest.mark.parametrize("statement, finals, verdict", WORKSHEET_TWO)
def test_worksheet_two_part_is_marked_as_the_brief_requires(statement: str, finals: tuple, verdict: str) -> None:
    grade = _grade_one(CURVE_SETUP, statement, finals)
    assert grade.verdict == verdict
    assert grade.method == "sympy_computed"


def test_points_that_are_not_on_the_curve_are_named() -> None:
    grade = _grade_one(CURVE_SETUP, HORIZONTAL, ("(-1,0),(1,0)",))
    assert "(-1, 0) is not on the curve." in grade.explanation


def test_all_worksheet_two_parts_grade_together_in_one_reading() -> None:
    grades = _grade(CURVE_SETUP, [(statement, finals) for statement, finals, _verdict in WORKSHEET_TWO])
    assert [grade.verdict for grade in grades] == ["correct", "correct", "incorrect", "correct"]


# ---------------------------------------------------------------------------
# The blind AI cross-check: it can confirm a SymPy mark or make it unsure; it never overrides
# ---------------------------------------------------------------------------


def test_ai_reply_that_agrees_with_sympy_confirms_an_incorrect_mark() -> None:
    solver = FakeSolver({join_statement(FUNCTION_SETUP, TANGENT): "y=-3x+3"})
    grade = _grade_one(FUNCTION_SETUP, TANGENT, ("y=-3x-3",), solver)
    assert grade.verdict == "incorrect"
    assert CROSS_CHECK_AGREES in grade.explanation


def test_ai_reply_that_disagrees_makes_a_correct_mark_unsure() -> None:
    solver = FakeSolver({join_statement(FUNCTION_SETUP, TANGENT): "y=-3x-3"})
    grade = _grade_one(FUNCTION_SETUP, TANGENT, ("y=-3x+3",), solver)
    assert grade.verdict == "unsure"
    assert grade.method == "sympy_computed"


def test_ai_reply_matching_the_student_cannot_make_a_wrong_mark_correct() -> None:
    solver = FakeSolver({join_statement(FUNCTION_SETUP, TANGENT): "y=-3x-3"})
    grade = _grade_one(FUNCTION_SETUP, TANGENT, ("y=-3x-3",), solver)
    assert grade.verdict == "unsure"


def test_ai_reply_that_agrees_with_sympy_confirms_a_correct_set_mark() -> None:
    solver = FakeSolver({join_statement(FUNCTION_SETUP, CRITICAL): "2; 0"})
    grade = _grade_one(FUNCTION_SETUP, CRITICAL, ("0; 2",), solver)
    assert grade.verdict == "correct"
    assert CROSS_CHECK_AGREES in grade.explanation


def test_no_ai_cross_check_is_recorded_when_the_solver_fails() -> None:
    grade = _grade_one(FUNCTION_SETUP, SOLVE_SQUARE, (r"x=\pm\sqrt{2}",), FakeSolver(error="down"))
    assert grade.verdict == "correct"
    assert "No independent AI cross-check was available" in grade.explanation
