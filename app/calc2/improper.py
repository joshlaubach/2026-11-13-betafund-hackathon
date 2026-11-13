"""Verify an improper-integral candidate and derive everything the student sees.

Three kinds of task, all checked by the server:
  value   the integral over an interval with an infinite end or a singular point has an elementary
          antiderivative: the server takes limits, cross-checks numerically and answers with the exact value or
          "diverges".
  limit   limit comparison with a p-integral g = c/x^p (at infinity) or c/(x - a)^p (at a singular end): the
          server computes lim f/g with SymPy and gives the verdict from p. Verdict only.
  direct  direct comparison 0 <= f <= c*g (or f >= c*g >= 0) with a p-integral g, proved by solving the
          inequality. Verdict only. Used when f has no elementary antiderivative.
"""
import sympy as sp

from app.shared.integral_core import L, Reject, _antiderivative, _hash, _parse, _shape, x
from app.shared.integral_finish import _INF, _key, bound_ext, definite_ext, fast_discontinuities, finish
from app.shared.integral_core import _discontinuities

ASKS = ("value", "limit", "direct")


def verify(f: str, bounds: list[str], g: str | None = None, ask: str = "value", axes: dict | None = None,
           calculator: str = "none") -> dict:
    try:
        return _verify(f, bounds, g, ask, axes or {}, calculator)
    except Reject as r:
        return {"ok": False, "cause": r.cause, "reason": r.reason, "cap": r.cap}


def _singular_points(f, a, b):
    finite = [p for p in (a, b) if p not in _INF]
    if len(finite) == 2:
        pts = fast_discontinuities(f, a, b)
        return _discontinuities(f, a, b) if pts is None else pts
    if finite:
        lo, hi = (finite[0], finite[0] + 50) if b == sp.oo else (finite[0] - 50, finite[0])
        return [p for p in _discontinuities(f, lo, hi) if a <= p <= b]
    return []


def _kind(a, b, pts) -> str:
    if a == -sp.oo and b == sp.oo:
        return "both_inf"
    if b == sp.oo:
        return "inf_upper"
    if a == -sp.oo:
        return "inf_lower"
    if pts and all(p in (a, b) for p in pts):
        return "singular_end"
    if pts:
        return "singular_inside"
    return "proper"


def _p_form(g, a, b):
    """(p, point) when g = c/(x - point)^p (a singular end) or c/x^p at infinity; None otherwise."""
    c, rest = g.as_independent(x, as_Add=False)
    if not (c.is_Rational and c > 0) or not rest.is_Pow:
        return None
    base, e = rest.as_base_exp()
    if not (e.is_Rational and e < 0):
        return None
    p = -e
    if sp.degree(base, x) == 1 if base.is_polynomial(x) else False:
        P = sp.Poly(base, x)
        k, c0 = P.coeff_monomial(x), P.coeff_monomial(1)
        if abs(k) == 1:
            return p, sp.simplify(-c0 / k), k
    return None


def _verify(f_s, bounds, g_s, ask, axes, calculator):
    if ask not in ASKS:
        raise Reject("slip", f"ask must be one of {', '.join(ASKS)}")
    f = _parse(f_s, x, "f")
    if not bounds or len(bounds) != 2:
        raise Reject("slip", "bounds are required: an improper integral has an infinite bound or a singular end")
    a, b = bound_ext(bounds[0], "lower bound"), bound_ext(bounds[1], "upper bound")
    if not _key(a) < _key(b):
        raise Reject("slip", "lower bound must be less than upper bound")
    pts = _singular_points(f, a, b)
    kind = _kind(a, b, pts)
    if kind == "proper":
        raise Reject("redraw", "the integral is proper: it needs an infinite bound or a point where f is undefined")
    for key, val in (("type", kind),):
        if key in axes and str(axes[key]) != val:
            raise Reject("redraw", f"axes: the server assigned type = {axes[key]} (not {val})")
    if ask == "value":
        F = _antiderivative(f, x)
        steps = [{"text": "The integral is improper: " + {
            "inf_upper": "the upper bound is infinite.", "inf_lower": "the lower bound is infinite.",
            "both_inf": "both bounds are infinite: split at a finite point.",
            "singular_end": "f is undefined at an end of the interval.",
            "singular_inside": "f is undefined inside the interval: split there."}[kind],
            "latex": f"\\int_{{{L(a)}}}^{{{L(b)}}} {L(f)}\\,dx", "sympy": None}]
        res = finish(f, F, f, steps, (a, b), calculator=calculator, allow_improper=True,
                     how="Find an antiderivative.", extra_raw={"type": kind, "ask": "value", "rules":
                     ["RewriteRule"]})
        verdict = "diverges" if res["answer"]["type"] == "enum" else "converges"
        if "verdict" in axes and str(axes["verdict"]) != verdict:
            raise Reject("redraw", f"axes: the server assigned verdict = {axes['verdict']} (this one {verdict})")
        res["raw"]["verdict"] = verdict
        return res
    # comparison tests
    if g_s is None:
        raise Reject("slip", "g is required for a comparison test")
    g = _parse(g_s, x, "g")
    if kind not in ("inf_upper", "singular_end"):
        raise Reject("redraw", "comparison tests are used on [A, oo) or on an interval with one singular end")
    if kind == "inf_upper" and a <= 0:
        raise Reject("slip", "the lower bound must be positive so that 1/x^p is defined")
    form = _p_form(g, a, b)
    if form is not None:
        p, point, _k = form
        if kind == "inf_upper" and point != 0:
            raise Reject("slip", "for an infinite upper bound a p-integral g must be c/x^p")
        if kind == "singular_end" and not (point in pts and point in (a, b)):
            raise Reject("slip", "g must be singular at the same end as f")
        converges_g = (p > 1) if kind == "inf_upper" else (p < 1)
        g_note = ("\\int_A^\\infty \\frac{dx}{x^p}\\text{ converges iff } p > 1" if kind == "inf_upper" else
                  "\\int_a^b \\frac{dx}{(x-a)^p}\\text{ converges iff } p < 1")
    else:                                   # any g whose own integral the server can evaluate
        G = _antiderivative(g, x)
        gval, _pieces, _gpts, _m = definite_ext(g, G, a, b, True)
        converges_g = gval is not None
        p = None
        g_note = "\\int g\\,dx " + ("\\text{ converges (it can be evaluated)}" if converges_g
                                          else "\\text{ diverges (it can be evaluated)}")
    steps = [{"text": "Choose a comparison function whose integral is known.", "latex": f"g(x) = {L(g)}",
              "sympy": str(g)},
             {"text": "State what is known about the integral of g.", "latex": g_note, "sympy": None}]
    if ask == "limit":
        target = sp.oo if kind == "inf_upper" else (a if pts and a in pts else b)
        side = "+" if kind == "inf_upper" or target == a else "-"
        ratio = sp.limit(sp.simplify(f / g), x, target, side)
        if not (ratio.is_finite and ratio.is_positive):
            raise Reject("redraw", "the limit of f/g is not a finite positive number, so the limit comparison "
                         "test does not apply")
        verdict = "converges" if converges_g else "diverges"
        steps.append({"text": "Take the limit of the ratio.", "latex": f"\\lim \\frac{{f(x)}}{{g(x)}} = {L(ratio)}",
                      "sympy": str(ratio)})
        method = "limit_comparison"
    else:
        dom = sp.Interval.open(a, sp.oo) if kind == "inf_upper" else sp.Interval.open(a, b)

        xp = sp.Symbol("x", positive=True)

        def proved_nonneg(expr) -> bool:
            d = sp.simplify(expr)
            if a >= 0 and sp.simplify(expr.subs(x, xp)).is_nonnegative:
                return True
            if d.is_nonnegative:
                return True
            try:
                return sp.solveset(d < 0, x, domain=dom) == sp.S.EmptySet
            except (NotImplementedError, ValueError, TypeError):
                return False

        if not proved_nonneg(f):
            raise Reject("redraw", "f must be provably nonnegative on the interval for a comparison test")
        if converges_g and proved_nonneg(g - f):
            verdict, rel = "converges", "\\le"
        elif not converges_g and proved_nonneg(f - g):
            verdict, rel = "diverges", "\\ge"
        else:
            raise Reject("redraw", "the direct comparison is inconclusive: f is on the wrong side of g, or the "
                         "inequality could not be proved")
        steps.append({"text": "Compare f with g on the interval.", "latex": f"0 \\le f(x) {rel} g(x)", "sympy": None})
        method = "direct_comparison"
    steps.append({"text": "Conclude.", "latex": f"\\text{{{verdict}}}", "sympy": None})
    if "verdict" in axes and str(axes["verdict"]) != verdict:
        raise Reject("redraw", f"axes: the server assigned verdict = {axes['verdict']} (this one {verdict})")
    if "ask" in axes and str(axes["ask"]) != ask:
        raise Reject("redraw", f"axes: the server assigned ask = {axes['ask']}")
    answer = {"type": "enum", "latex": f"\\text{{{verdict}}}", "sympy": None, "numeric": None}
    under = f"\\left({L(f)}\\right)" if isinstance(f, sp.Add) else L(f)
    statement = (f"Determine whether $\\displaystyle \\int_{{{L(a)}}}^{{{L(b)}}} {under}\\,dx$ converges or diverges. "
                 "Do not evaluate it; justify with a comparison test.")
    raw = {"ops_integrand": int(sp.count_ops(f)), "ops_R": int(sp.count_ops(f)), "ops_F": 0, "g_polynomial": True,
           "deg_g": None, "n_terms_R": len(sp.Add.make_args(sp.expand(f))), "const_factor": False, "definite": True,
           "has_discontinuity": bool(pts), "steps": len(steps), "answer_type": "enum", "rules": ["RewriteRule"],
           "type": kind, "ask": ask, "verdict": verdict, "p": str(p)}
    return {"ok": True, "statement": statement, "answer": answer, "steps": steps, "method": method,
            "calculator_check": "n/a", "hash": _hash(f, (a, b)), "shape": _shape(f, True) + f"|{ask}",
            "has_discontinuity": bool(pts), "integrand": str(f), "raw": raw}
