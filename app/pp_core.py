"""Shared pieces of the parametric and polar verifiers; called only by the sandbox worker."""
import hashlib
import json
import math

import mpmath as mp
import sympy as sp

from app import integration_basics as c4
from app.clean_answer import canon, expression_reason
from app.integral_core import L, Reject, _parse, x

t = sp.Symbol("t", real=True)
th = sp.Symbol("theta", real=True)

GRID = 401
SIGN_TOL = 1e-9
POLYLINE_N = 4000


def exact(s, label):
    if not isinstance(s, str):
        raise Reject("slip", f"{label} is required as a string")
    return c4._exact(s, label)


def interval(lo_s, hi_s, label="t"):
    lo, hi = exact(lo_s, f"{label}0"), exact(hi_s, f"{label}1")
    if not lo < hi:
        raise Reject("slip", f"{label}0 must be less than {label}1")
    return lo, hi


def _linear(arg, sym):
    if not arg.is_polynomial(sym) or sp.degree(arg, sym) != 1 or arg.free_symbols != {sym}:
        return False
    return all(c.is_Rational for c in sp.Poly(arg, sym).all_coeffs())


def curve_expr(s, sym, label):
    """Parse one coordinate function and enforce the shared scope whitelist."""
    if not isinstance(s, str):
        raise Reject("slip", f"{label} must be a string")
    e = _parse(s, sym, label, depends=False)
    if e.has(sp.Float) or sp.count_ops(e) > 30:
        raise Reject("redraw", f"{label} must use exact numbers and at most 30 operations")
    for f in e.atoms(sp.Function):
        if f.func not in (sp.sin, sp.cos, sp.exp) or not _linear(f.args[0], sym):
            raise Reject("redraw", f"{label} is outside the scope whitelist (sin, cos, exp of a linear argument)")
    for p in e.atoms(sp.Pow):
        base, ex = p.as_base_exp()
        small_int = ex.is_Integer and 0 < ex <= 6
        recip = ex.is_Integer and -3 <= ex < 0 and base.is_polynomial(sym) and sp.degree(base, sym) <= 3
        root = ex.is_Rational and ex.q == 2 and abs(ex.p) <= 3 and base.is_polynomial(sym) and sp.degree(base, sym) <= 2
        if not (small_int or recip or root):
            raise Reject("redraw", f"{label} is outside the scope whitelist (small powers, reciprocals, square roots)")
    return e


def family_of(*exprs):
    """Coarse class of a set of coordinate functions: polynomial, rational, sqrt, trig, exp or exp_trig."""
    has = lambda *cls: any(e.has(*cls) for e in exprs)
    if has(sp.exp) and has(sp.sin, sp.cos):
        return "exp_trig"
    if has(sp.sin, sp.cos):
        return "trig"
    if has(sp.exp):
        return "exp"
    if any(p.exp.is_Rational and p.exp.q == 2 for e in exprs for p in e.atoms(sp.Pow)):
        return "sqrt"
    if all(e.is_polynomial(*e.free_symbols) for e in exprs):
        return "polynomial"
    return "rational"


def check_axes(axes, **actual):
    for key, want in axes.items():
        if key != "recipe" and key in actual and str(actual[key]) != str(want):
            raise Reject("redraw", f"axes: the server assigned {key} = {want} (not {actual[key]})")


def _points(lo, hi, n):
    a, b = float(lo), float(hi)
    return [a + (b - a) * i / (n - 1) for i in range(n)]


def float_fn(e, sym):
    return sp.lambdify(sym, e, "math")


def finite_on(exprs, sym, lo, hi, label="the curve"):
    """Each expression is real and finite on a dense grid of [lo, hi]."""
    for e in exprs:
        f = float_fn(e, sym)
        for p in _points(lo, hi, GRID):
            try:
                v = f(p)
            except (ValueError, ZeroDivisionError, OverflowError):
                raise Reject("redraw", f"{label} is not defined and finite on the whole interval") from None
            if isinstance(v, complex) or not math.isfinite(v) or abs(v) > 1e8:
                raise Reject("redraw", f"{label} is not defined and finite on the whole interval")


def sign_on(e, sym, lo, hi):
    """'pos' (>= 0), 'neg' (<= 0), 'zero' or 'mixed' for e on [lo, hi], from a dense grid."""
    f = float_fn(e, sym)
    vals = [f(p) for p in _points(lo, hi, 4 * GRID)]
    if all(abs(v) <= SIGN_TOL for v in vals):
        return "zero"
    if all(v >= -SIGN_TOL for v in vals):
        return "pos"
    if all(v <= SIGN_TOL for v in vals):
        return "neg"
    return "mixed"


def unabs(e, sym, lo, hi):
    """Drop each |g| whose sign is constant on [lo, hi]; reject a sign change."""
    for a in sorted(e.atoms(sp.Abs), key=lambda z: -sp.count_ops(z)):
        s = sign_on(a.args[0], sym, lo, hi)
        if s == "mixed":
            raise Reject("redraw", "the integrand has an absolute value whose sign changes on the interval")
        e = e.subs(a, a.args[0] if s != "neg" else -a.args[0])
    return e


def _direct_root(s2, sym):
    return sp.simplify(sp.sqrt(s2))


def _factored_root(s2, sym):
    return sp.powdenest(sp.sqrt(sp.factor(s2)), force=True)


def _half_angle_root(s2, sym):
    """A trig radicand such as 2 - 2cos(t) is a square in t/2: substitute t = 2u, take the root, go back."""
    doubled = sp.simplify(sp.expand_trig(s2.subs(sym, 2 * sym)))
    return sp.simplify(sp.sqrt(doubled)).subs(sym, sym / 2)


def _same_speed(speed, s2, sym, lo, hi):
    f, g = float_fn(speed, sym), float_fn(s2, sym)
    for p in _points(lo, hi, 25):
        if abs(f(p) - math.sqrt(max(g(p), 0.0))) > 1e-9 * max(1.0, abs(f(p))):
            raise Reject("redraw", "could not simplify the speed to a sign-free closed form")


def integrate_speed(s2, sym, lo, hi, weight=1):
    """(speed, exact integral of weight * speed) where speed = sqrt(s2) as a sign-free closed form."""
    s2 = sp.simplify(s2)
    makers = ((_half_angle_root, _direct_root) if s2.has(sp.sin, sp.cos) else (_factored_root, _direct_root))
    first = None
    for make in makers:
        try:
            speed = unabs(make(s2, sym), sym, lo, hi)
            _same_speed(speed, s2, sym, lo, hi)
            return speed, exact_integral(sp.expand(weight * speed), sym, lo, hi)
        except Reject as r:
            first = first or r
    raise first


def exact_integral(f, sym, lo, hi):
    """The exact definite integral, or a rejection when SymPy has no closed form."""
    v = sp.integrate(f, (sym, lo, hi))
    if v.has(sp.Integral, sp.Piecewise, sp.nan, sp.zoo, sp.oo, -sp.oo):
        F = sp.integrate(f, sym)
        if F.has(sp.Integral, sp.Piecewise):
            raise Reject("redraw", "the integral has no closed form in the supported scope")
        v = F.subs(sym, hi) - F.subs(sym, lo)
    if v.has(sp.Integral, sp.Piecewise, sp.nan, sp.zoo, sp.oo, -sp.oo) or v.is_real is not True:
        raise Reject("redraw", "the integral has no closed form in the supported scope")
    return canon(v)


def numeric_answer(value, calculator):
    return c4._answer(value, calculator)


def line_answer(F, calculator):
    return c4._answer(F, calculator, expression=True)


def t_expression_answer(F):
    F = sp.simplify(F)
    F = sp.factor(F)
    if sp.count_ops(F) > 60:
        raise Reject("redraw", "derived expression is too large")
    why = expression_reason(F, t, True)
    if why:
        raise Reject("redraw", f"answer is not a usable expression ({why})", why)
    return {"type": "expression", "latex": L(F), "sympy": str(F), "numeric": None}


def enum_answer(word):
    return {"type": "enum", "latex": rf"\text{{{word}}}", "sympy": None, "numeric": None}


def step(text, latex, expr=None):
    return {"text": text, "latex": latex, "sympy": None if expr is None else str(expr)}


def close(got, want, tol):
    return abs(got - want) <= tol * max(1.0, abs(want))


def richardson(fn):
    """Polyline estimate with O(h^4) error from two O(h^2) estimates."""
    coarse, fine = fn(POLYLINE_N), fn(2 * POLYLINE_N)
    return fine + (fine - coarse) / 3


def path(fx, fy, lo, hi, n):
    ts = _points(lo, hi, n + 1)
    return [(fx(p), fy(p)) for p in ts]


def finish(topic, ident, statement, steps, answer, method, detail, curves, value, extra):
    """The verifier's result dict, with the raw measures app/difficulty.py reads."""
    key = json.dumps(ident, sort_keys=True)
    ops = sum(int(sp.count_ops(e)) for e in curves)
    raw = {"ops_integrand": ops, "ops_R": ops, "ops_F": int(sp.count_ops(value)) if value is not None else 0,
           "g_polynomial": all(e.is_polynomial(*e.free_symbols) for e in curves), "deg_g": None,
           "n_terms_R": sum(len(sp.Add.make_args(sp.expand(e))) for e in curves), "const_factor": False,
           "definite": True, "has_discontinuity": False, "steps": len(steps), "answer_type": answer["type"],
           "rules": [], "topic": topic, "numeric_check": detail, **extra}
    return {"ok": True, "statement": statement, "answer": answer, "steps": steps, "method": method,
            "calculator_check": "passed", "has_discontinuity": False, "integrand": str(curves[0]),
            "hash": hashlib.sha256(key.encode()).hexdigest()[:16], "shape": topic + "|" + key, "raw": raw}


def wrap(fn):
    """Run a topic body and turn a Reject into the verifier's failure dict."""
    def run(*args, **kw):
        try:
            return fn(*args, **kw)
        except Reject as r:
            return {"ok": False, "cause": r.cause, "reason": r.reason, "cap": r.cap}
    return run


def mp_fn(e, sym):
    mp.mp.dps = 40
    return sp.lambdify(sym, e, "mpmath")
