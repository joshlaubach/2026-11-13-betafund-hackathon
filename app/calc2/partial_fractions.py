"""Verify a partial-fractions candidate and derive everything the student sees.

The model supplies the decomposition itself: a sum of terms A/(x - a)^k, (Bx + C)/(x^2 + bx + c)^k with an
irreducible quadratic, and optionally a polynomial part. The server adds them over a common denominator (the
integrand the student sees, with the factored form hidden), checks with SymPy's apart that the decomposition is
the unique one, writes the steps (long division, factor, set up, solve, integrate) and checks the derivative.
"""
import sympy as sp

from app.shared.integral_core import L, Reject, _parse, x
from app.shared.integral_finish import bound_ext, finish

MAX_LINEAR_POWER = 3
MAX_QUAD_POWER = 2
MAX_TERMS = 5


def verify(decomposition: str, bounds=None, axes: dict | None = None, calculator: str = "none") -> dict:
    try:
        return _verify(decomposition, bounds, axes or {}, calculator)
    except Reject as r:
        return {"ok": False, "cause": r.cause, "reason": r.reason, "cap": r.cap}


def _linear(e) -> bool:
    return e.is_polynomial(x) and sp.degree(e, x) == 1


def classify_term(t):
    """('poly', degree) | ('lin', a_coeff_expr, power) | ('quad', power) for one additive term, or None."""
    n, d = sp.fraction(sp.together(t))
    if not d.has(x):
        return ("poly", sp.degree(sp.expand(t), x) if t.has(x) else 0) if sp.expand(t).is_polynomial(x) else None
    if not n.is_polynomial(x):
        return None
    base, k = (d.base, d.exp) if d.is_Pow else (d, sp.Integer(1))
    c, base = base.as_independent(x, as_Add=False) if base.is_Mul else (sp.Integer(1), base)
    if not (k.is_Integer and k >= 1 and base.is_polynomial(x)):
        return None
    deg = sp.degree(base, x)
    if deg == 1:
        if n.has(x) or k > MAX_LINEAR_POWER:
            return None
        return ("lin", sp.solve(base, x)[0], int(k))
    if deg == 2 and sp.degree(n, x) <= 1 and k <= MAX_QUAD_POWER:
        P = sp.Poly(base, x)
        disc = P.coeff_monomial(x) ** 2 - 4 * P.coeff_monomial(x ** 2) * P.coeff_monomial(1)
        if disc < 0:
            return ("quad", int(k), base)
    return None


def _letters(n: int):
    return [sp.Symbol(chr(ord("A") + i)) for i in range(n)]


def _template(terms, kinds):
    """The decomposition with unknown constants A, B, C, ... in the same shape as the terms."""
    syms = iter(_letters(2 * len(terms)))
    out = []
    for t, k in zip(terms, kinds):
        n, d = sp.fraction(sp.together(t))
        if k[0] == "lin":
            out.append(next(syms) / d)
        elif k[0] == "quad":
            a, b = next(syms), next(syms)
            out.append((a * x + b) / d)
        else:
            out.append(t)
    return sp.Add(*out, evaluate=False)


def _constants(terms, kinds):
    vals = []
    letters = iter(_letters(2 * len(terms)))
    for t, k in zip(terms, kinds):
        n, d = sp.fraction(sp.together(t))
        if k[0] == "lin":
            vals.append((next(letters), sp.simplify(n)))
        elif k[0] == "quad":
            a, b = next(letters), next(letters)
            P = sp.Poly(n, x)
            vals += [(a, P.coeff_monomial(x)), (b, P.coeff_monomial(1))]
    return vals


def _axes_reason(axes, kinds, terms) -> str | None:
    lin_roots = {k[1] for k in kinds if k[0] == "lin"}
    got = {
        "linear": len(lin_roots),
        "repeat": max([k[2] for k in kinds if k[0] == "lin"] + [1]),
        "quad": any(k[0] == "quad" for k in kinds),
        "improper": any(k[0] == "poly" for k in kinds),
        "terms": len([k for k in kinds if k[0] != "poly"]),
        "qpow": max([k[1] for k in kinds if k[0] == "quad"] + [0]),
    }
    want = [f"{n} = {axes[n]} (not {got[n]})" for n in got if n in axes and str(axes[n]).lower() != str(got[n]).lower()]
    return ("axes: the server assigned " + "; ".join(want)) if want else None


def _verify(decomp, bounds, axes, calculator):
    f = _parse(decomp, x, "decomposition")
    terms = list(sp.Add.make_args(f))
    if not 2 <= len(terms) <= MAX_TERMS + 1:
        raise Reject("slip", f"the decomposition must have 2 to {MAX_TERMS} fraction terms (plus an optional polynomial)")
    kinds = []
    for t in terms:
        k = classify_term(t)
        if k is None:
            raise Reject("redraw", "each term must be A/(ax+b)^k (k up to 3), (Bx + C)/(quadratic)^k with an "
                         "irreducible quadratic (k up to 2), or a polynomial")
        kinds.append(k)
    fractions = [t for t, k in zip(terms, kinds) if k[0] != "poly"]
    if not fractions:
        raise Reject("redraw", "no fraction terms: this is not a partial-fractions problem")
    if axes and (why := _axes_reason(axes, kinds, terms)):
        raise Reject("redraw", why)
    shown = sp.cancel(sp.together(f))
    num, den = sp.fraction(shown)
    decomposed = sp.apart(shown, x)
    if len([t for t in sp.Add.make_args(decomposed) if classify_term(t) and classify_term(t)[0] != "poly"]) !=             len(fractions):
        raise Reject("redraw", "two terms share a denominator or a term is not in lowest terms; write one term "
                     "for each factor and power")
    if sp.cancel(sp.together(decomposed - f)) != 0:
        raise Reject("redraw", "the decomposition is not the partial-fraction decomposition of the sum "
                     "(a factor cancelled, or a term is not in lowest terms)")
    if sp.degree(den, x) < 2:
        raise Reject("redraw", "the denominator must have degree at least 2")
    a_b = None
    if bounds is not None:
        a_b = (bound_ext(bounds[0], "lower bound"), bound_ext(bounds[1], "upper bound"))
    fac = sp.factor(den)
    steps = []
    improper = any(k[0] == "poly" for k in kinds)
    if improper:
        q, r = sp.div(num, den, x)
        steps.append({"text": "The degree of the numerator is not less than the degree of the denominator, so divide first.",
                      "latex": f"{L(shown)} = {L(q)} + {L(sp.simplify(r / den))}", "sympy": str(q)})
    steps.append({"text": "Factor the denominator.", "latex": f"{L(den)} = {L(fac)}", "sympy": str(fac)})
    steps.append({"text": "Write the decomposition with unknown constants.",
                  "latex": L(_template(fractions, [k for k in kinds if k[0] != 'poly'])), "sympy": None})
    cons = _constants(fractions, [k for k in kinds if k[0] != "poly"])
    steps.append({"text": "Match the numerators and solve for the constants.",
                  "latex": ",\\quad ".join(f"{L(a)} = {L(v)}" for a, v in cons), "sympy": str(cons)})
    steps.append({"text": "Rewrite the integral as a sum of simple fractions.", "latex": f"\\int {L(f)}\\,dx", "sympy": str(f)})
    F = sp.Integer(0)
    for t, k in zip(terms, kinds):
        piece = sp.integrate(t, x)
        if k[0] == "lin":                         # ln|ax + b|, as a textbook writes it
            piece = piece.replace(lambda e: isinstance(e, sp.log) and not e.args[0].has(sp.Abs),
                                  lambda e: sp.log(sp.Abs(e.args[0])))
        F += piece
    steps.append({"text": "Integrate each term.", "latex": f"{L(F)} + C", "sympy": str(F)})
    extra = {"linear": len({k[1] for k in kinds if k[0] == "lin"}),
             "repeat": max([k[2] for k in kinds if k[0] == "lin"] + [1]),
             "quad": any(k[0] == "quad" for k in kinds), "improper": improper, "fractions": len(fractions),
             "rules": ["PartialFractionsRule", "RewriteRule"]}
    return finish(shown, F, shown, steps, a_b, calculator=calculator, allow_improper=False,
                  how="Integrate each term.", extra_raw=extra)
