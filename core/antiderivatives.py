"""Indefinite integrals graded by SymPy: "Find \\int g(x) dx".

SymPy integrates g and fixes the logarithms to ln|x| so the antiderivative is real on both sides of 0.
The student's answer is then checked the other way round: SymPy differentiates it and compares the
derivative with g at sample points on both sides of 0 where g is defined. An answer that is real only on
one side (for example 3 ln x) agrees only for x > 0 and is unsure. A correct derivative with no trailing
"+ C" is unsure. Nothing here is marked from an AI answer.
"""

from __future__ import annotations

import math
import re
from typing import NamedTuple, Optional

import sympy as sp

from core.definitions import ASK_VERBS
from core.derivative_checker import (
    ABS_FLOOR,
    MIN_COMPARABLE_POINTS,
    REL_TOLERANCE,
    SAMPLE_POINTS,
    TRAILING_CONSTANT,
    X,
    strip_constant,
)
from core.equations import SYMPY_METHOD, ask_text, read_or_none
from core.solvers import NEGATIVE_SAMPLE_POINTS, Mark

MATCH = "match"
MISMATCH = "mismatch"
DOMAIN = "domain"
UNKNOWN = "unknown"
SIDES = (("x>0", SAMPLE_POINTS), ("x<0", NEGATIVE_SAMPLE_POINTS))
AGREES_ON = {"x<0": "x>0", "x>0": "x<0"}
DOMAIN_TEXT = "Agrees only for {side}; the answer should be {answer} + C."
MISSING_CONSTANT_TEXT = (
    "SymPy's derivative of the answer matches the integrand {integrand}, but the answer has no "
    "+ C: add + C."
)
MISMATCH_TEXT = (
    "SymPy's derivative of the answer {shown} is {slope} at x = {point}, but the integrand is "
    "{target}, so the answer is wrong. SymPy's antiderivative is {answer} + C."
)
CORRECT_TEXT = (
    "SymPy differentiated the answer {shown} and it matches the integrand {integrand} at {count} "
    "sample points where the integrand is defined, so the antiderivative is correct."
)
_INTEGRAL_ASK = re.compile(ASK_VERBS + r" \\int(?!_)\s*(.+?)\s*(?:\\[,;!]\s*)?d(x)")
_LN_BARS = re.compile(r"\\ln\s*\|([^|]+)\|")
_CONSTANT_TAIL = re.compile(r"\+\s*C\s*$")
_LOG_ABS = re.compile(r"log\(Abs\(([^()]*)\)\)")
_LOG = re.compile(r"log\(([^()]*)\)")
_COEFFICIENT = re.compile(r"(\d)\*(?=[A-Za-z(])")


class IntegralSpec(NamedTuple):
    """An indefinite integral: the integrand's LaTeX, in x."""

    integrand_latex: str


class Check(NamedTuple):
    """How the student's answer compares with the integrand at the sample points."""

    status: str
    matched: int = 0
    missing: tuple[str, ...] = ()
    point: float = 0.0
    target: float = 0.0
    slope: float = 0.0


def owns(spec: object) -> bool:
    return isinstance(spec, IntegralSpec)


def parse_spec(statement: str, context: str = "") -> Optional[IntegralSpec]:
    """The integral spec for "Find \\int g(x) dx" with no limits, or None for any other ask."""
    match = _INTEGRAL_ASK.fullmatch(ask_text(statement))
    if match is None:
        return None
    integrand = match.group(1).strip()
    return IntegralSpec(integrand) if read_or_none(integrand) is not None else None


# ---------------------------------------------------------------------------
# Reading and checking (the student's text is read only through latex_reader)
# ---------------------------------------------------------------------------


def readable_bars(text: str) -> str:
    """Write \\ln|x| as \\ln{|x|} so latex_reader accepts the bars as the argument."""
    unwrapped = text.replace("\\left|", "|").replace("\\right|", "|")
    return _LN_BARS.sub(r"\\ln{|\1|}", unwrapped)


def split_constant(text: str) -> tuple[str, bool]:
    """The answer without a trailing + C, and whether it had one."""
    normalized = _CONSTANT_TAIL.sub(TRAILING_CONSTANT, text.strip())
    body = strip_constant(normalized)
    return body, body != normalized


def _with_absolute_logs(expr: sp.Basic) -> sp.Basic:
    return expr.replace(
        lambda node: isinstance(node, sp.log), lambda node: sp.log(sp.Abs(node.args[0]))
    )


def _real_at(expr: sp.Basic, point: float) -> Optional[float]:
    try:
        value = complex(sp.N(expr.subs(X, sp.Float(point))))
    except (TypeError, ValueError, ArithmeticError):
        return None
    return value.real if value.imag == 0 and math.isfinite(value.real) else None


def _close(left: float, right: float) -> bool:
    scale = max(abs(left), abs(right))
    return abs(left - right) <= REL_TOLERANCE * scale + ABS_FLOOR


def _check(integrand: sp.Basic, antiderivative: sp.Basic) -> Check:
    """Compare the derivative of the antiderivative with the integrand, point by point, on both sides of 0."""
    derivative = sp.diff(antiderivative, X)
    matched = 0
    missing: list[str] = []
    for side, points in SIDES:
        side_missing = False
        for point in points:
            target = _real_at(integrand, point)
            if target is None:
                continue
            value = _real_at(antiderivative, point)
            if value is None:
                side_missing = True
                continue
            slope = _real_at(derivative, point)
            if slope is None:
                return Check(UNKNOWN)
            if not _close(slope, target):
                return Check(MISMATCH, point=point, target=target, slope=slope)
            matched += 1
        if side_missing:
            missing.append(side)
    if matched < MIN_COMPARABLE_POINTS or len(missing) == len(SIDES):
        return Check(UNKNOWN)
    if missing:
        return Check(DOMAIN, matched=matched, missing=tuple(missing))
    return Check(MATCH, matched=matched)


# ---------------------------------------------------------------------------
# SymPy computes the reference (runs in the child process)
# ---------------------------------------------------------------------------


def compute_spec(spec: object) -> Optional[sp.Basic]:
    """SymPy's antiderivative, with ln|x| for logarithms, when SymPy's answer checks out; else None."""
    if not isinstance(spec, IntegralSpec):
        return None
    integrand = read_or_none(spec.integrand_latex)
    if integrand is None:
        return None
    antiderivative = sp.integrate(integrand, X)
    if antiderivative.has(sp.Integral):
        return None
    value = _with_absolute_logs(antiderivative)
    return value if _check(integrand, value).status == MATCH else None


# ---------------------------------------------------------------------------
# Plain text for the explanations
# ---------------------------------------------------------------------------


def plain_antiderivative(value: sp.Basic) -> str:
    """The antiderivative in plain words, such as "3 ln|x|", without the + C."""
    text = sp.sstr(value)
    text = _LOG_ABS.sub(r"ln|\1|", text)
    text = _LOG.sub(r"ln(\1)", text)
    text = _COEFFICIENT.sub(r"\1 ", text)
    return text.replace("**", "^").replace("*", " ")


# ---------------------------------------------------------------------------
# Marks
# ---------------------------------------------------------------------------


def _domain_mark(check: Check, value: sp.Basic) -> Mark:
    side = AGREES_ON[check.missing[0]]
    answer = plain_antiderivative(value)
    explanation = DOMAIN_TEXT.format(side=side, answer=answer)
    return Mark("unsure", SYMPY_METHOD, explanation, f"{sp.latex(value)} + C")


def _mismatch_mark(check: Check, value: sp.Basic, shown: str) -> Mark:
    explanation = MISMATCH_TEXT.format(
        shown=shown,
        slope=f"{check.slope:.6g}",
        point=f"{check.point:g}",
        target=f"{check.target:.6g}",
        answer=plain_antiderivative(value),
    )
    return Mark("incorrect", SYMPY_METHOD, explanation, f"{sp.latex(value)} + C")


def _match_mark(check: Check, value: sp.Basic, shown: str, integrand: sp.Basic, has_constant: bool) -> Mark:
    reference = f"{sp.latex(value)} + C"
    if not has_constant:
        text = MISSING_CONSTANT_TEXT.format(integrand=sp.latex(integrand))
        return Mark("unsure", SYMPY_METHOD, text, reference)
    text = CORRECT_TEXT.format(shown=shown, integrand=sp.latex(integrand), count=check.matched)
    return Mark("correct", SYMPY_METHOD, text, reference)


def mark_spec(spec: object, value: sp.Basic, answers: tuple[str, ...]) -> Optional[Mark]:
    """The mark for an integral ask from the student's one antiderivative, or None when it cannot be read or checked."""
    if not isinstance(spec, IntegralSpec) or len(answers) != 1 or not isinstance(value, sp.Basic):
        return None
    integrand = read_or_none(spec.integrand_latex)
    body, has_constant = split_constant(readable_bars(answers[0]))
    student = read_or_none(body)
    if integrand is None or student is None:
        return None
    check = _check(integrand, student)
    if check.status == MISMATCH:
        return _mismatch_mark(check, value, answers[0])
    if check.status == DOMAIN:
        return _domain_mark(check, value)
    if check.status == MATCH:
        return _match_mark(check, value, answers[0], integrand, has_constant)
    return None
