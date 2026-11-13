"""Verify a trigonometric-substitution candidate and derive the worked solution.

The model names the kind of radical (a^2 - x^2, a^2 + x^2 or x^2 - a^2), the constant a, the exponent p of the
radical (an odd integer: the integrand is num(x) * sqrt(S)^p) and a polynomial numerator, plus an optional
shift h when the radicand is a completed square (x + h)^2 + .. written expanded. The server does the
substitution itself: x = a sin t, a tan t or a sec t, the radical, dx, the integral in t (through the
trigonometric-integral engine), the reference triangle and the back-substitution. Every step is derived, and the
final antiderivative is checked by differentiating it against the original integrand.
"""
import sympy as sp

from app.calc2 import trigfam
from app.shared.integral_core import L, Reject, _parse, _tidy, x
from app.shared.integral_finish import bound_ext, finish, table_ok

t = sp.Symbol("theta", real=True)
KINDS = ("a2-x2", "a2+x2", "x2-a2")
SUB = {"a2-x2": "x = {a}\\sin\\theta", "a2+x2": "x = {a}\\tan\\theta", "x2-a2": "x = {a}\\sec\\theta"}


def verify(kind: str, a: str, num: str, p: str, h: str | None = None, bounds=None, axes: dict | None = None,
           calculator: str = "none") -> dict:
    try:
        return _verify(kind, a, num, p, h, bounds, axes or {}, calculator)
    except Reject as r:
        return {"ok": False, "cause": r.cause, "reason": r.reason, "cap": r.cap}


def _int(s, label, lo, hi):
    try:
        v = int(str(s).strip())
    except ValueError:
        raise Reject("slip", f"{label} must be an integer") from None
    if not lo <= v <= hi:
        raise Reject("slip", f"{label} must be between {lo} and {hi}")
    return v


def _back_map(kind, a, r):
    """Trig functions of theta as expressions in x, from the reference triangle."""
    if kind == "a2-x2":
        return {sp.sin(t): x / a, sp.cos(t): r / a, sp.tan(t): x / r, sp.sec(t): a / r, sp.csc(t): a / x,
                sp.cot(t): r / x}, sp.asin(x / a)
    if kind == "a2+x2":
        return {sp.sin(t): x / r, sp.cos(t): a / r, sp.tan(t): x / a, sp.sec(t): r / a, sp.csc(t): r / x,
                sp.cot(t): a / x}, sp.atan(x / a)
    return {sp.sin(t): r / x, sp.cos(t): a / x, sp.tan(t): r / a, sp.sec(t): x / a, sp.csc(t): x / r,
            sp.cot(t): a / r}, sp.acos(a / x)


def _drop_log_constants(F):
    """ln|(x + r)/a| is shown as ln|x + r|: the constant -ln a is absorbed into C, as a textbook writes it."""
    def fix(e):
        inner = e.args[0]
        core = inner.args[0] if isinstance(inner, sp.Abs) else inner
        c, rest = sp.factor_terms(core).as_independent(x, as_Add=False)
        if c.is_Rational and c != 1 and rest.has(x):
            return sp.log(sp.Abs(rest)) if isinstance(inner, sp.Abs) else sp.log(rest)
        return e
    return F.replace(lambda e: isinstance(e, sp.log), fix)


def _theta_integral(g):
    """(G(theta), steps, tech) for the integrand in theta, by the trigonometric-integral engine when the
    integrand is a product of sin and cos powers (or tan and sec), else SymPy."""
    gx = g.subs(t, x)
    c, rest = gx.as_independent(x, as_Add=False)
    pw = sp.powsimp(sp.simplify(rest.rewrite(sp.cos))).as_powers_dict() if rest != 1 else {}
    m = pw.get(sp.sin(x), 0)
    n = pw.get(sp.cos(x), 0)
    other = [k for k in pw if k not in (sp.sin(x), sp.cos(x))]
    if not other and c.is_Rational and all(sp.Integer(v) == v for v in (m, n)):
        m, n = int(m), int(n)
        fam = None
        if m >= 0 and n >= 0 and m + n > 0:
            tech = "u_cos" if m % 2 else "u_sin" if n % 2 else "reduce"
            fam = {"family": "sc", "k": 1, "m": m, "n": n, "c": c, "tech": tech}
        elif m >= 0 and n < 0 and -(m + n) >= 0:
            mm, ee = m, -(m + n)
            tech = ("u_tan" if ee % 2 == 0 and ee >= 2 else "u_sec" if mm % 2 and ee >= 1
                    else "tan_reduce" if ee == 0 else "sec_reduce")
            fam = {"family": "ts", "k": 1, "m": mm, "n": ee, "c": c, "tech": tech}
        if fam is not None:
            try:
                F, _, steps = trigfam.antiderivative(fam, False)
                return F.subs(x, t), steps, fam["tech"]
            except Exception:
                pass
    G = sp.integrate(g, t)
    if G.has(sp.Integral):
        raise Reject("redraw", "the integral in theta has no elementary antiderivative")
    return G, [], "sympy"


def _verify(kind, a_s, num_s, p_s, h_s, bounds, axes, calculator):
    if kind not in KINDS:
        raise Reject("slip", f"kind must be one of {', '.join(KINDS)}")
    a = _int(a_s, "a", 1, 6)
    p = _int(p_s, "p", -5, 5)
    h = _int(h_s, "h", -4, 4) if h_s not in (None, "") else 0
    if p % 2 == 0:
        raise Reject("slip", "p must be odd (the radical is sqrt(S)^p)")
    N = _parse(num_s, x, "num", depends=False)
    if not (N.is_polynomial(x) and sp.degree(N, x) <= 4 and all(c.is_Integer for c in sp.Poly(N, x).coeffs())):
        raise Reject("slip", "num must be a polynomial in x of degree at most 4 with integer coefficients")
    S0 = {"a2-x2": a ** 2 - x ** 2, "a2+x2": a ** 2 + x ** 2, "x2-a2": x ** 2 - a ** 2}[kind]
    u_shift = x + h
    # the problem in terms of w = x + h: the integrand num(w) * S0(w)^(p/2); shown with w replaced by x + h
    f0 = N * S0 ** sp.Rational(p, 2)
    f = sp.expand(S0.subs(x, u_shift)) ** sp.Rational(p, 2) if h else f0      # the radicand is shown expanded
    if h and N != 1:
        raise Reject("redraw", "a completed-square shift is only used with num = 1")
    ax = {"kind": kind, "p": p, "a": a, "num_deg": int(sp.degree(N, x)) if N.has(x) else 0, "h": h}
    for key in ("kind", "p", "a", "num_deg", "h"):
        if key in axes and str(axes[key]) != str(ax[key]):
            raise Reject("redraw", f"axes: the server assigned {key} = {axes[key]} (not {ax[key]})")
    if kind == "a2-x2" and N == 1 and p == -1 and not h:
        raise Reject("redraw", "1/sqrt(a^2 - x^2) is the standard arcsin form: no substitution is needed")
    if (N != 1 or p != -1) and table_ok(f0, x):
        raise Reject("redraw", "a substitution u = g(x) solves this without a trigonometric substitution")
    # the substitution in t
    xs, R, dxdt = {"a2-x2": (a * sp.sin(t), a * sp.cos(t), a * sp.cos(t)),
                   "a2+x2": (a * sp.tan(t), a * sp.sec(t), a * sp.sec(t) ** 2),
                   "x2-a2": (a * sp.sec(t), a * sp.tan(t), a * sp.sec(t) * sp.tan(t))}[kind]
    g = sp.simplify(N.subs(x, xs) * R ** p * dxdt)
    G, tsteps, tech = _theta_integral(g)
    r = sp.sqrt(S0)
    back, theta_back = _back_map(kind, a, r)
    F0 = sp.expand_trig(G).subs(back).subs(t, theta_back)
    F0 = _drop_log_constants(sp.simplify(F0))
    F = F0.subs(x, u_shift) if h else F0
    # a log of a positive quantity does not need absolute value bars; keep them off the radical forms
    F = sp.simplify(F) if sp.count_ops(F) < 60 else F
    a_b = None
    if bounds is not None:
        a_b = (bound_ext(bounds[0], "lower bound"), bound_ext(bounds[1], "upper bound"))
    side = {"a2-x2": "\\sqrt{{{a}^2 - x^2}} = {a}\\cos\\theta \\quad (-\\pi/2 < \\theta < \\pi/2)",
            "a2+x2": "\\sqrt{{{a}^2 + x^2}} = {a}\\sec\\theta \\quad (-\\pi/2 < \\theta < \\pi/2)",
            "x2-a2": "\\sqrt{{x^2 - {a}^2}} = {a}\\tan\\theta \\quad (0 < \\theta < \\pi/2)"}[kind]
    steps = []
    if h:
        steps.append({"text": "Complete the square: the radicand is a sum or difference of squares in w = x + h.",
                      "latex": f"{L(S0.subs(x, u_shift).expand())} = {L(S0.subs(x, u_shift))}", "sympy": None})
        steps.append({"text": "Let w = x + h, so that dw = dx.", "latex": f"w = x + {h}" if h > 0 else f"w = x - {-h}",
                      "sympy": None})
    steps += [
        {"text": f"Choose the trigonometric substitution (a = {a}).", "latex": SUB[kind].format(a=a), "sympy": str(xs)},
        {"text": "Differentiate.", "latex": f"dx = {L(dxdt)}\\,d\\theta", "sympy": str(dxdt)},
        {"text": "Simplify the radical.", "latex": side.format(a=a), "sympy": str(R)},
        {"text": "Rewrite the integral in theta and simplify.", "latex": f"\\int {L(g)}\\,d\\theta", "sympy": str(g)},
    ]
    steps += [s for s in tsteps if s.get("text")] if tsteps else []
    steps.append({"text": "Integrate in theta.", "latex": f"{L(G)} + C", "sympy": str(G)})
    steps.append({"text": "Use the reference triangle to express the trigonometric functions in x.",
                  "latex": ",\\quad ".join(f"{L(k)} = {L(v)}" for k, v in list(back.items())[:3]), "sympy": None})
    steps.append({"text": "Substitute back.", "latex": f"{L(F)} + C", "sympy": str(F)})
    extra = {"kind": kind, "a": a, "p": p, "num_deg": ax["num_deg"], "h": h, "tech": tech,
             "rules": ["TrigSubstitutionRule"] + (["RewriteRule"] if tech in ("reduce", "prod_sum") else [])}
    shown = f
    return finish(f, F, shown, steps, a_b, calculator=calculator, allow_improper=False,
                  how="Find an antiderivative by trigonometric substitution.", extra_raw=extra)
