"""Solution sets graded by SymPy: "Solve" an equation, critical points, and intervals of increase or decrease.

SymPy computes the reference set (solveset, or solve_univariate_inequality for intervals). The student's
final answers are read as ONE set: several final answers for the same part are alternatives, joined by
";", "or", "and", "\\cup", or commas outside brackets. Each alternative is a value (x = a, x = \\pm a,
a bare number), an interval (a,b) with \\infty, or a one-sided inequality in x. Any other shape is refused,
so the part falls through to the AI ladder. Sets are compared with exact SymPy subset tests.
"""

from __future__ import annotations

import re
from typing import NamedTuple, Optional

import sympy as sp

from core.definitions import parse_definitions, plain_text
from core.derivative_checker import X
from core.equations import (
    ALTERNATIVE_SEPARATOR,
    COMMA,
    NOT_DIFFERENTIABLE,
    SYMPY_METHOD,
    ask_text,
    constant_or_none,
    read_equation,
    read_or_none,
    same_set,
    split_top_level,
)
from core.solvers import Mark

SOLVE = "solve"
CRITICAL = "critical"
INCREASING = "increasing"
DECREASING = "decreasing"
SET_TYPES = (sp.FiniteSet, sp.Interval, sp.Union)
_SOLVE_ASK = re.compile(r"Solve (?:for x[:,]?\s+)?(.+)")
_CRITICAL_ASK = re.compile(r"Find all critical points where ([A-Za-z])'\(x\)\s*=\s*0")
_INTERVALS_ASK = re.compile(r"On what intervals is ([A-Za-z]) (increasing|decreasing)")
_RELATION = re.compile(r"(.+?)\s*(<=|>=|<|>|\\(?:le|leq|ge|geq)(?![A-Za-z]))\s*(.+)")
_ASSIGNMENT = re.compile(r"x\s*=\s*(.+)")
_LESS_OPS = frozenset({"<", "<=", "\\le", "\\leq"})
_CLOSED_OPS = frozenset({"<=", ">=", "\\le", "\\leq", "\\ge", "\\geq"})
_INTERVAL_OPEN = "(["
_INTERVAL_CLOSE = ")]"
_PM = "\\pm"
_ENDPOINTS = {"\\infty": sp.oo, "-\\infty": -sp.oo}
_SPACING_COMMAND = re.compile(r"\\(?:[,;:! ]|qquad|quad)")


class SetSpec(NamedTuple):
    """One set ask. body_latex is the equation (solve) or the function's body (critical, intervals)."""

    kind: str
    body_latex: str


def owns(spec: object) -> bool:
    return isinstance(spec, SetSpec)


def _named_set(name: str, kind: str, context: str) -> Optional[SetSpec]:
    definition = parse_definitions(context).get(name)
    if definition is None or definition.variable != "x":
        return None
    return SetSpec(kind, definition.body_latex)


def parse_spec(statement: str, context: str = "") -> Optional[SetSpec]:
    """The set spec for a solve, critical-point, or increasing/decreasing ask, or None for any other ask."""
    text = ask_text(statement)
    solve = _SOLVE_ASK.fullmatch(text)
    if solve is not None:
        body = solve.group(1).strip()
        return SetSpec(SOLVE, body) if read_equation(body, ("x",)) is not None else None
    critical = _CRITICAL_ASK.fullmatch(text)
    if critical is not None:
        return _named_set(critical.group(1), CRITICAL, context)
    intervals = _INTERVALS_ASK.fullmatch(text)
    if intervals is not None:
        kind = INCREASING if intervals.group(2) == "increasing" else DECREASING
        return _named_set(intervals.group(1), kind, context)
    return None


# ---------------------------------------------------------------------------
# SymPy computes the reference (runs in the child process)
# ---------------------------------------------------------------------------


def _accepted(result: object) -> bool:
    return isinstance(result, SET_TYPES) or result in (sp.S.EmptySet, sp.S.Reals)


def _reference_set(spec: SetSpec) -> Optional[sp.Basic]:
    if spec.kind == SOLVE:
        equation = read_equation(spec.body_latex, ("x",))
        return None if equation is None else sp.solveset(equation, X, sp.S.Reals)
    function = read_or_none(spec.body_latex)
    if function is None:
        return None
    derivative = sp.diff(function, X)
    if derivative.has(*NOT_DIFFERENTIABLE):
        return None
    if spec.kind == CRITICAL:
        return sp.solveset(derivative, X, sp.S.Reals)
    relation = derivative > 0 if spec.kind == INCREASING else derivative < 0
    return sp.solve_univariate_inequality(relation, X, relational=False)


def compute_spec(spec: object) -> Optional[sp.Basic]:
    """SymPy's solution set for a set spec, or None when the result is not a plain set."""
    if not isinstance(spec, SetSpec):
        return None
    result = _reference_set(spec)
    return result if result is not None and _accepted(result) else None


# ---------------------------------------------------------------------------
# Reading the student's alternatives as one set (runs in the parent process)
# ---------------------------------------------------------------------------


def _endpoint(text: str) -> Optional[sp.Basic]:
    compact = text.replace(" ", "")
    if compact in _ENDPOINTS:
        return _ENDPOINTS[compact]
    return constant_or_none(text)


def _interval_piece(piece: str) -> Optional[sp.Basic]:
    """(a,b), [a,b], (a,b], or [a,b) with a or b possibly \\infty, or None when the piece is not an interval."""
    if len(piece) < 2 or piece[0] not in _INTERVAL_OPEN or piece[-1] not in _INTERVAL_CLOSE:
        return None
    bounds = split_top_level(piece[1:-1], COMMA)
    if len(bounds) != 2:
        return None
    low = _endpoint(bounds[0])
    high = _endpoint(bounds[1])
    if low is None or high is None:
        return None
    return sp.Interval(low, high, left_open=piece[0] == "(", right_open=piece[-1] == ")")


def _relation_piece(piece: str) -> Optional[sp.Basic]:
    """x < c, c > x, x >= c, and so on, as an interval; None when the piece is not such an inequality."""
    match = _RELATION.fullmatch(piece)
    if match is None:
        return None
    left, op, right = match.group(1).strip(), match.group(2), match.group(3).strip()
    if left == "x":
        other, less = right, op in _LESS_OPS
    elif right == "x":
        other, less = left, op not in _LESS_OPS
    else:
        return None
    bound = constant_or_none(other)
    if bound is None:
        return None
    closed = op in _CLOSED_OPS
    if less:
        return sp.Interval(-sp.oo, bound, left_open=True, right_open=not closed)
    return sp.Interval(bound, sp.oo, left_open=not closed, right_open=True)


def _values(text: str) -> Optional[tuple[sp.Basic, ...]]:
    """The constant or the two constants of "a \\pm b" (a + b and a - b), or None when unreadable."""
    if _PM not in text:
        value = constant_or_none(text)
        return None if value is None else (value,)
    if text.count(_PM) != 1:
        return None
    plus = text.replace(_PM, "+", 1)
    plus = plus[1:] if plus.startswith("+") else plus
    values = (constant_or_none(plus), constant_or_none(text.replace(_PM, "-", 1)))
    if values[0] is None or values[1] is None:
        return None
    return values


def _assignment_piece(piece: str) -> Optional[sp.Basic]:
    match = _ASSIGNMENT.fullmatch(piece)
    if match is None:
        return None
    values = _values(match.group(1))
    return None if values is None else sp.FiniteSet(*values)


def _piece_set(piece: str) -> Optional[sp.Basic]:
    """One alternative as a set: interval, inequality, x = value, or a bare value. None when none of these reads it."""
    for reader in (_interval_piece, _relation_piece, _assignment_piece):
        found = reader(piece)
        if found is not None:
            return found
    values = _values(piece)
    return None if values is None else sp.FiniteSet(*values)


def read_student_set(answers: tuple[str, ...]) -> Optional[sp.Basic]:
    """All of a part's final answers read as one set (they are alternatives), or None when any is unreadable."""
    pieces = split_top_level(plain_text("; ".join(answers)), ALTERNATIVE_SEPARATOR)
    parts = [_piece_set(piece) for piece in pieces]
    if not parts or any(part is None for part in parts):
        return None
    return sp.Union(*[part for part in parts if part is not None])


def without_spacing(text: str) -> str:
    """The text with LaTeX spacing commands (\\, \\; \\  \\quad) turned into plain spaces, as an AI reply writes them.

    The AI reply "x=0,\\ x=2" reads as "x=0, x=2" only after this; a student's answer is never changed.
    """
    return _SPACING_COMMAND.sub(" ", text)


# ---------------------------------------------------------------------------
# Marks
# ---------------------------------------------------------------------------


def mark_spec(spec: object, value: sp.Basic, answers: tuple[str, ...]) -> Optional[Mark]:
    """The mark for a set ask, or None when the student's answers cannot be read as one set."""
    if not isinstance(spec, SetSpec) or not _accepted(value):
        return None
    student = read_student_set(answers)
    if student is None:
        return None
    same = same_set(student, value)
    if same is None:
        return None
    reference = sp.latex(value)
    shown = "; ".join(answers)
    if same:
        explanation = f"The student's answer {shown} matches the set SymPy computed, {reference}."
        return Mark("correct", SYMPY_METHOD, explanation, reference)
    explanation = (
        f"SymPy computes the set {reference}; the student wrote {shown}, which is a different set."
    )
    return Mark("incorrect", SYMPY_METHOD, explanation, reference)
