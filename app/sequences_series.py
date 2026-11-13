"""Verified sequence and first-series-test problems; called only by the sandbox worker."""
import hashlib

import sympy as sp

from app.clean_answer import canon, value_reason
from app.integral_core import L, Reject, _parse
from app.sequences_series_checks import sequence as numeric_sequence
from app.sequences_series_checks import series as numeric_series

n = sp.Symbol("n", integer=True, positive=True)
a = sp.Symbol("a", real=True)

TOPICS = ("limits", "monotone_bounded", "recursive", "geometric", "telescoping", "p_series")
SERIES = {"geometric", "telescoping", "p_series"}


def verify(topic, term, ratio=None, start="1", axes=None, calculator="none", bounds=None):
    try:
        if bounds is not None:
            raise Reject("slip", "sequence and series payloads do not use bounds")
        return _verify(topic, term, ratio, start, axes or {}, calculator)
    except Reject as r:
        return {"ok": False, "cause": r.cause, "reason": r.reason, "cap": r.cap}


def _exact(s, label):
    if not isinstance(s, str):
        raise Reject("slip", f"{label} must be a string")
    v = _parse(s, n, label, depends=False)
    if v.has(sp.Float) or v.is_real is not True or sp.count_ops(v) > 8:
        raise Reject("slip", f"{label} must be a small exact real number")
    return v


def _start(s):
    v = _exact(s, "starting index")
    if v.is_Integer is not True or not 0 <= v <= 20:
        raise Reject("slip", "starting index must be an integer from 0 to 20")
    return int(v)


def _term(s, symbol=n):
    if not isinstance(s, str):
        raise Reject("slip", "term must be a string")
    v = _parse(s, symbol, "term")
    if v.has(sp.Float) or sp.count_ops(v) > 30:
        raise Reject("redraw", "term must use exact numbers and at most 30 operations")
    return v


def _check_axes(axes, **actual):
    for key, want in axes.items():
        if key == "recipe":
            continue
        if key in actual and str(actual[key]) != str(want):
            raise Reject("redraw", f"axes: the server assigned {key} = {want} (not {actual[key]})")


def _pow_with_n(e, base=None):
    return any(p.exp.has(n) and (base is None or p.base == base) for p in e.atoms(sp.Pow))


def _sequence_family(t):
    if any(f.func != sp.exp for f in t.atoms(sp.Function)):
        raise Reject("redraw", "term is outside the sequence scope whitelist")
    if _pow_with_n(t, sp.Integer(-1)):
        return "alternating"
    if _pow_with_n(t) or t.has(sp.exp):
        for p in t.atoms(sp.Pow):
            if p.exp.has(n) and p.base != -1 and not (p.base.is_Rational and p.base > 0):
                raise Reject("redraw", "exponential sequence bases must be positive rational numbers")
        return "exponential"
    radicals = [p for p in t.atoms(sp.Pow) if p.exp.q == 2]
    if radicals:
        if len(radicals) > 2 or not all(p.base.is_polynomial(n) and sp.degree(p.base, n) <= 2 for p in radicals):
            raise Reject("redraw", "radical sequences allow at most two square roots of quadratics")
        return "radical"
    if t.is_polynomial(n):
        if sp.degree(t, n) > 4:
            raise Reject("redraw", "polynomial sequence degree must be at most four")
        return "polynomial"
    if t.is_rational_function(n):
        num, den = sp.fraction(sp.cancel(t))
        if max(sp.degree(num, n), sp.degree(den, n)) > 4:
            raise Reject("redraw", "rational sequence degrees must be at most four")
        return "rational"
    raise Reject("redraw", "term is outside the sequence scope whitelist")


def _limit(t):
    if _pow_with_n(t, sp.Integer(-1)):
        m = sp.Symbol("m", integer=True, positive=True)
        even = sp.limit(t.subs(n, 2 * m), m, sp.oo)
        odd = sp.limit(t.subs(n, 2 * m + 1), m, sp.oo)
        return even if even == odd and even.is_finite else None
    v = sp.limit(t, n, sp.oo)
    return v if v.is_finite and v.is_real else None


def _monotonicity(t):
    d = sp.factor(sp.cancel(t.subs(n, n + 1) - t))
    if d.is_positive:
        return "increasing", d
    if d.is_negative:
        return "decreasing", d
    if d == 0:
        return "constant", d
    return "not_monotone", d


def _geometric(t, ratio, start):
    if ratio is None:
        raise Reject("slip", "ratio is required for a geometric series")
    r = _exact(ratio, "ratio")
    if not r.is_Rational or r == 0 or abs(r) > 4:
        raise Reject("redraw", "geometric ratio must be a nonzero rational number of magnitude at most four")
    if sp.simplify(t.subs(n, n + 1) - r * t) != 0:
        raise Reject("redraw", "term does not have the proposed constant ratio")
    first = sp.simplify(t.subs(n, start))
    if first.is_Rational is not True or first == 0 or abs(first) > 50:
        raise Reject("redraw", "the first term must be a small nonzero rational number")
    if set(t.free_symbols) != {n}:
        raise Reject("redraw", "geometric term must depend only on n")
    return r, first


def _p_form(t, start):
    c, rest = t.as_independent(n, as_Add=False)
    if c.is_Rational is not True or not 0 < c <= 20 or not rest.is_Pow:
        raise Reject("redraw", "p-series term must be c/(n+s)^p with positive rational c")
    base, exponent = rest.as_base_exp()
    if exponent.is_Rational is not True or exponent >= 0:
        raise Reject("redraw", "p-series exponent must be a positive rational p")
    p = -exponent
    if not 0 < p <= 6 or not base.is_polynomial(n) or sp.degree(base, n) != 1:
        raise Reject("redraw", "p-series must use a positive rational p at most six and a linear base")
    poly = sp.Poly(base, n)
    if poly.coeff_monomial(n) != 1 or poly.coeff_monomial(1).is_Integer is not True:
        raise Reject("redraw", "p-series base must be n plus an integer shift")
    shift = int(poly.coeff_monomial(1))
    if start + shift <= 0:
        raise Reject("redraw", "p-series denominator must be positive from the starting index onward")
    return c, p, shift


def _telescoping(t, start):
    for power in (1, 2):
        for shift in range(-8, 9):
            for gap in range(1, 5):
                if start + shift <= 0:
                    continue
                base = 1 / (n + shift) ** power - 1 / (n + shift + gap) ** power
                c = sp.cancel(t / base)
                if not c.has(n) and c.is_Rational and c != 0 and abs(c) <= 20:
                    return {"family": "telescoping", "coefficient": str(c), "shift": shift,
                            "gap": gap, "power": power, "radical": False}
    for shift in range(0, 9):
        for gap in range(1, 5):
            base = sp.sqrt(n + shift + gap) - sp.sqrt(n + shift)
            c = sp.simplify(t / base)
            if not c.has(n) and c.is_Rational and c != 0 and abs(c) <= 20:
                return {"family": "telescoping", "coefficient": str(c), "shift": shift,
                        "gap": gap, "power": 0, "radical": True}
    raise Reject("redraw", "term is outside the telescoping-series scope whitelist")


def _answer(value, verdict, calculator):
    if verdict == "diverges" or value is None:
        word = verdict if verdict == "diverges" else "converges"
        return {"type": "enum", "latex": rf"\text{{{word}}}", "sympy": None, "numeric": None}
    value = canon(value)
    why = value_reason(value, True)
    if why:
        raise Reject("redraw", f"answer is not a usable short exact value ({why})", why)
    return {"type": "numeric", "latex": L(value) if calculator == "none" else f"{float(value):.3f}",
            "sympy": str(value), "numeric": float(value)}


def _step(text, latex, expr=None):
    return {"text": text, "latex": latex, "sympy": None if expr is None else str(expr)}


def _finish(topic, term, ratio, start, family, verdict, value, statement, steps, method, check, extra=None,
            calculator="none", answer=None):
    answer = answer or _answer(value, verdict, calculator)
    identity = f"{topic}|{sp.srepr(term)}|{ratio}|{start}"
    raw = {"ops_integrand": int(sp.count_ops(term)), "ops_R": int(sp.count_ops(term)),
           "ops_F": int(sp.count_ops(value)) if value is not None else 0,
           "g_polynomial": bool(term.is_polynomial(n)), "deg_g": int(sp.degree(term, n)) if term.is_polynomial(n) else None,
           "n_terms_R": len(sp.Add.make_args(sp.expand(term))), "const_factor": False, "definite": True,
           "has_discontinuity": False, "steps": len(steps), "answer_type": answer["type"], "rules": [],
           "topic": topic, "family": family, "verdict": verdict, "start": start,
           "numeric_check": check, **(extra or {})}
    return {"ok": True, "statement": statement, "answer": answer, "steps": steps, "method": method,
            "calculator_check": "passed", "hash": hashlib.sha256(identity.encode()).hexdigest()[:16],
            "shape": identity, "has_discontinuity": False, "integrand": str(term), "raw": raw}


def _verify(topic, term_s, ratio_s, start_s, axes, calculator):
    if topic not in TOPICS:
        raise Reject("slip", "unknown sequences/series topic")
    if calculator not in ("none", "scientific"):
        raise Reject("slip", "unsupported calculator tier")
    start = _start(start_s)
    ratio_value = None if ratio_s is None else _exact(ratio_s, "ratio")
    ratio = None if ratio_value is None else str(ratio_value)
    if topic == "recursive":
        return _recursive(_term(term_s, a), ratio_value, _exact(start_s, "initial value"), axes, calculator)
    term = _term(term_s)
    if topic in ("limits", "monotone_bounded"):
        family = _sequence_family(term)
        value = _limit(term)
        verdict = "converges" if value is not None else "diverges"
        behavior = None
        if topic == "monotone_bounded":
            behavior, delta = _monotonicity(term)
            if verdict == "converges" and behavior == "not_monotone":
                raise Reject("redraw", "convergent monotone-bounded tasks must be provably monotone")
            if verdict == "diverges" and behavior == "not_monotone" and family != "alternating":
                raise Reject("redraw", "divergent task must be provably unbounded monotone or bounded oscillatory")
        _check_axes(axes, family=family, verdict=verdict, ask="value", behavior=behavior)
        ok, detail = numeric_sequence(term, start, verdict, value, meta={"family": family})
        if not ok:
            raise Reject("redraw", "independent numeric sequence check disagrees")
        if topic == "limits":
            statement = rf"Find $\displaystyle\lim_{{n\to\infty}} a_n$ for $a_n={L(term)}$, or state that the sequence diverges."
            steps = [_step("Take the limit of the term formula.",
                           rf"\lim_{{n\to\infty}} {L(term)}=" + (L(value) if value is not None else r"\text{does not exist}"), value)]
            method = "sympy_limit+mpmath_limit"
        else:
            bound_text = ("A finite limit and monotonicity give a bound in the direction of motion." if value is not None
                          else "The terms are unbounded or oscillate between separated subsequences.")
            steps = [_step("Compare consecutive terms.", rf"a_{{n+1}}-a_n={L(delta)}", delta),
                     _step(bound_text, L(value) if value is not None else rf"\text{{{verdict}}}", value)]
            statement = (rf"Determine whether $a_n={L(term)}$ converges or diverges by analyzing monotonicity and "
                         "boundedness. If it converges, find its limit.")
            method = "symbolic_difference+sympy_limit+mpmath_limit"
        return _finish(topic, term, ratio, start, family, verdict, value, statement, steps, method, detail,
                       {"behavior": behavior}, calculator)
    if topic == "geometric":
        r, first = _geometric(term, ratio_s, start)
        verdict = "converges" if abs(r) < 1 else "diverges"
        value = sp.simplify(first / (1 - r)) if verdict == "converges" else None
        family, ask = "geometric", "value"
        meta = {"family": family, "ratio": str(r)}
        _check_axes(axes, family=family, verdict=verdict, ask=ask)
        ok, detail = numeric_series(term, start, verdict, value, meta)
        if not ok:
            raise Reject("redraw", "mpmath geometric partial sum disagrees with the explicit tail bound")
        steps = [_step("Compute the constant ratio.", rf"r={L(r)}", r),
                 _step("Use the geometric-series criterion and sum formula." if value is not None else
                       "Since the terms do not approach zero, the series diverges.",
                       L(value) if value is not None else r"\text{diverges}", value)]
        statement = rf"Determine whether $\displaystyle\sum_{{n={start}}}^\infty {L(term)}$ converges or diverges. If it converges, find its sum."
        return _finish(topic, term, r, start, family, verdict, value, statement, steps,
                       "geometric_formula+mpmath_partial_sum_tail_bound", detail, {"ratio": str(r)}, calculator)
    if ratio_s is not None:
        raise Reject("slip", "ratio must be null for a non-geometric series")
    if topic == "telescoping":
        meta = _telescoping(term, start)
        verdict = "diverges" if meta["radical"] else "converges"
        value = None if meta["radical"] else sp.summation(term, (n, start, sp.oo))
        if value is not None and (value.has(sp.Sum) or value.is_finite is not True):
            raise Reject("redraw", "telescoping sum did not reduce to a finite exact value")
        ask, family = "value", "telescoping"
    else:
        c, p, shift = _p_form(term, start)
        verdict = "converges" if p > 1 else "diverges"
        ask = str(axes.get("ask", "value" if p in (2, 4) else "verdict"))
        if ask not in ("value", "verdict"):
            raise Reject("redraw", "p-series ask axis must be value or verdict")
        value = sp.summation(term, (n, start, sp.oo)) if verdict == "converges" and ask == "value" else None
        if value is not None and (value.has(sp.zeta, sp.Sum) or value.is_finite is not True):
            raise Reject("redraw", "p-series value must reduce to a short exact form")
        family = "p_series"
        meta = {"family": family, "coefficient": str(c), "shift": shift, "power": str(p)}
    _check_axes(axes, family=family, verdict=verdict, ask=ask)
    ok, detail = numeric_series(term, start, verdict, value, meta)
    if not ok:
        raise Reject("redraw", "mpmath partial sum disagrees with the explicit tail or growth bound")
    if topic == "telescoping":
        steps = [_step("Rewrite the term as a difference so consecutive partial sums cancel.", L(term), term),
                 _step("Take the limit of the remaining boundary terms.",
                       L(value) if value is not None else r"\text{diverges}", value)]
    else:
        p = sp.Rational(meta["power"])
        steps = [_step("Identify the exponent in the p-series.", rf"p={L(p)}", p),
                 _step("Apply the p-series criterion: convergence occurs exactly when p>1.",
                       L(value) if value is not None else rf"\text{{{verdict}}}", value)]
    statement = rf"Determine whether $\displaystyle\sum_{{n={start}}}^\infty {L(term)}$ converges or diverges."
    if ask == "value":
        statement += " If it converges, find its sum."
    return _finish(topic, term, None, start, family, verdict, value, statement, steps,
                   f"{family}+mpmath_partial_sum_tail_bound", detail, meta, calculator)


def _recursive(term, ratio_s, initial, axes, calculator):
    if initial.is_Rational is not True or abs(initial) > 50:
        raise Reject("redraw", "recursive sequence initial value must be a small rational number")
    poly = sp.Poly(term, a) if term.is_polynomial(a) else None
    if poly is not None and poly.degree() == 1:
        r = sp.simplify(sp.diff(term, a))
        c = sp.simplify(term.subs(a, 0))
        if not (r.is_Rational and c.is_Rational and abs(r) <= 4 and abs(c) <= 20):
            raise Reject("redraw", "affine recurrence coefficients must be small rational numbers")
        if ratio_s is None or ratio_s != r:
            raise Reject("redraw", "ratio must equal the coefficient of the previous term")
        value = sp.simplify(c / (1 - r)) if r != 1 else None
        fixed = value is not None and initial == value
        verdict = "converges" if abs(r) < 1 or fixed else "diverges"
        value = value if verdict == "converges" else None
        family = "affine"
        ratio = r
    else:
        C = sp.simplify(a * (2 * term - a))
        if C.has(a) or C.is_Integer is not True or C <= 0 or C > 50 or sp.sqrt(C).is_Rational:
            raise Reject("redraw", "nonlinear recurrence must be (a + C/a)/2 for a positive nonsquare integer C")
        if ratio_s is not None:
            raise Reject("slip", "ratio must be null for the square-root recurrence")
        if initial <= 0:
            raise Reject("redraw", "square-root recurrence needs a positive initial value")
        family, verdict, value, ratio = "babylonian", "converges", sp.sqrt(C), None
    _check_axes(axes, family=family, verdict=verdict, ask="value")
    ok, detail = numeric_sequence(term, initial, verdict, value, recurrence=True, meta={"family": family})
    if not ok:
        raise Reject("redraw", "independent recurrence iteration disagrees with the symbolic fixed-point result")
    fixed_eq = sp.Eq(a, term)
    steps = [_step("Assume a finite limit and solve the fixed-point equation.", L(fixed_eq), fixed_eq),
             _step("Check stability and the initial value, then iterate numerically as an independent check.",
                   L(value) if value is not None else r"\text{diverges}", value)]
    an = sp.Symbol("a_n")
    statement = (rf"Let $a_0={L(initial)}$ and $a_{{n+1}}={L(term.subs(a, an))}$. "
                 "Determine whether the sequence converges or diverges. If it converges, find its limit.")
    return _finish("recursive", term, ratio, int(initial) if initial.is_Integer else str(initial), family, verdict,
                   value, statement, steps, "fixed_point+stability+mpmath_iteration", detail,
                   {"ratio": None if ratio is None else str(ratio)}, calculator)
