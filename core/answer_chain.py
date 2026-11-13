"""A student's chain of equal signs, such as "dy/dx = 100 = 1/2", which asserts every step is equal.

Only a value, slope, or derivative answer with more than one "=" is a chain. Each step that reads as an
expression must equal the reference; one that does not makes the whole chain contradictory, so the mark
is unsure rather than judged by its last step. A single "=" (a label and a value, or an equation) is not a chain.
"""

from __future__ import annotations

import re
from typing import Callable, Optional

import sympy as sp

from core.solvers import DIFFERENT, Mark, WHY_FORMAT, compare_expressions
from core.worksheet_types import GradeMethod

CHAIN_EXPLANATION = "The written chain of equal signs contains a step that does not match."
MIN_CHAIN_SIGNS = 2  # "=" signs; a chain has at least two, so "label = value" is never one
_LABEL_ONLY = re.compile(
    r"\\frac\{d[A-Za-z]\}\{d[A-Za-z]\}|d[A-Za-z]/d[A-Za-z]|[A-Za-z]'*(?:\(\s*[A-Za-z0-9]+\s*\))?"
)

Reader = Callable[[str], Optional[sp.Basic]]


def _steps(answer: str) -> list[str]:
    """The answer's pieces between its "=" signs, without a leading label such as "dy/dx" or "f'(1)"."""
    pieces = [piece.strip() for piece in answer.split("=")]
    if len(pieces) - 1 < MIN_CHAIN_SIGNS:
        return []
    if _LABEL_ONLY.fullmatch(pieces[0]):
        return pieces[1:]
    return pieces


def chain_mismatch(reference: sp.Basic, answer: str, reader: Reader) -> bool:
    """True when the answer is a chain and one of its readable steps differs from the reference.

    reader reads one step in the statement's variable, or returns None when it cannot read it.
    """
    for step in _steps(answer):
        expr = reader(step) if step else None
        if expr is not None and compare_expressions(reference, expr).status == DIFFERENT:
            return True
    return False


def chain_unsure(method: GradeMethod, reference: str) -> Mark:
    """The unsure mark for a contradictory chain: format, because the written form is what cannot be read."""
    return Mark("unsure", method, CHAIN_EXPLANATION, reference, WHY_FORMAT)
