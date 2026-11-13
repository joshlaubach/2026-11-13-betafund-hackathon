"""Verifiers for the modelling topics of the applications chapter that need no story (C3 milestone b, first half):
linear_approximation, lhopital, newtons_method, motion, marginal_analysis. The related rates and optimization word
problems live in app/rates_optimization.py. Same contract as app/applications.py: verify(stem, ...) in the sandbox.

The model proposes a function and a question; the server derives the answer exactly with SymPy, re-checks it numerically
by a method that does not use the exact derivation (mpmath quadrature, evaluation near the limit point, a grid of
the objective), and writes the statement and the steps.
"""
from decimal import Decimal

import mpmath as mp
import sympy as sp

from app import function_pool as pool
from app.applications import _set_answer, _short
from app.calculus_core import fd_agrees, finish, step
from app.clean_answer import canon
from app.integral_core import L, Reject, x
from app.limits import _expr, _point

STEMS = ("linear_approximation", "lhopital", "newtons_method", "motion", "marginal_analysis")
S = sp.S
t = sp.Symbol("t", real=True)
q = sp.Symbol("q", real=True)


def verify(stem: str, bounds=None, axes: dict | None = None, calculator: str = "none", **fields) -> dict:
    try:
        if stem not in STEMS:
            raise Reject("slip", f"unknown applications topic {stem}")
        if calculator != "none":
            raise Reject("redraw", "these topics have only the exact tier")
        return _VERIFY[stem](stem, axes or {}, **fields)
    except Reject as r:
        return {"ok": False, "cause": r.cause, "reason": r.reason, "cap": r.cap}


# -- shared helpers ------------------------------------------------------------------------------------------------

def _fn(expr, var):
    fl = sp.lambdify(var, expr, "mpmath")

    def g(v):
        try:
            r = fl(mp.mpf(v))
        except (ValueError, ZeroDivisionError, ArithmeticError, TypeError):
            return None
        if isinstance(r, mp.mpc):
            return None if abs(r.imag) > 1e-20 else r.real
        return r
    return g


def _dec(v):
    """A terminating decimal string for a rational (at most four places), or None."""
    v = sp.Rational(v)
    for k in range(5):
        if (v * 10 ** k).is_Integer:
            return format(Decimal(int(v.p)) / Decimal(int(v.q)), "f") if k else str(int(v))
    return None


def _decimal(s, label):
    v = _point(s, label)
    if not v.is_Rational or _dec(v) is None:
        raise Reject("redraw", f"{label} must be a terminating decimal of at most four places")
    return sp.Rational(v)


def _smooth(f, var=x, label="f", symbols=None):
    fe = _expr(f, label, symbols)
    if fe.has(sp.Abs, sp.Piecewise, sp.sign, sp.floor) or not fe.has(var):
        raise Reject("redraw", f"{label} must be a smooth expression in {var}")
    if pool.complexity(fe) > 10:
        raise Reject("redraw", f"{label} is too complicated for this topic")
    return fe


def _numeric(v, what="the answer"):
    v = _short(v, what)
    return {"type": "numeric", "latex": L(v), "sympy": str(v), "numeric": float(sp.N(v, 15))}, v


def _kind(fe) -> str:
    if fe.is_polynomial(x):
        return "poly"
    if fe.is_rational_function(x):
        return "rational"
    if any(isinstance(p, sp.Pow) and p.exp.is_Rational and not p.exp.is_Integer and p.base.has(x)
           for p in sp.preorder_traversal(fe)):
        return "root"
    return "trans"


# -- linear approximation and differentials ------------------------------------------------------------------------

_NAMED = {"sqrt(x)": "\\sqrt{{{v}}}", "x^(1/3)": "\\sqrt[3]{{{v}}}", "exp(x)": "e^{{{v}}}", "ln(x)": "\\ln {v}",
          "x^(1/4)": "\\sqrt[4]{{{v}}}", "1/x": "\\frac{{1}}{{{v}}}"}


def _verify_linear(stem, axes, f, a, x1="", dx="", ask="estimate", **_):
    if ask not in ("estimate", "differential"):
        raise Reject("slip", "ask must be estimate or differential")
    fe = _smooth(f)
    a_ = _point(a, "a")
    if not a_.is_Rational or _dec(a_) is None:
        raise Reject("redraw", "a must be a terminating decimal")
    try:
        fa, d = canon(fe.subs(x, a_)), sp.diff(fe, x)
    except (ZeroDivisionError, ValueError):
        raise Reject("redraw", "f is not defined at a") from None
    if fa.is_real is not True or fa.has(sp.zoo, sp.nan):
        raise Reject("redraw", "f(a) is not a finite real number")
    if not fd_agrees(fe, d):
        raise Reject("redraw", "the derivative failed the finite-difference check")
    da = canon(d.subs(x, a_))
    _short(fa, "f(a)")
    _short(da, "f'(a)")
    if da == 0:
        raise Reject("redraw", "f'(a) = 0: the linearization is a constant; choose a point with a slope")
    kind = _kind(fe)
    _check_axes(axes, kind=kind, ask=ask)
    if ask == "estimate":
        x1_ = _decimal(x1, "x1")
        if x1_ == a_ or abs(x1_ - a_) > max(sp.Rational(1, 2), abs(a_) / 5):
            raise Reject("redraw", "x1 must differ from a and stay close to it")
        est = canon(fa + da * (x1_ - a_))
        true = _fn(fe, x)(float(x1_))
        if true is None:
            raise Reject("redraw", "f is not defined at x1")
        if abs(float(est) - float(true)) > 0.06 * max(abs(float(true)), 0.05):
            raise Reject("redraw", "x1 is too far from a for the linearization to be a good estimate")
        ans, val = _numeric(est, "the estimate")
        named = _NAMED.get(str(f).replace(" ", ""))
        target = ("$" + named.format(v=_dec(x1_)) + "$") if named else f"$f({_dec(x1_)})$"
        st = (f"Use the linearization of $f(x) = {L(fe)}$ at $a = {_dec(a_)}$ to approximate {target}.")
        steps = [step("The linearization is L(x) = f(a) + f'(a)(x - a).", "L(x) = f(a) + f'(a)(x - a)"),
                 step("Find f(a) and f'(a).", f"f({L(a_)}) = {L(fa)},\\ f'({L(a_)}) = {L(da)}", str(da)),
                 step("Evaluate L at the target.", f"L({_dec(x1_)}) = {L(fa)} + {L(da)}({L(x1_ - a_)}) = {L(est)}", str(est))]
        key = f"estimate|{a_}|{x1_}"
    else:
        dx_ = _decimal(dx, "dx")
        if dx_ == 0 or abs(dx_) > max(sp.Rational(1, 2), abs(a_) / 5):
            raise Reject("redraw", "dx must be a small nonzero number")
        dy = canon(da * dx_)
        ans, val = _numeric(dy, "dy")
        st = f"Find the differential $dy$ of $y = {L(fe)}$ at $x = {_dec(a_)}$ when $dx = {_dec(dx_)}$."
        steps = [step("The differential is dy = f'(x) dx.", "dy = f'(x)\\,dx"),
                 step("Find f'(a).", f"f'({L(a_)}) = {L(da)}", str(da)),
                 step("Multiply by dx.", f"dy = {L(da)} \\cdot {_dec(dx_)} = {L(dy)}", str(dy))]
        key = f"differential|{a_}|{dx_}"
    return finish(stem, fe, key, st, ans, steps, kind, axes, exact=True, raw_extra={"kind": kind, "ask": ask})


def _check_axes(axes, **have):
    for k, v in have.items():
        if k in axes and str(axes[k]) != str(v):
            raise Reject("redraw", f"axes: the server assigned {k} = {axes[k]} (this is {v})")


# -- L'Hopital's rule ----------------------------------------------------------------------------------------------

def _lim(expr, a, side):
    try:
        return canon(sp.limit(expr, x, a, side) if side else sp.limit(expr, x, a))
    except (NotImplementedError, ValueError, TypeError):
        raise Reject("redraw", "a limit could not be found") from None


def _inf(v) -> bool:
    return v in (sp.oo, -sp.oo)


def _numeric_limit(fe, a, side) -> float:
    """f evaluated closer and closer to a (a method that does not use sp.limit); the last values must settle."""
    mp.mp.dps = 60
    g = _fn(fe, x)
    pts = []
    for k in range(5, 12):
        h = mp.mpf(10) ** -k
        if a in (sp.oo, -sp.oo):
            pts.append(g(mp.mpf(10) ** k * (1 if a == sp.oo else -1)))
        elif side == "-":
            pts.append(g(mp.mpf(str(sp.N(a, 40))) - h))
        else:
            pts.append(g(mp.mpf(str(sp.N(a, 40))) + h))
    vals = [v for v in pts if v is not None]
    if len(vals) < 4 or abs(vals[-1] - vals[-3]) > mp.mpf(10) ** -3 * max(1, abs(vals[-1])):
        raise Reject("redraw", "a numerical check of the limit did not settle")
    return float(vals[-1])


def _is_zero(v):
    return v == 0


def _quotient_apps(num, den, a, side, steps):
    """Apply L'Hopital's rule until the quotient has a determinate limit. Returns (value, applications)."""
    apps = 0
    while True:
        ln, ld = _lim(num, a, side), _lim(den, a, side)
        if not ((_is_zero(ln) and _is_zero(ld)) or (_inf(ln) and _inf(ld))):
            break
        if apps >= 3:
            raise Reject("redraw", "needs more than three applications of L'Hopital's rule")
        form = "\\frac{0}{0}" if _is_zero(ln) else "\\frac{\\infty}{\\infty}"
        num, den = sp.fraction(sp.cancel(sp.together(sp.diff(num, x) / sp.diff(den, x))))   # simplify, as a student would
        apps += 1
        steps.append(step(f"The form is {form}: apply L'Hopital's rule (differentiate the numerator and the denominator).",
                          f"\\lim \\frac{{{L(num)}}}{{{L(den)}}}"))
    if apps == 0:
        raise Reject("redraw", "the quotient is not an indeterminate form")
    return canon(sp.limit(num / den, x, a, side) if side else sp.limit(num / den, x, a)), apps


def _verify_lhopital(stem, axes, f, a, side="", **_):
    if side not in ("", "+", "-"):
        raise Reject("slip", "side must be empty, + or -")
    a_ = _point(a, "a", infinite=True)
    fe = _expr(f, "f")
    if fe.has(sp.Abs, sp.Piecewise) or pool.complexity(fe) > 12:
        raise Reject("redraw", "f must be a smooth, short expression")
    if side and _inf(a_):
        raise Reject("slip", "a one-sided limit needs a finite point")
    steps = []
    num, den = sp.fraction(sp.together(fe))
    base, expo = (fe.as_base_exp() if isinstance(fe, sp.Pow) else (None, None))
    if isinstance(fe, sp.Pow) and base.has(x) and expo.has(x):
        kind = "power"
        lb = _lim(base, a_, side)
        le = _lim(expo, a_, side)
        tag = "1^\\infty" if (lb == 1 and _inf(le)) else "0^0" if (lb == 0 and le == 0) else \
            "\\infty^0" if (_inf(lb) and le == 0) else None
        if tag is None:
            raise Reject("redraw", "the power is not an indeterminate form (1^oo, 0^0 or oo^0)")
        w = sp.log(base) * expo
        steps.append(step(f"The form is {tag}: let y = f(x) and take the natural logarithm.", f"\\ln y = {L(w)}"))
        small, big = (sp.log(base), expo) if _is_zero(_lim(sp.log(base), a_, side)) else (expo, sp.log(base))
        steps.append(step("This is a product 0 times infinity: rewrite it as a quotient.",
                          f"\\ln y = \\frac{{{L(small)}}}{{{L(1 / big)}}}"))
        val, apps = _quotient_apps(small, 1 / big, a_, side, steps)
        value = canon(sp.exp(val))
        steps.append(step("Undo the logarithm: the limit of y is e to that value.", f"\\lim y = e^{{{L(val)}}} = {L(value)}"))
    elif den.has(x) and not isinstance(fe, sp.Add):
        kind = "quotient"
        ln, ld = _lim(num, a_, side), _lim(den, a_, side)
        if _is_zero(ln) and _is_zero(ld):
            tag = "zero"
        elif _inf(ln) and _inf(ld):
            tag = "infinity"
        else:
            raise Reject("redraw", "the quotient is not 0/0 or oo/oo at the point")
        kind = "quotient_" + tag
        val, apps = _quotient_apps(num, den, a_, side, steps)
        value = val
    else:
        factors = [p for p in sp.Mul.make_args(fe) if p.has(x)]
        if len(factors) != 2:
            raise Reject("redraw", "f must be a quotient, a product of two functions or a power")
        u, v = factors
        lu, lv = _lim(u, a_, side), _lim(v, a_, side)
        if not ((_is_zero(lu) and _inf(lv)) or (_inf(lu) and _is_zero(lv))):
            raise Reject("redraw", "the product is not 0 times oo")
        if _inf(lu):
            u, v = v, u
        kind = "product"
        steps.append(step("The form is 0 \\cdot \\infty: rewrite the product as a quotient.",
                          f"f(x) = \\frac{{{L(u)}}}{{{L(1 / v)}}}"))
        val, apps = _quotient_apps(u, 1 / v, a_, side, steps)
        value = val
    if not (1 <= apps <= 3):
        raise Reject("redraw", "L'Hopital's rule must be needed one to three times")
    if _inf(value) or value.is_real is not True:
        raise Reject("redraw", "the limit must be a finite number")
    _check_axes(axes, kind=kind, n_apps=apps)
    shown = _numeric_limit(fe, a_, side or "+")
    if side == "" and not _inf(a_):
        other = _numeric_limit(fe, a_, "-")
        if abs(other - shown) > 1e-3 * max(1, abs(shown)):
            raise Reject("redraw", "the two sides of the limit disagree numerically")
    ans, val_ = _numeric(value, "the limit")
    if abs(float(value) - shown) > 1e-3 * max(1, abs(shown)):
        raise Reject("redraw", "the numerical check disagrees with the exact limit")
    steps.append(step("The limit is determinate: that is the value.", f"\\lim = {L(value)}", str(value)))
    point = "\\infty" if a_ == sp.oo else "-\\infty" if a_ == -sp.oo else L(a_)
    arrow = point + {"+": "^{+}", "-": "^{-}", "": ""}[side]
    st = f"Evaluate $\\displaystyle \\lim_{{x \\to {arrow}}} {L(fe)}$."
    return finish(stem, fe, f"{a_}|{side}", st, ans, steps, kind, axes, exact=True,
                  raw_extra={"kind": kind, "n_apps": apps, "ask": "limit"})


# -- Newton's method -----------------------------------------------------------------------------------------------

def _verify_newton(stem, axes, f, x0, n, **_):
    fe = _smooth(f)
    if not (fe.is_polynomial(x) or fe.is_rational_function(x)):
        raise Reject("redraw", "f must be a polynomial or a rational function, so every iterate is exact")
    x0_ = _point(x0, "x0")
    if not x0_.is_Rational:
        raise Reject("slip", "x0 must be a rational number")
    try:
        n_ = int(n)
    except (TypeError, ValueError):
        raise Reject("slip", "n must be a whole number") from None
    if not 1 <= n_ <= 3:
        raise Reject("redraw", "n must be 1, 2 or 3")
    d = sp.diff(fe, x)
    kind = "quad" if sp.degree(sp.numer(sp.together(fe)), x) <= 2 and fe.is_polynomial(x) else "cubic" if fe.is_polynomial(x) else "rational"
    _check_axes(axes, kind=kind, n=n_)
    xs, steps = [sp.Rational(x0_)], []
    for k in range(n_):
        fx, dx = canon(fe.subs(x, xs[-1])), canon(d.subs(x, xs[-1]))
        if dx == 0 or dx.has(sp.zoo, sp.nan) or fx.has(sp.zoo, sp.nan):
            raise Reject("redraw", f"f'(x{k}) is zero or undefined: the method breaks down")
        nxt = canon(xs[-1] - fx / dx)
        if not nxt.is_Rational:
            raise Reject("redraw", "an iterate is not rational")
        if abs(nxt.q) > 5000 or abs(nxt.p) > 5000:
            raise Reject("redraw", "an iterate has too large a numerator or denominator", )
        steps.append(step(f"x_{{{k + 1}}} = x_{{{k}}} - f(x_{{{k}}})/f'(x_{{{k}}}).",
                          f"x_{{{k + 1}}} = {L(xs[-1])} - \\frac{{{L(fx)}}}{{{L(dx)}}} = {L(nxt)}", str(nxt)))
        xs.append(nxt)
    if xs[-1] == xs[-2]:
        raise Reject("redraw", "the iteration has already converged exactly")
    # an independent run in floating point, with the derivative taken numerically
    mp.mp.dps = 40
    g = _fn(fe, x)
    v = mp.mpf(str(sp.N(x0_, 40)))
    for _ in range(n_):
        v = v - g(v) / mp.diff(g, v)
    if abs(v - mp.mpf(str(sp.N(xs[-1], 40)))) > mp.mpf(10) ** -12:
        raise Reject("redraw", "the floating-point iteration disagrees with the exact one")
    ans, val = _numeric(xs[-1], f"x{n_}")
    st = (f"Use Newton's method with initial approximation $x_0 = {L(x0_)}$ to find $x_{{{n_}}}$ for "
          f"$f(x) = {L(fe)}$.")
    return finish(stem, fe, f"{x0_}|{n_}", st, ans, steps, kind, axes, exact=True,
                  raw_extra={"kind": kind, "n": n_, "ask": "iterate"})


# -- position, velocity and acceleration ---------------------------------------------------------------------------

def _verify_motion(stem, axes, s, at="", a="", b="", ask="velocity", **_):
    if ask not in ("velocity", "acceleration", "speed", "displacement", "total_distance", "at_rest"):
        raise Reject("slip", "ask must be velocity, acceleration, speed, displacement, total_distance or at_rest")
    se = _expr(s, "s", {"t": t})
    if se.has(sp.Abs, sp.Piecewise) or not se.has(t) or se.has(x) or pool.complexity(se) > 10:
        raise Reject("redraw", "s must be a short smooth expression in t")
    v, acc = sp.diff(se, t), sp.diff(se, t, 2)
    kind = "poly" if se.is_polynomial(t) else "trig" if se.has(sp.sin, sp.cos) else "trans"
    _check_axes(axes, kind=kind, ask=ask)
    if ask in ("velocity", "acceleration", "speed"):
        t0 = _point(at, "t")
        if t0 < 0:
            raise Reject("redraw", "t must not be negative")
        val = {"velocity": v, "acceleration": acc, "speed": sp.Abs(v)}[ask].subs(t, t0)
        val = canon(val)
        ans, value = _numeric(val, f"the {ask}")
        name = {"velocity": "velocity", "acceleration": "acceleration", "speed": "speed"}[ask]
        st = (f"A particle moves along a line with position $s(t) = {L(se)}$ metres at time $t$ seconds. "
              f"Find the {name} of the particle at $t = {L(t0)}$.")
        steps = [step("Velocity is the derivative of position.", f"v(t) = {L(v)}", str(v))]
        if ask != "velocity":
            steps.append(step("Acceleration is the derivative of velocity." if ask == "acceleration"
                              else "Speed is the absolute value of velocity.",
                              f"a(t) = {L(acc)}" if ask == "acceleration" else f"|v({L(t0)})|", str(acc) if ask == "acceleration" else None))
        steps.append(step(f"Evaluate at t = {L(t0)}.", L(value), str(value)))
        g = _fn({"velocity": v, "acceleration": acc, "speed": sp.Abs(v)}[ask], t)
        if abs(g(float(t0)) - float(value)) > 1e-9 * max(1, abs(float(value))):
            raise Reject("redraw", "the numerical evaluation disagrees")
        return finish(stem, se, f"{ask}|{t0}", st, ans, steps, kind, axes, exact=True, raw_extra={"kind": kind, "ask": ask})
    lo, hi = _point(a, "a"), _point(b, "b")
    if not 0 <= lo < hi:
        raise Reject("redraw", "the interval must satisfy 0 <= a < b")
    iv = sp.Interval(lo, hi)
    try:
        stops = sp.solveset(v, t, sp.Interval.open(lo, hi))
    except (NotImplementedError, ValueError):
        raise Reject("redraw", "the times when v = 0 could not be solved exactly") from None
    if stops == S.EmptySet:
        stops = []
    elif not isinstance(stops, sp.FiniteSet):
        raise Reject("redraw", "the times when v = 0 could not be found as a finite set")
    stops = sorted((_short(canon(p), "a time") for p in stops), key=float)
    if ask == "at_rest":
        if not stops:
            raise Reject("redraw", "the particle is never at rest on the interval")
        ans = _set_answer(stops)
        st = (f"A particle moves along a line with position $s(t) = {L(se)}$ metres at time $t$ seconds. "
              f"Find all times $t$ with ${L(lo)} < t < {L(hi)}$ at which the particle is at rest.")
        steps = [step("At rest means the velocity is zero.", f"v(t) = {L(v)} = 0", str(v)),
                 step("Solve for t inside the interval.", ans["latex"], ans["sympy"])]
        return finish(stem, se, f"at_rest|{lo}|{hi}", st, ans, steps, kind, axes, exact=True,
                      raw_extra={"kind": kind, "ask": ask})
    cuts = [lo] + stops + [hi]
    vals = [canon(se.subs(t, c)) for c in cuts]
    if ask == "displacement":
        val = canon(vals[-1] - vals[0])
        steps = [step("Displacement is the change in position, s(b) - s(a).", f"s({L(hi)}) - s({L(lo)}) = {L(vals[-1])} - {L(vals[0])}"),
                 step("Subtract.", L(val), str(val))]
        what = "the displacement of the particle"
    else:
        if not stops:
            raise Reject("redraw", "the velocity does not change sign: use displacement")
        pieces = [canon(vals[i + 1] - vals[i]) for i in range(len(vals) - 1)]
        val = canon(sum(abs(p) for p in pieces))
        steps = [step("The velocity is zero where the particle turns around.", f"v(t) = {L(v)},\\ t \\in {_set_answer(stops)['latex']}", str(stops)),
                 step("Add the distances travelled on each stretch.", " + ".join(f"|{L(p)}|" for p in pieces) + f" = {L(val)}", str(val))]
        what = "the total distance travelled by the particle"
        mp.mp.dps = 30
        gv = _fn(v, t)
        pts = [mp.mpf(str(sp.N(c, 30))) for c in cuts]
        numeric = mp.quad(lambda w: abs(gv(w) or 0), pts)
        if abs(numeric - mp.mpf(str(sp.N(val, 30)))) > mp.mpf(10) ** -6 * max(1, abs(numeric)):
            raise Reject("redraw", "the quadrature of |v| disagrees with the total distance")
    ans, value = _numeric(val, "the result")
    if value <= 0 and ask == "total_distance":
        raise Reject("redraw", "the total distance must be positive")
    st = (f"A particle moves along a line with position $s(t) = {L(se)}$ metres at time $t$ seconds. "
          f"Find {what} for ${L(lo)} \\le t \\le {L(hi)}$.")
    return finish(stem, se, f"{ask}|{lo}|{hi}", st, ans, steps, kind, axes, exact=True, raw_extra={"kind": kind, "ask": ask})


# -- marginal analysis ---------------------------------------------------------------------------------------------

def _ordinal(n) -> str:
    n = int(n)
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"



def _verify_marginal(stem, axes, C, p="", q0="", ask="marginal_cost", **_):
    if ask not in ("marginal_cost", "next_unit", "marginal_profit", "max_profit", "min_average_cost"):
        raise Reject("slip", "ask must be marginal_cost, next_unit, marginal_profit, max_profit or min_average_cost")
    ce = _expr(C, "C", {"q": q})
    if ce.has(sp.Abs, sp.Piecewise) or not ce.has(q) or ce.has(x) or not ce.is_polynomial(q) or sp.degree(ce, q) > 3:
        raise Reject("redraw", "C must be a polynomial in q of degree at most three")
    kind = "poly"
    _check_axes(axes, kind=kind, ask=ask)
    cp = sp.diff(ce, q)
    needs_price = ask in ("marginal_profit", "max_profit")
    if needs_price:
        pe = _expr(p, "p", {"q": q})
        if pe.has(x) or not pe.is_polynomial(q) or sp.degree(pe, q) != 1 or sp.Poly(pe, q).all_coeffs()[0] >= 0:
            raise Reject("redraw", "the price p must be a decreasing linear function of q")
        rev = sp.expand(q * pe)
        profit = sp.expand(rev - ce)
    if ask in ("marginal_cost", "next_unit", "marginal_profit"):
        n0 = _point(q0, "q0")
        if not n0.is_Integer or not 1 <= n0 <= 1000:
            raise Reject("redraw", "q0 must be a whole number from 1 to 1000")
        if ce.subs(q, n0) <= 0 or cp.subs(q, n0) <= 0:
            raise Reject("redraw", "the cost and the marginal cost must both be positive at q0")
    unit = "dollars"
    ctx = f"The cost of producing $q$ units of an item is $C(q) = {L(ce)}$ {unit}"
    if ask == "marginal_cost":
        val = canon(cp.subs(q, n0))
        st = ctx + f". Find the marginal cost at $q = {L(n0)}$ (in dollars per unit)."
        steps = [step("Marginal cost is the derivative of cost.", f"C'(q) = {L(cp)}", str(cp)),
                 step(f"Evaluate at q = {L(n0)}.", L(val), str(val))]
    elif ask == "next_unit":
        val = canon(ce.subs(q, n0 + 1) - ce.subs(q, n0))
        st = ctx + f". Find the exact cost of producing the {_ordinal(n0 + 1)} unit, that is, the extra cost of going from {L(n0)} to {L(n0 + 1)} units."
        steps = [step("The cost of the next unit is C(q+1) - C(q).", f"C({L(n0 + 1)}) - C({L(n0)}) = {L(canon(ce.subs(q, n0 + 1)))} - {L(canon(ce.subs(q, n0)))}"),
                 step("Subtract.", L(val), str(val))]
    elif ask == "marginal_profit":
        val = canon((sp.diff(profit, q)).subs(q, n0))
        st = (ctx + f", and the price at which $q$ units can be sold is $p(q) = {L(pe)}$ dollars per unit. "
              f"Find the marginal profit at $q = {L(n0)}$ (in dollars per unit).")
        steps = [step("Revenue is R(q) = q p(q), and profit is P(q) = R(q) - C(q).", f"P(q) = {L(profit)}"),
                 step("Marginal profit is P'(q).", f"P'(q) = {L(sp.diff(profit, q))}", str(sp.diff(profit, q))),
                 step(f"Evaluate at q = {L(n0)}.", L(val), str(val))]
    elif ask == "max_profit":
        dp = sp.diff(profit, q)
        crit = [c for c in sp.solve(dp, q) if c.is_real and c > 0]
        if len(crit) != 1 or sp.diff(profit, q, 2).subs(q, crit[0]) >= 0:
            raise Reject("redraw", "profit must have exactly one positive critical point, and it must be a maximum")
        val = canon(crit[0])
        if not val.is_Integer:
            raise Reject("redraw", "the number of units must be a whole number: choose a price and cost whose best quantity is one")
        if profit.subs(q, val) <= 0:
            raise Reject("redraw", "the maximum profit must be positive")
        st = (ctx + f", and the price at which $q$ units can be sold is $p(q) = {L(pe)}$ dollars per unit. "
              "Find the number of units that maximizes profit.")
        steps = [step("Profit is revenue minus cost.", f"P(q) = q\\,p(q) - C(q) = {L(profit)}"),
                 step("Set the marginal profit to zero.", f"P'(q) = {L(dp)} = 0", str(dp)),
                 step("Keep the positive solution; P'' < 0 there, so it is a maximum.", L(val), str(val))]
        g = _fn(profit, q)
        grid = [mp.mpf(i) / 50 for i in range(1, 50 * int(max(2, 4 * float(val))))]
        best = max(grid, key=lambda w: g(w) if g(w) is not None else -mp.inf)
        if abs(best - mp.mpf(str(sp.N(val, 20)))) > mp.mpf("0.05"):
            raise Reject("redraw", "a grid of the profit disagrees with the maximizing quantity")
    else:
        avg = sp.cancel(ce / q)
        crit = [c for c in sp.solve(sp.diff(avg, q), q) if c.is_real and c > 0]
        if len(crit) != 1 or sp.diff(avg, q, 2).subs(q, crit[0]) <= 0:
            raise Reject("redraw", "average cost must have exactly one positive critical point, and it must be a minimum")
        val = canon(crit[0])
        if not val.is_Integer:
            raise Reject("redraw", "the number of units must be a whole number: choose a cost whose best quantity is one")
        st = ctx + ". Find the number of units that minimizes the average cost per unit."
        steps = [step("Average cost is C(q)/q.", f"\\bar C(q) = {L(avg)}"),
                 step("Set its derivative to zero.", f"\\bar C'(q) = {L(sp.diff(avg, q))} = 0", str(sp.diff(avg, q))),
                 step("Keep the positive solution; the second derivative is positive there, so it is a minimum.", L(val), str(val))]
        g = _fn(avg, q)
        grid = [mp.mpf(i) / 50 for i in range(1, 50 * int(max(2, 4 * float(val))))]
        best = min(grid, key=lambda w: g(w) if g(w) is not None else mp.inf)
        if abs(best - mp.mpf(str(sp.N(val, 20)))) > mp.mpf("0.05"):
            raise Reject("redraw", "a grid of the average cost disagrees with the minimizing quantity")
    ans, value = _numeric(val, "the result")
    return finish(stem, ce, f"{ask}|{p}|{q0}", st, ans, steps, kind, axes, exact=True, raw_extra={"kind": kind, "ask": ask})


_VERIFY = {"linear_approximation": _verify_linear, "lhopital": _verify_lhopital, "newtons_method": _verify_newton,
           "motion": _verify_motion, "marginal_analysis": _verify_marginal}
