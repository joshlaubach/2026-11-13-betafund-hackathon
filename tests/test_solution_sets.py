"""Solution sets graded by SymPy: solve, critical points, and intervals of increase or decrease.

Offline and in-process. The student's several final answers are tested as ONE set (alternatives).
"""

import sys
from pathlib import Path

import pytest
import sympy as sp

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core.solution_sets import (  # noqa: E402
    CRITICAL,
    DECREASING,
    INCREASING,
    SOLVE,
    SetSpec,
    compute_spec,
    mark_spec,
    parse_spec,
    read_student_set,
)

FUNCTION_SETUP = r"f(x) = x^3 - 3x^2 + 2"
INCREASING_SET = sp.Union(sp.Interval.open(-sp.oo, 0), sp.Interval.open(2, sp.oo))


def _verdict(spec: SetSpec, *answers: str) -> str:
    value = compute_spec(spec)
    assert value is not None
    mark = mark_spec(spec, value, answers)
    assert mark is not None
    return mark.verdict


# ---------------------------------------------------------------------------
# Shape of the ask
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "statement, body",
    [
        (r"Solve $x^2 = 2$.", "x^2 = 2"),
        (r"Solve for x: $2x + 3 = 7$.", "2x + 3 = 7"),
    ],
)
def test_solve_asks_read_their_equation(statement: str, body: str) -> None:
    assert parse_spec(statement) == SetSpec(SOLVE, body)


def test_solve_asks_with_two_unknowns_fall_through() -> None:
    assert parse_spec(r"Solve $x^2 + y^2 = 2$.") is None


def test_critical_point_ask_reads_the_named_function() -> None:
    spec = parse_spec(r"Find all critical points where $f'(x)=0$.", FUNCTION_SETUP)
    assert spec == SetSpec(CRITICAL, "x^3 - 3x^2 + 2")


def test_critical_point_ask_without_the_definition_falls_through() -> None:
    assert parse_spec(r"Find all critical points where $f'(x)=0$.", "") is None


def test_increasing_and_decreasing_asks_read_the_named_function() -> None:
    assert parse_spec(r"On what intervals is $f$ increasing?", FUNCTION_SETUP) == SetSpec(
        INCREASING, "x^3 - 3x^2 + 2"
    )
    assert parse_spec(r"On what intervals is $f$ decreasing?", FUNCTION_SETUP) == SetSpec(
        DECREASING, "x^3 - 3x^2 + 2"
    )


# ---------------------------------------------------------------------------
# SymPy's reference sets
# ---------------------------------------------------------------------------


def test_solve_reference_is_plus_and_minus_root_two() -> None:
    value = compute_spec(SetSpec(SOLVE, "x^2 = 2"))
    assert value == sp.FiniteSet(-sp.sqrt(2), sp.sqrt(2))


def test_critical_point_reference_is_zero_and_two() -> None:
    assert compute_spec(SetSpec(CRITICAL, "x^3 - 3x^2 + 2")) == sp.FiniteSet(0, 2)


def test_increasing_reference_is_x_less_than_zero_or_x_greater_than_two() -> None:
    assert compute_spec(SetSpec(INCREASING, "x^3 - 3x^2 + 2")) == INCREASING_SET


def test_decreasing_reference_is_the_open_interval_between_zero_and_two() -> None:
    assert compute_spec(SetSpec(DECREASING, "x^3 - 3x^2 + 2")) == sp.Interval.open(0, 2)


def test_solve_with_no_real_root_is_the_empty_set_and_is_accepted() -> None:
    assert compute_spec(SetSpec(SOLVE, "x^2 = -1")) is sp.S.EmptySet


def test_solve_with_a_free_symbol_has_no_reference() -> None:
    assert compute_spec(SetSpec(SOLVE, "x^2 = y")) is None


# ---------------------------------------------------------------------------
# Reading the student's alternatives as one set
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "answers",
    [
        ("0>x", "x>2"),
        ("0>x; x>2",),
        ("x<0 or x>2",),
        (r"(-\infty,0)\cup(2,\infty)",),
        (r"(-\infty,0) \cup (2,\infty)",),
        ("x<0", "x>2"),
        ("2<x", "x<0"),
    ],
)
def test_alternatives_for_increasing_are_one_set(answers: tuple) -> None:
    assert read_student_set(answers) is not None
    assert _verdict(SetSpec(INCREASING, "x^3 - 3x^2 + 2"), *answers) == "correct"


def test_open_interval_for_increasing_is_incorrect() -> None:
    assert _verdict(SetSpec(INCREASING, "x^3 - 3x^2 + 2"), "(0,2)") == "incorrect"


def test_critical_points_in_either_order_are_correct() -> None:
    spec = SetSpec(CRITICAL, "x^3 - 3x^2 + 2")
    assert _verdict(spec, "0; 2") == "correct"
    assert _verdict(spec, "2; 0") == "correct"
    assert _verdict(spec, "2", "0") == "correct"


def test_critical_points_with_a_wrong_element_are_incorrect() -> None:
    assert _verdict(SetSpec(CRITICAL, "x^3 - 3x^2 + 2"), "0; -2") == "incorrect"


def test_critical_points_with_an_extra_element_are_incorrect() -> None:
    assert _verdict(SetSpec(CRITICAL, "x^3 - 3x^2 + 2"), "0; 2; 3") == "incorrect"


def test_critical_points_with_a_missing_element_are_incorrect() -> None:
    assert _verdict(SetSpec(CRITICAL, "x^3 - 3x^2 + 2"), "0") == "incorrect"


def test_solve_plus_or_minus_root_two_is_correct() -> None:
    spec = SetSpec(SOLVE, "x^2 = 2")
    assert _verdict(spec, r"x=\pm\sqrt{2}") == "correct"
    assert _verdict(spec, r"x=\sqrt{2}") == "incorrect"
    assert _verdict(spec, r"x=-\sqrt{2}, \sqrt{2}") == "correct"


def test_solve_with_a_bare_pm_and_no_x_is_read_as_a_set() -> None:
    assert read_student_set((r"\pm\sqrt{2}",)) == sp.FiniteSet(-sp.sqrt(2), sp.sqrt(2))


@pytest.mark.parametrize(
    "answers",
    [
        ("y=2",),  # an equation in y is not a value of x
        (r"\emptyset",),  # not in the grammar, so the part falls through
        ("x",),  # a free variable is not a value
        ("(0,2",),  # unbalanced bracket
        ("",),
    ],
)
def test_unreadable_alternatives_fall_through(answers: tuple) -> None:
    assert read_student_set(answers) is None


def test_one_unreadable_alternative_makes_the_whole_set_unreadable() -> None:
    assert read_student_set(("0", "x")) is None


def test_mark_with_no_readable_set_is_none() -> None:
    spec = SetSpec(CRITICAL, "x^3 - 3x^2 + 2")
    assert mark_spec(spec, compute_spec(spec), ("the point zero",)) is None


def test_mark_explanation_names_the_set_sympy_computed() -> None:
    spec = SetSpec(INCREASING, "x^3 - 3x^2 + 2")
    value = compute_spec(spec)
    mark = mark_spec(spec, value, ("(0,2)",))
    assert mark is not None
    assert mark.method == "sympy_computed"
    assert "(0,2)" in mark.explanation
    assert "SymPy computes the set" in mark.explanation
    assert mark.reference is not None and "2" in mark.reference
