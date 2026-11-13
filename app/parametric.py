"""Parametric-curve topics: tangents, second derivatives, area, arc length and surface area."""
import math

import mpmath as mp
import sympy as sp

from app.integral_core import L, Reject, x as X_SYMBOL
from app.pp_core import (check_axes, close, curve_expr, enum_answer, exact, exact_integral, family_of, finish,
                         finite_on, float_fn, integrate_speed, interval, line_answer, mp_fn, numeric_answer, path,
                         richardson, sign_on, step, t, t_expression_answer)

TANGENT_ASKS = ("slope", "line", "horizontal")
SECOND_ASKS = ("value", "concavity", "expression")
EXPRESSION_PROBES = (0.37, 0.91, 1.43, 2.17, 3.11)


def _curves(x_s, y_s):
    ex, ey = curve_expr(x_s, t, "x(t)"), curve_expr(y_s, t, "y(t)")
    if not (ex.has(t) or ey.has(t)):
        raise Reject("slip", "the curve must depend on t")
    return ex, ey


def _curve_text(ex, ey):
    return rf"$x={L(ex)}$, $y={L(ey)}$"


def _slope_numeric(ex, ey, a):
    fx, fy = mp_fn(ex, t), mp_fn(ey, t)
    h = mp.mpf("1e-12")
    a = mp.mpf(str(sp.N(a, 40)))
    return (fy(a + h) - fy(a - h)) / (fx(a + h) - fx(a - h))


def tangents(x, y, t0, ask, t1=None, axes=None, calculator="none"):
    ex, ey = _curves(x, y)
    if ask not in TANGENT_ASKS:
        raise Reject("slip", "ask must be slope, line or horizontal")
    a = exact(t0, "t0")
    xp, yp = sp.diff(ex, t), sp.diff(ey, t)
    check_axes(axes or {}, family=family_of(ex, ey), ask=ask)
    curve = _curve_text(ex, ey)
    if ask == "horizontal":
        return _horizontal(ex, ey, xp, yp, a, t1, curve, calculator)
    if t1 is not None:
        raise Reject("slip", "t1 must be null unless ask is horizontal")
    finite_on([ex, ey, xp, yp], t, a, a + sp.Rational(1, 100))
    den = xp.subs(t, a)
    if den == 0:
        raise Reject("redraw", "dx/dt is 0 at the given t: the tangent is vertical or undefined")
    slope = sp.simplify(yp.subs(t, a) / den)
    got, want = float(slope), float(_slope_numeric(ex, ey, a))
    if not close(got, want, 1e-8):
        raise Reject("redraw", "independent difference quotient disagrees with dy/dx")
    steps = [step("Differentiate both coordinate functions.", rf"\frac{{dx}}{{dt}}={L(xp)},\ \frac{{dy}}{{dt}}={L(yp)}", None),
             step("Divide: dy/dx = (dy/dt)/(dx/dt), evaluated at the given t.", rf"\frac{{dy}}{{dx}}={L(slope)}", slope)]
    ident = {"x": str(ex), "y": str(ey), "t0": str(a), "ask": ask}
    if ask == "slope":
        answer = numeric_answer(slope, calculator)
        statement = rf"Find $\dfrac{{dy}}{{dx}}$ at $t={L(a)}$ on the curve {curve}."
        return finish("tangents", ident, statement, steps, answer, "parametric_slope+difference_quotient",
                      f"difference quotient {got:.10g} vs {want:.10g}", [ex, ey], slope,
                      {"family": family_of(ex, ey), "ask": ask})
    x0, y0 = sp.simplify(ex.subs(t, a)), sp.simplify(ey.subs(t, a))
    line = sp.expand(slope * (X_SYMBOL - x0) + y0)
    answer = line_answer(line, calculator)
    steps.append(step("Write the line through the point with this slope.", rf"y={L(line)}", line))
    statement = rf"Find an equation of the tangent line, with $y$ as a function of $x$, to the curve {curve} at $t={L(a)}$."
    return finish("tangents", ident, statement, steps, answer, "parametric_tangent_line+difference_quotient",
                  f"difference quotient {got:.10g} vs {want:.10g}", [ex, ey], line, {"family": family_of(ex, ey), "ask": ask})


def _horizontal(ex, ey, xp, yp, a, t1, curve, calculator):
    if t1 is None:
        raise Reject("slip", "t1 is required when ask is horizontal")
    b = exact(t1, "t1")
    if not a < b:
        raise Reject("slip", "t0 must be less than t1")
    finite_on([ex, ey, xp, yp], t, a, b)
    sols = sp.solveset(yp, t, sp.Interval.open(a, b))
    if not isinstance(sols, sp.FiniteSet) or len(sols) != 1:
        raise Reject("redraw", "dy/dt must vanish at exactly one t in the open interval")
    tstar = sp.simplify(next(iter(sols)))
    if sp.simplify(xp.subs(t, tstar)) == 0:
        raise Reject("redraw", "dx/dt also vanishes there, so the tangent is not simply horizontal")
    fy = float_fn(yp, t)
    grid = [float(a) + (float(b) - float(a)) * i / 2000 for i in range(2001)]
    flips = sum(1 for p, q in zip(grid, grid[1:]) if fy(p) * fy(q) < 0)
    if flips > 1 or abs(fy(float(tstar))) > 1e-9:
        raise Reject("redraw", "independent scan of dy/dt disagrees with the solution")
    answer = numeric_answer(tstar, calculator)
    steps = [step("A horizontal tangent needs dy/dt = 0 with dx/dt not 0.", rf"\frac{{dy}}{{dt}}={L(yp)}=0", yp),
             step("Solve in the given interval and check dx/dt there.", rf"t={L(tstar)}", tstar)]
    statement = (rf"Find the value of $t$ with ${L(a)}<t<{L(b)}$ at which the curve {curve} has a horizontal tangent.")
    ident = {"x": str(ex), "y": str(ey), "t0": str(a), "t1": str(b), "ask": "horizontal"}
    return finish("tangents", ident, statement, steps, answer, "parametric_horizontal+scan",
                  f"sign scan: {flips} sign change(s) of dy/dt", [ex, ey], tstar,
                  {"family": family_of(ex, ey), "ask": "horizontal"})


def _second_numeric(ex, ey, a):
    fx, fy = mp_fn(ex, t), mp_fn(ey, t)
    k, h = mp.mpf("1e-14"), mp.mpf("1e-7")
    slope = lambda s: (fy(s + k) - fy(s - k)) / (fx(s + k) - fx(s - k))
    a = mp.mpf(str(sp.N(a, 40)))
    return (slope(a + h) - slope(a - h)) / (fx(a + h) - fx(a - h))


def second_derivatives(x, y, ask, t0=None, axes=None, calculator="none"):
    ex, ey = _curves(x, y)
    if ask not in SECOND_ASKS:
        raise Reject("slip", "ask must be value, concavity or expression")
    xp, yp = sp.diff(ex, t), sp.diff(ey, t)
    check_axes(axes or {}, family=family_of(ex, ey), ask=ask)
    first = sp.simplify(yp / xp)
    second = sp.simplify(sp.diff(first, t) / xp)
    curve = _curve_text(ex, ey)
    steps = [step("First derivative of the curve.", rf"\frac{{dy}}{{dx}}=\frac{{dy/dt}}{{dx/dt}}={L(first)}", first),
             step("Differentiate dy/dx with respect to t and divide by dx/dt.",
                  rf"\frac{{d^2y}}{{dx^2}}=\frac{{\frac{{d}}{{dt}}(dy/dx)}}{{dx/dt}}={L(second)}", second)]
    ident = {"x": str(ex), "y": str(ey), "t0": str(t0), "ask": ask}
    extra = {"family": family_of(ex, ey), "ask": ask}
    if ask == "expression":
        if t0 is not None:
            raise Reject("slip", "t0 must be null when ask is expression")
        return _second_expression(ex, ey, xp, second, curve, steps, ident, extra)
    a = exact(t0, "t0")
    finite_on([ex, ey, xp, yp], t, a, a + sp.Rational(1, 100))
    if xp.subs(t, a) == 0:
        raise Reject("redraw", "dx/dt is 0 at the given t")
    value = sp.simplify(second.subs(t, a))
    got, want = float(value), float(_second_numeric(ex, ey, a))
    detail = f"nested difference quotients {want:.10g} vs {got:.10g}"
    if not close(got, want, 1e-7):
        raise Reject("redraw", "independent second difference quotient disagrees with d2y/dx2")
    if ask == "value":
        statement = rf"Find $\dfrac{{d^2y}}{{dx^2}}$ at $t={L(a)}$ on the curve {curve}."
        return finish("second_derivatives", ident, statement, steps, numeric_answer(value, calculator),
                      "parametric_second_derivative+nested_difference", detail, [ex, ey], value, extra)
    if value == 0:
        raise Reject("redraw", "the second derivative is 0 there, so the concavity is undetermined")
    word = "concave up" if value > 0 else "concave down"
    steps.append(step("The sign of the second derivative gives the concavity.", rf"{L(value)}\ \text{{ is }}"
                      + (">0" if value > 0 else "<0"), value))
    statement = (rf"Determine whether the curve {curve} is concave up or concave down at $t={L(a)}$. "
                 "Answer \"concave up\" or \"concave down\".")
    return finish("second_derivatives", ident, statement, steps, enum_answer(word),
                  "parametric_second_derivative_sign+nested_difference", detail, [ex, ey], value, extra)


def _second_expression(ex, ey, xp, second, curve, steps, ident, extra):
    if not second.has(t):
        raise Reject("redraw", "d2y/dx2 does not depend on t, so there is no expression to find")
    checked = 0
    f2, fx = float_fn(second, t), float_fn(xp, t)
    for p in EXPRESSION_PROBES:
        try:
            if abs(fx(p)) < 1e-6:
                continue
            got, want = f2(p), float(_second_numeric(ex, ey, sp.Float(p)))
        except (ValueError, ZeroDivisionError, OverflowError):
            continue
        if not close(got, want, 1e-6):
            raise Reject("redraw", "independent second difference quotient disagrees with d2y/dx2")
        checked += 1
    if checked < 2:
        raise Reject("redraw", "the expression could not be checked at enough points")
    answer = t_expression_answer(second)
    statement = rf"Find $\dfrac{{d^2y}}{{dx^2}}$ as a function of $t$ for the curve {curve}."
    return finish("second_derivatives", ident, statement, steps, answer,
                  "parametric_second_derivative+nested_difference", f"{checked} sample points agree", [ex, ey], second, extra)


def _span(x, y, t0, t1):
    ex, ey = _curves(x, y)
    lo, hi = interval(t0, t1)
    xp = sp.diff(ex, t)
    finite_on([ex, ey, xp, sp.diff(ey, t)], t, lo, hi)
    return ex, ey, xp, lo, hi


def parametric_area(x, y, t0, t1, axes=None, calculator="none"):
    ex, ey, xp, lo, hi = _span(x, y, t0, t1)
    check_axes(axes or {}, family=family_of(ex, ey))
    direction = sign_on(xp, t, lo, hi)
    if direction in ("mixed", "zero"):
        raise Reject("redraw", "x(t) must be monotone on the interval so the curve is a graph over x")
    if sign_on(ey, t, lo, hi) != "pos":
        raise Reject("redraw", "y(t) must be nonnegative on the interval")
    signed = exact_integral(sp.expand(ey * xp), t, lo, hi)
    value = abs(signed)
    if value == 0:
        raise Reject("redraw", "the area is 0")
    fx, fy = float_fn(ex, t), float_fn(ey, t)

    def trapezoid(n):
        pts = path(fx, fy, lo, hi, n)
        return abs(sum((q[0] - p[0]) * (p[1] + q[1]) / 2 for p, q in zip(pts, pts[1:])))
    got, want = richardson(trapezoid), float(value)
    if not close(got, want, 1e-6):
        raise Reject("redraw", "independent trapezoid area disagrees with the integral")
    steps = [step("Area under a parametric curve: integrate y dx = y (dx/dt) dt.", rf"A=\left|\int_{{{L(lo)}}}^{{{L(hi)}}} {L(ey)}\cdot\left({L(xp)}\right)dt\right|", ey * xp),
             step("Evaluate the definite integral." + (" x decreases, so take the absolute value." if direction == "neg" else ""),
                  rf"A={L(value)}", value)]
    statement = rf"Find the area of the region between the curve {_curve_text(ex, ey)}, ${L(lo)}\le t\le {L(hi)}$, and the $x$-axis."
    ident = {"x": str(ex), "y": str(ey), "t0": str(lo), "t1": str(hi)}
    return finish("parametric_area", ident, statement, steps, numeric_answer(value, calculator),
                  "parametric_area+trapezoid_polyline", f"polyline {got:.10g} vs {want:.10g}", [ex, ey], value,
                  {"family": family_of(ex, ey), "direction": direction})


def _polyline_length(fx, fy, lo, hi, weight=None):
    def length(n):
        pts = path(fx, fy, lo, hi, n)
        total = 0.0
        for p, q in zip(pts, pts[1:]):
            chord = math.hypot(q[0] - p[0], q[1] - p[1])
            total += chord if weight is None else math.pi * (weight(p) + weight(q)) * chord
        return total
    return richardson(length)


def parametric_arc_length(x, y, t0, t1, axes=None, calculator="none"):
    ex, ey, _, lo, hi = _span(x, y, t0, t1)
    check_axes(axes or {}, family=family_of(ex, ey))
    xp, yp = sp.diff(ex, t), sp.diff(ey, t)
    speed, value = integrate_speed(xp**2 + yp**2, t, lo, hi)
    got, want = _polyline_length(float_fn(ex, t), float_fn(ey, t), lo, hi), float(value)
    if not close(got, want, 1e-6):
        raise Reject("redraw", "independent polyline length disagrees with the integral")
    steps = [step("Arc length formula with the speed.", rf"L=\int_{{{L(lo)}}}^{{{L(hi)}}}\sqrt{{\left({L(xp)}\right)^2+\left({L(yp)}\right)^2}}\,dt", None),
             step("Simplify the speed.", rf"\sqrt{{x'^2+y'^2}}={L(speed)}", speed),
             step("Evaluate the definite integral.", rf"L={L(value)}", value)]
    statement = rf"Find the length of the curve {_curve_text(ex, ey)} for ${L(lo)}\le t\le {L(hi)}$."
    ident = {"x": str(ex), "y": str(ey), "t0": str(lo), "t1": str(hi)}
    return finish("parametric_arc_length", ident, statement, steps, numeric_answer(value, calculator),
                  "parametric_arc_length+chord_polyline", f"polyline {got:.10g} vs {want:.10g}", [ex, ey], value,
                  {"family": family_of(ex, ey)})


def surface_area(x, y, t0, t1, axis, axes=None, calculator="none"):
    if axis not in ("x", "y"):
        raise Reject("slip", "axis must be x or y")
    ex, ey, _, lo, hi = _span(x, y, t0, t1)
    check_axes(axes or {}, family=family_of(ex, ey), axis=axis)
    radius = ey if axis == "x" else ex
    if sign_on(radius, t, lo, hi) != "pos":
        raise Reject("redraw", "the distance from the axis of revolution must be nonnegative on the interval")
    guide = [sign_on(sp.diff(e, t), t, lo, hi) for e in (ex, ey)]
    if "pos" not in guide and "neg" not in guide:
        raise Reject("redraw", "the curve must be traced once: x or y must be monotone on the interval")
    xp, yp = sp.diff(ex, t), sp.diff(ey, t)
    speed, value = integrate_speed(xp**2 + yp**2, t, lo, hi, 2 * sp.pi * radius)
    if value == 0:
        raise Reject("redraw", "the surface area is 0")
    fx, fy = float_fn(ex, t), float_fn(ey, t)
    weight = (lambda p: p[1]) if axis == "x" else (lambda p: p[0])
    got, want = _polyline_length(fx, fy, lo, hi, weight), float(value)
    if not close(got, want, 1e-6):
        raise Reject("redraw", "independent frustum sum disagrees with the integral")
    steps = [step("Surface area of revolution about the axis.",
                  rf"S=\int_{{{L(lo)}}}^{{{L(hi)}}}2\pi\left({L(radius)}\right)\sqrt{{\left({L(xp)}\right)^2+\left({L(yp)}\right)^2}}\,dt", None),
             step("Simplify the speed and form the integrand.", rf"2\pi\left({L(radius)}\right)\left({L(speed)}\right)", 2 * sp.pi * radius * speed),
             step("Evaluate the definite integral.", rf"S={L(value)}", value)]
    statement = (rf"The curve {_curve_text(ex, ey)}, ${L(lo)}\le t\le {L(hi)}$, is revolved about the ${axis}$-axis. "
                 "Find the area of the surface that is generated.")
    ident = {"x": str(ex), "y": str(ey), "t0": str(lo), "t1": str(hi), "axis": axis}
    return finish("parametric_surface_area", ident, statement, steps, numeric_answer(value, calculator),
                  "parametric_surface_area+frustum_sum", f"frustum sum {got:.10g} vs {want:.10g}", [ex, ey], value,
                  {"family": family_of(ex, ey), "axis": axis})
