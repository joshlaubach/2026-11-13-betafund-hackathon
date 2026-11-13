"""Packet audit for the parametric and polar topics: mpmath numerical differentiation and quadrature, in place of the
engine's SymPy derivations. Parsing still happens in the sandbox worker."""
import mpmath as mp
import sympy as sp

from app.shared.integral_core import x as X_SYMBOL
from app.calc2.pp_core import t, th
from app.safe_parse import safe_parse

POLAR = {"slopes", "polar_area", "polar_arc_length"}
TOL = mp.mpf("1e-7")


def _num(value):
    return mp.mpf(str(sp.N(safe_parse(value), 40)))


def _parse(s, sym):
    return safe_parse(s, {sym.name: sym})


def _curve(topic, p):
    """Numeric coordinate functions x(u), y(u) and the parameter symbol name."""
    if topic in POLAR:
        r = sp.lambdify(th, _parse(p["r"], th), "mpmath")
        return (lambda u: r(u) * mp.cos(u)), (lambda u: r(u) * mp.sin(u)), r
    return (sp.lambdify(t, _parse(p["x"], t), "mpmath"), sp.lambdify(t, _parse(p["y"], t), "mpmath"), None)


def _slope(fx, fy, a):
    return mp.diff(fy, a) / mp.diff(fx, a)


def _second(fx, fy, a):
    return mp.diff(lambda u: mp.diff(fy, u) / mp.diff(fx, u), a) / mp.diff(fx, a)


def _check(name, ok, detail):
    return [name, bool(ok), detail]


def _near(got, want, tol=TOL):
    return abs(got - want) <= tol * max(1, abs(want))


def audit(topic, payload, answer, raw):
    mp.mp.dps = 30
    fx, fy, fr = _curve(topic, payload)
    if topic in ("tangents", "slopes"):
        return _tangent_audit(topic, payload, answer, fx, fy)
    if topic == "second_derivatives":
        return _second_audit(payload, answer, fx, fy)
    lo, hi = _num(payload["t0"]), _num(payload["t1"])
    want = _num(answer["sympy"])
    dx, dy = (lambda u: mp.diff(fx, u)), (lambda u: mp.diff(fy, u))
    if topic == "parametric_area":
        got = abs(mp.quad(lambda u: fy(u) * dx(u), mp.linspace(lo, hi, 5)))
        return [_check("P8 area = |integral of y dx/dt| by mpmath quadrature of numeric derivatives", _near(got, want),
                       f"{mp.nstr(got, 10)} vs {mp.nstr(want, 10)}")]
    if topic in ("parametric_arc_length", "polar_arc_length"):
        got = mp.quad(lambda u: mp.sqrt(dx(u) ** 2 + dy(u) ** 2), mp.linspace(lo, hi, 9))
        return [_check("P8 length = integral of the speed by mpmath quadrature of numeric derivatives", _near(got, want),
                       f"{mp.nstr(got, 10)} vs {mp.nstr(want, 10)}")]
    if topic == "parametric_surface_area":
        radius = fy if payload["axis"] == "x" else fx
        got = mp.quad(lambda u: 2 * mp.pi * radius(u) * mp.sqrt(dx(u) ** 2 + dy(u) ** 2), mp.linspace(lo, hi, 9))
        return [_check("P8 surface area = integral of 2 pi r ds by mpmath quadrature", _near(got, want),
                       f"{mp.nstr(got, 10)} vs {mp.nstr(want, 10)}")]
    inner = payload.get("r2")
    r2 = sp.lambdify(th, _parse(inner, th), "mpmath") if inner else (lambda u: 0)
    got = mp.quad(lambda u: (fr(u) ** 2 - r2(u) ** 2) / 2, mp.linspace(lo, hi, 9))
    return [_check("P8 polar area = integral of (R^2 - r^2)/2 by mpmath quadrature", _near(got, want),
                   f"{mp.nstr(got, 10)} vs {mp.nstr(want, 10)}")]


def _tangent_audit(topic, payload, answer, fx, fy):
    ask = payload["ask"]
    if ask == "horizontal":
        star = _num(answer["sympy"])
        lo, hi = _num(payload["t0"]), _num(payload["t1"])
        h = mp.mpf("1e-6")
        slope_zero = abs(mp.diff(fy, star)) < mp.mpf("1e-12")
        flips = sum(1 for a, b in zip(mp.linspace(lo, hi, 400), mp.linspace(lo, hi, 400)[1:])
                    if mp.diff(fy, a) * mp.diff(fy, b) < 0)
        return [_check("P8 dy/dt is 0 at the answer (numeric) and changes sign once in the interval",
                       lo < star < hi and slope_zero and flips <= 1 and abs(mp.diff(fx, star)) > h,
                       f"dy/dt={mp.nstr(mp.diff(fy, star), 4)}, {flips} sign change(s)")]
    a = _num(payload["t0"])
    slope = _slope(fx, fy, a)
    if ask == "slope":
        want = _num(answer["sympy"])
        return [_check("P8 dy/dx recomputed from numeric derivatives", _near(slope, want),
                       f"{mp.nstr(slope, 10)} vs {mp.nstr(want, 10)}")]
    line = sp.lambdify(X_SYMBOL, safe_parse(answer["sympy"], {"x": X_SYMBOL}), "mpmath")
    x0, y0 = fx(a), fy(a)
    return [_check("P8 the line passes through the point with the numeric slope",
                   abs(line(x0) - y0) < mp.mpf("1e-12") * max(1, abs(y0)) and _near(mp.diff(line, x0), slope),
                   f"line({mp.nstr(x0, 6)})={mp.nstr(line(x0), 8)} vs {mp.nstr(y0, 8)}, slope {mp.nstr(slope, 8)}")]


def _second_audit(payload, answer, fx, fy):
    ask = payload["ask"]
    if ask == "expression":
        f = sp.lambdify(t, safe_parse(answer["sympy"], {"t": t}), "mpmath")
        good = bad = 0
        for p in (mp.mpf("0.37"), mp.mpf("0.91"), mp.mpf("1.43"), mp.mpf("2.17")):
            try:
                ref = _second(fx, fy, p)
                got = f(p)
            except (ValueError, ZeroDivisionError, ArithmeticError):
                continue
            good += 1
            bad += not _near(got, ref, mp.mpf("1e-6"))
        return [_check("P8 d2y/dx2 expression agrees with nested numeric derivatives at sample t", good >= 2 and bad == 0,
                       f"{good} points, {bad} differ")]
    a = _num(payload["t0"])
    ref = _second(fx, fy, a)
    if ask == "value":
        want = _num(answer["sympy"])
        return [_check("P8 d2y/dx2 recomputed from nested numeric derivatives", _near(ref, want, mp.mpf("1e-6")),
                       f"{mp.nstr(ref, 10)} vs {mp.nstr(want, 10)}")]
    word = "concave up" if ref > 0 else "concave down"
    return [_check("P8 concavity from the sign of the nested numeric second derivative",
                   word in answer["latex"], f"{mp.nstr(ref, 6)} -> {word}")]
