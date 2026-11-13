"""Verify a numerical-integration candidate (midpoint, trapezoid, Simpson) and derive everything shown.

The model supplies f (or a table of values), the rule, n, the bounds and what is asked: the approximation, the
exact error of the approximation, or a table problem. The server computes the rule exactly from f at the nodes
with SymPy (so the answer is an exact number), cross-checks it with an independent floating-point sum, and for
an error question also computes the exact integral. Calculator tiers: none (exact short form) and scientific
(three decimals).
"""
import mpmath as mp
import sympy as sp

from app.clean_answer import canon, value_reason
from app.integral_core import L, Reject, _discontinuities, _hash, _parse, _shape, x
from app.integral_finish import bound_ext, fast_discontinuities, scientific_reason

RULES = ("midpoint", "trapezoid", "simpson")
ASKS = ("approx", "error", "table")
NAME = {"midpoint": "midpoint", "trapezoid": "trapezoidal", "simpson": "Simpson's"}
MAX_N = 8


def verify(f: str | None, rule: str, n: str, ask: str, values: str | None, bounds: list[str] | None,
           axes: dict | None = None, calculator: str = "none") -> dict:
    try:
        return _verify(f, rule, n, ask, values, bounds, axes or {}, calculator)
    except Reject as r:
        return {"ok": False, "cause": r.cause, "reason": r.reason, "cap": r.cap}


def ftype(f) -> str:
    if f.is_polynomial(x):
        return f"poly{sp.degree(f, x)}"
    if f.has(sp.sin, sp.cos):
        return "trig"
    if f.has(sp.exp):
        return "exp"
    if f.has(sp.log):
        return "ln"
    if f.has(sp.sqrt(x)) or any(p.exp.is_Rational and not p.exp.is_Integer for p in f.atoms(sp.Pow)):
        return "root"
    if f.is_rational_function(x):
        return "rational"
    return "other"


def rule_value(vals: list, a, b, n: int, rule: str):
    """The rule from the values at the nodes (n + 1 values for trapezoid and Simpson, n midpoints for midpoint)."""
    dx = (b - a) / n
    if rule == "trapezoid":
        return dx / 2 * (vals[0] + 2 * sum(vals[1:-1]) + vals[-1])
    if rule == "midpoint":
        return dx * sum(vals)
    return dx / 3 * (vals[0] + 4 * sum(vals[1:-1:2]) + 2 * sum(vals[2:-1:2]) + vals[-1])


def _int(s, label, lo, hi):
    try:
        v = int(str(s).strip())
    except ValueError:
        raise Reject("slip", f"{label} must be an integer") from None
    if not lo <= v <= hi:
        raise Reject("slip", f"{label} must be between {lo} and {hi}")
    return v


def _verify(f_s, rule, n_s, ask, values_s, bounds, axes, calculator):
    if rule not in RULES:
        raise Reject("slip", f"rule must be one of {', '.join(RULES)}")
    if ask not in ASKS:
        raise Reject("slip", f"ask must be one of {', '.join(ASKS)}")
    if not bounds or len(bounds) != 2:
        raise Reject("slip", "bounds are required")
    a, b = bound_ext(bounds[0], "lower bound"), bound_ext(bounds[1], "upper bound")
    if a in (sp.oo, -sp.oo) or b in (sp.oo, -sp.oo):
        raise Reject("slip", "bounds must be finite")
    if not a < b:
        raise Reject("slip", "lower bound must be less than upper bound")
    n = _int(n_s, "n", 1, MAX_N)
    if rule == "simpson" and (n % 2 or n < 2):
        raise Reject("slip", "Simpson's rule needs an even n of at least 2")
    dx = (b - a) / n
    nodes = [a + i * dx for i in range(n + 1)]
    mids = [a + (i + sp.Rational(1, 2)) * dx for i in range(n)]
    pts = mids if rule == "midpoint" else nodes
    f = None
    if ask == "table":
        if rule == "midpoint":
            raise Reject("redraw", "a data table gives values at the nodes, so use the trapezoidal or Simpson rule")
        try:
            vals = [sp.Rational(v.strip()) for v in (values_s or "").split(",") if v.strip()]
        except (TypeError, ValueError):
            raise Reject("slip", "values must be comma-separated rational numbers") from None
        if len(vals) != n + 1:
            raise Reject("slip", f"a table for n = {n} needs {n + 1} values")
        f_text = None
    else:
        if not f_s:
            raise Reject("slip", "f is required")
        f = _parse(f_s, x, "f")
        pts_bad = fast_discontinuities(f, a, b)
        if pts_bad is None:
            pts_bad = _discontinuities(f, a, b)
        if pts_bad:
            raise Reject("redraw", "f is undefined at a point of [a, b]")
        vals = []
        for p in pts:
            v = sp.simplify(f.subs(x, p))
            if v.has(sp.zoo, sp.nan, sp.oo, -sp.oo) or v.is_real is not True:
                raise Reject("redraw", "f is not a real number at a node")
            vals.append(v)
        f_text = f"\\left({L(f)}\\right)" if isinstance(f, sp.Add) else L(f)
    for key, val in (("rule", rule), ("n", n), ("ask", ask)):
        if key in axes and str(axes[key]) != str(val):
            raise Reject("redraw", f"axes: the server assigned {key} = {axes[key]} (not {val})")
    if f is not None and "ftype" in axes and str(axes["ftype"]) != ftype(f):
        raise Reject("redraw", f"axes: the server assigned ftype = {axes['ftype']} (not {ftype(f)})")
    approx = sp.simplify(rule_value(vals, a, b, n, rule))
    # an independent floating-point evaluation of the same rule
    mp.mp.dps = 30
    fl = [mp.mpf(str(sp.N(v, 30))) for v in vals]
    da, db = mp.mpf(str(sp.N(a, 30))), mp.mpf(str(sp.N(b, 30)))
    check = rule_value(fl, da, db, n, rule)
    if abs(check - mp.mpf(str(sp.N(approx, 30)))) > mp.mpf(10) ** -20 * max(1, abs(check)):
        raise Reject("redraw", "the exact and floating-point values of the rule disagree")
    result, exact = approx, None
    if ask == "error":
        exact = sp.simplify(sp.integrate(f, (x, a, b)))
        if exact.has(sp.Integral) or exact.has(sp.zoo, sp.nan, sp.oo):
            raise Reject("redraw", "the exact integral is not elementary, so the error cannot be written exactly")
        result = sp.simplify(sp.Abs(exact - approx))
        if result == 0:
            raise Reject("redraw", "the rule is exact for this f, so the error is 0")
    if calculator == "scientific":
        if r := scientific_reason(result):
            raise Reject("redraw", f"answer is not a usable decimal ({r})", cap=r)
        latex = f"{float(sp.N(result)):.3f}"
    else:
        if r := value_reason(result, True):
            raise Reject("redraw", f"answer is not a short exact form ({r})", cap=r)
        result = canon(result)
        latex = L(result)
    steps = [
        {"text": "Find the width of each subinterval.", "latex": f"\\Delta x = \\frac{{{L(b)} - {L(a)}}}{{{n}}} = {L(dx)}",
         "sympy": str(dx)},
        {"text": "List the " + ("midpoints" if rule == "midpoint" else "nodes") + ".",
         "latex": ",\\ ".join(f"{L(p)}" for p in pts), "sympy": None},
        {"text": "Evaluate f at each point." if f is not None else "Read the values from the table.",
         "latex": ",\\ ".join(L(v) for v in vals), "sympy": str(vals)},
        {"text": f"Apply the {NAME[rule]} rule.",
         "latex": {"trapezoid": "\\frac{\\Delta x}{2}\\left[f_0 + 2f_1 + \\cdots + 2f_{n-1} + f_n\\right]",
                   "midpoint": "\\Delta x\\left[f(m_1) + f(m_2) + \\cdots + f(m_n)\\right]",
                   "simpson": "\\frac{\\Delta x}{3}\\left[f_0 + 4f_1 + 2f_2 + \\cdots + 4f_{n-1} + f_n\\right]"}[rule]
         + f" = {L(approx)}", "sympy": str(approx)},
    ]
    if ask == "error":
        steps.append({"text": "Find the exact integral and subtract.",
                      "latex": f"\\left|{L(exact)} - ({L(approx)})\\right| = {L(result)}", "sympy": str(result)})
    end = "Give the answer to three decimal places." if calculator == "scientific" else "Give an exact answer."
    lim = f"$\\displaystyle \\int_{{{L(a)}}}^{{{L(b)}}}"
    if ask == "table":
        table = ", ".join(f"f({L(p)}) = {L(v)}" for p, v in zip(nodes, vals))
        statement = (f"A function f has the values {table}. Use the {NAME[rule]} rule with n = {n} to approximate "
                     f"{lim} f(x)\\,dx$. {end}")
    elif ask == "error":
        statement = (f"Use the {NAME[rule]} rule with n = {n} to approximate {lim} {f_text}\\,dx$, then find the "
                     f"absolute error |exact value - approximation|. {end}")
    else:
        statement = f"Use the {NAME[rule]} rule with n = {n} to approximate {lim} {f_text}\\,dx$. {end}"
    answer = {"type": "numeric", "latex": latex, "sympy": str(result), "numeric": float(sp.N(result))}
    raw = {"ops_integrand": int(sp.count_ops(f)) if f is not None else 2, "ops_R": 1, "ops_F": 1, "g_polynomial": True,
           "deg_g": None, "n_terms_R": len(sp.Add.make_args(sp.expand(f))) if f is not None else 1,
           "const_factor": False, "definite": True, "has_discontinuity": False, "steps": len(steps),
           "answer_type": "numeric", "rules": ["RewriteRule"], "rule": rule, "n": n, "ask": ask,
           "ftype": ftype(f) if f is not None else "table"}
    key = (str(f) if f is not None else str(vals), rule, n, ask)
    return {"ok": True, "statement": statement, "answer": answer, "steps": steps, "method": "exact_rule+mpmath",
            "calculator_check": "passed", "hash": _hash(sp.Symbol(str(key)), (a, b)),
            "shape": (_shape(f, True) if f is not None else "table") + f"|{rule}|{n}|{ask}",
            "has_discontinuity": False, "integrand": str(f) if f is not None else "table", "raw": raw}
