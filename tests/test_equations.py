"""Equations, tangent lines, and horizontal tangents: reading, comparing, and SymPy's references.

Offline and in-process: no network, no model call. The child-process path is covered in test_worksheet_shapes.py.
"""

import sys
from pathlib import Path

import pytest
import sympy as sp

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core import equations  # noqa: E402
from core.derivative_checker import X  # noqa: E402
from core.equations import (  # noqa: E402
    CurveTangent,
    HorizontalPoints,
    NamedTangent,
    Y,
    compute_spec,
    equation_comparison,
    line_text,
    read_equation,
    split_top_level,
)
from core.solvers import DIFFERENT, EQUAL, UNKNOWN  # noqa: E402

FUNCTION_SETUP = r"f(x) = x^3 - 3x^2 + 2"
CURVE_SETUP = r"The curve is y^2 = x^3 - 3x + 3."
TANGENT_AT_ONE = Y - (0 + (-3) * (X - 1))  # y = -3x + 3, the true tangent of f at x = 1


def _status(student: str, reference: sp.Basic = TANGENT_AT_ONE) -> str:
    return equation_comparison(reference, read_equation(student)).status


# ---------------------------------------------------------------------------
# Reading and comparing equations
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "student",
    [r"y=-3x+3", r"3x+y=3", r"y-0=-3(x-1)", r"y = -3x + 3", r"y=-3 x+3"],
)
def test_equivalent_forms_of_the_true_tangent_are_equal(student: str) -> None:
    assert _status(student) == EQUAL


def test_same_slope_with_a_different_intercept_is_different() -> None:
    assert _status(r"y=-3x-3") == DIFFERENT


def test_a_constant_only_offset_is_not_equivalent() -> None:
    reference = Y - 3
    assert _status(r"y=5", reference) == DIFFERENT
    assert _status(r"y=3", reference) == EQUAL


def test_a_nonzero_multiple_of_the_same_equation_is_equal() -> None:
    assert _status(r"2y=6", Y - 3) == EQUAL


def test_comparison_needs_at_least_six_comparable_points() -> None:
    comparison = equation_comparison(TANGENT_AT_ONE, sp.nan * X)
    assert comparison.status == UNKNOWN
    assert comparison.points == 0


def test_comparison_samples_are_off_grid_and_numerous() -> None:
    assert len(equations.EQUATION_SAMPLES) >= 6
    grid = {0.0, 0.5, 1.0, 1.5, 2.0}
    assert all(px not in grid and py not in grid for px, py in equations.EQUATION_SAMPLES)


@pytest.mark.parametrize("text", [r"x<=2", r"y=\pm 2", r"y", "=3", "y==3", r"x^{2} y = 2 = 3"])
def test_text_that_is_not_one_equation_reads_as_none(text: str) -> None:
    assert read_equation(text) is None


def test_read_equation_refuses_a_variable_outside_x_and_y() -> None:
    assert read_equation(r"z = 3") is None


def test_line_text_names_the_line_as_y() -> None:
    assert line_text(TANGENT_AT_ONE) == r"y = 3 - 3 x"


# ---------------------------------------------------------------------------
# Splitting answers
# ---------------------------------------------------------------------------


def test_split_top_level_keeps_bracketed_commas_together() -> None:
    assert split_top_level(r"(-1,0),(1,0)", equations.COMMA) == ("(-1,0)", "(1,0)")
    assert split_top_level(r"(0,2)", equations.COMMA) == ("(0,2)",)


def test_split_top_level_refuses_unbalanced_brackets() -> None:
    assert split_top_level(r"(0,2", equations.COMMA) == ()


def test_alternative_separators_include_or_and_cup() -> None:
    pieces = split_top_level(r"x<0 or x>2", equations.ALTERNATIVE_SEPARATOR)
    assert pieces == ("x<0", "x>2")


# ---------------------------------------------------------------------------
# Shape of the ask and the setup
# ---------------------------------------------------------------------------


def test_named_tangent_is_read_from_the_setup_definition() -> None:
    spec = equations.parse_spec(r"Write the equation of the tangent line at $x=1$.", FUNCTION_SETUP)
    assert spec == NamedTangent(r"x^3 - 3x^2 + 2", "1")


def test_named_tangent_with_a_label_and_a_writing_request_still_reads() -> None:
    statement = r"(c) Write the equation of the tangent line at $x=1$ and write a sentence about it."
    assert equations.parse_spec(statement, FUNCTION_SETUP) == NamedTangent(r"x^3 - 3x^2 + 2", "1")


def test_named_tangent_without_a_definition_falls_through() -> None:
    assert equations.parse_spec(r"Write the equation of the tangent line at $x=1$.", "") is None


def test_curve_asks_need_the_curve_in_the_setup() -> None:
    assert equations.parse_spec(r"Find the slope of the tangent at $(-2,1)$.", "") is None


def test_curve_slope_and_tangent_shapes_are_read() -> None:
    slope = equations.parse_spec(r"Find the slope of the tangent to the curve at $(-2,1)$.", CURVE_SETUP)
    line = equations.parse_spec(r"Find the equation of the tangent line at $(-2,1)$.", CURVE_SETUP)
    assert slope == CurveTangent("y^2 = x^3 - 3x + 3", "-2", "1", slope=True)
    assert line == CurveTangent("y^2 = x^3 - 3x + 3", "-2", "1", slope=False)


def test_horizontal_points_shape_is_read() -> None:
    statement = r"Find all points where the tangent line is horizontal."
    assert equations.parse_spec(statement, CURVE_SETUP) == HorizontalPoints("y^2 = x^3 - 3x + 3")


@pytest.mark.parametrize(
    "statement",
    [r"Find $f'(x)$.", r"Compute $f'(1)$.", r"Solve $x^2 = 2$.", r"Find $\int \frac{3}{x}\,dx$."],
)
def test_other_asks_are_not_equation_asks(statement: str) -> None:
    assert equations.parse_spec(statement, FUNCTION_SETUP + " " + CURVE_SETUP) is None


# ---------------------------------------------------------------------------
# SymPy's references
# ---------------------------------------------------------------------------


def test_named_tangent_reference_is_the_true_line() -> None:
    line = compute_spec(NamedTangent(r"x^3 - 3x^2 + 2", "1"))
    assert line is not None
    assert sp.simplify(line - TANGENT_AT_ONE) == 0


def test_tangent_at_a_kink_has_no_reference() -> None:
    assert compute_spec(NamedTangent("|x|", "0")) is None


def test_implicit_slope_at_the_point_is_nine_halves() -> None:
    slope = compute_spec(CurveTangent("y^2 = x^3 - 3x + 3", "-2", "1", slope=True))
    assert slope == sp.Rational(9, 2)


def test_implicit_tangent_line_at_the_point() -> None:
    line = compute_spec(CurveTangent("y^2 = x^3 - 3x + 3", "-2", "1"))
    assert line is not None
    expected = Y - (sp.Rational(9, 2) * X + 10)
    assert sp.simplify(line - expected) == 0


def test_a_point_off_the_curve_has_no_reference() -> None:
    assert compute_spec(CurveTangent("y^2 = x^3 - 3x + 3", "-2", "2")) is None
    assert compute_spec(CurveTangent("y^2 = x^3 - 3x + 3", "-2", "2", slope=True)) is None


def test_horizontal_points_are_the_four_true_points() -> None:
    points = compute_spec(HorizontalPoints("y^2 = x^3 - 3x + 3"))
    expected = sp.FiniteSet(
        sp.Tuple(1, 1), sp.Tuple(1, -1), sp.Tuple(-1, sp.sqrt(5)), sp.Tuple(-1, -sp.sqrt(5))
    )
    assert points == expected


def test_horizontal_points_exclude_points_where_the_slope_is_undefined() -> None:
    points = compute_spec(HorizontalPoints("y^2 = x^3 - 3x + 3"))
    assert sp.Tuple(-1, 0) not in points
    assert sp.Tuple(1, 0) not in points


def test_implicit_slope_matches_the_hand_formula() -> None:
    curve = read_equation("y^2 = x^3 - 3x + 3")
    assert curve is not None
    slope = sp.idiff(curve, Y, X)
    assert sp.simplify(slope - (3 * X**2 - 3) / (2 * Y)) == 0


# ---------------------------------------------------------------------------
# Marks
# ---------------------------------------------------------------------------


def test_points_mark_names_the_point_that_is_not_on_the_curve() -> None:
    value = compute_spec(HorizontalPoints("y^2 = x^3 - 3x + 3"))
    mark = equations.mark_spec(HorizontalPoints("y^2 = x^3 - 3x + 3"), value, (r"(-1,0),(1,0)",))
    assert mark is not None
    assert mark.verdict == "incorrect"
    assert "(-1, 0) is not on the curve." in mark.explanation


def test_correct_points_are_marked_correct_in_any_order() -> None:
    value = compute_spec(HorizontalPoints("y^2 = x^3 - 3x + 3"))
    spec = HorizontalPoints("y^2 = x^3 - 3x + 3")
    answer = (r"(1,-1),(-1,-\sqrt{5}),(1,1),(-1,\sqrt{5})",)
    mark = equations.mark_spec(spec, value, answer)
    assert mark is not None and mark.verdict == "correct"


def test_points_set_with_an_extra_point_is_incorrect() -> None:
    value = compute_spec(HorizontalPoints("y^2 = x^3 - 3x + 3"))
    answer = (r"(1,1),(1,-1),(-1,\sqrt{5}),(-1,-\sqrt{5}),(1,0)",)
    mark = equations.mark_spec(HorizontalPoints("y^2 = x^3 - 3x + 3"), value, answer)
    assert mark is not None and mark.verdict == "incorrect"
    assert "(1, 0) is not on the curve." in mark.explanation


def test_points_set_with_a_missing_point_is_incorrect() -> None:
    value = compute_spec(HorizontalPoints("y^2 = x^3 - 3x + 3"))
    mark = equations.mark_spec(HorizontalPoints("y^2 = x^3 - 3x + 3"), value, ("(1,1),(1,-1),(-1,\\sqrt{5})",))
    assert mark is not None and mark.verdict == "incorrect"


def test_implicit_slope_mark_accepts_the_decimal_and_the_fraction() -> None:
    spec = CurveTangent("y^2 = x^3 - 3x + 3", "-2", "1", slope=True)
    value = compute_spec(spec)
    assert equations.mark_spec(spec, value, (r"\frac{9}{2}",)).verdict == "correct"
    assert equations.mark_spec(spec, value, ("4.5",)).verdict == "correct"
    assert equations.mark_spec(spec, value, ("9/4",)).verdict == "incorrect"


def test_implicit_tangent_line_mark_accepts_the_point_slope_form() -> None:
    spec = CurveTangent("y^2 = x^3 - 3x + 3", "-2", "1")
    value = compute_spec(spec)
    mark = equations.mark_spec(spec, value, (r"y-1=\frac{9}{2}(x+2)",))
    assert mark is not None and mark.verdict == "correct"


def test_tangent_mark_for_a_line_with_two_answers_falls_through() -> None:
    spec = NamedTangent(r"x^3 - 3x^2 + 2", "1")
    assert equations.mark_spec(spec, compute_spec(spec), ("y=-3x+3", "y=0")) is None
