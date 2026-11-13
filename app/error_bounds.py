"""Verify a numerical-integration error-bound candidate and derive everything shown.

The model supplies f, the rule, n (or, for min_n, the tolerance eps) and the interval. The server finds the exact
maximum K of |f''| (trapezoid, midpoint) or |f''''| (Simpson) on [a, b] from the endpoints and the critical
points of that derivative, forms the standard bound, and cross-checks K against a dense sample. The question
is always well posed because the statement says to use the exact maximum: there is one correct answer.

  bound   the error bound for the given n:  K(b-a)^3 / (12 n^2)  trapezoid,  K(b-a)^3 / (24 n^2)  midpoint,
          K(b-a)^5 / (180 n^4)  Simpson.
  min_n   the smallest n (even for Simpson) for which that bound is at most eps.
  gap     how much larger the bound is than the actual error: bound - |exact integral - rule value|, for the given n.
"""
import mpmath as mp
import sympy as sp

from app.clean_answer import canon, value_reason
from app.integral_core import L, Reject, _hash, _parse, _shape, x
from app.integral_finish import bound_ext, fast_discontinuities, scientific_reason
from app.integral_core import _discontinuities
from app.rules import rule_value

RULES = ("midpoint", "trapezoid", "simpson")
ASKS = ("bound", "min_n", "gap")
NAME = {"midpoint": "midpoint", "trapezoid": "trapezoidal", "simpson": "Simpson's"}
ORDER = {"midpoint": 2, "trapezoid": 2, "simpson": 4}
MAX_N = 12


def verify(f: str, rule: str, n: str | None, ask: str, eps: str | None, bounds: list[str] | None,
           axes: dict | None = None, calculator: str = "none") -> dict:
    try:
        return _verify(f, rule, n, ask, eps, bounds, axes or {}, calculator)
    except Reject as r:
        return {"ok": False, "cause": r.cause, "reason": r.reason, "cap": r.cap}


def max_abs(fk, a, b):
    """The exact maximum of |fk| on [a, b]: endpoints plus critical points. Raises Reject if it cannot be found."""
    d = sp.diff(fk, x)
    if d == 0:
        return sp.Abs(fk.subs(x, a)), []
    try:
        crit = sp.solveset(d, x, sp.Interval(a, b))
    except (NotImplementedError, ValueError):
        raise Reject("redraw", "could not locate the critical points of the derivative") from None
    if crit == sp.S.EmptySet:
        crit = []
    elif isinstance(crit, sp.FiniteSet):
        crit = list(crit)
    else:
        raise Reject("redraw", "the critical points could not be found exactly")
    cands = [a, b, *[c for c in crit if sp.im(c) == 0]]
    vals = [(sp.simplify(sp.Abs(fk.subs(x, c))), c) for c in cands]
    best = max(vals, key=lambda t: float(sp.N(t[0])))
    return best[0], list(crit)


def _int(s, label, lo, hi):
    try:
        v = int(str(s).strip())
    except ValueError:
        raise Reject("slip", f"{label} must be an integer") from None
    if not lo <= v <= hi:
        raise Reject("slip", f"{label} must be between {lo} and {hi}")
    return v


def error_bound(K, a, b, n, rule):
    w = b - a
    if rule == "trapezoid":
        return K * w ** 3 / (12 * n ** 2)
    if rule == "midpoint":
        return K * w ** 3 / (24 * n ** 2)
    return K * w ** 5 / (180 * n ** 4)


def actual_error(f, a, b, n: int, rule: str):
    """(rule value, exact integral, |exact - rule value|), all exact. Raises Reject if the integral is not elementary."""
    dx = (b - a) / n
    pts = ([a + (i + sp.Rational(1, 2)) * dx for i in range(n)] if rule == "midpoint"
           else [a + i * dx for i in range(n + 1)])
    vals = []
    for p in pts:
        v = sp.simplify(f.subs(x, p))
        if v.has(sp.zoo, sp.nan, sp.oo, -sp.oo) or v.is_real is not True:
            raise Reject("redraw", "f is not a real number at a node")
        vals.append(v)
    approx = sp.simplify(rule_value(vals, a, b, n, rule))
    exact = sp.simplify(sp.integrate(f, (x, a, b)))
    if exact.has(sp.Integral, sp.erf, sp.zoo, sp.nan, sp.oo):
        raise Reject("redraw", "the exact integral is not elementary, so the actual error cannot be written exactly")
    mp.mp.dps = 25
    num = mp.quad(sp.lambdify(x, f, "mpmath"), [mp.mpf(str(sp.N(a, 25))), mp.mpf(str(sp.N(b, 25)))])
    if abs(num - mp.mpf(str(sp.N(exact, 25)))) > mp.mpf(10) ** -15:
        raise Reject("redraw", "the exact integral did not match numerical integration")
    return approx, exact, sp.simplify(sp.Abs(exact - approx))


def ftype(f) -> str:
    if f.is_polynomial(x):
        return f"poly{sp.degree(f, x)}"
    if f.has(sp.sin, sp.cos):
        return "trig"
    if f.has(sp.exp):
        return "exp"
    if f.has(sp.log):
        return "ln"
    if f.is_rational_function(x):
        return "rational"
    return "root" if f.has(sp.sqrt(x)) else "other"


def _verify(f_s, rule, n_s, ask, eps_s, bounds, axes, calculator):
    if rule not in RULES:
        raise Reject("slip", f"rule must be one of {', '.join(RULES)}")
    if ask not in ASKS:
        raise Reject("slip", f"ask must be one of {', '.join(ASKS)}")
    if not bounds or len(bounds) != 2:
        raise Reject("slip", "bounds are required")
    a, b = bound_ext(bounds[0], "lower bound"), bound_ext(bounds[1], "upper bound")
    if a in (sp.oo, -sp.oo) or b in (sp.oo, -sp.oo) or not a < b:
        raise Reject("slip", "bounds must be finite with lower < upper")
    f = _parse(f_s, x, "f")
    pts = fast_discontinuities(f, a, b)
    if pts is None:
        pts = _discontinuities(f, a, b)
    if pts:
        raise Reject("redraw", "f (or a derivative) is undefined at a point of [a, b]")
    k = ORDER[rule]
    fk = sp.simplify(sp.diff(f, x, k))
    if fk == 0:
        raise Reject("redraw", f"the derivative of order {k} is 0, so the rule is exact and the bound is 0")
    if fk.has(sp.zoo, sp.nan, sp.oo):
        raise Reject("redraw", "the derivative is undefined on the interval")
    K, crit = max_abs(fk, a, b)
    if K == 0 or K.has(sp.zoo, sp.nan, sp.oo):
        raise Reject("redraw", "the maximum of the derivative could not be found")
    # cross-check K against a dense sample of |f^(k)|
    mp.mp.dps = 25
    fl = sp.lambdify(x, fk, "mpmath")
    lo, hi = float(sp.N(a)), float(sp.N(b))
    sample = max(abs(mp.mpf(fl(mp.mpf(lo + (hi - lo) * i / 2000)))) for i in range(2001))
    Kf = float(sp.N(K))
    if sample > Kf * (1 + 1e-9) or sample < Kf * (1 - 5e-3):
        raise Reject("redraw", "the maximum of the derivative did not match a dense numerical sample")
    if ask in ("bound", "gap"):
        n = _int(n_s, "n", 1, MAX_N)
        if rule == "simpson" and n % 2:
            raise Reject("slip", "Simpson's rule needs an even n")
        result = sp.simplify(error_bound(K, a, b, n, rule))
        eps = None
        if ask == "gap":
            approx, exact, actual = actual_error(f, a, b, n, rule)
            bound = result
            result = sp.simplify(bound - actual)
            if float(sp.N(result)) < -1e-12:
                raise Reject("redraw", "internal check failed: the actual error exceeds the bound")
            if result == 0 or abs(float(sp.N(result))) < 1e-12:
                raise Reject("redraw", "the bound equals the actual error, so the difference is 0")
    else:
        if calculator != "scientific" and any(c.has(sp.pi) for c in (a, b)):
            raise Reject("redraw", "min_n at the none tier: an interval with pi needs a hand estimate of a power of pi")
        if not eps_s:
            raise Reject("slip", "eps is required for min_n")
        try:
            eps = sp.Rational(str(eps_s))
        except (TypeError, ValueError):
            raise Reject("slip", "eps must be a rational number such as 1/1000") from None
        if not (0 < eps < 1):
            raise Reject("slip", "eps must be between 0 and 1")
        w = b - a
        base = {"trapezoid": K * w ** 3 / (12 * eps), "midpoint": K * w ** 3 / (24 * eps),
                "simpson": K * w ** 5 / (180 * eps)}[rule]
        root = sp.sqrt(base) if rule != "simpson" else base ** sp.Rational(1, 4)
        n = int(sp.ceiling(sp.N(root, 30)))
        if rule == "simpson" and n % 2:
            n += 1
        n = max(n, 2 if rule == "simpson" else 1)
        if n > 5000 or n < 1:
            raise Reject("redraw", "n is too large")
        step = 2 if rule == "simpson" else 1
        if not sp.simplify(error_bound(K, a, b, n, rule) - eps) <= 0:
            raise Reject("redraw", "internal check failed: the bound exceeds eps at the chosen n")
        if n - step >= 1 and not error_bound(K, a, b, n - step, rule) > eps:
            raise Reject("redraw", "internal check failed: a smaller n also works")
        result = sp.Integer(n)
        if rule != "simpson" and n > 200:
            raise Reject("redraw", "n is too large for a worked problem")
    for key, val in (("rule", rule), ("ask", ask)):
        if key in axes and str(axes[key]) != str(val):
            raise Reject("redraw", f"axes: the server assigned {key} = {axes[key]} (not {val})")
    if "ftype" in axes and str(axes["ftype"]) != ftype(f):
        raise Reject("redraw", f"axes: the server assigned ftype = {axes['ftype']} (not {ftype(f)})")
    if "interior" in axes and bool(axes["interior"]) != any(c not in (a, b) for c in crit if a < c < b):
        raise Reject("redraw", "axes: the server assigned whether the maximum of the derivative is interior")
    if ask != "min_n" and calculator == "scientific":
        if r := scientific_reason(result):
            raise Reject("redraw", f"answer is not a usable decimal ({r})", cap=r)
        latex = f"{float(sp.N(result)):.3f}" if float(sp.N(result)) >= 0.001 else f"{float(sp.N(result)):.6f}"
    elif ask != "min_n":
        if r := value_reason(result, True):
            raise Reject("redraw", f"answer is not a short exact form ({r})", cap=r)
        result = canon(result)
        latex = L(result)
    else:
        latex = str(int(result))
    deriv = {2: "f''", 4: "f^{(4)}"}[k]
    steps = [
        {"text": f"Find the derivative that controls the error: {deriv}.", "latex": f"{deriv}(x) = {L(fk)}", "sympy": str(fk)},
        {"text": "Find the largest value of its absolute value on the interval (check the endpoints and the "
                 "critical points).", "latex": f"K = \\max_{{[{L(a)},\\,{L(b)}]}} |{deriv}(x)| = {L(K)}", "sympy": str(K)},
        {"text": f"Write the error bound for the {NAME[rule]} rule.",
         "latex": {"trapezoid": "|E_T| \\le \\frac{K(b-a)^3}{12n^2}", "midpoint": "|E_M| \\le \\frac{K(b-a)^3}{24n^2}",
                   "simpson": "|E_S| \\le \\frac{K(b-a)^5}{180n^4}"}[rule], "sympy": None},
    ]
    if ask == "bound":
        steps.append({"text": "Substitute K, a, b and n.", "latex": f"{L(result)}", "sympy": str(result)})
    elif ask == "gap":
        steps += [
            {"text": "Substitute K, a, b and n to get the error bound.", "latex": f"{L(bound)}", "sympy": str(bound)},
            {"text": f"Apply the {NAME[rule]} rule with n = {n}.", "latex": f"{L(approx)}", "sympy": str(approx)},
            {"text": "Find the exact integral and the actual error.",
             "latex": f"\\left|{L(exact)} - ({L(approx)})\\right| = {L(actual)}", "sympy": str(actual)},
            {"text": "Subtract the actual error from the bound.", "latex": f"{L(bound)} - ({L(actual)}) = {L(result)}",
             "sympy": str(result)}]
    else:
        steps.append({"text": "Solve the inequality for n and round up" + (" to the next even integer." if rule == "simpson" else "."),
                      "latex": f"n \\ge {L(sp.N(root, 6))}\\ \\Rightarrow\\ n = {n}", "sympy": str(n)})
    under = f"\\left({L(f)}\\right)" if isinstance(f, sp.Add) else L(f)
    lim = f"$\\displaystyle \\int_{{{L(a)}}}^{{{L(b)}}} {under}\\,dx$"
    unit = ("Give the answer to three decimal places." if calculator == "scientific" and ask != "min_n"
            else "Give an exact answer." if ask != "min_n" else "Give the integer.")
    if ask == "bound":
        statement = (f"Use the exact maximum of $|{deriv}|$ on the interval to find the error bound for the {NAME[rule]} "
                     f"rule with n = {n} applied to {lim}. {unit}")
    elif ask == "gap":
        statement = (f"For the {NAME[rule]} rule with n = {n} applied to {lim}, find the error bound (using the exact "
                     f"maximum of $|{deriv}|$) minus the actual error |exact value - approximation|. {unit}")
    else:
        statement = (f"Find the smallest n{' (even)' if rule == 'simpson' else ''} for which the error bound of the "
                     f"{NAME[rule]} rule for {lim} is at most ${L(eps)}$, using the exact maximum of $|{deriv}|$. {unit}")
    answer = {"type": "numeric", "latex": latex, "sympy": str(result), "numeric": float(sp.N(result))}
    raw = {"ops_integrand": int(sp.count_ops(f)), "ops_R": 1, "ops_F": 1, "g_polynomial": True, "deg_g": None,
           "n_terms_R": len(sp.Add.make_args(sp.expand(f))), "const_factor": False, "definite": True,
           "has_discontinuity": False, "steps": len(steps), "answer_type": "numeric", "rules": ["RewriteRule"],
           "rule": rule, "n": n, "ask": ask, "ftype": ftype(f), "interior": bool(any(a < c < b for c in crit))}
    return {"ok": True, "statement": statement, "answer": answer, "steps": steps, "method": "exact_max+mpmath",
            "calculator_check": "passed", "hash": _hash(sp.Symbol(str((str(f), rule, ask, str(n_s), str(eps_s)))), (a, b)),
            "shape": _shape(f, True) + f"|{rule}|{ask}", "has_discontinuity": False, "integrand": str(f), "raw": raw}
