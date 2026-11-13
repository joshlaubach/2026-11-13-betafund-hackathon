"""Restricted reader for math text that comes from outside the app.

Outside text (an AI draft or a tutor edit) is tokenized and parsed by a small
recursive-descent parser. The input becomes an immutable tree (parse_tree), and
only that tree is turned into SymPy objects (to_sympy) using SymPy constructors.
Every rejection raises BoundaryError with a short message.
"""

from __future__ import annotations

import operator
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction

import sympy as sp

MAX_LENGTH = 200
MAX_DEPTH = 20
MAX_EXPONENT = 20
MAX_CONSTANT_BITS = 1024
DEFAULT_VARIABLES = ("x",)

FUNCTIONS: dict[str, Callable[[sp.Basic], sp.Basic]] = {
    "sin": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "sec": sp.sec,
    "csc": sp.csc,
    "cot": sp.cot,
    "asin": sp.asin,
    "acos": sp.acos,
    "atan": sp.atan,
    "sinh": sp.sinh,
    "cosh": sp.cosh,
    "tanh": sp.tanh,
    "abs": sp.Abs,
    "exp": sp.exp,
    "log": sp.log,
    "sqrt": sp.sqrt,
}
CONSTANTS: dict[str, sp.Basic] = {"pi": sp.pi, "e": sp.E}
_RESERVED = frozenset(FUNCTIONS) | frozenset(CONSTANTS)

_DIGITS = "0123456789"
_LETTERS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
_BLANKS = " \t\r\n"
_OPERATORS = "+-*/^"
_CONSTANT_OPS: dict[str, Callable[[Fraction, Fraction], Fraction]] = {
    "+": operator.add,
    "-": operator.sub,
    "*": operator.mul,
}

_NUM = "num"
_NAME = "name"
_OP = "op"
_LPAREN = "("
_RPAREN = ")"


class BoundaryError(ValueError):
    """Raised for any text the restricted grammar rejects."""


@dataclass(frozen=True)
class Num:
    value: Fraction


@dataclass(frozen=True)
class Var:
    name: str


@dataclass(frozen=True)
class Const:
    name: str


@dataclass(frozen=True)
class Neg:
    operand: Node


@dataclass(frozen=True)
class Bin:
    op: str
    left: Node
    right: Node


@dataclass(frozen=True)
class Call:
    name: str
    arg: Node


Node = Num | Var | Const | Neg | Bin | Call


@dataclass(frozen=True)
class Token:
    kind: str
    text: str


def _run_end(text: str, start: int, charset: str) -> int:
    end = start
    while end < len(text) and text[end] in charset:
        end += 1
    return end


def _scan_number(text: str, start: int) -> tuple[Token, int]:
    end = _run_end(text, start, _DIGITS)
    has_fraction = end + 1 < len(text) and text[end] == "." and text[end + 1] in _DIGITS
    if has_fraction:
        end = _run_end(text, end + 1, _DIGITS)
    return Token(_NUM, text[start:end]), end


def _scan_token(text: str, start: int) -> tuple[Token, int]:
    char = text[start]
    if char in _DIGITS:
        return _scan_number(text, start)
    if char in _LETTERS:
        end = _run_end(text, start, _LETTERS)
        return Token(_NAME, text[start:end]), end
    if text[start : start + 2] == "**":
        raise BoundaryError("'**' is not allowed; use ^ for powers")
    if char in _OPERATORS:
        return Token(_OP, char), start + 1
    if char in "()":
        kind = _LPAREN if char == "(" else _RPAREN
        return Token(kind, char), start + 1
    raise BoundaryError("character not allowed in math text")


def _tokenize(text: str) -> tuple[Token, ...]:
    tokens: list[Token] = []
    index = 0
    while index < len(text):
        if text[index] in _BLANKS:
            index += 1
            continue
        token, index = _scan_token(text, index)
        tokens.append(token)
    return tuple(tokens)


def _descend(depth: int) -> int:
    if depth + 1 > MAX_DEPTH:
        raise BoundaryError("expression is nested too deeply")
    return depth + 1


class _Parser:
    """Recursive-descent parser. Nesting depth is passed explicitly and capped."""

    def __init__(self, tokens: tuple[Token, ...], variables: frozenset[str]) -> None:
        self._tokens = tokens
        self._variables = variables
        self._pos = 0

    def parse_all(self) -> Node:
        node = self._expr(0)
        leftover = self._peek()
        if leftover is None:
            return node
        if leftover.kind == _RPAREN:
            raise BoundaryError("unbalanced parentheses")
        raise BoundaryError("unexpected token after expression")

    def _peek(self) -> Token | None:
        return self._tokens[self._pos] if self._pos < len(self._tokens) else None

    def _peek_op(self) -> str:
        token = self._peek()
        return token.text if token is not None and token.kind == _OP else ""

    def _next_is(self, kind: str) -> bool:
        token = self._peek()
        return token is not None and token.kind == kind

    def _take(self) -> Token:
        token = self._tokens[self._pos]
        self._pos += 1
        return token

    def _expect_rparen(self) -> None:
        if self._next_is(_RPAREN):
            self._pos += 1
            return
        if self._peek() is None:
            raise BoundaryError("unbalanced parentheses")
        raise BoundaryError("unexpected token")

    def _expr(self, depth: int) -> Node:
        node = self._term(depth)
        while self._peek_op() in ("+", "-"):
            op = self._take().text
            node = Bin(op, node, self._term(depth))
        return node

    def _term(self, depth: int) -> Node:
        node = self._unary(depth)
        while self._peek_op() in ("*", "/"):
            op = self._take().text
            node = Bin(op, node, self._unary(depth))
        return node

    def _unary(self, depth: int) -> Node:
        if self._peek_op() == "-":
            self._take()
            return Neg(self._unary(_descend(depth)))
        return self._power(depth)

    def _power(self, depth: int) -> Node:
        base = self._atom(depth)
        if self._peek_op() != "^":
            return base
        self._take()
        return Bin("^", base, self._exponent(depth))

    def _exponent(self, depth: int) -> Node:
        negative = self._peek_op() == "-"
        if negative:
            self._take()
        if self._next_is(_NUM):
            node: Node = Num(Fraction(self._take().text))
        elif self._next_is(_LPAREN):
            self._take()
            node = self._expr(_descend(depth))
            self._expect_rparen()
        else:
            raise BoundaryError("exponent must be a number or a parenthesized number")
        if negative:
            node = Neg(node)
        _check_exponent(node)
        return node

    def _atom(self, depth: int) -> Node:
        token = self._peek()
        if token is None:
            raise BoundaryError("unexpected end of expression")
        if token.kind == _NUM:
            self._take()
            return Num(Fraction(token.text))
        if token.kind == _NAME:
            self._take()
            return self._named(token.text, depth)
        if token.kind == _LPAREN:
            self._take()
            node = self._expr(_descend(depth))
            self._expect_rparen()
            return node
        raise BoundaryError("unexpected token")

    def _named(self, name: str, depth: int) -> Node:
        if name in self._variables:
            return Var(name)
        if name in CONSTANTS:
            return Const(name)
        if name in FUNCTIONS:
            return self._call(name, depth)
        raise BoundaryError(f"unknown name '{name}'")

    def _call(self, name: str, depth: int) -> Node:
        if not self._next_is(_LPAREN):
            raise BoundaryError(f"'{name}' must be followed by a parenthesized argument")
        self._take()
        arg = self._expr(_descend(depth))
        self._expect_rparen()
        return Call(name, arg)


def _constant_value(node: Node) -> Fraction | None:
    if isinstance(node, Num):
        return node.value
    if isinstance(node, Neg):
        inner = _constant_value(node.operand)
        return None if inner is None else -inner
    if isinstance(node, Bin):
        return _binary_constant(node)
    return None


def _binary_constant(node: Bin) -> Fraction | None:
    left = _constant_value(node.left)
    right = _constant_value(node.right)
    if left is None or right is None:
        return None
    if node.op in _CONSTANT_OPS:
        return _CONSTANT_OPS[node.op](left, right)
    if node.op == "/":
        return _divide(left, right)
    return _constant_power(left, right)


def _divide(left: Fraction, right: Fraction) -> Fraction:
    if right == 0:
        raise BoundaryError("division by zero in exponent")
    return left / right


def _bit_size(value: Fraction) -> int:
    return max(abs(value.numerator).bit_length(), value.denominator.bit_length())


def _constant_power(base: Fraction, exponent: Fraction) -> Fraction:
    if exponent.denominator != 1:
        raise BoundaryError("exponent must be an integer inside an exponent")
    power = int(exponent)
    if _bit_size(base) * abs(power) > MAX_CONSTANT_BITS:
        raise BoundaryError("exponent value is too large")
    if base == 0 and power < 0:
        raise BoundaryError("division by zero in exponent")
    return base**power


def _check_exponent(node: Node) -> None:
    value = _constant_value(node)
    if value is None:
        raise BoundaryError("exponent must be a numeric constant")
    if abs(value) > MAX_EXPONENT:
        raise BoundaryError(f"exponent must have absolute value at most {MAX_EXPONENT}")


def _is_variable_name(name: object) -> bool:
    return (
        isinstance(name, str)
        and bool(name)
        and all(char in _LETTERS for char in name)
        and name not in _RESERVED
    )


def _validate_variables(variables: Sequence[str]) -> tuple[str, ...]:
    names = tuple(variables)
    if not all(_is_variable_name(name) for name in names):
        raise BoundaryError("invalid variable name")
    if len(set(names)) != len(names):
        raise BoundaryError("duplicate variable name")
    return names


def _check_text(text: object) -> str:
    if not isinstance(text, str):
        raise BoundaryError("expression must be text")
    if len(text) > MAX_LENGTH:
        raise BoundaryError(f"expression is longer than {MAX_LENGTH} characters")
    return text


def parse_tree(text: str, variables: Sequence[str] = DEFAULT_VARIABLES) -> Node:
    """Return the immutable source tree for text, before any SymPy work."""
    checked = _check_text(text)
    names = _validate_variables(variables)
    tokens = _tokenize(checked)
    if not tokens:
        raise BoundaryError("empty expression")
    return _Parser(tokens, frozenset(names)).parse_all()


def _real_symbol(name: str, symbols: Mapping[str, sp.Symbol]) -> sp.Symbol:
    symbol = symbols.get(name)
    if symbol is None or symbol.is_real is not True:
        raise BoundaryError("variable must be a declared real symbol")
    return symbol


def _binary_to_sympy(node: Bin, symbols: Mapping[str, sp.Symbol]) -> sp.Basic:
    left = to_sympy(node.left, symbols)
    right = to_sympy(node.right, symbols)
    if node.op == "+":
        return sp.Add(left, right)
    if node.op == "-":
        return sp.Add(left, sp.Mul(sp.Integer(-1), right))
    if node.op == "*":
        return sp.Mul(left, right)
    if node.op == "/":
        return sp.Mul(left, sp.Pow(right, sp.Integer(-1)))
    return sp.Pow(left, right)


def to_sympy(node: Node, symbols: Mapping[str, sp.Symbol]) -> sp.Basic:
    """Build a SymPy expression from a parse tree using SymPy constructors only."""
    if isinstance(node, Num):
        return sp.Rational(node.value.numerator, node.value.denominator)
    if isinstance(node, Var):
        return _real_symbol(node.name, symbols)
    if isinstance(node, Const):
        return CONSTANTS[node.name]
    if isinstance(node, Neg):
        return sp.Mul(sp.Integer(-1), to_sympy(node.operand, symbols))
    if isinstance(node, Call):
        return FUNCTIONS[node.name](to_sympy(node.arg, symbols))
    return _binary_to_sympy(node, symbols)


def parse(text: str, variables: Sequence[str] = DEFAULT_VARIABLES) -> sp.Basic:
    """Parse text into a SymPy expression whose variables are declared real."""
    names = _validate_variables(variables)
    tree = parse_tree(text, names)
    symbols = {name: sp.Symbol(name, real=True) for name in names}
    return to_sympy(tree, symbols)
