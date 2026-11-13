"""Echo-checked practice problems written offline and verified by SymPy.

verify_pair() is the gate: a function and its answer key are parsed from a
whitelisted text grammar, differentiated by SymPy, and then run through
core.derivative_checker. load_generated() reads the saved problem file for the
app and never raises.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import sympy
from sympy.parsing.sympy_parser import parse_expr, standard_transformations

from core.derivative_checker import check_derivative
from core.drafter import LABEL_ACCEPTED, build_statement
from core.practice import _text_error as practice_text_error
from core.solvers import EQUAL, compare_answers, is_readable

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATED_PATH = REPO_ROOT / "docs" / "echo_checked_problems.json"
NET_CHANGE_TOPIC = "net_change_total_distance"
GENERATED_TOPICS = ("chain_rule", "quotient_rule", NET_CHANGE_TOPIC)
VERSION = 1
SQRT_WORD = "sqrt"
ALLOWED_TEXT = re.compile(r"[0-9x+\-*/().^ ]*")
X = sympy.Symbol("x", real=True)
PARSE_LOCALS = {"x": X, "sqrt": sympy.sqrt}
REQUIRED_KEYS = ("id", "topic", "level", "statement", "answer_latex", "sympy_check")
T = sympy.Symbol("t", real=True)
INTEGRAL_WORDS = frozenset({"t", "sqrt", "exp"})
INTEGRAL_LOCALS = {"t": T, "sqrt": sympy.sqrt, "exp": sympy.exp}
INTEGRAL_CHARS = re.compile(r"[0-9+\-*/().^ ]*")
IDENTIFIER = re.compile(r"[A-Za-z_]\w*")
INTEGRAL_SAMPLES = 200
MAX_BOUND = 5
NEGATIVE_LIMIT = -1e-9
INTEGRAL_TOLERANCE = 1e-9

logger = logging.getLogger(__name__)


def _failed(reason: str, **extra: str | None) -> dict:
    result = {"ok": False, "reason": reason, "function_latex": None, "answer_latex": None, "statement": None}
    result.update(extra)
    return result


def _text_problem(text: str) -> str | None:
    if not isinstance(text, str) or not text.strip():
        return "empty text"
    # "sqrt" is allowed by the whitelist; it is removed only for this check and the original text is parsed.
    if ALLOWED_TEXT.fullmatch(text.replace(SQRT_WORD, "")) is None:
        return "unsupported characters"
    return None


def _parse(text: str) -> sympy.Expr:
    return parse_expr(
        text.replace("^", "**"),
        local_dict=PARSE_LOCALS,
        transformations=standard_transformations,
    )


def verify_pair(function_text: str, answer_text: str) -> dict:
    """Check that answer_text is exactly the derivative of function_text, then render the problem."""
    for text in (function_text, answer_text):
        problem = _text_problem(text)
        if problem is not None:
            return _failed(problem)
    try:
        f = _parse(function_text)
        g = _parse(answer_text)
    except Exception:
        return _failed("could not parse")
    if not isinstance(f, sympy.Expr) or not isinstance(g, sympy.Expr):
        return _failed("could not parse")
    if f.free_symbols != {X} or g.free_symbols != {X}:
        return _failed("must use only x")
    try:
        exact = sympy.simplify(sympy.diff(f, X) - g) == 0
    except Exception as error:
        return _failed(f"could not check the derivative ({type(error).__name__})")
    if not exact:
        return _failed("the derivative of the function is not the answer")
    function_latex = sympy.latex(f)
    answer_latex = sympy.latex(g)
    if practice_text_error(answer_latex) is not None:
        return _failed("the answer is not accepted by the practice checker")
    verdict = check_derivative(function_latex, answer_latex)
    if not verdict["ok"]:
        return _failed(
            f"the checker did not accept the rendered problem: {verdict['reason']}",
            function_latex=function_latex,
            answer_latex=answer_latex,
        )
    return {
        "ok": True,
        "reason": "verified by SymPy",
        "function_latex": function_latex,
        "answer_latex": answer_latex,
        "statement": build_statement(function_latex, None),
    }


def _integral_failed(reason: str, a=None, b=None) -> dict:
    return {
        "ok": False,
        "reason": reason,
        "statement": None,
        "answer_latex": None,
        "velocity_latex": None,
        "a": a,
        "b": b,
    }


def _integral_text_problem(text: str) -> str | None:
    if not isinstance(text, str) or not text.strip():
        return "empty text"
    if any(word not in INTEGRAL_WORDS for word in IDENTIFIER.findall(text)):
        return "only t, sqrt and exp are allowed as words"
    if INTEGRAL_CHARS.fullmatch(IDENTIFIER.sub("", text)) is None:
        return "unsupported characters"
    return None


def _parse_integral(text: str) -> sympy.Expr:
    return parse_expr(
        text.replace("^", "**"),
        local_dict=INTEGRAL_LOCALS,
        transformations=standard_transformations,
    )


def verify_integral(antiderivative_text: str, velocity_text: str, a: int, b: int) -> dict:
    """Check F, v, and bounds a, b; then render the net-change problem for the integral of v on [a, b]."""
    for text in (antiderivative_text, velocity_text):
        problem = _integral_text_problem(text)
        if problem is not None:
            return _integral_failed(problem, a, b)
    if not all(type(value) is int for value in (a, b)) or not 0 <= a < b <= MAX_BOUND:
        return _integral_failed("bounds must be integers with 0 <= a < b <= 5", a, b)
    try:
        antiderivative = _parse_integral(antiderivative_text)
        velocity = _parse_integral(velocity_text)
    except Exception:
        return _integral_failed("could not parse", a, b)
    if not isinstance(antiderivative, sympy.Expr) or not isinstance(velocity, sympy.Expr):
        return _integral_failed("could not parse", a, b)
    if antiderivative.free_symbols != {T} or velocity.free_symbols != {T}:
        return _integral_failed("must use only t", a, b)
    try:
        exact = sympy.simplify(sympy.diff(antiderivative, T) - velocity) == 0
    except Exception as error:
        return _integral_failed(f"could not check the derivative ({type(error).__name__})", a, b)
    if not exact:
        return _integral_failed("the velocity is not the derivative of the antiderivative", a, b)
    try:
        samples = [
            float(velocity.subs(T, a + (b - a) * index / (INTEGRAL_SAMPLES - 1)))
            for index in range(INTEGRAL_SAMPLES)
        ]
    except Exception as error:
        return _integral_failed(f"could not evaluate the velocity ({type(error).__name__})", a, b)
    if min(samples) < NEGATIVE_LIMIT:
        return _integral_failed("the velocity is negative somewhere on the interval", a, b)
    key = sympy.simplify(antiderivative.subs(T, b) - antiderivative.subs(T, a))
    try:
        area = sympy.integrate(velocity, (T, a, b))
        if sympy.simplify(area - key) != 0:
            return _integral_failed("the integral of the velocity is not F(b) - F(a)", a, b)
        gap = abs(float(sympy.N(area, 15)) - float(sympy.N(key, 15)))
    except Exception as error:
        return _integral_failed(f"could not evaluate the integral ({type(error).__name__})", a, b)
    if gap >= INTEGRAL_TOLERANCE:
        return _integral_failed("the numeric check of the integral failed", a, b)
    velocity_latex = sympy.latex(velocity)
    answer_latex = sympy.latex(key)
    statement = (
        "Compute $\\int_{" + str(a) + "}^{" + str(b) + "} v(t)\\,dt$ for $v(t) = "
        + velocity_latex + "$. Give an exact answer."
    )
    if practice_text_error(answer_latex) is not None:
        return _integral_failed("the answer is not accepted by the practice checker", a, b)
    if compare_answers(answer_latex, answer_latex).status != EQUAL or not is_readable(answer_latex):
        return _integral_failed("the answer could not be read by the practice checker", a, b)
    return {
        "ok": True,
        "reason": "verified by SymPy",
        "statement": statement,
        "answer_latex": answer_latex,
        "velocity_latex": velocity_latex,
        "a": a,
        "b": b,
    }


def _warn(path: Path, detail: str) -> list:
    logger.warning("generated problems not loaded from %s: %s", path, detail)
    return []


def load_generated(topic: str, level: int, path: Path = GENERATED_PATH) -> list[dict]:
    """Return the passed problems for topic and level. Never raises; any bad file gives []."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return _warn(path, f"{type(error).__name__}")
    if not isinstance(data, dict) or not isinstance(data.get("problems"), list):
        return _warn(path, "wrong shape")
    problems = data["problems"]
    if not all(isinstance(item, dict) and all(key in item for key in REQUIRED_KEYS) for item in problems):
        return _warn(path, "wrong shape")
    return [
        {
            "id": item["id"],
            "statement": item["statement"],
            "answer_latex": item["answer_latex"],
            "level": item["level"],
            "label": LABEL_ACCEPTED,
        }
        for item in problems
        if item["topic"] == topic and item["level"] == level and item["sympy_check"] == "passed"
    ]
