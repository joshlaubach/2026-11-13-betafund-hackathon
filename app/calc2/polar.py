"""Polar-curve topics: slopes, area and arc length."""
import math

import mpmath as mp
import sympy as sp

from app.shared.integral_core import L, Reject, x as X_SYMBOL
from app.calc2.pp_core import (check_axes, close, curve_expr, exact, exact_integral, family_of, finish, finite_on,
                         float_fn, integrate_speed, interval, line_answer, mp_fn, numeric_answer, path,
                         richardson, sign_on, step, th)

POLAR_ASKS = ("slope", "line", "horizontal")
FULL_TURN = 2 * sp.pi


def _radius(r, label="r(theta)"):
    return curve_expr(r, th, label)


def _xy(er):
    return er * sp.cos(th), er * sp.sin(th)


def _slope_numeric(er, a):
    ex, ey = _xy(er)
    fx, fy = mp_fn(ex, th), mp_fn(ey, th)
    h = mp.mpf("1e-12")
    a = mp.mpf(str(sp.N(a, 40)))
    return (fy(a + h) - fy(a - h)) / (fx(a + h) - fx(a - h))


def slopes(r, t0, ask, t1=None, axes=None, calculator="none"):
    er = _radius(r)
    if ask not in POLAR_ASKS:
        raise Reject("slip", "ask must be slope, line or horizontal")
    a = exact(t0, "t0")
    ex, ey = _xy(er)
    xp, yp = sp.diff(ex, th), sp.diff(ey, th)
    check_axes(axes or {}, family=family_of(er), ask=ask)
    rp = sp.diff(er, th)
    num, den = rp * sp.sin(th) + er * sp.cos(th), rp * sp.cos(th) - er * sp.sin(th)
    curve = rf"$r={L(er)}$"
    extra = {"family": family_of(er), "ask": ask}
    if ask == "horizontal":
        return _horizontal(er, xp, yp, num, a, t1, curve, extra, calculator)
    if t1 is not None:
        raise Reject("slip", "t1 must be null unless ask is horizontal")
    finite_on([er, rp], th, a, a + sp.Rational(1, 100))
    if sp.simplify(den.subs(th, a)) == 0:
        raise Reject("redraw", "dx/dtheta is 0 at the given angle: the tangent is vertical or undefined")
    slope = sp.simplify(num.subs(th, a) / den.subs(th, a))
    got, want = float(slope), float(_slope_numeric(er, a))
    if not close(got, want, 1e-8):
        raise Reject("redraw", "independent difference quotient disagrees with dy/dx")
    steps = [step("Write x and y in terms of theta and differentiate.",
                  rf"\frac{{dy}}{{dx}}=\frac{{r'\sin\theta+r\cos\theta}}{{r'\cos\theta-r\sin\theta}},\ r'={L(rp)}", rp),
             step("Evaluate at the given angle.", rf"\frac{{dy}}{{dx}}={L(slope)}", slope)]
    ident = {"r": str(er), "t0": str(a), "ask": ask}
    detail = f"difference quotient {got:.10g} vs {want:.10g}"
    if ask == "slope":
        statement = rf"Find $\dfrac{{dy}}{{dx}}$ for the polar curve {curve} at $\theta={L(a)}$."
        return finish("slopes", ident, statement, steps, numeric_answer(slope, calculator),
                      "polar_slope+difference_quotient", detail, [er], slope, extra)
    x0, y0 = sp.simplify(ex.subs(th, a)), sp.simplify(ey.subs(th, a))
    line = sp.expand(slope * (X_SYMBOL - x0) + y0)
    steps.append(step("The tangent line passes through the Cartesian point of the curve.", rf"y={L(line)}", line))
    statement = (rf"Find an equation of the tangent line, with $y$ as a function of $x$, to the polar curve {curve} "
                 rf"at $\theta={L(a)}$.")
    return finish("slopes", ident, statement, steps, line_answer(line, calculator),
                  "polar_tangent_line+difference_quotient", detail, [er], line, extra)


def _horizontal(er, xp, yp, num, a, t1, curve, extra, calculator):
    if t1 is None:
        raise Reject("slip", "t1 is required when ask is horizontal")
    b = exact(t1, "t1")
    if not a < b:
        raise Reject("slip", "t0 must be less than t1")
    finite_on([er, sp.diff(er, th)], th, a, b)
    sols = sp.solveset(sp.simplify(yp), th, sp.Interval.open(a, b))
    if not isinstance(sols, sp.FiniteSet) or len(sols) != 1:
        raise Reject("redraw", "dy/dtheta must vanish at exactly one angle in the open interval")
    star = sp.simplify(next(iter(sols)))
    if sp.simplify(xp.subs(th, star)) == 0:
        raise Reject("redraw", "dx/dtheta also vanishes there")
    fy = float_fn(yp, th)
    grid = [float(a) + (float(b) - float(a)) * i / 2000 for i in range(2001)]
    flips = sum(1 for p, q in zip(grid, grid[1:]) if fy(p) * fy(q) < 0)
    if flips > 1 or abs(fy(float(star))) > 1e-9:
        raise Reject("redraw", "independent scan of dy/dtheta disagrees with the solution")
    steps = [step("A horizontal tangent needs dy/dtheta = 0 with dx/dtheta not 0.",
                  rf"\frac{{dy}}{{d\theta}}=r'\sin\theta+r\cos\theta={L(sp.simplify(num))}=0", num),
             step("Solve in the given interval and check dx/dtheta there.", rf"\theta={L(star)}", star)]
    statement = rf"Find the value of $\theta$ with ${L(a)}<\theta<{L(b)}$ at which the polar curve {curve} has a horizontal tangent."
    ident = {"r": str(er), "t0": str(a), "t1": str(b), "ask": "horizontal"}
    return finish("slopes", ident, statement, steps, numeric_answer(star, calculator), "polar_horizontal+scan",
                  f"sign scan: {flips} sign change(s) of dy/dtheta", [er], star, extra)


def _span(r, t0, t1):
    er = _radius(r)
    lo, hi = interval(t0, t1, "theta")
    if hi - lo > FULL_TURN:
        raise Reject("redraw", "the angle interval may not be longer than one full turn")
    finite_on([er, sp.diff(er, th)], th, lo, hi)
    return er, lo, hi


def _rose_frequency(er):
    args = {f.args[0] for f in er.atoms(sp.sin, sp.cos)}
    if len(args) != 1:
        return None
    k = sp.Poly(next(iter(args)), th).coeff_monomial(th)
    return abs(k) if k.is_Integer and abs(k) >= 2 else None


def _fan_area(fx, fy, lo, hi):
    def area(n):
        pts = path(fx, fy, lo, hi, n)
        return sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(pts, pts[1:])) / 2
    return richardson(area)


def _area_style(er, lo, hi, inner):
    if inner is not None:
        return "between"
    ends_equal = sp.simplify(er.subs(th, lo) - er.subs(th, hi)) == 0
    if hi - lo == FULL_TURN and ends_equal:
        return "full"
    k = _rose_frequency(er)
    if k and sp.simplify(hi - lo - sp.pi / k) == 0 and er.subs(th, lo) == 0 and er.subs(th, hi) == 0:
        interior = float_fn(er, th)
        if all(interior(p) > 1e-6 for p in [float(lo) + (float(hi) - float(lo)) * i / 50 for i in range(1, 50)]):
            return "petal"
    return "sector"


def polar_area(r, t0, t1, r2=None, axes=None, calculator="none"):
    er, lo, hi = _span(r, t0, t1)
    inner = None if r2 is None else _radius(r2, "inner r(theta)")
    style = _area_style(er, lo, hi, inner)
    check_axes(axes or {}, family=family_of(er), style=style)
    if sign_on(er, th, lo, hi) != "pos":
        raise Reject("redraw", "r must be nonnegative on the interval")
    integrand = er**2 / 2
    fxo, fyo = (float_fn(e, th) for e in _xy(er))
    if inner is not None:
        finite_on([inner], th, lo, hi)
        if sign_on(inner, th, lo, hi) != "pos" or sign_on(er - inner, th, lo, hi) != "pos":
            raise Reject("redraw", "the outer curve must stay at or beyond the inner curve, and both must have r >= 0")
        integrand = (er**2 - inner**2) / 2
    value = exact_integral(sp.expand(integrand), th, lo, hi)
    if value <= 0:
        raise Reject("redraw", "the area is not positive")
    got = _fan_area(fxo, fyo, lo, hi)
    if inner is not None:
        got -= _fan_area(*(float_fn(e, th) for e in _xy(inner)), lo, hi)
    want = float(value)
    if not close(got, want, 1e-6):
        raise Reject("redraw", "independent fan-of-triangles area disagrees with the integral")
    if inner is None:
        steps = [step("Polar area formula.", rf"A=\frac12\int_{{{L(lo)}}}^{{{L(hi)}}}r^2\,d\theta=\frac12\int_{{{L(lo)}}}^{{{L(hi)}}}\left({L(er)}\right)^2d\theta", integrand)]
    else:
        steps = [step("Area between two polar curves.", rf"A=\frac12\int_{{{L(lo)}}}^{{{L(hi)}}}\left(R^2-r^2\right)d\theta,\ R={L(er)},\ r={L(inner)}", integrand)]
    steps.append(step("Evaluate the definite integral.", rf"A={L(value)}", value))
    if style == "between":
        statement = (rf"Find the area of the region inside $r={L(er)}$ and outside $r={L(inner)}$ "
                     rf"for ${L(lo)}\le\theta\le{L(hi)}$.")
    elif style == "petal":
        statement = rf"Find the area enclosed by one petal of the polar curve $r={L(er)}$."
    elif style == "full":
        statement = rf"Find the area enclosed by the polar curve $r={L(er)}$ for ${L(lo)}\le\theta\le{L(hi)}$."
    else:
        statement = (rf"Find the area of the region bounded by the polar curve $r={L(er)}$ and the rays "
                     rf"$\theta={L(lo)}$ and $\theta={L(hi)}$.")
    ident = {"r": str(er), "r2": None if inner is None else str(inner), "t0": str(lo), "t1": str(hi)}
    curves = [er] if inner is None else [er, inner]
    return finish("polar_area", ident, statement, steps, numeric_answer(value, calculator),
                  "polar_area+triangle_fan", f"triangle fan {got:.10g} vs {want:.10g}", curves, value,
                  {"family": family_of(er), "style": style})


def polar_arc_length(r, t0, t1, axes=None, calculator="none"):
    er, lo, hi = _span(r, t0, t1)
    check_axes(axes or {}, family=family_of(er))
    rp = sp.diff(er, th)
    speed, value = integrate_speed(er**2 + rp**2, th, lo, hi)
    fx, fy = (float_fn(e, th) for e in _xy(er))

    def length(n):
        pts = path(fx, fy, lo, hi, n)
        return sum(math.hypot(q[0] - p[0], q[1] - p[1]) for p, q in zip(pts, pts[1:]))
    got, want = richardson(length), float(value)
    if not close(got, want, 1e-6):
        raise Reject("redraw", "independent polyline length disagrees with the integral")
    steps = [step("Polar arc length formula.", rf"L=\int_{{{L(lo)}}}^{{{L(hi)}}}\sqrt{{r^2+\left(\frac{{dr}}{{d\theta}}\right)^2}}\,d\theta,\ r'={L(rp)}", rp),
             step("Simplify the integrand.", rf"\sqrt{{r^2+r'^2}}={L(speed)}", speed),
             step("Evaluate the definite integral.", rf"L={L(value)}", value)]
    statement = rf"Find the length of the polar curve $r={L(er)}$ for ${L(lo)}\le\theta\le{L(hi)}$."
    ident = {"r": str(er), "t0": str(lo), "t1": str(hi)}
    return finish("polar_arc_length", ident, statement, steps, numeric_answer(value, calculator),
                  "polar_arc_length+chord_polyline", f"polyline {got:.10g} vs {want:.10g}", [er], value,
                  {"family": family_of(er)})
