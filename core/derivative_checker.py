"""Check a derivative answer by differentiating the problem with SymPy.

The problem statement, the answer key, and the evaluation point are all read
with core.latex_reader, so only the restricted grammar is turned into SymPy
objects. The checker never raises to its caller: every failure is returned in
the result dict.
"""

from __future__ import annotations

import math
import re

import sympy as sp

from core.input_boundary import BoundaryError
from core.latex_reader import read_latex

X = sp.Symbol("x", real=True)
# Two non-grid sets. A grid such as k/10 lets periodic keys (sin(10 pi x)) vanish
# at every sample, so the second set is offset from the first.
SAMPLE_POINTS = (
    0.3137, 0.7071, 1.2718, 1.9319, 2.6458,
    0.4142, 0.8660, 1.5708, 2.2361, 2.9,
)
MIN_COMPARABLE_POINTS = 6
KEY_MUST_BE_NUMBER_REASON = "the key must be a number for f'(a)"
REL_TOLERANCE = 1e-9
ABS_FLOOR = 1e-12
TRAILING_CONSTANT = "+ C"
DIGITS_IN_REASON = 6

ACCEPTED = "accepted"
WRONG_KEY = "wrong_key"
UNREADABLE_PROBLEM = "unreadable_problem"
UNREADABLE_KEY = "unreadable_key"
NO_COMPARABLE_POINTS = "no_comparable_points"

_NUMBER_TEXT = r"-?\d+(?:\.\d+)?"
_EXACT_SUFFIX = r"(?: Give an exact answer\.)?"
_AT_POINT_SHAPE = re.compile(
    r"Find \$f'\((" + _NUMBER_TEXT + r")\)\$ for \$f\(x\) = ([^$]+)\$\." + _EXACT_SUFFIX
)
_GENERAL_SHAPE = re.compile(r"Find \$f'\(x\)\$ for \$f\(x\) = ([^$]+)\$\." + _EXACT_SUFFIX)


def parse_derivative_statement(statement: str) -> dict | None:
    """Return the function and evaluation point of a derivative statement, or None."""
    if not isinstance(statement, str):
        return None
    text = statement.strip()
    at_match = _AT_POINT_SHAPE.fullmatch(text)
    if at_match is not None:
        return {"function_latex": at_match.group(2).strip(), "at": at_match.group(1)}
    general_match = _GENERAL_SHAPE.fullmatch(text)
    if general_match is not None:
        return {"function_latex": general_match.group(1).strip(), "at": None}
    return None


def strip_constant(latex: str) -> str:
    """Remove a trailing "+ C" from an answer key."""
    stripped = latex.strip()
    if stripped.endswith(TRAILING_CONSTANT):
        return stripped[: -len(TRAILING_CONSTANT)].rstrip()
    return stripped


def check_derivative(function_latex: str, key_latex: str, at: str | None = None) -> dict:
    """Differentiate the function and compare the key with the derivative.

    With at=None the comparison runs at fixed sample points in x. With at given,
    the derivative and the key are both evaluated at that point.
    """
    try:
        return _check(function_latex, key_latex, at)
    except Exception as error:  # the checker must never raise to its caller
        return _result(
            False,
            UNREADABLE_PROBLEM,
            f"the checker could not finish ({type(error).__name__})",
        )


def _check(function_latex: object, key_latex: object, at: str | None) -> dict:
    try:
        function = read_latex(function_latex)  # type: ignore[arg-type]
    except BoundaryError as error:
        return _result(False, UNREADABLE_PROBLEM, f"the problem's function could not be read: {error}")
    try:
        key = read_latex(_strip_if_text(key_latex))
    except BoundaryError as error:
        return _result(False, UNREADABLE_KEY, f"the key could not be read: {error}")
    point = None
    if at is not None:
        try:
            point = read_latex(at)
        except BoundaryError as error:
            return _result(False, UNREADABLE_PROBLEM, f"the evaluation point could not be read: {error}")
    derivative = sp.diff(function, X)
    if point is None:
        return _compare_samples(derivative, key)
    if key.free_symbols:
        return _result(False, UNREADABLE_KEY, KEY_MUST_BE_NUMBER_REASON)
    return _compare_point(derivative, key, point)


def _strip_if_text(latex: object) -> object:
    return strip_constant(latex) if isinstance(latex, str) else latex


def _compare_samples(derivative: sp.Basic, key: sp.Basic) -> dict:
    samples = []
    for point in SAMPLE_POINTS:
        true_value = _real_value(derivative.subs(X, sp.Float(point)))
        key_value = _real_value(key.subs(X, sp.Float(point)))
        if true_value is not None and key_value is not None:
            samples.append((point, true_value, key_value))
    true_text = str(derivative)
    key_text = str(key)
    if len(samples) < MIN_COMPARABLE_POINTS:
        return _result(
            False,
            NO_COMPARABLE_POINTS,
            f"only {len(samples)} sample points give finite real values on both sides; "
            f"at least {MIN_COMPARABLE_POINTS} are needed",
            true_text,
            key_text,
            samples,
        )
    for point, true_value, key_value in samples:
        if not _values_agree(true_value, key_value):
            return _result(
                False,
                WRONG_KEY,
                _mismatch_reason(f"{point:g}", true_value, key_value),
                true_text,
                key_text,
                samples,
            )
    return _result(
        True,
        ACCEPTED,
        f"the key matches the checker's derivative at {len(samples)} sample points",
        true_text,
        key_text,
        samples,
    )


def _compare_point(derivative: sp.Basic, key: sp.Basic, point: sp.Basic) -> dict:
    true_expr = derivative.subs(X, point)
    key_expr = key.subs(X, point)
    true_text = str(true_expr)
    key_text = str(key_expr)
    true_value = _real_value(true_expr)
    key_value = _real_value(key_expr)
    point_value = _real_value(point)
    label = f"{point_value:g}" if point_value is not None else str(point)
    if true_value is None or key_value is None or point_value is None:
        return _result(
            False,
            NO_COMPARABLE_POINTS,
            f"at x = {label} the derivative or the key is not a finite real number",
            true_text,
            key_text,
        )
    samples = [(point_value, true_value, key_value)]
    if not _values_agree(true_value, key_value):
        return _result(
            False,
            WRONG_KEY,
            _mismatch_reason(label, true_value, key_value),
            true_text,
            key_text,
            samples,
        )
    match = "exact" if _exactly_equal(true_expr, key_expr) else "numeric"
    return _result(
        True,
        ACCEPTED,
        f"at x = {label} the checker computes {true_value:.{DIGITS_IN_REASON}g} "
        f"and the key gives {key_value:.{DIGITS_IN_REASON}g} ({match} match)",
        true_text,
        key_text,
        samples,
        match=match,
    )


def _mismatch_reason(label: str, true_value: float, key_value: float) -> str:
    return (
        f"at x = {label} the checker computes {true_value:.{DIGITS_IN_REASON}g} "
        f"but the key gives {key_value:.{DIGITS_IN_REASON}g}"
    )


def _real_value(expr: sp.Basic) -> float | None:
    """Return expr as a finite real float, or None if it is not one."""
    try:
        value = complex(sp.N(expr))
    except (TypeError, ValueError, ArithmeticError):
        return None
    if value.imag != 0 or not math.isfinite(value.real):
        return None
    return value.real


def _values_agree(left: float, right: float) -> bool:
    scale = max(abs(left), abs(right))
    return abs(left - right) <= REL_TOLERANCE * scale + ABS_FLOOR


def _exactly_equal(left: sp.Basic, right: sp.Basic) -> bool:
    try:
        return sp.simplify(left - right) == 0
    except (TypeError, ValueError, ArithmeticError):
        return False


def _result(
    ok: bool,
    outcome: str,
    reason: str,
    true_answer: str = "",
    key_value: str = "",
    samples: list | tuple = (),
    match: str = "",
) -> dict:
    return {
        "ok": ok,
        "outcome": outcome,
        "reason": reason,
        "true_answer": true_answer,
        "key_value": key_value,
        "samples": list(samples),
        "match": match,
    }
