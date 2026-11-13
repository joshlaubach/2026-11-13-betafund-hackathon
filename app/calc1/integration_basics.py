"""Integration-basics verifiers; called only by the sandbox worker."""
import hashlib
import json

import sympy as sp

from app.shared.clean_answer import canon, expression_reason, value_reason
from app.shared.integral_core import (L, Reject, _bound, _crosscheck,
                               _derivative_matches, _discontinuities, _parse, _shape, x)
from app.shared.integral_finish import finish, generic_raw, scientific_reason, _under

TOPICS = ("basic_antiderivatives", "initial_value_problems", "riemann_sums", "definite_properties",
          "ftc_part1", "ftc_evaluate", "net_change_total_distance", "symmetry", "average_value")


def verify(topic, f, bounds=None, axes=None, calculator="none", **fields):
    try:
        return _verify(topic, f, bounds, axes or {}, calculator, fields)
    except Reject as r:
        return {"ok": False, "cause": r.cause, "reason": r.reason, "cap": r.cap}


def _step(text, expr, latex=None):
    return {"text": text, "latex": L(expr) if latex is None else latex, "sympy": str(expr)}


def _exact(s, label):
    if not isinstance(s, str):
        raise Reject("slip", f"{label} is required as a string")
    v = _bound(s, label)
    if v.has(sp.Float) or sp.count_ops(v) > 12:
        raise Reject("slip", f"{label} must be a small exact number")
    return v


def _expression(s, label):
    if not isinstance(s, str):
        raise Reject("slip", f"{label} is required as a string")
    e = _parse(s, x, label, depends=False)
    if e.has(sp.Float):
        raise Reject("slip", f"{label} must use exact coefficients")
    return e


def _span(bounds):
    if not isinstance(bounds, (list, tuple)) or len(bounds) != 2:
        raise Reject("slip", "two finite bounds are required")
    a, b = (_exact(s, "bound") for s in bounds)
    if not a < b:
        raise Reject("slip", "lower bound must be less than upper bound")
    return a, b


def _continuous(f, a, b):
    if _discontinuities(f, a, b):
        raise Reject("redraw", "function must be continuous on the closed interval")


def _primitive(f):
    from app.shared.integral_core import basic_primitive
    return basic_primitive(f)


def _integral(f, a, b):
    _continuous(f, a, b)
    F = _primitive(f)
    value = sp.simplify(F.subs(x, b) - F.subs(x, a))
    if not _crosscheck(f, a, b, value):
        raise Reject("redraw", "numeric cross-check disagrees with the integral")
    return F, value


def _answer(v, calculator, expression=False):
    v = canon(v)
    if expression:
        if sp.count_ops(v) > 100:
            raise Reject("redraw", "derived expression is too large")
        why = expression_reason(v, x, True)
    else:
        why = scientific_reason(v) if calculator == "scientific" else value_reason(v, True)
    if why:
        raise Reject("redraw", f"answer is not a usable {'expression' if expression else 'value'} ({why})", why)
    return {"type": "expression" if expression else "numeric",
            "latex": L(v) if expression or calculator == "none" else f"{float(v):.3f}",
            "sympy": str(v), "numeric": None if expression else float(v)}


def _result(topic, f, answer, statement, steps, identity, method, bounds=None, extra=None):
    raw = generic_raw(f, _expression(answer["sympy"], "derived answer"), steps, bounds is not None,
                      False, answer["type"], {"rules": [], "topic": topic, **(extra or {})})
    key = json.dumps(identity, sort_keys=True)
    return {"ok": True, "statement": statement, "answer": answer, "steps": steps,
            "method": method, "calculator_check": "passed", "has_discontinuity": False,
            "integrand": str(f), "hash": hashlib.sha256((key + str(f)).encode()).hexdigest()[:16],
            "shape": topic + "|" + key, "raw": raw}


def _verify(topic, f_s, bounds, axes, calculator, fields):
    if topic not in TOPICS:
        raise Reject("slip", "unknown integration-basics topic")
    if calculator not in ("none", "scientific"):
        raise Reject("slip", "unsupported calculator tier")
    payload = {"f": f_s, "bounds": bounds, **fields}
    for name, want in axes.items():
        if name == "recipe":
            continue
        if name == "lower" or name == "upper":
            got = bounds[0 if name == "lower" else 1] if bounds else None
        else:
            got = payload.get(name)
        matches = got == str(want)
        if not matches and name in ("f", "g", "h", "lower", "upper", "point", "value", "n") and isinstance(got, str):
            matches = sp.simplify(_expression(got, "assigned field") - _expression(str(want), "assigned field")) == 0
        if not matches:
            raise Reject("redraw", f"assigned axes require {name} = {want}")
    f = _expression(f_s, "f")
    mode = fields.get("mode")
    if topic == "definite_properties":
        if bounds is not None or f.has(x):
            raise Reject("slip", "properties use given integral values, not a formula or bounds")
        left = _exact(fields.get("value"), "left integral") if mode in ("split", "combine") else sp.Integer(0)
        c = _exact(fields.get("n"), "coefficient")
        cf = L(c * sp.Function("f")(x))
        if mode == "reverse":
            v = -c * f
            statement = rf"Determine $\int_b^a {cf}\,dx$ given $a<b$ and $\int_a^b f(x)\,dx={L(f)}$."
        elif mode == "split":
            v = c * (f - left)
            statement = rf"Determine $\int_c^b {cf}\,dx$ given $a<c<b$, $\int_a^b f(x)\,dx={L(f)}$ and $\int_a^c f(x)\,dx={L(left)}$."
        elif mode == "combine":
            d = _exact(fields.get("point"), "second coefficient")
            v = c * f + d * left
            combination = L(c * sp.Function("f")(x) + d * sp.Function("g")(x))
            statement = rf"Determine $\int_a^b \left({combination}\right)\,dx$ given $\int_a^b f(x)\,dx={L(f)}$ and $\int_a^b g(x)\,dx={L(left)}$."
        else:
            raise Reject("slip", "mode must be reverse, split or combine")
        steps = [_step("Use orientation, additivity and linearity of definite integrals.", v)]
        return _result(topic, f, _answer(v, calculator), statement, steps,
                       {"topic": topic, "mode": mode, "given": str(f), "left": str(left), "c": str(c),
                        "d": fields.get("point") if mode == "combine" else None}, "integral_properties")
    if topic == "ftc_part1":
        if bounds is not None:
            raise Reject("slip", "FTC accumulation tasks require null bounds")
        g = _expression(fields.get("g"), "upper endpoint")
        h = _expression(fields.get("h"), "lower endpoint")
        if not (g.is_polynomial(x) and h.is_polynomial(x)) or any(e.has(x) and sp.degree(e, x) > 4 for e in (g, h)):
            raise Reject("redraw", "endpoints must be polynomials of degree at most four")
        # FTC accepts continuous functions without requiring an elementary primitive.
        if any(not isinstance(node, (sp.Add, sp.Mul, sp.Pow, sp.Symbol, sp.Number, sp.NumberSymbol,
                                     sp.sin, sp.cos, sp.exp)) or
               (node.is_Pow and not (node.exp.is_Integer and 0 <= node.exp <= 8))
               for node in sp.preorder_traversal(f)):
            raise Reject("redraw", "FTC integrand must be globally continuous polynomial, sin, cos or exp")
        if f == 0 or g == h:
            raise Reject("redraw", "accumulation function must be nontrivial")
        v = sp.simplify(f.subs(x, g) * sp.diff(g, x) - f.subs(x, h) * sp.diff(h, x))
        statement = rf"Find $A'(x)$ for $A(x)=\int_{{{L(h)}}}^{{{L(g)}}} {_under(f).replace('x', 't')}\,dt$."
        steps = [_step("Differentiate each moving endpoint and apply the chain rule.", v,
                       rf"A'(x)=f(g(x))g'(x)-f(h(x))h'(x)={L(v)}")]
        return _result(topic, f, _answer(v, calculator, True), statement, steps,
                       {"topic": topic, "f": _shape(f, False), "g": str(g), "h": str(h)}, "ftc_chain_rule")
    if topic == "basic_antiderivatives":
        if bounds is not None:
            raise Reject("slip", "basic antiderivatives require null bounds")
        F = _primitive(f)
        steps = []
        if sp.expand(f) != f:
            steps.append(_step("Expand or divide to expose the standard table terms.", sp.expand(f)))
        steps.append(_step("Integrate the standard forms term by term.", F))
        r = finish(f, F, f, steps, None,
                   calculator=calculator, extra_raw={"rules": [], "topic": topic})
        return r
    if topic == "initial_value_problems":
        if bounds is not None:
            raise Reject("slip", "initial-value problems require null bounds")
        p = _exact(fields.get("point"), "initial point")
        v0 = _exact(fields.get("value"), "initial value")
        F = _primitive(f)
        _continuous(f, p, p)
        c = sp.simplify(v0 - F.subs(x, p))
        v = sp.simplify(F + c)
        if v.subs(x, p) != v0 or not _derivative_matches(v, f):
            raise Reject("redraw", "initial condition or derivative check failed")
        steps = [_step("Integrate to obtain the general solution.", F, rf"y={L(F)}+C"),
                 _step("Substitute the initial condition to determine C.", c, rf"C={L(c)}"),
                 _step("Write the solution satisfying the initial condition.", v)]
        statement = rf"Find $y(x)$ if $y'(x)={L(f)}$ and $y({L(p)})={L(v0)}$."
        return _result(topic, f, _answer(v, calculator, True), statement, steps,
                       {"topic": topic, "f": _shape(f, False), "point": str(p), "value": str(v0)},
                       "diff_antiderivative+initial_condition")
    a, b = _span(bounds)
    if topic == "riemann_sums":
        if mode not in ("left", "right", "midpoint"):
            raise Reject("slip", "rule must be left, right or midpoint")
        n = _exact(fields.get("n"), "number of subintervals")
        if n.is_Integer is not True or not 2 <= n <= 12:
            raise Reject("slip", "number of subintervals must be an integer from 2 to 12")
        if not f.is_polynomial(x) or sp.degree(f, x) > 6:
            raise Reject("redraw", "Riemann sums support polynomials of degree at most six")
        dx = (b - a) / n
        offset = {"left": 0, "right": 1, "midpoint": sp.Rational(1, 2)}[mode]
        nodes = [a + (i + offset) * dx for i in range(int(n))]
        v = sp.simplify(dx * sum(f.subs(x, t) for t in nodes))
        # Independent finite numeric sum, without symbolic substitution.
        fn = sp.lambdify(x, f, "mpmath")
        num = float(dx) * sum(float(fn(float(t))) for t in nodes)
        if abs(num - float(v)) > 1e-9 * max(1, abs(float(v))):
            raise Reject("redraw", "numeric node sum disagrees")
        steps = [_step("Compute the width of each equal subinterval.", dx, rf"\Delta x={L(dx)}"),
                 _step("Use the specified sample point in each subinterval.", sp.Tuple(*nodes)),
                 _step("Evaluate f at those sample points.", sp.Tuple(*(f.subs(x,t) for t in nodes))),
                 _step("Multiply the sum of those values by the subinterval width.", v)]
        sample = {"left": "left endpoint", "right": "right endpoint", "midpoint": "midpoint"}[mode]
        statement = rf"Evaluate the {mode} Riemann sum for $f(x)={L(f)}$ on $[{L(a)},{L(b)}]$ with ${n}$ equal subintervals. Evaluate $f$ at the {sample} of each subinterval."
        return _result(topic, f, _answer(v, calculator), statement, steps,
                       {"topic": topic, "f": _shape(f, True), "rule": mode, "n": str(n), "a": str(a), "b": str(b)},
                       "finite_sum+numeric_check", bounds)
    if topic == "symmetry":
        if a != -b:
            raise Reject("slip", "symmetry requires an interval [-a,a]")
        even = sp.simplify((f + f.subs(x, -x)) / 2)
        odd = sp.simplify((f - f.subs(x, -x)) / 2)
        if any(not isinstance(node, (sp.Add, sp.Mul, sp.Pow, sp.Symbol, sp.Number, sp.NumberSymbol,
                                     sp.sin, sp.cos, sp.exp)) or
               (node.is_Pow and not (node.exp.is_Integer and 0 <= node.exp <= 8))
               for node in sp.preorder_traversal(odd)):
            raise Reject("redraw", "odd component requires a globally continuous polynomial, sin, cos or exp form")
        v = sp.Integer(0)
        steps = []
        if even == 0:
            parity = "odd"
            steps.append(_step("The function is odd, so opposite halves cancel.", v))
        else:
            parity = "even" if odd == 0 else "mixed"
            if odd != 0:
                steps.append(_step("Split into even and odd components; the odd component cancels.", even,
                                   rf"f_{{\mathrm{{even}}}}(x)={L(even)}"))
            F, half = _integral(even, sp.Integer(0), b)
            v = sp.simplify(2 * half)
            steps.append(_step("Double the integral of the even component on the positive half.", v,
                               rf"2\int_0^{{{L(b)}}}{_under(even)}\,dx={L(v)}"))
        if not _crosscheck(f, a, b, v):
            raise Reject("redraw", "numeric symmetry cross-check failed")
        return _result(topic, f, _answer(v, calculator),
                       rf"Evaluate $\int_{{{L(a)}}}^{{{L(b)}}}{_under(f)}\,dx$.", steps,
                       {"topic": topic, "f": _shape(f, True), "a": str(a), "b": str(b)},
                       "parity+ftc+mpmath", bounds, {"parity": parity})
    F, integral = _integral(f, a, b)
    steps = [_step("Find an antiderivative using the standard forms.", F)]
    if topic == "ftc_evaluate":
        r = finish(f, F, f, steps, (a, b), calculator=calculator, extra_raw={"rules": [], "topic": topic})
        r["statement"] = r["statement"].replace(", or state that it diverges", "")
        r["shape"] += "|bounds:" + str((a,b))
        return r
    if topic == "average_value":
        v = sp.simplify(integral / (b - a))
        steps += [_step("Divide the definite integral by the length of the interval.", v,
                        rf"f_{{\mathrm{{avg}}}}=\frac{{{L(integral)}}}{{{L(b-a)}}}={L(v)}")]
        statement = rf"Find the average value of $f(x)={L(f)}$ on $[{L(a)},{L(b)}]$."
        return _result(topic, f, _answer(v, calculator), statement, steps,
                       {"topic": topic, "f": _shape(f, True), "a": str(a), "b": str(b)},
                       "ftc_average+mpmath", bounds)
    if topic == "net_change_total_distance":
        if mode not in ("net", "distance"):
            raise Reject("slip", "mode must be net or distance")
        if not f.is_polynomial(x) or not 1 <= sp.degree(f, x) <= 4:
            raise Reject("redraw", "velocity must be a polynomial of degree one to four")
        roots = sp.solveset(f, x, domain=sp.Interval(a, b))
        if not isinstance(roots, sp.FiniteSet):
            raise Reject("redraw", "could not determine every velocity zero")
        cuts = sorted({a, b, *roots}, key=float)
        distance = sp.Integer(0)
        changes = []
        for p, q in zip(cuts, cuts[1:]):
            piece = sp.simplify(F.subs(x, q) - F.subs(x, p))
            if not _crosscheck(sp.Abs(f), p, q, sp.Abs(piece)):
                raise Reject("redraw", "distance numeric cross-check failed")
            distance += sp.Abs(piece)
            changes.append(sp.sign(f.subs(x, (p + q) / 2)))
        if len(set(changes)) < 2:
            raise Reject("redraw", "velocity must change sign inside the interval")
        v = integral if mode == "net" else sp.simplify(distance)
        steps = [_step("Find the velocity zeros and split the interval there.", sp.Tuple(*cuts)),
                 _step("Find an antiderivative of velocity to compute each displacement.", F)]
        for p, q in zip(cuts, cuts[1:]):
            piece = sp.simplify(F.subs(x, q) - F.subs(x, p))
            steps.append(_step("Compute the signed displacement on this interval.", piece,
                               rf"\int_{{{L(p)}}}^{{{L(q)}}}{_under(f)}\,dx={L(piece)}"))
        steps.append(_step("Add signed displacements." if mode == "net" else "Add the absolute values of the displacements.", v))
        statement = rf"Find the {'net change in position' if mode == 'net' else 'total distance traveled'} for velocity $v(t)={L(f).replace('x', 't')}$ on $[{L(a)},{L(b)}]$."
        return _result(topic, f, _answer(v, calculator), statement, steps,
                       {"topic": topic, "f": _shape(f, True), "a": str(a), "b": str(b), "ask": mode, "zeros": [str(t) for t in sorted(roots,key=float)]},
                       "sign_split+ftc+mpmath", bounds,
                       {"zeros": [str(t) for t in roots], "net": str(integral), "distance": str(distance)})
    raise Reject("slip", "unknown task")
