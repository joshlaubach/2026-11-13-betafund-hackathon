"""Tests for core/input_boundary.py, the restricted reader for outside math text."""

import dataclasses
import sys
import time
from fractions import Fraction
from pathlib import Path

import pytest
import sympy as sp

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core.input_boundary import (  # noqa: E402
    BoundaryError,
    Bin,
    Var,
    Num,
    parse,
    parse_tree,
    to_sympy,
)

MODULE_PATH = REPO_ROOT / "core" / "input_boundary.py"
HOSTILE_TIME_LIMIT_SECONDS = 0.5
MAX_MESSAGE_LENGTH = 80
FORBIDDEN_SOURCE_WORDS = ("eval(", "exec(", "compile(", "sympify", "parse_expr")

X = sp.Symbol("x", real=True)
T = sp.Symbol("t", real=True)

VALID_CASES = [
    ("2*x*cos(x^2)", 2 * X * sp.cos(X**2)),
    ("(5*x+3)^3", (5 * X + 3) ** 3),
    ("sqrt(x^4)", sp.sqrt(X**4)),
    ("x^(1/2)", sp.sqrt(X)),
    ("exp(-x^2)", sp.exp(-(X**2))),
    ("log(x)", sp.log(X)),
    ("sin(x)^2", sp.sin(X) ** 2),
    ("pi/4", sp.pi / 4),
    ("e^2", sp.E**2),
    ("-x", -X),
    ("3.5*x", sp.Rational(7, 2) * X),
    ("abs(x-1)", sp.Abs(X - 1)),
    ("atan(x)", sp.atan(X)),
    ("sec(x)*tan(x)", sp.sec(X) * sp.tan(X)),
    ("(x+1)/(x-1)", (X + 1) / (X - 1)),
    ("x", X),
    ("2*x", 2 * X),
    ("x^2", X**2),
    ("x^-3", X**-3),
    ("x^(-3)", X**-3),
    ("x^(3/2)", X ** sp.Rational(3, 2)),
    ("x^(-1/2)", X ** sp.Rational(-1, 2)),
    ("x^(2^3)", X**8),
    ("x^0", sp.Integer(1)),
    ("x^20", X**20),
    ("1/x", 1 / X),
    ("x-1", X - 1),
    ("2.5*x^2", sp.Rational(5, 2) * X**2),
    ("sin(x)", sp.sin(X)),
    ("cos(x)", sp.cos(X)),
    ("tan(x)", sp.tan(X)),
    ("cot(x)", sp.cot(X)),
    ("csc(x)", sp.csc(X)),
    ("asin(x)", sp.asin(X)),
    ("acos(x)", sp.acos(X)),
    ("sinh(x)", sp.sinh(X)),
    ("cosh(x)", sp.cosh(X)),
    ("tanh(x)", sp.tanh(X)),
    ("sqrt(x)", sp.sqrt(X)),
    ("(x)", X),
    ("  x  +  1 ", X + 1),
]

HOSTILE_CASES = [
    "__import__('os').system('echo hi')",
    "x.__class__",
    "lambda: 1",
    "9^(9^9)",
    "9^9^9^9",
    "2**3",
    "x^21",
    "x^x",
    "x^(1/0)",
    "1e5",
    "x[0]",
    '"x"',
    "x+" * 100 + "x",
    "(" * 21 + "x" + ")" * 21,
    "sin(x",
    "sin(x))",
    "foo(x)",
    "Integral(x)",
    "x;y",
    "x\x00",
    "x²",
    "α*x",
    "",
    "   ",
]

EXTRA_REJECTS = [
    "2x",
    "2(x+1)",
    "2 x",
    "x(x+1)",
    "x2",
    "x^2^3",
    "sin x",
    "()",
    "+x",
    "x^(sin(1))",
    "2^-x",
    "x)",
    "(x",
    "x y",
    "1.",
    ".5",
    "X",
    "pi(x)",
    "e(x)",
    "x^(2^(1/2))",
    "x^(-21)",
    "t",
]


@pytest.mark.parametrize(("text", "expected"), VALID_CASES)
def test_valid_input_parses_to_expected_sympy(text, expected):
    assert parse(text) == expected


def test_parse_renders_expected_text():
    assert str(parse("2*x*cos(x^2)")) == "2*x*cos(x**2)"


@pytest.mark.parametrize("text", HOSTILE_CASES)
def test_hostile_input_is_rejected_quickly(text):
    started = time.perf_counter()
    with pytest.raises(BoundaryError):
        parse(text)
    assert time.perf_counter() - started < HOSTILE_TIME_LIMIT_SECONDS


@pytest.mark.parametrize("text", HOSTILE_CASES)
def test_hostile_rejection_message_is_short(text):
    with pytest.raises(BoundaryError) as info:
        parse(text)
    message = str(info.value)
    assert message
    assert len(message) <= MAX_MESSAGE_LENGTH


@pytest.mark.parametrize("text", EXTRA_REJECTS)
def test_extra_invalid_input_is_rejected(text):
    with pytest.raises(BoundaryError):
        parse(text)


def test_explicit_multiplication_is_accepted():
    assert parse("2*x") == 2 * X


def test_length_limit_is_inclusive():
    assert parse("1" * 200) == sp.Integer(int("1" * 200))
    with pytest.raises(BoundaryError):
        parse("1" * 201)


def test_depth_limit_is_inclusive():
    assert parse("(" * 20 + "x" + ")" * 20) == X


def test_exponent_limit_is_inclusive():
    assert parse("x^20") == X**20
    assert parse("x^-20") == X**-20


def test_declared_variable_other_than_default_is_accepted():
    assert parse("t^2", variables=("t",)) == T**2


def test_parse_tree_exposes_division_and_denominator():
    tree = parse_tree("(x+1)/(x-1)")
    assert isinstance(tree, Bin)
    assert tree.op == "/"
    assert tree.left == Bin("+", Var("x"), Num(Fraction(1)))
    assert tree.right == Bin("-", Var("x"), Num(Fraction(1)))


def _children(node):
    if isinstance(node, Bin):
        return (node.left, node.right)
    if hasattr(node, "operand"):
        return (node.operand,)
    if hasattr(node, "arg"):
        return (node.arg,)
    return ()


def _walk(node):
    yield node
    for child in _children(node):
        yield from _walk(child)


def _denominators(tree):
    return [n.right for n in _walk(tree) if isinstance(n, Bin) and n.op == "/"]


def test_walking_tree_finds_every_denominator():
    tree = parse_tree("1/(x-1) + x/(x^2+1)")
    assert _denominators(tree) == [
        Bin("-", Var("x"), Num(Fraction(1))),
        Bin("+", Bin("^", Var("x"), Num(Fraction(2))), Num(Fraction(1))),
    ]


def test_tree_nodes_are_frozen():
    tree = parse_tree("x+1")
    with pytest.raises(dataclasses.FrozenInstanceError):
        tree.op = "-"


def test_to_sympy_requires_real_symbols():
    with pytest.raises(BoundaryError):
        to_sympy(parse_tree("x"), {"x": sp.Symbol("x")})


def test_module_source_avoids_eval_style_calls():
    source = MODULE_PATH.read_text(encoding="utf-8")
    for word in FORBIDDEN_SOURCE_WORDS:
        assert word not in source


def test_inputs_are_not_mutated():
    variables = ["x", "t"]
    snapshot = list(variables)
    parse_tree("x+t", variables)
    parse("x+t", variables)
    assert variables == snapshot
    assert isinstance(variables, list)
