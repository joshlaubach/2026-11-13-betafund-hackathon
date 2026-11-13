"""Build deliberately wrong keys from a correct key, for negative gate tests."""

from __future__ import annotations

import sympy as sp

from core.derivative_checker import strip_constant
from core.input_boundary import BoundaryError
from core.latex_reader import read_latex

CORRUPTION_KINDS = (0, 1, 2)
ADDED_TERM = " + 1"
DOUBLE_PREFIX = "2"
NEGATE_PREFIX = "-"


def corrupt_key(key_latex: str, kind: int) -> str | None:
    """Return a wrong key derived from key_latex, or None if no wrong key results.

    kind 0 adds 1, kind 1 doubles, kind 2 negates. None is returned when the
    corrupted key would be mathematically the same as the original (for example
    when the original key is identically zero).
    """
    if kind not in CORRUPTION_KINDS:
        raise ValueError(f"unknown corruption kind: {kind!r}")
    base = strip_constant(key_latex)
    if kind == 0:
        wrong = base + ADDED_TERM
    elif kind == 1:
        wrong = f"{DOUBLE_PREFIX}\\left({base}\\right)"
    else:
        wrong = f"{NEGATE_PREFIX}\\left({base}\\right)"
    if _is_identically_zero(base):
        return None
    return wrong


def _is_identically_zero(latex: str) -> bool:
    try:
        expr = read_latex(latex)
    except BoundaryError:
        return False
    return bool(sp.simplify(expr) == 0)
