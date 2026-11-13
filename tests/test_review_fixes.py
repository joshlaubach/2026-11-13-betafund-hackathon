"""Regression tests for the five grading bugs in docs/review-grading.md, plus the old behaviour they must not change.

Offline only: FakeSolvers, scripted worksheet readings, and SymPy in the spawned child process, as in production.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tests"))

from core import solution_sets, sympy_task  # noqa: E402
from core.answer_chain import CHAIN_EXPLANATION  # noqa: E402
from core.definitions import parse_definitions, restricted_names, split_asks  # noqa: E402
from core.solvers import CallBudget, CallLedger, FakeSolver  # noqa: E402
from core.sympy_task import ROUNDED_EXPLANATION, parse_tasks  # noqa: E402
from test_worksheet_shapes import (  # noqa: E402
    CURVE_SETUP,
    FUNCTION_SETUP,
    INTEGRAL_THREE_OVER_X,
    TANGENT,
    _grade_one,
)

DRONE_CONTEXT = "A drone has velocity v(t) = 1 - e^{-t}."
RESTRICTED_SETUP = "f(x)=x^2 for x>0."
SLOPE = r"Find the slope of the tangent to the curve at $(-2,1)$."
SECOND_ASK = r"Find $f'(x)$ for $f(x) = x^2$ and state where $f'(x) > 0$."
EXACT_PI = r"Find $f'(0)$ for $f(x) = \pi x$. Give an exact answer."
EXACT_HALF = r"Find $f'(0)$ for $f(x) = \frac{x}{2}$. Give an exact answer."
EXACT_INTEGRAL_STATEMENT = r"Compute $\int_0^1 e^x\,dx$. Give an exact answer."
PLAIN_EXACT_INTEGRAL = r"Compute $\int_0^1 e^x\,dx$."
SOLVE_ONE = r"Solve $x=1$."


def _is_ai(grade) -> bool:
    return grade.method.startswith("ai_")


# ---------------------------------------------------------------------------
# Fix 1: a domain restriction in a definition sends its parts to the AI path
# ---------------------------------------------------------------------------


def test_review_fix_1_restricted_definition_is_not_sympy_computed_correct() -> None:
    grade = _grade_one(RESTRICTED_SETUP, "Find $f'(-1)$.", ("-2",), FakeSolver())
    assert grade.method != "sympy_computed"
    assert _is_ai(grade)


@pytest.mark.parametrize(
    "setup",
    [
        pytest.param("f(x)=x^2 if x>0.", id="if"),
        pytest.param(r"f(x)=x^2 when x \ge 0.", id="when-geq"),
        pytest.param("f(x)=x^2 defined for x>0.", id="defined-for"),
    ],
)
def test_review_fix_1_other_restriction_wordings_also_fall_through(setup: str) -> None:
    assert "f" in restricted_names(setup)
    assert "f" not in parse_definitions(setup)
    grade = _grade_one(setup, "Find $f'(-1)$.", ("-2",), FakeSolver())
    assert grade.method != "sympy_computed"


def test_review_fix_1_restricted_definition_is_left_out_of_the_parsed_definitions() -> None:
    assert parse_definitions(RESTRICTED_SETUP) == {}
    assert restricted_names(RESTRICTED_SETUP) == frozenset({"f"})


def test_review_fix_1_definition_followed_by_units_prose_still_grades_by_sympy() -> None:
    setup = "A drone has velocity v(t) = 1 - e^{-t} meters per second."
    assert parse_definitions(setup)["v"].body_latex == "1 - e^{-t}"
    grade = _grade_one(setup, "Compute $v(0)$.", ("0",), FakeSolver())
    assert grade.method == "sympy_computed"
    assert grade.verdict == "correct"


# ---------------------------------------------------------------------------
# Fix 2: a second math ask is kept; only genuine writing instructions are stripped
# ---------------------------------------------------------------------------


def test_review_fix_2_second_math_ask_is_kept_and_falls_through() -> None:
    assert len(split_asks(SECOND_ASK)) == 1
    assert "state where" in split_asks(SECOND_ASK)[0]
    grade = _grade_one("", SECOND_ASK, ("2x",), FakeSolver())
    assert grade.method != "sympy_computed"
    assert _is_ai(grade)


def test_review_fix_2_writing_instruction_after_a_derivative_is_still_stripped() -> None:
    grade = _grade_one(FUNCTION_SETUP, r"Find $f'(x)$ and explain your reasoning.", ("3x(x-2)",))
    assert grade.verdict == "correct"
    assert grade.method == "sympy_computed"


def test_review_fix_2_state_in_a_sentence_is_a_writing_instruction() -> None:
    assert split_asks(r"Find $f'(x)$ and state in a sentence what it means.") == ("Find f'(x)",)


def test_review_fix_2_drone_write_a_sentence_is_still_stripped() -> None:
    assert split_asks("Compute $v(0)$ and write a sentence about it.") == ("Compute v(0)",)
    assert parse_tasks("Compute $v(0)$ and write a sentence.", DRONE_CONTEXT) is not None


def test_review_fix_2_power_rule_derivative_is_unchanged() -> None:
    grade = _grade_one(FUNCTION_SETUP, r"Find $f'(x)$.", ("3x(x-2)",))
    assert grade.verdict == "correct"
    assert grade.method == "sympy_computed"


def test_review_fix_2_unsure_for_a_log_without_plus_c_is_unchanged() -> None:
    grade = _grade_one(FUNCTION_SETUP, INTEGRAL_THREE_OVER_X, (r"3\ln x + C",))
    assert grade.verdict == "unsure"


# ---------------------------------------------------------------------------
# Fix 3: a chain of equal signs is only correct when every readable step matches
# ---------------------------------------------------------------------------


def test_review_fix_3_contradictory_slope_chain_is_unsure_with_format_reason() -> None:
    grade = _grade_one(CURVE_SETUP, SLOPE, ("dy/dx = 100 = 9/2",), FakeSolver())
    assert grade.verdict == "unsure"
    assert grade.reason == "format"
    assert grade.explanation == CHAIN_EXPLANATION


def test_review_fix_3_consistent_slope_chain_stays_correct() -> None:
    grade = _grade_one(CURVE_SETUP, SLOPE, ("dy/dx = 18/4 = 9/2",), FakeSolver())
    assert grade.verdict == "correct"
    assert grade.method == "sympy_computed"


def test_review_fix_3_contradictory_derivative_chain_is_unsure() -> None:
    grade = _grade_one(FUNCTION_SETUP, r"Compute $f'(1)$.", ("-3 = 2 = -3",), FakeSolver())
    assert grade.verdict == "unsure"
    assert grade.explanation == CHAIN_EXPLANATION


def test_review_fix_3_tangent_line_equation_is_not_a_chain() -> None:
    assert _grade_one(FUNCTION_SETUP, TANGENT, ("y=-3x+3",)).verdict == "correct"
    assert _grade_one(FUNCTION_SETUP, TANGENT, ("y=-3x-3",)).verdict == "incorrect"
    assert _grade_one(FUNCTION_SETUP, TANGENT, ("3x+y=3",)).verdict == "correct"


def test_review_fix_3_solution_set_with_equal_sign_is_not_a_chain() -> None:
    grade = _grade_one(FUNCTION_SETUP, r"Solve $x^2 = 2$.", (r"x=\pm\sqrt{2}",))
    assert grade.verdict == "correct"


# ---------------------------------------------------------------------------
# Fix 4: a decimal is not the exact answer when the statement asks for an exact answer
# ---------------------------------------------------------------------------


def test_review_fix_4_decimal_for_pi_is_unsure_when_exact_is_asked() -> None:
    grade = _grade_one("", EXACT_PI, ("3.14159265359",), FakeSolver())
    assert grade.verdict == "unsure"
    assert grade.reason == "rule"
    assert grade.explanation == ROUNDED_EXPLANATION


def test_review_fix_4_terminating_decimal_for_a_rational_stays_correct_when_exact_is_asked() -> None:
    grade = _grade_one("", EXACT_HALF, ("0.5",), FakeSolver())
    assert grade.verdict == "correct"
    assert grade.method == "sympy_computed"


def test_review_fix_4_decimal_is_unchanged_when_exact_is_not_asked() -> None:
    grade = _grade_one("", r"Find $f'(0)$ for $f(x) = \pi x$.", ("3.14159265359",), FakeSolver())
    assert grade.verdict == "correct"
    assert grade.method == "sympy_computed"


def test_review_fix_4_rounded_decimal_of_exact_integral_is_not_correct() -> None:
    grade = _grade_one("", EXACT_INTEGRAL_STATEMENT, ("1.718",), FakeSolver())
    assert grade.verdict != "correct"


def test_review_fix_4_exact_e_minus_one_stays_correct() -> None:
    grade = _grade_one(FUNCTION_SETUP, PLAIN_EXACT_INTEGRAL, ("e-1",), FakeSolver())
    assert grade.verdict == "correct"
    assert grade.method == "sympy_computed"


# ---------------------------------------------------------------------------
# Fix 5: a non-real interval endpoint is unreadable, and the new SymPy path cannot crash the grader
# ---------------------------------------------------------------------------


def test_review_fix_5_non_real_interval_endpoint_is_unreadable_not_a_crash() -> None:
    assert solution_sets.read_student_set((r"(\sqrt{-1},1)",)) is None


def test_review_fix_5_non_real_interval_endpoint_grades_without_raising() -> None:
    grade = _grade_one("", SOLVE_ONE, (r"(\sqrt{-1},1)",), FakeSolver())
    assert grade.method != "sympy_computed"
    assert _is_ai(grade)


def test_review_fix_5_unexpected_error_on_the_set_path_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(spec: object, value: object, answers: object) -> None:
        raise RuntimeError("unexpected failure in the set path")

    monkeypatch.setattr(solution_sets, "mark_spec", fail)
    mark = sympy_task.sympy_mark(SOLVE_ONE, ("1",), FakeSolver(), CallLedger(CallBudget()), "")
    assert mark is None
