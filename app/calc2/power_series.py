"""Verified power-series problems (C9); called only by the sandbox worker.

The model proposes a coefficient, a function or a few numbers. The server parses them with safe_parse, derives every
radius, interval, coefficient and sum with SymPy (and exact Fraction series), and re-checks it with mpmath
(app/calc2/power_series_checks.py). This module holds the dispatcher, radius_interval and operations; the other four topics
are in app/calc2/power_series_b.py.
"""
import sympy as sp

from app.calc2 import power_series_checks as checks
from app.calc2 import power_series_core as core
from app.calc2 import series_tests_checks as series_checks
from app.shared.integral_core import L, Reject, _parse, x
from app.calc2.sequences_series import _answer, _check_axes, _exact, _finish, _start, _step
from app.calc2.series_tests import PRIORITY, _alternating_parts
from app.calc2.series_tests_core import (TEST_NAMES, abs_term, conclusive_tests, decreasing_from, exponential_in_n,
                                   has_factorial, n, parse_term, positive_from, ratio_limit, sign_atoms)

TOPICS = ("radius_interval", "operations", "taylor_maclaurin", "binomial_series", "taylor_remainder", "euler_formula")
FIELDS = {"radius_interval": ("term", "start", "m", "s"), "operations": ("f", "k", "x0"),
          "taylor_maclaurin": ("f", "a", "k", "x1"), "binomial_series": ("base", "p", "k", "x0"),
          "taylor_remainder": ("f", "a", "x1", "n", "eps"), "euler_formula": ("z", "n")}
MAX_K = 12


def verify(topic, axes=None, calculator="none", bounds=None, **payload):
    try:
        if bounds is not None:
            raise Reject("slip", "power-series payloads do not use bounds")
        if topic not in TOPICS:
            raise Reject("slip", "unknown power-series topic")
        if calculator not in ("none", "scientific"):
            raise Reject("slip", "unsupported calculator tier")
        unknown = set(payload) - set(FIELDS[topic])
        if unknown:
            raise Reject("slip", "unexpected fields: " + ", ".join(sorted(unknown)))
        if topic in ("radius_interval", "operations"):
            return _LOCAL[topic](payload, axes or {}, calculator)
        from app.calc2 import power_series_b
        return power_series_b.VERIFIERS[topic](payload, axes or {}, calculator)
    except Reject as r:
        return {"ok": False, "cause": r.cause, "reason": r.reason, "cap": r.cap}


def small_int(s, label, lo, hi):
    v = _exact(s, label) if isinstance(s, str) else None
    if v is None or v.is_Integer is not True or not lo <= v <= hi:
        raise Reject("slip", f"{label} must be an integer from {lo} to {hi}")
    return int(v)


def _interval_answer(lo, hi, lo_closed, hi_closed):
    def e(v):
        return r"\infty" if v == sp.oo else r"-\infty" if v == -sp.oo else L(v)
    left, right = ("[" if lo_closed else "("), ("]" if hi_closed else ")")
    return {"type": "interval", "latex": rf"\left{left}{e(lo)},\ {e(hi)}\right{right}",
            "sympy": f"Interval({lo}, {hi}, {not lo_closed}, {not hi_closed})", "numeric": None}


# ---- radius and interval of convergence -------------------------------------------------------------------------

def _c_family(c):
    if has_factorial(c):
        return "factorial"
    return "exponential" if exponential_in_n(c) else "polynomial"


def _normalised(c, R, sign):
    t = sp.powsimp(sp.expand_power_base(c * (sign * R) ** n, force=True), force=True)
    return t if checks.same_function(t, c * (sign * R) ** n) else c * (sign * R) ** n


def _endpoint(c, R, sign, start):
    """(converges, kind, details) for the series c_n (sign R)^n."""
    t = _normalised(c, R, sign)
    b = abs_term(t)
    if sign_atoms(b) or not positive_from(b, start):
        raise Reject("redraw", "the endpoint series must have nonzero terms of one magnitude pattern from the start")
    tests = conclusive_tests(b, start)
    if not tests:
        raise Reject("redraw", "no supported convergence test decides an endpoint series")
    if len({v["verdict"] for v in tests.values()}) > 1:
        raise Reject("redraw", "conclusive tests disagree at an endpoint")
    chosen = next(name for name in PRIORITY if name in tests)
    info = tests[chosen]
    ok, detail = series_checks.positive(b, start, chosen, info["verdict"], info.get("value"), info.get("p"), info.get("F"))
    if not ok:
        raise Reject("redraw", f"independent endpoint check disagrees: {detail}")
    if not sign_atoms(t):
        return info["verdict"] == "converges", "positive", chosen, detail
    _alternating_parts(t, start)
    if info["verdict"] == "converges":
        return True, "absolute", chosen, detail
    if chosen == "nth_term":
        return False, "terms", chosen, detail
    if not decreasing_from(b, start)[0]:
        raise Reject("redraw", "the alternating series test cannot be applied at an endpoint")
    good, extra = series_checks.alternating_converges(t, b, start)
    if not good:
        raise Reject("redraw", f"independent alternating check disagrees: {extra}")
    return True, "conditional", chosen, detail + "; " + extra


def _endpoint_step(sign, x_end, converges, kind, test):
    name = TEST_NAMES[test]
    why = {"positive": f"the {name} gives {'convergence' if converges else 'divergence'}",
           "absolute": f"the series converges absolutely by the {name}",
           "terms": "the terms do not approach 0, so the series diverges",
           "conditional": "the absolute series diverges, but the alternating series test applies"}[kind]
    return _step(f"At $x={L(x_end)}$, {why}.", rf"x={L(x_end)}:\ \text{{{'converges' if converges else 'diverges'}}}")


def _radius_interval(p, axes, calculator):
    c = parse_term(p["term"])
    start = _start(p["start"])
    m, s = small_int(p["m"], "m", 1, 4), small_int(p["s"], "s", -9, 9)
    form = "plain" if (m, s) == (1, 0) else "scaled" if m != 1 else "shifted"
    ask = str(axes.get("ask", "interval"))
    if ask not in ("radius", "interval"):
        raise Reject("slip", "ask must be radius or interval")
    family = _c_family(c)
    if not positive_from(abs_term(c), start):
        raise Reject("redraw", "the coefficients must be nonzero from the starting index")
    limit = ratio_limit(c)
    if limit is None or limit == sp.oo:
        raise Reject("redraw", "the ratio limit is undecided or the radius is 0")
    R_u = sp.oo if limit == 0 else 1 / limit
    if R_u != sp.oo and R_u.is_Rational is not True:
        raise Reject("redraw", "the radius must be a rational number")
    _check_axes(axes, family=family, form=form, ask=ask)
    ok, detail = checks.radius_probe(c, R_u)
    if not ok:
        raise Reject("redraw", f"independent ratio and root probes disagree: {detail}")
    center = sp.Rational(-s, m)
    series = c * (m * x + s) ** n
    head = rf"\displaystyle\sum_{{n={start}}}^\infty {L(series)}"
    meta = {"kind": "radius", "c": str(c), "m": m, "s": s, "ratio": str(limit), "R_u": str(R_u)}
    steps = [_step("Find the limit of consecutive coefficient ratios.",
                   rf"L=\lim_{{n\to\infty}}\left|\frac{{a_{{n+1}}}}{{a_n}}\right|={L(limit)}", limit)]
    if R_u == sp.oo:
        if ask != "interval":
            raise Reject("redraw", "a radius question needs a finite radius")
        answer = _interval_answer(-sp.oo, sp.oo, False, False)
        steps.append(_step("Since $L=0$ the series converges for every x.", r"(-\infty,\ \infty)"))
        statement = rf"Find the interval of convergence of ${head}$."
        return _finish("radius_interval", c, f"{ask}|{m}|{s}", start, family, "converges", None, statement, steps,
                       "sympy_ratio_limit+mpmath_probe", detail, {"ask": ask, "form": form, "check": meta}, calculator, answer)
    R_x = R_u / m
    steps.append(_step("The radius in the variable of the power is 1/L" +
                       ("" if form == "plain" else ", then solve |mx+s|<R for x"),
                       rf"R={L(R_x)}", R_x))
    if ask == "radius":
        answer = _answer(R_x, "converges", calculator)
        statement = rf"Find the radius of convergence of ${head}$."
        return _finish("radius_interval", c, f"{ask}|{m}|{s}", start, family, "converges", R_x, statement, steps,
                       "sympy_ratio_limit+mpmath_probe", detail, {"ask": ask, "form": form, "check": meta}, calculator, answer)
    ends = {}
    for sign, label in ((-1, "left"), (1, "right")):
        x_end = center + sign * R_x
        good, kind, test, edetail = _endpoint(c, R_u, sign, start)
        ends[label] = good
        steps.append(_endpoint_step(sign, x_end, good, kind, test))
        meta[label] = {"closed": good, "kind": kind, "test": test}
        detail += f"; {label}: {edetail}"
    closed = sum(ends.values())
    _check_axes(axes, ends=("none", "one", "both")[closed])
    answer = _interval_answer(center - R_x, center + R_x, ends["left"], ends["right"])
    statement = rf"Find the interval of convergence of ${head}$."
    return _finish("radius_interval", c, f"{ask}|{m}|{s}", start, family, "converges", None, statement, steps,
                   "sympy_ratio_limit+mpmath_probe+endpoint_tests", detail,
                   {"ask": ask, "form": form, "check": meta}, calculator, answer)


# ---- operations on known series ---------------------------------------------------------------------------------

def _sum_term(kind, scale, u, start_n):
    """The general term (in n) of the numeric series whose sum is scale * B(u)."""
    return {"geom": scale * u ** n, "exp": scale * u ** n / sp.factorial(n),
            "sin": scale * (-1) ** n * u ** (2 * n + 1) / sp.factorial(2 * n + 1),
            "cos": scale * (-1) ** n * u ** (2 * n) / sp.factorial(2 * n),
            "log1p": scale * (-1) ** (n + 1) * u ** n / n,
            "atan": scale * (-1) ** n * u ** (2 * n + 1) / (2 * n + 1)}[kind]


_SUM_VALUE = {"geom": lambda u: 1 / (1 - u), "exp": sp.exp, "sin": sp.sin, "cos": sp.cos,
              "log1p": lambda u: sp.log(1 + u), "atan": sp.atan}


def _series_sum(f, terms, family, x0_s, axes, calculator):
    if len(terms) != 1 or len(terms[0]["factors"]) != 1:
        raise Reject("redraw", "a sum question needs one term with one known series")
    x0 = _exact(x0_s, "x0") if isinstance(x0_s, str) else None
    if x0 is None or x0.is_Rational is not True or x0 == 0:
        raise Reject("slip", "x0 must be a nonzero rational number")
    term = terms[0]
    kind, a, p = term["factors"][0]
    u = sp.Rational(a.numerator, a.denominator) * x0 ** p
    inside = abs(u) < 1 if kind == "geom" else (abs(u) <= 1 and u != -1 if kind in ("log1p", "atan") else True)
    if not inside:
        raise Reject("redraw", "the point is outside the interval where the series converges to the function")
    scale = core.to_rational(term["c"]) * x0 ** term["m"]
    start_n = 1 if kind == "log1p" else 0
    general = _sum_term(kind, scale, u, start_n)
    value = sp.simplify(scale * _SUM_VALUE[kind](u))
    if value == 0:
        raise Reject("redraw", "the sum is zero")
    ok, detail = checks.series_sum(general, start_n, value)
    if not ok:
        raise Reject("redraw", f"independent nsum disagrees: {detail}")
    statement = rf"Find the sum of the series $\displaystyle\sum_{{n={start_n}}}^\infty {L(general)}$."
    steps = [_step("Recognise the series as a known Maclaurin series evaluated at a point.",
                   rf"u={L(u)}", u),
             _step("Evaluate the function there.", rf"{L(value)}", value)]
    return _finish("operations", f, f"sum|{x0}", start_n, family, "converges", value, statement, steps,
                   "known_series+mpmath_nsum", detail, {"ask": "sum", "check": {"kind": "sum", "start": start_n,
                   "term": str(general), "value": str(value)}}, calculator, _answer(value, "converges", calculator))


def _operations(p, axes, calculator):
    f = _parse(p["f"], x, "f")
    if sp.count_ops(f) > 25:
        raise Reject("redraw", "f must use at most 25 operations")
    terms = core.parse_function(f)
    family = core.family_of(terms)
    ask = str(axes.get("ask", "coeff"))
    if ask not in ("coeff", "deriv", "integral", "sum"):
        raise Reject("slip", "ask must be coeff, deriv, integral or sum")
    _check_axes(axes, family=family, ask=ask)
    if ask == "sum":
        return _series_sum(f, terms, family, p.get("x0"), axes, calculator)
    k = small_int(p.get("k"), "k", 0 if ask != "integral" else 1, MAX_K)
    series = core.function_series(terms)
    if ask == "coeff":
        target, claim = series, core.sympy_coefficient(f, k)
    elif ask == "deriv":
        target, claim = core.derivative(series), core.sympy_coefficient(sp.diff(f, x), k)
    else:
        target, claim = core.antiderivative(series), core.sympy_coefficient(f, k - 1) / k
    value = core.to_rational(target[k])
    if sp.simplify(claim - value) != 0:
        raise Reject("redraw", "SymPy series and the exact series engine disagree")
    if value == 0:
        raise Reject("redraw", "the coefficient is zero")
    ok, detail = checks.operation(f, terms, ask, target)
    if not ok:
        raise Reject("redraw", f"independent evaluation disagrees: {detail}")
    shown = L(f)
    lead = {"coeff": rf"Find the coefficient of $x^{{{k}}}$ in the Maclaurin series of $f(x)={shown}$.",
            "deriv": rf"Let $f(x)={shown}$. Find the coefficient of $x^{{{k}}}$ in the Maclaurin series of $f'(x)$.",
            "integral": rf"Let $f(x)={shown}$ and $F(x)=\int_0^x f(t)\,dt$. Find the coefficient of $x^{{{k}}}$ in the "
                        rf"Maclaurin series of $F(x)$."}[ask]
    poly = sum(core.to_rational(target[j]) * x ** j for j in range(k + 1))
    steps = [_step("Build the series of f from the known series.",
                   rf"f(x)={L(sum(core.to_rational(series[j]) * x ** j for j in range(k + 2)))}+\cdots", None)]
    if ask != "coeff":
        steps.append(_step("Differentiate term by term." if ask == "deriv" else "Integrate term by term from 0 to x.",
                           rf"{L(poly)}+\cdots"))
    steps.append(_step("Read off the coefficient.", rf"[x^{{{k}}}]={L(value)}", value))
    return _finish("operations", f, f"{ask}|{k}", 0, family, "converges", value, lead, steps,
                   "exact_series+sympy_series+mpmath_evaluation", detail,
                   {"ask": ask, "k": k, "check": {"kind": "operation", "f": str(f), "ask": ask, "k": k,
                                                   "value": str(value)}}, calculator,
                   _answer(value, "converges", calculator))


_LOCAL = {"radius_interval": _radius_interval, "operations": _operations}
