"""Two grading fixes: the AI cross-check reads solution sets as sets, and implicit-curve shapes are recognised.

Offline only, with the same scripted reading and FakeSolver helpers as test_worksheet_shapes.py.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core import sympy_task  # noqa: E402
from core.solution_sets import SOLVE, SetSpec  # noqa: E402
from core.solvers import FakeSolver  # noqa: E402
from core.worksheet_types import join_statement  # noqa: E402
from test_worksheet_shapes import (  # noqa: E402
    CRITICAL,
    CROSS_CHECK_AGREES,
    FUNCTION_SETUP,
    SOLVE_SQUARE,
    _grade_one,
)

AI_LIST_OF_ZERO_AND_TWO = r"x=0,\ x=2"
SUPPOSE_SETUP = "Suppose we have an implicitly defined curve given by: y^2 = x^3 - 3x + 3"
SLOPE_LEAD_IN = (
    r"Use implicit differentiation to find the slope of the tangent line to the curve at the point "
    r"$(-2,1)$. Give an exact answer."
)
TANGENT_IN_WORDS = r"Write the equation of the tangent line to the curve at the point $(-2,1)$."
COORDINATES_HORIZONTAL = (
    r"Find the coordinates of all points on the curve where the tangent line is horizontal."
)
TRUE_HORIZONTAL_POINTS = r"(1,1),(1,-1),(-1,\sqrt{5}),(-1,-\sqrt{5})"
VERTICAL = r"Find all points on the curve where the tangent line is vertical."
SLOPE_NO_DOLLARS = r"Find the slope of the tangent line to the curve at the point (-2,1)."


def _ai(setup: str, statement: str, reply: str) -> FakeSolver:
    """A FakeSolver whose blind solve of this part returns reply."""
    return FakeSolver({join_statement(setup, statement): reply})


# ---------------------------------------------------------------------------
# Bug 1: a solution-set cross-check reply is read as a set, like the student's answer
# ---------------------------------------------------------------------------


def test_set_crosscheck_ai_list_with_spacing_confirms_a_correct_set() -> None:
    solver = _ai(FUNCTION_SETUP, CRITICAL, AI_LIST_OF_ZERO_AND_TWO)
    grade = _grade_one(FUNCTION_SETUP, CRITICAL, ("0; 2",), solver)
    assert grade.verdict == "correct"
    assert grade.method == "sympy_computed"
    assert CROSS_CHECK_AGREES in grade.explanation


def test_set_crosscheck_ai_list_keeps_an_incorrect_set_incorrect_not_unsure() -> None:
    solver = _ai(FUNCTION_SETUP, CRITICAL, AI_LIST_OF_ZERO_AND_TWO)
    grade = _grade_one(FUNCTION_SETUP, CRITICAL, ("0; -2",), solver)
    assert grade.verdict == "incorrect"
    assert CROSS_CHECK_AGREES in grade.explanation
    assert "may have been read wrongly" not in grade.explanation


def test_set_crosscheck_plus_minus_student_and_ai_roots_agree() -> None:
    solver = _ai(FUNCTION_SETUP, SOLVE_SQUARE, r"x=\sqrt{2},\ x=-\sqrt{2}")
    grade = _grade_one(FUNCTION_SETUP, SOLVE_SQUARE, (r"x=\pm\sqrt{2}",), solver)
    assert grade.verdict == "correct"
    assert CROSS_CHECK_AGREES in grade.explanation


def test_set_crosscheck_ai_list_of_a_different_set_makes_a_correct_mark_unsure() -> None:
    solver = _ai(FUNCTION_SETUP, CRITICAL, r"x=0,\ x=3")
    grade = _grade_one(FUNCTION_SETUP, CRITICAL, ("0; 2",), solver)
    assert grade.verdict == "unsure"
    assert "may have been read wrongly" in grade.explanation


def test_set_crosscheck_unreadable_ai_reply_stays_unsure() -> None:
    solver = _ai(FUNCTION_SETUP, CRITICAL, "the critical points are nice")
    grade = _grade_one(FUNCTION_SETUP, CRITICAL, ("0; 2",), solver)
    assert grade.verdict == "unsure"


def test_set_crosscheck_spacing_is_removed_from_set_replies_only() -> None:
    assert sympy_task._reply_text(SetSpec(SOLVE, "x^2 = 2"), r"x=1,\ x=2") == "x=1, x=2"
    assert sympy_task._reply_text("not a set spec", r"x=1,\ x=2") == r"x=1,\ x=2"


# ---------------------------------------------------------------------------
# Bug 2: implicit-curve setups, the slope and tangent asks, and horizontal or vertical points
# ---------------------------------------------------------------------------


def test_implicit_setup_slope_with_lead_in_and_exact_request_is_marked_by_sympy() -> None:
    grade = _grade_one(SUPPOSE_SETUP, SLOPE_LEAD_IN, (r"\frac{9}{2}",))
    assert grade.verdict == "correct"
    assert grade.method == "sympy_computed"


def test_implicit_setup_tangent_line_at_the_point_in_words_is_marked_by_sympy() -> None:
    grade = _grade_one(SUPPOSE_SETUP, TANGENT_IN_WORDS, (r"y-1=\frac{9}{2}(x+2)",))
    assert grade.verdict == "correct"
    assert grade.method == "sympy_computed"


def test_implicit_setup_slope_without_dollar_signs_is_marked_by_sympy() -> None:
    grade = _grade_one(SUPPOSE_SETUP, SLOPE_NO_DOLLARS, (r"\frac{9}{2}",))
    assert grade.verdict == "correct"
    assert grade.method == "sympy_computed"


def test_implicit_setup_wrong_horizontal_points_are_incorrect_with_sympy() -> None:
    grade = _grade_one(SUPPOSE_SETUP, COORDINATES_HORIZONTAL, ("(-1,0); (1,0)",))
    assert grade.verdict == "incorrect"
    assert grade.method == "sympy_computed"
    assert "(-1, 0) is not on the curve." in grade.explanation


def test_implicit_setup_true_horizontal_points_are_correct() -> None:
    grade = _grade_one(SUPPOSE_SETUP, COORDINATES_HORIZONTAL, (TRUE_HORIZONTAL_POINTS,))
    assert grade.verdict == "correct"
    assert grade.method == "sympy_computed"


def test_implicit_setup_vertical_points_are_marked_by_sympy() -> None:
    grade = _grade_one(SUPPOSE_SETUP, VERTICAL, ("(1,0)",))
    assert grade.verdict == "incorrect"
    assert grade.method == "sympy_computed"
    assert "is not on the curve" in grade.explanation


def test_implicit_setup_point_off_the_curve_falls_through_to_the_ai_ladder() -> None:
    off_curve = r"Find the slope of the tangent to the curve at $(-2,2)$."
    grade = _grade_one(SUPPOSE_SETUP, off_curve, (r"\frac{9}{2}",))
    assert grade.method.startswith("ai_")


def test_implicit_setup_curve_without_x_is_not_a_curve_and_falls_through() -> None:
    grade = _grade_one("Suppose the curve is given by: y^2 = 4.", SLOPE_NO_DOLLARS, (r"\frac{9}{2}",))
    assert grade.method.startswith("ai_")


def test_implicit_setup_unrelated_ask_about_the_curve_falls_through() -> None:
    grade = _grade_one(SUPPOSE_SETUP, r"Sketch the curve.", ("a sketch",))
    assert grade.method.startswith("ai_")
