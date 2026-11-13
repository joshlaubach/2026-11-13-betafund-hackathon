"""Cartesian arc length from bounded, server-defined curve families."""
import math

import mpmath as mp
import sympy as sp

from app import integration_basics as c4
from app.integral_core import L, Reject, x

FAMILIES = ("line", "root", "log_quadratic", "cubic_reciprocal")


def verify(family, a, span, scale, shift, slope, bounds=None, axes=None, calculator="none"):
    try:
        if bounds is not None:
            raise Reject("slip", "bounds are derived and must be null")
        return _verify(family, a, span, scale, shift, slope, axes or {}, calculator)
    except Reject as exc:
        return {"ok": False, "cause": exc.cause, "reason": exc.reason, "cap": exc.cap}


def _integer(value, name, low, high):
    n = c4._exact(value, name)
    if n.is_Integer is not True or not low <= n <= high:
        raise Reject("redraw", f"{name} must be an integer from {low} to {high}")
    return n


def _verify(family, a_s, span_s, scale_s, shift_s, slope_s, axes, calculator):
    payload = {"family": family, "a": a_s, "span": span_s, "scale": scale_s,
               "shift": shift_s, "slope": slope_s}
    for key, wanted in axes.items():
        if key != "recipe" and str(payload.get(key)) != str(wanted):
            raise Reject("redraw", f"assigned axes require {key} = {wanted}")
    if family not in FAMILIES:
        raise Reject("redraw", "family is outside the Cartesian arc-length whitelist")
    if calculator not in ("none", "scientific"):
        raise Reject("slip", "unsupported calculator tier")
    a = _integer(a_s, "a", 0 if family in ("line", "root") else 1, 7)
    span = _integer(span_s, "span", 1, 3)
    scale = _integer(scale_s, "scale", 1, 4)
    shift = _integer(shift_s, "shift", -3, 3)
    if family == "line":
        slope = _integer(slope_s, "slope", 1, 8)
    elif slope_s != "none":
        raise Reject("redraw", "slope must be none outside the line family")
    else:
        slope = None
    if family == "root" and span > 2:
        raise Reject("redraw", "root span must be 1 or 2")

    u = x / scale
    if family == "line":
        lo, hi = scale * a, scale * (a + span)
        curve = slope * x + shift
        speed = sp.sqrt(1 + slope**2)
        primitive = x * speed
    elif family == "root":
        lo = scale * ((a + 1)**2 - 1)
        hi = scale * ((a + span + 1)**2 - 1)
        curve = sp.Rational(2, 3) * scale * u**sp.Rational(3, 2) + shift
        speed = sp.sqrt(1 + u)
        primitive = sp.Rational(2, 3) * scale * (1 + u)**sp.Rational(3, 2)
    elif family == "log_quadratic":
        lo, hi = scale * a, scale * (a + span)
        curve = scale * (u**2 / 4 - sp.log(u) / 2) + shift
        speed = (u**2 + 1) / (2 * u)
        primitive = scale * (u**2 / 4 + sp.log(u) / 2)
    else:
        lo, hi = scale * a, scale * (a + span)
        curve = scale * (u**3 / 3 + 1 / (4 * u)) + shift
        speed = u**2 + 1 / (4 * u**2)
        primitive = scale * (u**3 / 3 - 1 / (4 * u))

    derivative = sp.diff(curve, x)
    if sp.simplify(speed**2 - (1 + derivative**2)) != 0 or sp.simplify(sp.diff(primitive, x) - speed) != 0:
        raise Reject("redraw", "the arc-length identity or antiderivative failed")
    if lo < 0 or (family in ("log_quadratic", "cubic_reciprocal") and lo <= 0):
        raise Reject("redraw", "the curve is outside its real domain")
    value = sp.simplify(primitive.subs(x, hi) - primitive.subs(x, lo))
    fn = sp.lambdify(x, sp.sqrt(1 + derivative**2), "mpmath")
    with mp.workdps(35):
        checked = mp.quad(fn, [int(lo), int(hi)])
        if not math.isfinite(float(checked)) or abs(checked - mp.mpf(str(sp.N(value, 35)))) > mp.mpf("1e-9") * max(1, abs(checked)):
            raise Reject("redraw", "independent arc-length quadrature disagrees")
    answer = c4._answer(value, calculator)
    statement = rf"Find the arc length of $y={L(curve)}$ from $x={L(lo)}$ to $x={L(hi)}$."
    steps = [
        {"text": "Differentiate the curve.", "latex": rf"y'={L(derivative)}", "sympy": str(derivative)},
        {"text": "Use the Cartesian arc-length formula and simplify the positive speed on this interval.",
         "latex": rf"L=\int_{{{L(lo)}}}^{{{L(hi)}}}\sqrt{{1+(y')^2}}\,dx=\int_{{{L(lo)}}}^{{{L(hi)}}}{L(speed)}\,dx",
         "sympy": str(speed)},
        {"text": "Evaluate the definite integral.", "latex": rf"L=\left[{L(primitive)}\right]_{{{L(lo)}}}^{{{L(hi)}}}={L(value)}",
         "sympy": str(value)},
    ]
    identity = {"topic": "arc_length", **payload}
    result = c4._result("arc_length", speed, answer, statement, steps, identity,
                        "cartesian_arc_length+independent_quadrature", (lo, hi),
                        {"family": family, "curve": str(curve), "lower": str(lo), "upper": str(hi)})
    result["integrand"] = str(speed)
    return result
