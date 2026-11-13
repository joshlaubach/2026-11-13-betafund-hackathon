"""Domain and tolerance checks in core/solvers.py.

Answers that agree for x > 0 but not for x < 0 are DOMAIN_DIFFERS, which is always unsure. Two
constants use a tighter tolerance than sampled expressions. Offline only: SymPy, no model, no network.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core.solvers import (  # noqa: E402
    DOMAIN_DIFFERS,
    DOMAIN_EXPLANATION,
    Comparison,
    compare_answers,
    comparison_mark,
)

LN_ABS = r"\ln(|x|)"
LN = r"\ln x"


@pytest.mark.parametrize(
    "key, student",
    [(LN_ABS, LN), (r"|x|", "x"), (r"\sqrt{x^{2}}", "x")],
)
def test_answers_that_differ_for_negative_x_are_domain_differs(key: str, student: str) -> None:
    assert compare_answers(key, student).status == DOMAIN_DIFFERS


@pytest.mark.parametrize(
    "key, student",
    [(LN_ABS, LN), (r"|x|", "x"), (r"\sqrt{x^{2}}", "x")],
)
def test_domain_differs_is_unsure_with_the_domain_explanation_and_never_correct(
    key: str, student: str
) -> None:
    comparison = compare_answers(key, student)
    mark = comparison_mark(comparison, student, key, "ai_ladder", "the agreed AI answer")
    assert mark is not None
    assert mark.verdict == "unsure"
    assert mark.explanation == DOMAIN_EXPLANATION
    assert mark.explanation == (
        "The answers agree for positive x but differ for negative x (for example ln|x| against ln x). "
        "Check the domain."
    )


def test_domain_differs_mark_is_unsure_for_a_bank_method_too() -> None:
    mark = comparison_mark(Comparison(DOMAIN_DIFFERS, 10), "x", "|x|", "bank_key", "the verified key")
    assert mark is not None
    assert mark.verdict == "unsure"
    assert mark.method == "bank_key"


@pytest.mark.parametrize(
    "key, student",
    [
        ("x^{2}+2x", "2x+x^{2}"),
        (r"\sqrt{x}", r"\sqrt{x}"),
        (r"\frac{1}{x}", r"\frac{1}{x}"),
    ],
)
def test_answers_that_agree_on_both_sides_stay_equal(key: str, student: str) -> None:
    assert compare_answers(key, student).status == "equal"


def test_constant_answers_skip_the_negative_check_and_stay_equal() -> None:
    assert compare_answers(r"\frac{1}{8}", r"\frac{2}{16}").status == "equal"


def test_constants_one_in_a_billion_apart_are_different() -> None:
    assert compare_answers("1000000000", "1000000001").status == "different"
