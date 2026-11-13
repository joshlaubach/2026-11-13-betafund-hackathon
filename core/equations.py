"""Equations, tangent lines, and horizontal tangents, graded by SymPy.

read_equation reads each side of "A = B" with core.latex_reader in x and y, so an equation is A - B.
Two equations are the same line or curve when A1 - B1 = k * (A2 - B2) for one nonzero constant k,
checked at fixed off-grid (x, y) points. Every reference is computed by SymPy: the tangent line of a
named function, the slope and tangent line of an implicit curve (by implicit differentiation), and the
points where a curve has a horizontal tangent. A point that is not on the curve is refused, so the
part falls through to the AI ladder instead of being guessed.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from typing import NamedTuple, Optional

import sympy as sp

from core.definitions import parse_definitions, plain_text
from core.derivative_checker import (
    ABS_FLOOR,
    MIN_COMPARABLE_POINTS,
    REL_TOLERANCE,
    SAMPLE_POINTS,
    X,
)
from core.input_boundary import BoundaryError
from core.latex_reader import read_latex
from core.solvers import (
    DIFFERENT,
    EQUAL,
    UNKNOWN,
    Comparison,
    Mark,
    comparison_mark,
    compare_expressions,
)

Y = sp.Symbol("y", real=True)
SYMPY_METHOD = "sympy_computed"
SOURCE_PHRASE = "SymPy's computed answer"
EQUATION_VARIABLES = ("x", "y")
NUMBER = r"-?\d+(?:\.\d+)?"
NOT_DIFFERENTIABLE = (sp.sign, sp.Abs, sp.Piecewise, sp.Heaviside, sp.DiracDelta)
_SAMPLE_Y = SAMPLE_POINTS[3:] + SAMPLE_POINTS[:3]  # shifted so no (x, y) pair repeats a grid value
EQUATION_SAMPLES = tuple(zip(SAMPLE_POINTS, _SAMPLE_Y)) + tuple(
    (-px, py) for px, py in zip(SAMPLE_POINTS, _SAMPLE_Y)
)
_OPENERS = frozenset("([{")
_CLOSERS = frozenset(")]}")
ALTERNATIVE_SEPARATOR = re.compile(r"[;,]|\s+or\s+|\s+and\s+|\\cup")
COMMA = re.compile(",")
_PART_LABEL = re.compile(r"^\s*(?:\([a-z0-9]+\)|[a-z][.)])\s*")
_WRITING_TAIL = re.compile(
    r"(?:[,.;]\s*|\s+)(?:and\s+)?(?:write|explain|state|justify|interpret)\b.*$", re.IGNORECASE
)
_CURVE = re.compile(r"(?<![A-Za-z])(y\s*\^\s*\{?2\}?\s*=\s*[^.;]+?)(?=\s*(?:\.\s|\.$|;|$))")
_CURVE_MARKER = re.compile(r"given by|:", re.IGNORECASE)
_SENTENCE_END = re.compile(r"\.(?=\s|$)|;")
_METHOD_LEAD = re.compile(r"^Use implicit differentiation to\s+", re.IGNORECASE)
_EXACT_REQUEST = re.compile(r"[.;]?\s*Give an exact answer\b.*$", re.IGNORECASE)
_NAMED_TANGENT = re.compile(
    r"(?:Write|Find|Determine) the equation of the tangent line"
    r"(?: to (?:the graph of )?([A-Za-z]))? at x\s*=\s*(" + NUMBER + r")"
)
_CURVE_TANGENT = re.compile(
    r"(?:Write|Find|Determine) the equation of the tangent line (?:to the curve )?at (?:the point )?\(("
    + NUMBER + r"),\s*(" + NUMBER + r")\)"
)
_CURVE_SLOPE = re.compile(
    r"(?:Find|Compute|Determine|Calculate) (?:the )?(?:slope of the tangent(?: line)?|"
    r"\\frac\{dy\}\{dx\}|dy/dx) (?:to the curve )?at (?:the point )?\((" + NUMBER + r"),\s*(" + NUMBER + r")\)"
)
_TANGENT_POINTS = re.compile(
    r"(?:Find|Determine) (?:the coordinates of )?(?:all )?(?:the )?points(?: on the curve)? "
    r"where the tangent(?: line)? is (horizontal|vertical)"
)


class NamedTangent(NamedTuple):
    """The tangent line of a named function at x = point, from the setup's definition of the function."""

    body_latex: str
    point_latex: str


class CurveTangent(NamedTuple):
    """The slope (slope=True) or tangent line of an implicit curve at a point on it."""

    curve_latex: str
    x_latex: str
    y_latex: str
    slope: bool = False


class HorizontalPoints(NamedTuple):
    """Every point of an implicit curve where its tangent is horizontal."""

    curve_latex: str


class VerticalPoints(NamedTuple):
    """Every point of an implicit curve where its tangent is vertical."""

    curve_latex: str


SPEC_TYPES = (NamedTangent, CurveTangent, HorizontalPoints, VerticalPoints)


def owns(spec: object) -> bool:
    return isinstance(spec, SPEC_TYPES)


# ---------------------------------------------------------------------------
# Reading text
# ---------------------------------------------------------------------------


def ask_text(statement: str) -> str:
    """The part's ask as plain text: no $ or \\text wrappers, no part label, no writing request, no final period.

    A writing request needs a separator before it, so an ask that starts with "Write the equation" is kept.
    """
    text = _PART_LABEL.sub("", plain_text(statement), count=1)
    return _WRITING_TAIL.sub("", _EXACT_REQUEST.sub("", text)).rstrip(". ?").strip()


def _separator_end(separator: re.Pattern[str], text: str, index: int) -> Optional[int]:
    """The end of a separator match starting at index, or None when there is none."""
    match = separator.match(text, index)
    if match is None or match.end() == index:
        return None
    return match.end()


def split_top_level(text: str, separator: re.Pattern[str]) -> tuple[str, ...]:
    """The non-empty pieces of text cut at separator matches outside every bracket. () when brackets do not balance."""
    pieces: list[str] = []
    depth = 0
    start = 0
    index = 0
    while index < len(text):
        char = text[index]
        if char in _OPENERS:
            depth += 1
        elif char in _CLOSERS:
            depth -= 1
        else:
            end = _separator_end(separator, text, index) if depth == 0 else None
            if end is not None:
                pieces.append(text[start:index])
                start = index = end
                continue
        index += 1
    if depth != 0:
        return ()
    pieces.append(text[start:])
    return tuple(piece.strip() for piece in pieces if piece.strip())


def read_or_none(text: str, variables: Sequence[str] = ("x",)) -> Optional[sp.Basic]:
    """latex_reader's reading of text, or None when the reader refuses it."""
    try:
        return read_latex(text, variables)
    except BoundaryError:
        return None


def constant_or_none(text: str) -> Optional[sp.Basic]:
    """A reading with no variables, or None when it is unreadable or depends on x."""
    value = read_or_none(text)
    return None if value is None or value.free_symbols else value


def finite_real(expr: sp.Basic) -> Optional[sp.Basic]:
    """expr when it is a finite real number, else None."""
    try:
        value = complex(sp.N(expr))
    except (TypeError, ValueError, ArithmeticError):
        return None
    return expr if value.imag == 0 and math.isfinite(value.real) else None


def split_equation(text: str) -> Optional[tuple[str, str]]:
    """The two sides of an equation with exactly one "=", or None."""
    sides = text.split("=")
    if len(sides) != 2:
        return None
    left, right = (side.strip() for side in sides)
    return (left, right) if left and right else None


def read_equation(text: str, variables: Sequence[str] = EQUATION_VARIABLES) -> Optional[sp.Basic]:
    """The equation as A - B, or None when it is not one equation of readable sides."""
    sides = split_equation(text)
    if sides is None:
        return None
    left = read_or_none(sides[0], variables)
    right = read_or_none(sides[1], variables)
    return None if left is None or right is None else left - right


# ---------------------------------------------------------------------------
# Comparing equations and sets
# ---------------------------------------------------------------------------


def _close(left: float, right: float) -> bool:
    return abs(left - right) <= REL_TOLERANCE * max(abs(left), abs(right)) + ABS_FLOOR


def _value_at(expr: sp.Basic, point: tuple[float, float]) -> Optional[float]:
    try:
        value = complex(sp.N(expr.subs({X: sp.Float(point[0]), Y: sp.Float(point[1])})))
    except (TypeError, ValueError, ArithmeticError):
        return None
    return value.real if value.imag == 0 and math.isfinite(value.real) else None


def _paired_values(reference: sp.Basic, student: sp.Basic) -> list[tuple[float, float]]:
    pairs: list[tuple[float, float]] = []
    for point in EQUATION_SAMPLES:
        left = _value_at(reference, point)
        right = _value_at(student, point)
        if left is not None and right is not None:
            pairs.append((left, right))
    return pairs


def _proportional(pairs: list[tuple[float, float]]) -> bool:
    """True when reference = k * student at every pair, for one nonzero constant k."""
    if all(_close(left, 0.0) and _close(right, 0.0) for left, right in pairs):
        return True
    reference_value, student_value = max(pairs, key=lambda pair: abs(pair[1]))
    if _close(student_value, 0.0):
        return False
    scale = reference_value / student_value
    if _close(scale, 0.0):
        return False
    return all(_close(left, scale * right) for left, right in pairs)


def equation_comparison(reference: sp.Basic, student: sp.Basic) -> Comparison:
    """EQUAL when the two equations describe the same line or curve, DIFFERENT when not, UNKNOWN with too few points.

    A constant offset (same slope, different intercept) is DIFFERENT, because k must multiply the whole side.
    """
    pairs = _paired_values(reference, student)
    if len(pairs) < MIN_COMPARABLE_POINTS:
        return Comparison(UNKNOWN, len(pairs))
    return Comparison(EQUAL if _proportional(pairs) else DIFFERENT, len(pairs))


def _truth(value: object) -> Optional[bool]:
    if value in (True, sp.true):
        return True
    if value in (False, sp.false):
        return False
    return None


def same_set(student: sp.Basic, reference: sp.Basic) -> Optional[bool]:
    """True when the two sets are equal, False when they differ, None when SymPy cannot decide."""
    try:
        forward = _truth(student.is_subset(reference))
        backward = _truth(reference.is_subset(student))
    except (TypeError, ValueError, NotImplementedError):
        return None
    if forward is False or backward is False:
        return False
    if forward is True and backward is True:
        return True
    return None


# ---------------------------------------------------------------------------
# Specs: parsing the ask and the shared setup
# ---------------------------------------------------------------------------


def _is_implicit_curve(text: str) -> bool:
    """True when text is one equation A = B that reads in both x and y."""
    curve = read_equation(text)
    if curve is None:
        return False
    return {"x", "y"} <= {symbol.name for symbol in curve.free_symbols}


def _curve_in(context: str) -> Optional[str]:
    """The one implicit curve in the setup: y^2 = ..., or an equation in x and y after "given by" or ":"."""
    text = plain_text(context)
    candidates = [match.strip() for match in _CURVE.findall(text)]
    candidates += [_CURVE_MARKER.split(sentence)[-1].strip() for sentence in _SENTENCE_END.split(text)]
    found = [candidate for candidate in dict.fromkeys(candidates) if _is_implicit_curve(candidate)]
    return found[0] if len(found) == 1 else None


def _without_method_lead(text: str) -> str:
    """The ask without "Use implicit differentiation to", with its verb capitalised again."""
    stripped = _METHOD_LEAD.sub("", text, count=1)
    return stripped if stripped == text else stripped[:1].upper() + stripped[1:]


def _named_tangent(name: Optional[str], point: str, context: str) -> Optional[NamedTangent]:
    definitions = parse_definitions(context)
    if name:
        definition = definitions.get(name)
    else:
        candidates = [entry for entry in definitions.values() if entry.variable == "x"]
        definition = candidates[0] if len(candidates) == 1 else None
    if definition is None or definition.variable != "x":
        return None
    return NamedTangent(definition.body_latex, point)


def parse_spec(statement: str, context: str = "") -> Optional[object]:
    """The equation-type spec for a tangent-line or horizontal-tangent ask, or None for any other ask."""
    text = _without_method_lead(ask_text(statement))
    named = _NAMED_TANGENT.fullmatch(text)
    if named is not None:
        return _named_tangent(named.group(1), named.group(2), context)
    return _curve_spec(text, context)


def _curve_spec(text: str, context: str) -> Optional[object]:
    curve = _curve_in(context)
    if curve is None:
        return None
    point = _CURVE_TANGENT.fullmatch(text)
    if point is not None:
        return CurveTangent(curve, point.group(1), point.group(2))
    slope = _CURVE_SLOPE.fullmatch(text)
    if slope is not None:
        return CurveTangent(curve, slope.group(1), slope.group(2), slope=True)
    points = _TANGENT_POINTS.fullmatch(text)
    if points is None:
        return None
    return VerticalPoints(curve) if points.group(1) == "vertical" else HorizontalPoints(curve)


# ---------------------------------------------------------------------------
# SymPy computes the reference (runs in the child process)
# ---------------------------------------------------------------------------


def _line(height: sp.Basic, slope: sp.Basic, point: sp.Basic) -> sp.Basic:
    """The line y = height + slope (x - point), as the expression y - (height + slope (x - point))."""
    return Y - (height + slope * (X - point))


def _named_line(spec: NamedTangent) -> Optional[sp.Basic]:
    function = read_or_none(spec.body_latex)
    point = constant_or_none(spec.point_latex)
    if function is None or point is None:
        return None
    derivative = sp.diff(function, X)
    if derivative.has(*NOT_DIFFERENTIABLE):
        return None
    height = finite_real(function.subs(X, point))
    slope = finite_real(derivative.subs(X, point))
    if height is None or slope is None:
        return None
    return _line(height, slope, point)


def _on_curve(curve: sp.Basic, px: sp.Basic, py: sp.Basic) -> bool:
    return sp.simplify(curve.subs({X: px, Y: py})) == 0


def _implicit_slope(curve: sp.Basic, px: sp.Basic, py: sp.Basic) -> Optional[sp.Basic]:
    """dy/dx at (px, py) by implicit differentiation. None when the point is off the curve or the slope is not finite."""
    if not _on_curve(curve, px, py):
        return None
    slope = sp.idiff(curve, Y, X).subs({X: px, Y: py})
    return finite_real(sp.simplify(slope))


def _curve_tangent(spec: CurveTangent) -> Optional[sp.Basic]:
    curve = read_equation(spec.curve_latex)
    px = constant_or_none(spec.x_latex)
    py = constant_or_none(spec.y_latex)
    if curve is None or px is None or py is None:
        return None
    slope = _implicit_slope(curve, px, py)
    if slope is None:
        return None
    return slope if spec.slope else _line(py, slope, px)


def _nonzero(expr: sp.Basic) -> bool:
    return finite_real(expr) is not None and sp.simplify(expr) != 0


def _elements(found: sp.Basic) -> Optional[tuple[sp.Basic, ...]]:
    """The elements of a finite solution set (empty included), or None when SymPy did not return a finite set."""
    if found == sp.S.EmptySet:
        return ()
    return tuple(found) if isinstance(found, sp.FiniteSet) else None


def _tangent_points(curve_latex: str, vertical: bool) -> Optional[sp.Basic]:
    """Points on the curve where the tangent is horizontal, or vertical when vertical is True.

    dy/dx = numerator / denominator. A horizontal tangent has numerator 0 and denominator nonzero; a
    vertical one has denominator 0 and numerator nonzero. The zero part is solved first, and the other
    coordinate comes from the curve.
    """
    curve = read_equation(curve_latex)
    if curve is None:
        return None
    numerator, denominator = sp.fraction(sp.together(sp.idiff(curve, Y, X)))
    zero_part, check = (denominator, numerator) if vertical else (numerator, denominator)
    solved, other = (Y, X) if vertical else (X, Y)
    if zero_part.has(other):
        return None
    firsts = _elements(sp.solveset(zero_part, solved, sp.S.Reals))
    if firsts is None:
        return None
    points: list[sp.Basic] = []
    for first in firsts:
        seconds = _elements(sp.solveset(curve.subs(solved, first), other, sp.S.Reals))
        if seconds is None:
            return None
        for second in seconds:
            x0, y0 = (second, first) if vertical else (first, second)
            if _nonzero(check.subs({X: x0, Y: y0})):
                points.append(sp.Tuple(x0, y0))
    return sp.FiniteSet(*points)


def compute_spec(spec: object) -> Optional[sp.Basic]:
    """SymPy's reference for an equation-type spec, or None when SymPy cannot compute it."""
    if isinstance(spec, NamedTangent):
        return _named_line(spec)
    if isinstance(spec, CurveTangent):
        return _curve_tangent(spec)
    if isinstance(spec, HorizontalPoints):
        return _tangent_points(spec.curve_latex, vertical=False)
    if isinstance(spec, VerticalPoints):
        return _tangent_points(spec.curve_latex, vertical=True)
    return None


# ---------------------------------------------------------------------------
# Marks (run in the parent process; they only read and compare)
# ---------------------------------------------------------------------------


def line_text(line: sp.Basic) -> str:
    """The tangent line as "y = ..." in the statement's own variables."""
    solved = sp.solve(line, Y)
    return f"y = {sp.latex(solved[0])}" if len(solved) == 1 else sp.latex(line)


def _line_mark(value: sp.Basic, answers: tuple[str, ...]) -> Optional[Mark]:
    if len(answers) != 1:
        return None
    student = read_equation(answers[0])
    if student is None:
        return None
    return comparison_mark(
        equation_comparison(value, student), answers[0], line_text(value), SYMPY_METHOD, SOURCE_PHRASE
    )


def _slope_mark(value: sp.Basic, answers: tuple[str, ...]) -> Optional[Mark]:
    if len(answers) != 1:
        return None
    student = read_or_none(answers[0].rsplit("=", 1)[-1].strip())
    if student is None:
        return None
    comparison = compare_expressions(value, student)
    return comparison_mark(comparison, answers[0], sp.latex(value), SYMPY_METHOD, SOURCE_PHRASE)


def read_points(text: str) -> Optional[sp.Basic]:
    """A set of points written as (a,b), separated by ; or , or "or" or "and", or None."""
    pieces = split_top_level(plain_text(text), ALTERNATIVE_SEPARATOR)
    points = [_read_point(piece) for piece in pieces]
    valid = [point for point in points if point is not None]
    if not points or len(valid) != len(points):
        return None
    return sp.FiniteSet(*valid)


def _read_point(piece: str) -> Optional[sp.Basic]:
    if not (piece.startswith("(") and piece.endswith(")")):
        return None
    coordinates = split_top_level(piece[1:-1], COMMA)
    if len(coordinates) != 2:
        return None
    values = [constant_or_none(coordinate) for coordinate in coordinates]
    if values[0] is None or values[1] is None:
        return None
    return sp.Tuple(values[0], values[1])


def _point_notes(curve: Optional[sp.Basic], student: sp.Basic, value: sp.Basic, shape: str) -> list[str]:
    notes: list[str] = []
    for point in student.args:
        label = f"({sp.sstr(point[0])}, {sp.sstr(point[1])})"
        if curve is not None and not _on_curve(curve, point[0], point[1]):
            notes.append(f"{label} is not on the curve.")
        elif point not in value.args:
            notes.append(f"{label} is on the curve, but its tangent there is not {shape}.")
    return notes


def _points_mark(
    spec: HorizontalPoints | VerticalPoints, value: sp.Basic, answers: tuple[str, ...]
) -> Optional[Mark]:
    shape = "vertical" if isinstance(spec, VerticalPoints) else "horizontal"
    shown = "; ".join(answers)
    student = read_points(shown)
    if student is None:
        return None
    same = same_set(student, value)
    if same is None:
        return None
    reference = sp.latex(value)
    if same:
        explanation = (
            f"The student's points {shown} match the points SymPy computed, {reference}, "
            f"where the tangent is {shape}."
        )
        return Mark("correct", SYMPY_METHOD, explanation, reference)
    notes = _point_notes(read_equation(spec.curve_latex), student, value, shape)
    explanation = (
        f"SymPy computes {reference} as the points where the tangent is {shape}; the student wrote "
        f"{shown}. " + " ".join(notes)
    ).strip()
    return Mark("incorrect", SYMPY_METHOD, explanation, reference)


def mark_spec(spec: object, value: sp.Basic, answers: tuple[str, ...]) -> Optional[Mark]:
    """The mark for an equation-type ask, or None when this module cannot compare the answers."""
    if isinstance(spec, (HorizontalPoints, VerticalPoints)):
        return _points_mark(spec, value, answers)
    if isinstance(spec, CurveTangent) and spec.slope:
        return _slope_mark(value, answers)
    if isinstance(spec, (NamedTangent, CurveTangent)):
        return _line_mark(value, answers)
    return None
