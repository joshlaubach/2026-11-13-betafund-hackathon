"""Read LaTeX math fragments by translating them into the plain text grammar.

The LaTeX is tokenized and translated into the text grammar that
core.input_boundary accepts. Only that text is handed to input_boundary.parse,
so every restriction of the plain grammar still applies. Anything the
translator does not understand raises BoundaryError; nothing is guessed.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import NamedTuple

import sympy as sp

from core.input_boundary import MAX_DEPTH, BoundaryError, parse

MAX_LATEX_LENGTH = 1000
DEFAULT_VARIABLES = ("x",)

_NUMBER = "number"
_LETTER = "letter"
_COMMAND = "command"
_ROOT = "root"
_OP = "op"
_LPAREN = "("
_RPAREN = ")"
_LBRACE = "{"
_RBRACE = "}"
_BAR = "|"

_DIGITS = frozenset("0123456789")
_LETTERS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")
_BLANKS = frozenset(" \t\r\n")
_SPACING_COMMAND_CHARS = frozenset(",;! ")
_IGNORED_COMMANDS = frozenset({"displaystyle"})
_OPERATOR_COMMANDS = {"cdot": "*", "times": "*"}
_LEFT_DELIMITERS = frozenset({"(", "|"})
_RIGHT_DELIMITERS = frozenset({")", "|"})
_FUNCTION_NAMES = {
    "sin": "sin",
    "cos": "cos",
    "tan": "tan",
    "sec": "sec",
    "csc": "csc",
    "cot": "cot",
    "sinh": "sinh",
    "cosh": "cosh",
    "tanh": "tanh",
    "arcsin": "asin",
    "arccos": "acos",
    "arctan": "atan",
    "ln": "log",
    "exp": "exp",
}
_FRACTION_COMMANDS = frozenset({"frac", "dfrac"})
_FACTOR_COMMANDS = frozenset(_FUNCTION_NAMES) | _FRACTION_COMMANDS | {"sqrt", "pi"}
_FACTOR_KINDS = frozenset({_NUMBER, _LETTER, _LPAREN, _LBRACE, _ROOT})
_BARE_ARGUMENT_BREAKS = frozenset({_NUMBER, _LETTER, _COMMAND, _LPAREN, _LBRACE, _ROOT})
MIN_ROOT_INDEX = 2
MAX_ROOT_INDEX = 20
SQUARE_ROOT_INDEX = 2
_MAX_ROOT_INDEX_DIGITS = len(str(MAX_ROOT_INDEX))

# Precedence of a translated piece: higher binds tighter.
_ADD = 0
_MUL = 1
_NEG = 2
_POW = 3
_ATOM = 4


class _Token(NamedTuple):
    kind: str
    text: str


class _Piece(NamedTuple):
    """A translated fragment of plain grammar text and how tightly it binds."""

    text: str
    prec: int
    number: bool = False


_PLAIN_TOKENS = {
    "+": _Token(_OP, "+"),
    "-": _Token(_OP, "-"),
    "*": _Token(_OP, "*"),
    "/": _Token(_OP, "/"),
    "^": _Token(_OP, "^"),
    "(": _Token(_LPAREN, "("),
    ")": _Token(_RPAREN, ")"),
    "{": _Token(_LBRACE, "{"),
    "}": _Token(_RBRACE, "}"),
    "|": _Token(_BAR, "|"),
}


def _run_end(text: str, start: int, charset: frozenset[str]) -> int:
    end = start
    while end < len(text) and text[end] in charset:
        end += 1
    return end


def _skip_blanks(text: str, index: int) -> int:
    while index < len(text) and text[index] in _BLANKS:
        index += 1
    return index


def _unsupported_command_message(name: str) -> str:
    if name == "log":
        return "\\log is not supported (its base is unclear); use \\ln"
    return f"LaTeX command \\{name} is not supported"


def _scan_number(latex: str, start: int) -> tuple[_Token, int]:
    end = _run_end(latex, start, _DIGITS)
    if end < len(latex) and latex[end] == ".":
        fraction_end = _run_end(latex, end + 1, _DIGITS)
        if fraction_end == end + 1:
            raise BoundaryError("decimal point must be followed by digits")
        end = fraction_end
    return _Token(_NUMBER, latex[start:end]), end


def _scan_plain(latex: str, start: int) -> tuple[_Token | None, int]:
    char = latex[start]
    if char in _BLANKS:
        return None, start + 1
    if char in _DIGITS:
        return _scan_number(latex, start)
    if char in _LETTERS:
        return _Token(_LETTER, char), start + 1
    if latex.startswith("**", start):
        raise BoundaryError("'**' is not allowed; use ^ for powers")
    if char in _PLAIN_TOKENS:
        return _PLAIN_TOKENS[char], start + 1
    raise BoundaryError(f"character {char!r} is not allowed in LaTeX math")


def _scan_delimiter(latex: str, end: int, name: str) -> tuple[_Token, int]:
    position = _skip_blanks(latex, end)
    delimiter = latex[position : position + 1]
    allowed = _LEFT_DELIMITERS if name == "left" else _RIGHT_DELIMITERS
    if delimiter not in allowed:
        raise BoundaryError(f"\\{name} must be followed by a parenthesis or |")
    return _PLAIN_TOKENS[delimiter], position + 1


def _scan_root_index(latex: str, open_bracket: int) -> tuple[_Token, int]:
    """Read the index of \\sqrt[n]: plain decimal digits, 2 to 20, in one pair of brackets."""
    start = open_bracket + 1
    end = _run_end(latex, start, _DIGITS)
    if end == start or end >= len(latex) or latex[end] != "]":
        raise BoundaryError("root index must be a whole number in square brackets")
    if end - start > _MAX_ROOT_INDEX_DIGITS:
        raise BoundaryError(f"root index must be from {MIN_ROOT_INDEX} to {MAX_ROOT_INDEX}")
    index = int(latex[start:end])
    if not MIN_ROOT_INDEX <= index <= MAX_ROOT_INDEX:
        raise BoundaryError(f"root index must be from {MIN_ROOT_INDEX} to {MAX_ROOT_INDEX}")
    return _Token(_ROOT, str(index)), end + 1


def _scan_command(latex: str, start: int) -> tuple[_Token | None, int]:
    end = _run_end(latex, start + 1, _LETTERS)
    name = latex[start + 1 : end]
    if not name:
        following = latex[start + 1 : start + 2]
        if following in _SPACING_COMMAND_CHARS:
            return None, start + 2
        raise BoundaryError("LaTeX backslash command is not supported")
    if name in ("left", "right"):
        return _scan_delimiter(latex, end, name)
    if name == "sqrt" and latex[end : end + 1] == "[":
        return _scan_root_index(latex, end)
    if name in _IGNORED_COMMANDS:
        return None, end
    if name in _OPERATOR_COMMANDS:
        return _Token(_OP, _OPERATOR_COMMANDS[name]), end
    if name in _FACTOR_COMMANDS:
        return _Token(_COMMAND, name), end
    raise BoundaryError(_unsupported_command_message(name))


def _tokenize(latex: str) -> tuple[_Token, ...]:
    tokens: list[_Token] = []
    index = 0
    while index < len(latex):
        if latex[index] == "\\":
            token, index = _scan_command(latex, index)
        else:
            token, index = _scan_plain(latex, index)
        if token is not None:
            tokens.append(token)
    return tuple(tokens)


def _descend(depth: int) -> int:
    if depth + 1 > MAX_DEPTH:
        raise BoundaryError("LaTeX is nested too deeply")
    return depth + 1


def _leaf(token: _Token) -> _Piece:
    return _Piece(token.text, _ATOM, number=token.kind == _NUMBER)


def _is_single_symbol(token: _Token) -> bool:
    if token.kind == _NUMBER:
        return len(token.text) == 1
    return token.kind == _LETTER or (token.kind == _COMMAND and token.text == "pi")


def _as_atom(piece: _Piece) -> _Piece:
    if piece.prec == _ATOM:
        return piece
    return _Piece(f"({piece.text})", _ATOM)


def _negate(operand: _Piece) -> _Piece:
    text = operand.text if operand.prec >= _POW else f"({operand.text})"
    return _Piece(f"-{text}", _NEG)


def _sum(left: _Piece, op: str, right: _Piece) -> _Piece:
    right_text = f"({right.text})" if right.prec <= _ADD else right.text
    return _Piece(f"{left.text}{op}{right_text}", _ADD)


def _product(left: _Piece, op: str, right: _Piece) -> _Piece:
    left_text = left.text if left.prec >= _MUL else f"({left.text})"
    right_text = right.text if right.prec > _MUL else f"({right.text})"
    return _Piece(f"{left_text}{op}{right_text}", _MUL)


def _power_of(base: _Piece, exponent: _Piece) -> _Piece:
    if base.text == "e":
        return _Piece(f"exp({exponent.text})", _ATOM)
    base_text = base.text if base.prec == _ATOM else f"({base.text})"
    return _Piece(f"{base_text}^({exponent.text})", _POW)


class _Translator:
    """Recursive-descent translator from LaTeX tokens to plain grammar text.

    Nesting depth is passed explicitly through _descend and capped at MAX_DEPTH.
    Loops handle sequences such as sums and implicit products without recursion.
    """

    def __init__(self, tokens: tuple[_Token, ...]) -> None:
        self._tokens = tokens
        self._pos = 0
        self._open_bars = 0

    def translate(self) -> str:
        piece = self._expr(0)
        if self._peek() is not None:
            raise BoundaryError("unexpected token or unbalanced delimiter")
        return piece.text

    def _peek(self) -> _Token | None:
        return self._tokens[self._pos] if self._pos < len(self._tokens) else None

    def _peek_kind(self) -> str:
        token = self._peek()
        return token.kind if token is not None else ""

    def _peek_op(self) -> str:
        token = self._peek()
        return token.text if token is not None and token.kind == _OP else ""

    def _take(self) -> _Token:
        token = self._peek()
        if token is None:
            raise BoundaryError("unexpected end of LaTeX")
        self._pos += 1
        return token

    def _expect(self, kind: str) -> None:
        if self._peek_kind() != kind:
            raise BoundaryError("unbalanced braces, parentheses, or bars")
        self._pos += 1

    def _starts_factor(self) -> bool:
        token = self._peek()
        if token is None:
            return False
        if token.kind == _BAR:
            return self._open_bars == 0
        if token.kind == _COMMAND:
            return token.text in _FACTOR_COMMANDS
        return token.kind in _FACTOR_KINDS

    def _expr(self, depth: int) -> _Piece:
        piece = self._term(depth)
        while self._peek_op() in ("+", "-"):
            op = self._take().text
            piece = _sum(piece, op, self._term(depth))
        return piece

    def _term(self, depth: int) -> _Piece:
        piece = self._unary(depth)
        previous = piece
        while True:
            op = self._peek_op()
            if op in ("*", "/"):
                self._take()
            elif self._starts_factor():
                if previous.number and self._peek_kind() == _NUMBER:
                    raise BoundaryError("adjacent numbers are ambiguous")
                op = "*"
            else:
                return piece
            previous = self._unary(depth)
            piece = _product(piece, op, previous)

    def _unary(self, depth: int) -> _Piece:
        if self._peek_op() == "-":
            self._take()
            return _negate(self._unary(_descend(depth)))
        return self._power(depth)

    def _power(self, depth: int) -> _Piece:
        base = self._atom(depth)
        if self._peek_op() != "^":
            return base
        self._take()
        return _power_of(base, self._exponent(depth))

    def _exponent(self, depth: int) -> _Piece:
        if self._peek_kind() == _LBRACE:
            self._take()
            inner = self._expr(_descend(depth))
            self._expect(_RBRACE)
            return inner
        token = self._peek()
        if token is not None and _is_single_symbol(token):
            self._take()
            return _leaf(token)
        raise BoundaryError("superscript needs braces unless it is one symbol")

    def _atom(self, depth: int) -> _Piece:
        token = self._peek()
        if token is None:
            raise BoundaryError("unexpected end of LaTeX")
        if token.kind in (_NUMBER, _LETTER):
            self._take()
            return _leaf(token)
        if token.kind in (_LPAREN, _LBRACE):
            return self._group(depth)
        if token.kind == _BAR:
            return self._absolute(depth)
        if token.kind == _COMMAND:
            self._take()
            return self._command(token.text, depth)
        if token.kind == _ROOT:
            self._take()
            return self._root(int(token.text), depth)
        raise BoundaryError("unexpected token in LaTeX")

    def _root(self, index: int, depth: int) -> _Piece:
        """Read \\sqrt[n]{a}. A negative radicand reads as the principal complex root, so the checker skips such points as non-real."""
        radicand = self._root_radicand(depth)
        if index == SQUARE_ROOT_INDEX:
            return _Piece(f"sqrt({radicand.text})", _ATOM)
        return _Piece(f"{_as_atom(radicand).text}^(1/{index})", _POW)

    def _root_radicand(self, depth: int) -> _Piece:
        token = self._peek()
        if token is None:
            raise BoundaryError("missing root argument")
        if token.kind == _LBRACE:
            return self._group(depth)
        if _is_single_symbol(token):
            self._take()
            return _leaf(token)
        raise BoundaryError("root argument must be braced or a single symbol")

    def _group(self, depth: int) -> _Piece:
        closer = _RPAREN if self._take().kind == _LPAREN else _RBRACE
        inner = self._expr(_descend(depth))
        self._expect(closer)
        return _as_atom(inner)

    def _absolute(self, depth: int) -> _Piece:
        if self._open_bars:
            raise BoundaryError("nested absolute value bars are not supported")
        self._take()
        self._open_bars += 1
        inner = self._expr(_descend(depth))
        self._expect(_BAR)
        self._open_bars -= 1
        return _Piece(f"abs({inner.text})", _ATOM)

    def _command(self, name: str, depth: int) -> _Piece:
        if name in _FRACTION_COMMANDS:
            numerator = self._argument(depth)
            denominator = self._argument(depth)
            return _product(numerator, "/", denominator)
        if name == "sqrt":
            return _Piece(f"sqrt({self._argument(depth).text})", _ATOM)
        if name == "pi":
            return _Piece("pi", _ATOM)
        return self._function(_FUNCTION_NAMES[name], depth)

    def _argument(self, depth: int) -> _Piece:
        token = self._peek()
        if token is None:
            raise BoundaryError("missing argument")
        if token.kind in (_LBRACE, _LPAREN):
            return self._group(depth)
        if token.kind == _COMMAND and token.text in _FUNCTION_NAMES:
            self._take()
            return self._function(_FUNCTION_NAMES[token.text], _descend(depth))
        if _is_single_symbol(token):
            self._take()
            return _leaf(token)
        raise BoundaryError("argument must be braced, parenthesized, or one symbol")

    def _function(self, function: str, depth: int) -> _Piece:
        power = None
        if self._peek_op() == "^":
            self._take()
            power = self._exponent(depth)
            if power.prec == _NEG:
                raise BoundaryError("negative power before a function is ambiguous")
        delimited = self._peek_kind() in (_LBRACE, _LPAREN)
        argument = self._argument(depth)
        if not delimited and self._peek_kind() in _BARE_ARGUMENT_BREAKS:
            raise BoundaryError("function argument is ambiguous; use braces or parentheses")
        if self._peek_op() == "^" and (power is not None or not delimited):
            raise BoundaryError("power after a function argument is ambiguous")
        call = _Piece(f"{function}({argument.text})", _ATOM)
        if power is None:
            return call
        return _power_of(call, power)


def latex_to_text(latex: str) -> str:
    """Translate a LaTeX math fragment into the plain text grammar.

    Raises BoundaryError for anything the translator does not understand.
    """
    if not isinstance(latex, str):
        raise BoundaryError("LaTeX must be text")
    if len(latex) > MAX_LATEX_LENGTH:
        raise BoundaryError(f"LaTeX is longer than {MAX_LATEX_LENGTH} characters")
    tokens = _tokenize(latex)
    if not tokens:
        raise BoundaryError("empty LaTeX")
    return _Translator(tokens).translate()


def read_latex(latex: str, variables: Sequence[str] = DEFAULT_VARIABLES) -> sp.Basic:
    """Read a LaTeX math fragment as a SymPy expression via the plain grammar."""
    return parse(latex_to_text(latex), variables)
