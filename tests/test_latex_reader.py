"""Tests for core/latex_reader.py, which reads LaTeX via the plain text grammar."""

import sys
import time
from pathlib import Path

import pytest
import sympy as sp

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core.input_boundary import BoundaryError  # noqa: E402
from core.latex_reader import latex_to_text, read_latex  # noqa: E402

MODULE_PATH = REPO_ROOT / "core" / "latex_reader.py"
HOSTILE_TIME_LIMIT_SECONDS = 0.5
FORBIDDEN_SOURCE_WORDS = ("eval", "exec", "sympify", "parse_expr", "sympy.parsing", "import re")

X = sp.Symbol("x", real=True)

CONSTRUCT_CASES = [
    ("3", sp.Integer(3)),
    ("2.5", sp.Rational(5, 2)),
    ("x", X),
    ("2x", 2 * X),
    ("2 x", 2 * X),
    ("x + 1", X + 1),
    ("x - 1", X - 1),
    ("2 \\cdot x", 2 * X),
    ("2 \\times x", 2 * X),
    ("2 * x", 2 * X),
    ("\\frac{x}{2}", X / 2),
    ("\\dfrac{1}{x}", 1 / X),
    ("\\sqrt{x}", sp.sqrt(X)),
    ("\\sqrt{x^{2}}", sp.sqrt(X**2)),
    ("\\left(x+1\\right)\\left(x-1\\right)", (X + 1) * (X - 1)),
    ("\\displaystyle 2\\,x\\;+\\!1\\ ", 2 * X + 1),
    ("\\pi x", sp.pi * X),
    ("2\\pi x", 2 * sp.pi * X),
    ("\\pi/4", sp.pi / 4),
    ("e", sp.E),
    ("e^{x}", sp.exp(X)),
    ("e^{\\sqrt{x}}", sp.exp(sp.sqrt(X))),
    ("\\sin{\\left(x \\right)}", sp.sin(X)),
    ("\\sin(x)", sp.sin(X)),
    ("\\sin x", sp.sin(X)),
    ("\\sin^{2}{\\left(x\\right)}", sp.sin(X) ** 2),
    ("\\sin^{2} x", sp.sin(X) ** 2),
    ("\\cos^{3}{\\left(x \\right)}", sp.cos(X) ** 3),
    ("\\tan x", sp.tan(X)),
    ("\\sec x", sp.sec(X)),
    ("\\csc x", sp.csc(X)),
    ("\\cot x", sp.cot(X)),
    ("\\sinh x", sp.sinh(X)),
    ("\\cosh x", sp.cosh(X)),
    ("\\tanh x", sp.tanh(X)),
    ("\\ln{x}", sp.log(X)),
    ("\\ln{\\left(x \\right)}", sp.log(X)),
    ("\\arcsin{x}", sp.asin(X)),
    ("\\arccos x", sp.acos(X)),
    ("\\arctan{x}", sp.atan(X)),
    ("\\exp{x}", sp.exp(X)),
    ("|x|", sp.Abs(X)),
    ("\\left|x\\right|", sp.Abs(X)),
    ("\\left|{x - 1}\\right|", sp.Abs(X - 1)),
    ("3 x^{2}", 3 * X**2),
    ("(x+1)(x-1)", (X + 1) * (X - 1)),
    ("x^{-1}", X**-1),
    ("x^{\\frac{3}{2}}", X ** sp.Rational(3, 2)),
    ("x^2", X**2),
    ("\\sin x + 1", sp.sin(X) + 1),
    ("\\sin 2", sp.sin(2)),
    ("\\sin{2x}", sp.sin(2 * X)),
    ("\\sin(2x)", sp.sin(2 * X)),
    ("\\sin^{2} x + 1", sp.sin(X) ** 2 + 1),
    ("\\sin x \\cdot 2", 2 * sp.sin(X)),
]

BANK_EXAMPLE_CASES = [
    ("- \\frac{1}{8}", sp.Rational(-1, 8)),
    ("3 e^{\\sqrt{x}}", 3 * sp.exp(sp.sqrt(X))),
    ("\\sin^{3}{\\left(x \\right)}", sp.sin(X) ** 3),
    ("4 x^{3} + 6 x", 4 * X**3 + 6 * X),
]

PRECEDENCE_CASES = [
    ("-x^{2}", -(X**2)),
    ("\\frac{1}{2x}", 1 / (2 * X)),
    ("2^{3^{2}}", sp.Integer(512)),
    ("2^{2^{2}}", sp.Integer(16)),
    ("\\frac{3 e^{\\sqrt{x}}}{2 \\sqrt{x}}", 3 * sp.exp(sp.sqrt(X)) / (2 * sp.sqrt(X))),
    ("-2^{2}", sp.Integer(-4)),
    ("1 - \\frac{1}{x}", 1 - 1 / X),
    ("x - 2 - 3", X - 5),
    ("x / 2 x", X / 2 * X),
]

REJECTED_CASES = [
    "\\int x \\, dx",
    "\\log x",
    "\\sqrt[3]{x}",
    "x_1",
    "\\frac{1}{",
    "x^{99}",
    "x^{\\pi}",
    "__import__('os')",
    "\\input{file}",
    "\\lim_{x \\to 1} x",
    "\\sum x",
    "\\infty",
    "$x$",
    "x%",
    "x#",
    "x&x",
    "x!",
    "x**2",
    "1.",
    ".5",
    "+x",
    "",
    "   ",
    "()",
    "(x",
    "x)",
    "2 3",
    "x^2^3",
    "x^-1",
    "\\sin x^{2}",
    "\\sin 2x",
    "\\ln 2x",
    "\\cos x y",
    "\\sin 2\\pi",
    "\\sin^{2} 2x",
    "\\sin^{-1}{x}",
    "y = x",
    "i",
    "t",
    "\\operatorname{sech}{x}",
    "\\left[x\\right]",
    "||x||",
    "x \\to 1",
    "\\cdot",
    "X",
    "f(x)",
    "\\frac12\\frac12\\frac12\\sqrt{x}\\frac12\\frac12\\frac12\\sqrt[3]{x}",
    "1+" * 2500 + "1",
    "{" * 40 + "x" + "}" * 40,
    "(" * 40 + "x" + ")" * 40,
    "x^{" * 25 + "x" + "}" * 25,
    "\\sin" * 300 + "x",
    "- " * 300 + "x",
]


def _x_cases():
    return [pytest.param(text, expected, id=text) for text, expected in CONSTRUCT_CASES]


@pytest.mark.parametrize(("latex", "expected"), _x_cases())
def test_supported_construct_reads_to_expected_sympy(latex, expected):
    assert read_latex(latex) == expected


@pytest.mark.parametrize(("latex", "expected"), BANK_EXAMPLE_CASES)
def test_bank_answer_example_reads_to_expected_sympy(latex, expected):
    assert read_latex(latex) == expected


@pytest.mark.parametrize(("latex", "expected"), PRECEDENCE_CASES)
def test_precedence_matches_standard_reading(latex, expected):
    assert read_latex(latex) == expected


@pytest.mark.parametrize("latex", REJECTED_CASES)
def test_rejected_input_raises_quickly(latex):
    started = time.perf_counter()
    with pytest.raises(BoundaryError):
        read_latex(latex)
    assert time.perf_counter() - started < HOSTILE_TIME_LIMIT_SECONDS


@pytest.mark.parametrize("latex", REJECTED_CASES)
def test_rejected_input_gives_short_message(latex):
    with pytest.raises(BoundaryError) as info:
        read_latex(latex)
    assert str(info.value)
    assert len(str(info.value)) <= 120


def test_rejection_returns_no_partial_result():
    with pytest.raises(BoundaryError):
        read_latex("2 x + \\frac{1}{")


def test_length_cap_counts_raw_latex_before_work():
    assert read_latex("1+" * 99 + "1") == sp.Integer(100)
    with pytest.raises(BoundaryError):
        latex_to_text("1+" * 500 + "1")


def test_empty_and_non_text_inputs_are_rejected():
    with pytest.raises(BoundaryError):
        read_latex("")
    with pytest.raises(BoundaryError):
        latex_to_text(None)


def test_sqrt_bare_argument_is_not_ambiguous():
    assert latex_to_text("\\sqrt x y") == "sqrt(x)*y"


def test_translation_is_plain_grammar_text():
    assert latex_to_text("- \\frac{1}{8}") == "-(1/8)"
    assert latex_to_text("3 e^{\\sqrt{x}}") == "3*exp(sqrt(x))"
    assert latex_to_text("\\sin^{3}{\\left(x \\right)}") == "sin(x)^(3)"


def test_module_source_avoids_eval_style_calls():
    source = MODULE_PATH.read_text(encoding="utf-8")
    for word in FORBIDDEN_SOURCE_WORDS:
        assert word not in source
