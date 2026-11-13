"""The elementary-function pool: each family with its rule text, domain note and complexity weight.

Shared by the derivative topics (C2), the applications (C3), power series (C9) and Codex's parametric and polar
chapter (C10). Level comes from composition (how many families, terms and layers), never from polynomial degree:
`complexity(expr)` is the score, `level_guess(score)` the first-guess level.

A family is detected from a SymPy expression (`families_in`), so a verifier never trusts the model's label.
"""
from dataclasses import dataclass

import sympy as sp

x = sp.Symbol("x", real=True)


@dataclass(frozen=True)
class Family:
    id: str
    group: str            # which derivative topic teaches it
    weight: float
    rule: str             # the sentence a worked step uses
    domain: str           # domain note for the statement writer and the constraints


FAMILIES: dict[str, Family] = {f.id: f for f in (
    Family("power", "power_rule", 1.0, "Power rule: d/dx x^n = n x^(n-1).", "all real x for n >= 0"),
    Family("root", "power_rule", 1.5, "Write the root as a power, then use the power rule.", "x > 0 (or the radicand > 0)"),
    Family("reciprocal", "power_rule", 1.5, "Write 1/x^n as x^(-n), then use the power rule.", "x != 0"),
    Family("sincos", "trig", 1.5, "d/dx sin x = cos x and d/dx cos x = -sin x.", "all real x"),
    Family("tansec", "trig", 2.0, "d/dx tan x = sec^2 x and d/dx sec x = sec x tan x.", "cos x != 0"),
    Family("cotcsc", "trig", 2.0, "d/dx cot x = -csc^2 x and d/dx csc x = -csc x cot x.", "sin x != 0"),
    Family("exp", "exponential_log", 1.5, "d/dx e^x = e^x and d/dx a^x = a^x ln a.", "all real x"),
    Family("log", "exponential_log", 1.5, "d/dx ln x = 1/x and d/dx log_b x = 1/(x ln b).", "x > 0"),
    Family("asin", "inverse_trig", 2.5, "d/dx asin x = 1/sqrt(1 - x^2) and d/dx acos x = -1/sqrt(1 - x^2).", "|x| < 1"),
    Family("atan", "inverse_trig", 2.0, "d/dx atan x = 1/(1 + x^2) and d/dx acot x = -1/(1 + x^2).", "all real x"),
    Family("sinhcosh", "hyperbolic", 2.0, "d/dx sinh x = cosh x and d/dx cosh x = sinh x.", "all real x"),
    Family("tanhcoth", "hyperbolic", 2.5, "d/dx tanh x = sech^2 x and d/dx coth x = -csch^2 x.", "coth: x != 0"),
    Family("sechcsch", "hyperbolic", 2.5, "d/dx sech x = -sech x tanh x and d/dx csch x = -csch x coth x.", "csch: x != 0"),
)}

_BY_CLASS = [((sp.sin, sp.cos), "sincos"), ((sp.tan, sp.sec), "tansec"), ((sp.cot, sp.csc), "cotcsc"),
             ((sp.exp,), "exp"), ((sp.log,), "log"), ((sp.asin, sp.acos), "asin"), ((sp.atan, sp.acot), "atan"),
             ((sp.sinh, sp.cosh), "sinhcosh"), ((sp.tanh, sp.coth), "tanhcoth"), ((sp.sech, sp.csch), "sechcsch")]


def families_in(expr) -> set[str]:
    """The family ids that appear in expr (powers of x are detected as power, root or reciprocal)."""
    out = set()
    for node in sp.preorder_traversal(expr):
        for classes, fid in _BY_CLASS:
            if isinstance(node, classes):
                out.add(fid)
        if isinstance(node, sp.Pow):
            base, e = node.as_base_exp()
            if base.has(x) and not e.has(x):
                if e.is_Rational and not e.is_Integer:
                    out.add("root")
                elif e.is_negative:
                    out.add("reciprocal")
                else:
                    out.add("power")
            elif not base.has(x) and e.has(x):
                out.add("exp")
    return out


def layers(expr) -> int:
    """Composition depth: how many function applications are nested inside one another on the longest path."""
    if not expr.args:
        return 0
    deeper = max(layers(a) for a in expr.args)
    return deeper + (1 if isinstance(expr, (sp.Function, sp.Pow)) and expr.has(x) and not expr.is_polynomial(x) else 0)


def complexity(expr) -> float:
    """Sum of the weights of the distinct families, 1 per extra term, 1.5 per composition layer beyond the first."""
    fams = families_in(expr)
    terms = len(sp.Add.make_args(expr))
    return sum(FAMILIES[f].weight for f in fams) + max(0, terms - 1) + 1.5 * max(0, layers(expr) - 1)


def level_guess(score: float) -> int:
    """First-guess level from `complexity`; recalibrated from raters."""
    return 1 if score < 2.5 else 2 if score < 4 else 3 if score < 6 else 4


def rule_text(expr) -> str:
    """The rules a worked solution cites for expr, in a stable order."""
    return " ".join(FAMILIES[f].rule for f in sorted(families_in(expr), key=lambda f: list(FAMILIES).index(f)))
