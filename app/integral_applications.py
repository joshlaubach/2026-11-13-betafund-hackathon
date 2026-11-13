"""Area and volume applications, derived and checked inside the sandbox."""
import sympy as sp

from app import integration_basics as c4
from app.integral_core import L, Reject, x

TOPICS = ("area_between_curves", "volume_disk_washer", "volume_shell", "volume_cross_sections")
SHAPE_FACTORS = {
    "square": sp.Integer(1),
    "semicircle": sp.pi / 8,
    "equilateral": sp.sqrt(3) / 4,
    "right_isosceles": sp.Rational(1, 2),
}


def verify(topic, family, a, b, c, scale, shift, axis, shape, bounds=None, axes=None, calculator="none"):
    try:
        if bounds is not None:
            raise Reject("slip", "bounds are derived from a and b and must be null")
        return _verify(topic, family, a, b, c, scale, shift, axis, shape, axes or {}, calculator)
    except Reject as exc:
        return {"ok": False, "cause": exc.cause, "reason": exc.reason, "cap": exc.cap}


def _number(value, label):
    if value == "none":
        return None
    return c4._exact(value, label)


def _nonnegative(expr, a, b):
    derivative = sp.diff(expr, x)
    if derivative == 0:
        if sp.simplify(expr).is_nonnegative is not True:
            raise Reject("redraw", "a radius, height or base length is negative on the interval")
        return
    critical = sp.solve(derivative, x)
    if any(p.is_real is not True for p in critical):
        raise Reject("redraw", "could not prove the geometric length is nonnegative")
    critical = [p for p in critical if a <= p <= b]
    values = [sp.simplify(expr.subs(x, p)) for p in {a, b, *critical}]
    if any(v.is_nonnegative is not True for v in values):
        raise Reject("redraw", "a radius, height or base length is negative on the interval")


def _integral(expr, a, b, calculator):
    translated = sp.expand(expr.subs(x, x + a))
    factored = sp.factor_terms(translated)
    factor, core = factored.as_independent(x, as_Add=False)
    result = c4.verify("ftc_evaluate", str(sp.expand(core)), ["0", str(b - a)], calculator="none")
    if not result["ok"]:
        raise Reject(result["cause"], result["reason"], result.get("cap"))
    value = sp.simplify(factor * sp.sympify(result["answer"]["sympy"]))
    steps = result["steps"]
    if a != 0:
        steps.insert(0, {"text": "Translate the interval with u = x minus the left endpoint.",
                         "latex": rf"u=x-({L(a)})", "sympy": str(x - a)})
    if factor != 1:
        steps.append({"text": "Restore the constant geometric factor.", "latex": L(value), "sympy": str(value)})
    return value, steps


def _result(topic, integrand, a, b, value, statement, steps, identity, calculator, method, extra):
    answer = c4._answer(value, calculator)
    result = c4._result(topic, integrand, answer, statement, steps, identity, method, (a, b), extra)
    result["integrand"] = str(integrand)
    result["raw"].update({"lower": str(a), "upper": str(b), **extra})
    return result


def _verify(topic, family, a_s, b_s, c_s, scale_s, shift_s, axis, shape, axes, calculator):
    if topic not in TOPICS:
        raise Reject("slip", "unknown integral-applications topic")
    payload = {"family": family, "a": a_s, "b": b_s, "c": c_s, "scale": scale_s,
               "shift": shift_s, "axis": axis, "shape": shape}
    for key, wanted in axes.items():
        if key != "recipe" and str(payload.get(key)) != str(wanted):
            raise Reject("redraw", f"assigned axes require {key} = {wanted}")
    a, b = _number(a_s, "left endpoint"), _number(b_s, "right endpoint")
    c, scale, shift = _number(c_s, "middle intersection"), _number(scale_s, "scale"), _number(shift_s, "shift")
    if None in (a, b, scale, shift) or scale <= 0:
        raise Reject("slip", "a positive scale and exact interval parameters are required")
    if topic == "area_between_curves" and not a < b:
        raise Reject("slip", "area requires a < b")
    if topic != "area_between_curves" and b <= 0:
        raise Reject("slip", "the interval width b must be positive")
    identity = {"topic": topic, **payload}

    if topic == "area_between_curves":
        if family in ("cap", "tilted_cap"):
            lower = shift + (x if family == "tilted_cap" else 0)
            diff = sp.expand(scale * (x - a) * (b - x))
            upper = sp.expand(lower + diff)
            cuts = [a, b]
        elif family == "two_lobes":
            if c is None or not a < c < b:
                raise Reject("slip", "two_lobes requires a middle intersection between a and b")
            lower = shift
            diff = sp.expand(scale * (x - a) * (x - c) * (b - x))
            upper = sp.expand(lower + diff)
            cuts = [a, c, b]
        else:
            raise Reject("slip", "unknown area family")
        roots = sp.solveset(upper - lower, x, domain=sp.Interval(a, b))
        if not isinstance(roots, sp.FiniteSet) or set(roots) != set(cuts):
            raise Reject("redraw", "the boundary intersections could not be derived exactly")
        value, steps = sp.Integer(0), [{"text": "Solve for the intersection points and split there.",
                                        "latex": "x=" + ",".join(L(p) for p in cuts), "sympy": str(tuple(cuts))}]
        for lo, hi in zip(cuts, cuts[1:]):
            signed = sp.expand(diff * sp.sign(diff.subs(x, (lo + hi) / 2)))
            piece, piece_steps = _integral(signed, lo, hi, calculator)
            value += piece
            steps += piece_steps
        value = sp.simplify(value)
        integrand = sp.Abs(diff)
        statement = (f"Find the total area between $y={L(upper)}$ and $y={L(lower)}$ "
                     f"from $x={L(a)}$ to $x={L(b)}$.")
        return _result(topic, integrand, a, b, value, statement, steps, identity, calculator,
                       "intersections+absolute_definite_integrals", {"cuts": [str(p) for p in cuts]})

    # For the three volume topics, b is the positive interval width. This keeps translated
    # regions varied without making the verified polynomial coefficients unbounded.
    b = a + b

    if c is not None:
        raise Reject("slip", "c must be none for this topic")

    if topic == "volume_disk_washer":
        t = x - a
        if family == "disk_linear":
            outer, inner = 1 + scale * t, sp.Integer(0)
        elif family == "disk_quadratic":
            outer, inner = 1 + scale * t**2, sp.Integer(0)
        elif family == "washer_linear":
            inner, outer = 1 + t, 1 + t + scale
        elif family == "washer_curved":
            inner, outer = sp.Integer(1), 2 + scale * t**2
        else:
            raise Reject("slip", "unknown disk/washer family")
        if axis not in ("x", "shifted") or shape != "none":
            raise Reject("slip", "disk/washer axis must be x or shifted, and shape must be none")
        _nonnegative(inner, a, b)
        _nonnegative(outer - inner, a, b)
        axis_y = sp.Integer(0) if axis == "x" else shift
        integrand = sp.expand(sp.pi * (outer**2 - inner**2))
        value, steps = _integral(integrand, a, b, calculator)
        statement = (f"The region between $y={L(axis_y + outer)}$ and $y={L(axis_y + inner)}$ on "
                     f"$[{L(a)},{L(b)}]$ is revolved about {'the $x$-axis' if axis == 'x' else '$y='+L(axis_y)+'$'}. "
                     "Find its volume using disks or washers.")
        steps.insert(0, {"text": "Use the washer area pi(R^2-r^2).",
                         "latex": rf"A(x)=\pi\left(({L(outer)})^2-({L(inner)})^2\right)", "sympy": str(integrand)})
        return _result(topic, integrand, a, b, value, statement, steps, identity, calculator,
                       "washer+ftc", {"outer": str(outer), "inner": str(inner), "axis_value": str(axis_y)})

    if topic == "volume_shell":
        if axis not in ("y", "shifted") or shape != "none":
            raise Reject("slip", "shell axis must be y or shifted, and shape must be none")
        axis_x = sp.Integer(0) if axis == "y" else shift
        radius = x - axis_x
        if a <= axis_x:
            raise Reject("redraw", "the shell interval must lie to the right of the axis")
        if family == "linear_height":
            height = 1 + scale * (x - a)
        elif family == "decreasing_height":
            height = 1 + scale * (b - x)
        elif family == "quadratic_height":
            height = 1 + scale * (x - a) * (b - x)
        else:
            raise Reject("slip", "unknown shell family")
        _nonnegative(height, a, b)
        integrand = sp.expand(2 * sp.pi * radius * height)
        value, steps = _integral(integrand, a, b, calculator)
        statement = (f"The region under $y={L(height)}$ and above the x-axis on $[{L(a)},{L(b)}]$ is revolved "
                     f"about {'the $y$-axis' if axis == 'y' else '$x='+L(axis_x)+'$'}. Find its volume using shells.")
        steps.insert(0, {"text": "Use shell circumference times height.",
                         "latex": rf"2\pi({L(radius)})({L(height)})", "sympy": str(integrand)})
        return _result(topic, integrand, a, b, value, statement, steps, identity, calculator,
                       "shells+ftc", {"radius": str(radius), "height": str(height), "axis_value": str(axis_x)})

    if axis != "x" or shape not in SHAPE_FACTORS:
        raise Reject("slip", "cross-sections require axis=x and a supported shape")
    if family == "linear_base":
        width = 1 + scale * (x - a)
    elif family == "decreasing_base":
        width = 1 + scale * (b - x)
    elif family == "quadratic_base":
        width = 1 + scale * (x - a)**2
    elif family == "cap_base":
        width = 1 + scale * (x - a) * (b - x)
    else:
        raise Reject("slip", "unknown cross-section family")
    _nonnegative(width, a, b)
    factor = SHAPE_FACTORS[shape]
    integrand = sp.expand(factor * width**2)
    value, steps = _integral(integrand, a, b, calculator)
    names = {"square": "squares", "semicircle": "semicircles", "equilateral": "equilateral triangles",
             "right_isosceles": "right isosceles triangles with one leg in the base region"}
    statement = (f"A solid has base region between $y={L(shift + width)}$ and $y={L(shift)}$ on "
                 f"$[{L(a)},{L(b)}]$. Cross-sections perpendicular to the x-axis are {names[shape]}. Find the volume.")
    steps.insert(0, {"text": "Write the cross-sectional area in terms of the base width.",
                     "latex": rf"A(x)={L(factor)}\left({L(width)}\right)^2", "sympy": str(integrand)})
    return _result(topic, integrand, a, b, value, statement, steps, identity, calculator,
                   "cross_sections+ftc", {"width": str(width), "cross_section": shape})
