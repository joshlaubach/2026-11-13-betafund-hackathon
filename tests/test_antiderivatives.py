"""Indefinite integrals graded by SymPy: domain, the trailing + C, and ln|x| against ln x.

Offline and in-process. SymPy's reference is computed here directly; the child-process path is in
test_worksheet_shapes.py.
"""

import sys
from pathlib import Path

import pytest
import sympy as sp

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core import antiderivatives  # noqa: E402
from core.antiderivatives import IntegralSpec, compute_spec, mark_spec, parse_spec  # noqa: E402
from core.derivative_checker import X  # noqa: E402
from core.solvers import Mark  # noqa: E402

THREE_OVER_X = IntegralSpec(r"\frac{3}{x}")


def _mark(spec: IntegralSpec, answer: str) -> Mark:
    value = compute_spec(spec)
    assert value is not None
    mark = mark_spec(spec, value, (answer,))
    assert mark is not None
    return mark


# ---------------------------------------------------------------------------
# Shape of the ask
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "statement, integrand",
    [
        (r"Find $\int \frac{3}{x}\,dx$.", r"\frac{3}{x}"),
        (r"Find $\int e^x\,dx$.", "e^x"),
        (r"Find $\int 2x\,dx$", "2x"),
    ],
)
def test_indefinite_integral_asks_read_their_integrand(statement: str, integrand: str) -> None:
    assert parse_spec(statement) == IntegralSpec(integrand)


@pytest.mark.parametrize(
    "statement",
    [
        r"Compute $\int_0^1 e^x\,dx$.",  # definite: the existing integral shape handles it
        r"Integrate $\int 2x\,dx$",  # not an ask verb in this module
        r"Find $\int 2x\,dy$.",
        r"Find $\int \sqrt{y}\,dx$.",
    ],
)
def test_other_integrals_fall_through(statement: str) -> None:
    assert parse_spec(statement) is None


# ---------------------------------------------------------------------------
# SymPy's reference antiderivative
# ---------------------------------------------------------------------------


def test_reference_for_three_over_x_uses_ln_of_the_absolute_value() -> None:
    value = compute_spec(THREE_OVER_X)
    assert value == 3 * sp.log(sp.Abs(X))


def test_reference_for_exp_is_exp() -> None:
    assert compute_spec(IntegralSpec("e^x")) == sp.exp(X)


def test_an_antiderivative_sympy_cannot_produce_has_no_reference() -> None:
    assert compute_spec(IntegralSpec(r"\frac{1}{x^{2}+1}")) is not None  # arctan is produced
    assert compute_spec(IntegralSpec(r"\sqrt{\sin(x)}")) is None  # SymPy returns an unevaluated Integral


# ---------------------------------------------------------------------------
# The student's answer: correct, unsure, incorrect
# ---------------------------------------------------------------------------


def test_three_ln_abs_x_plus_c_is_correct() -> None:
    mark = _mark(THREE_OVER_X, r"3\ln|x| + C")
    assert mark is not None
    assert mark.verdict == "correct"
    assert mark.method == "sympy_computed"


def test_domain_explanation_is_the_brief_text_for_three_ln_x() -> None:
    mark = _mark(THREE_OVER_X, r"3\ln x + C")
    assert mark is not None
    assert mark.verdict == "unsure"
    assert "Agrees only for x>0; the answer should be 3 ln|x| + C" in mark.explanation


def test_missing_plus_c_is_unsure_and_says_add_plus_c() -> None:
    mark = _mark(THREE_OVER_X, r"3\ln|x|")
    assert mark is not None
    assert mark.verdict == "unsure"
    assert "add + C" in mark.explanation


def test_plus_c_written_without_a_space_still_counts() -> None:
    mark = _mark(THREE_OVER_X, r"3\ln|x|+C")
    assert mark is not None and mark.verdict == "correct"


def test_ln_abs_written_with_left_and_right_bars_is_read() -> None:
    mark = _mark(THREE_OVER_X, r"3\ln\left|x\right| + C")
    assert mark is not None and mark.verdict == "correct"


def test_wrong_coefficient_is_incorrect_even_with_plus_c() -> None:
    mark = _mark(THREE_OVER_X, r"2\ln|x| + C")
    assert mark is not None and mark.verdict == "incorrect"


def test_wrong_function_is_incorrect() -> None:
    mark = _mark(THREE_OVER_X, r"\ln|x| + C")
    assert mark is not None and mark.verdict == "incorrect"


def test_wrong_derivative_stays_incorrect_even_without_plus_c() -> None:
    mark = _mark(THREE_OVER_X, r"2\ln|x|")
    assert mark is not None and mark.verdict == "incorrect"


def test_answer_real_only_for_negative_x_agrees_only_for_x_less_than_zero() -> None:
    mark = _mark(THREE_OVER_X, r"3\ln(-x) + C")
    assert mark is not None
    assert mark.verdict == "unsure"
    assert "Agrees only for x<0" in mark.explanation


def test_multiple_answers_fall_through() -> None:
    value = compute_spec(THREE_OVER_X)
    assert mark_spec(THREE_OVER_X, value, (r"3\ln|x| + C", "0")) is None


def test_unreadable_answer_falls_through() -> None:
    value = compute_spec(THREE_OVER_X)
    assert mark_spec(THREE_OVER_X, value, (r"3\ln|x| + D",)) is None


def test_exp_answer_with_plus_c_is_correct() -> None:
    value = compute_spec(IntegralSpec("e^x"))
    assert mark_spec(IntegralSpec("e^x"), value, ("e^x + C",)).verdict == "correct"


# ---------------------------------------------------------------------------
# Reading helpers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text, expected",
    [
        (r"3\ln|x|", r"3\ln{|x|}"),
        (r"3\ln \left|x\right|", r"3\ln{|x|}"),
        (r"3\ln{|x|}", r"3\ln{|x|}"),
    ],
)
def test_bars_after_ln_are_wrapped_for_the_reader(text: str, expected: str) -> None:
    assert antiderivatives.readable_bars(text) == expected


def test_split_constant_removes_only_a_trailing_plus_c() -> None:
    assert antiderivatives.split_constant(r"3\ln|x| + C") == (r"3\ln|x|", True)
    assert antiderivatives.split_constant(r"3\ln|x|") == (r"3\ln|x|", False)
    assert antiderivatives.split_constant("C + x") == ("C + x", False)


def test_plain_text_of_the_reference_is_three_ln_abs_x() -> None:
    assert antiderivatives.plain_antiderivative(3 * sp.log(sp.Abs(X))) == "3 ln|x|"
