"""Parse model-produced math strings into SymPy without exposing eval.

parse_expr calls eval internally, so safety comes from rejecting the input
before it reaches the parser: a character whitelist, an identifier allowlist,
and size caps. Callers must still run this inside the sandbox, because a valid
expression such as 9^9^9^9 can hang SymPy.
"""
import re

import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication,
    parse_expr,
    standard_transformations,
)

MAX_LEN = 2000
MAX_DEPTH = 40
MAX_DIGITS = 60
MAX_OPS = 600

FUNCS = {
    name: getattr(sp, name)
    for name in (
        "sin cos tan sec csc cot asin acos atan acot asec acsc atan2 "
        "sinh cosh tanh sech csch coth asinh acosh atanh exp log sqrt cbrt root Abs "
        "factorial binomial floor ceiling sign re im conjugate arg "
        "Integral Derivative Limit Sum Product Matrix Eq Ne Lt Le Gt Ge "
        "Interval FiniteSet Union Intersection Complement Tuple Piecewise "
        "Rational Min Max"
    ).split()
}
FUNCS |= {"Matrix": sp.ImmutableMatrix, "ln": sp.log, "abs": sp.Abs, "arcsin": sp.asin, "arccos": sp.acos, "arctan": sp.atan}
CONSTS = {"pi": sp.pi, "E": sp.E, "I": sp.I, "oo": sp.oo, "e": sp.E, "inf": sp.oo,
          "EmptySet": sp.S.EmptySet, "Reals": sp.S.Reals, "true": sp.true, "false": sp.false}
GREEK = ("alpha beta gamma delta epsilon zeta eta theta iota kappa lamda mu nu xi "
         "rho sigma tau phi chi psi omega").split()
SYMBOLS = {g: sp.Symbol(g) for g in GREEK}
ALLOWED_NAMES = FUNCS.keys() | CONSTS.keys() | SYMBOLS.keys()

# Names parse_expr's transformations emit; they never come from the input text.
_GLOBALS = {"__builtins__": {}, "Symbol": sp.Symbol, "Integer": sp.Integer,
            "Float": sp.Float, "Rational": sp.Rational, "Function": sp.Function}
_TRANSFORMS = standard_transformations + (implicit_multiplication, convert_xor)

_CHARS = re.compile(r"[A-Za-z0-9\s+\-*/^(),.\[\]=<>!]*")
_IDENT = re.compile(r"[A-Za-z]+[0-9]*")
_BAD_DOT = re.compile(r"(?<![0-9])\.|\.(?![0-9])")
_DIGITS = re.compile(r"[0-9]+")


class ParseError(ValueError):
    pass


def check_text(s: str) -> None:
    """Reject anything that is not plain math notation."""
    if len(s) > MAX_LEN:
        raise ParseError("expression too long")
    if not _CHARS.fullmatch(s):
        raise ParseError("disallowed character")
    if _BAD_DOT.search(s):
        raise ParseError("'.' only allowed in decimals")
    if any(len(d) > MAX_DIGITS for d in _DIGITS.findall(s)):
        raise ParseError("number literal too long")
    depth = 0
    for ch in s:
        depth += ch in "(["
        depth -= ch in ")]"
        if depth > MAX_DEPTH:
            raise ParseError("nesting too deep")
        if depth < 0:
            raise ParseError("unbalanced brackets")
    if depth:
        raise ParseError("unbalanced brackets")
    for name in _IDENT.findall(s):
        letters = name.rstrip("0123456789")
        if len(letters) > 1 and name not in ALLOWED_NAMES:
            raise ParseError(f"unknown name '{name}'")


def safe_parse(s: str, symbols: dict[str, sp.Symbol] | None = None) -> sp.Basic:
    s = s.strip()
    if not s:
        raise ParseError("empty expression")
    check_text(s)
    local = {**SYMBOLS, **FUNCS, **CONSTS, **(symbols or {})}
    try:
        expr = parse_expr(s, local_dict=local, global_dict=dict(_GLOBALS),
                          transformations=_TRANSFORMS)
    except Exception as e:
        raise ParseError(f"could not parse: {type(e).__name__}") from None
    if not isinstance(expr, sp.Basic):
        raise ParseError("not a SymPy object")
    if sp.count_ops(expr) > MAX_OPS:
        raise ParseError("expression too large")
    return expr
