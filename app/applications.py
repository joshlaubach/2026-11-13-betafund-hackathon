"""Verifiers for the shape-of-a-graph topics of the applications chapter (C3 milestone a): critical_numbers,
absolute_extrema, increasing_decreasing, relative_extrema, rolle_mvt, concavity_inflection, curve_sketching.
Same contract as app/derivative_rules.py (verify(stem, ...) in the sandbox).

The model proposes a function (and an interval or a question); the server derives every answer with SymPy sign
charts and set solving, then re-checks it numerically on a dense grid (a method that does not use the sign chart).
Answers are sets, interval unions or multi-part values; the figure of curve_sketching is not graded.
"""
import mpmath as mp
import sympy as sp

from app import function_pool as pool
from app.calculus_core import fd_agrees, finish, step
from app.clean_answer import canon, value_reason
from app.derivatives import _check
from app.integral_core import L, Reject, x
from app.limits import _expr, _point

STEMS = ("critical_numbers", "absolute_extrema", "increasing_decreasing", "relative_extrema", "rolle_mvt",
         "concavity_inflection", "curve_sketching")
S = sp.S
GRID_N = 1601


def verify(stem: str, bounds=None, axes: dict | None = None, calculator: str = "none", **fields) -> dict:
    try:
        if stem not in STEMS:
            raise Reject("slip", f"unknown applications topic {stem}")
        if calculator != "none":
            raise Reject("redraw", "applications topics have only the exact tier")
        if fields.get("view") in ("graph", "trig"):              # the problem is a picture, not a formula (app/graph_problems.py)
            from app import graph_problems
            return graph_problems.verify_topic(stem, axes or {}, **fields)
        return _VERIFY[stem](stem, axes or {}, **fields)
    except Reject as r:
        return {"ok": False, "cause": r.cause, "reason": r.reason, "cap": r.cap}


# -- shared machinery ----------------------------------------------------------------------------------------------

def _short(v, what="a value"):
    v = canon(v)
    if v.is_real is not True or v.has(sp.zoo, sp.nan, sp.oo, -sp.oo):
        raise Reject("redraw", f"{what} is not a finite real number")
    if why := value_reason(v, True):
        raise Reject("redraw", f"{what} is not a short exact form ({why})", cap=why)
    return v


def _kind(fe) -> str:
    if fe.is_polynomial(x):
        return "poly"
    if fe.is_rational_function(x):
        return "rational"
    if any(isinstance(p, sp.Pow) and p.exp.is_Rational and not p.exp.is_Integer and p.base.has(x)
           for p in sp.preorder_traversal(fe)):
        return "root"
    return "trig" if fe.has(sp.sin, sp.cos, sp.tan) else "trans"


def _prepare(f, interval=None, scope: str = "any"):
    fe = _expr(f, "f")
    if fe.has(sp.Abs, sp.Piecewise, sp.sign, sp.floor) or not fe.has(x):
        raise Reject("redraw", "f must be a smooth expression in x")
    if pool.complexity(fe) > 10:
        raise Reject("redraw", "f is too complicated for this topic")
    try:
        dom = sp.calculus.util.continuous_domain(fe, x, S.Reals)
    except (NotImplementedError, ValueError, TypeError):
        raise Reject("redraw", "the domain of f could not be found") from None
    if interval is not None:
        dom = sp.Intersection(dom, interval)
    d = sp.cancel(sp.together(sp.diff(fe, x))) if fe.is_rational_function(x) else sp.diff(fe, x)
    if not fd_agrees(fe, d):
        raise Reject("redraw", "the derivative failed the finite-difference check")
    return fe, d, dom


def _finite(s, what):
    if s == S.EmptySet:
        return []
    if not isinstance(s, sp.FiniteSet):
        raise Reject("redraw", f"{what} could not be found as a finite set of exact values")
    return sorted((_short(v, what) for v in s), key=float)


def _zeros(expr, dom, what):
    num = sp.numer(sp.together(expr))
    if num == 0:
        raise Reject("redraw", f"{what} is identically zero")
    try:
        s = sp.solveset(num, x, dom)
    except (NotImplementedError, ValueError):
        raise Reject("redraw", f"{what} could not be solved exactly") from None
    return _finite(s, what)


def _singular(expr, dom):
    den = sp.denom(sp.together(expr))
    if not den.has(x):
        return []
    try:
        s = sp.solveset(den, x, dom)
    except (NotImplementedError, ValueError):
        raise Reject("redraw", "the singular points could not be solved exactly") from None
    return _finite(s, "a singular point")


def _interior(dom):
    return dom.interior if hasattr(dom, "interior") else dom


def _rationals_between(a, b):
    """A rational strictly between a and b (either may be +-oo)."""
    if a == -sp.oo and b == sp.oo:
        return sp.Integer(0)
    if a == -sp.oo:
        return sp.floor(b) - 1
    if b == sp.oo:
        return sp.floor(a) + 1
    return sp.nsimplify((a + b) / 2, rational=True) if not (a + b).is_Rational else (a + b) / 2


def _realize(expr, numeric: bool = False):
    """Odd roots take their real value for negative arguments: x^(2/3) is (x^(1/3))^2, not a principal complex root."""
    root = sp.Function("rroot") if numeric else sp.real_root
    return expr.replace(lambda e: e.is_Pow and e.exp.is_Rational and e.exp.q > 1 and e.exp.q % 2 == 1 and e.base.has(x),
                        lambda e: root(e.base, e.exp.q) ** e.exp.p)


def _rroot(b, q):
    b = mp.mpf(b)
    return mp.sign(b) * abs(b) ** (mp.mpf(1) / q)


def _fn(expr):
    fl = sp.lambdify(x, _realize(expr, True), [{"rroot": _rroot}, "mpmath"])

    def g(t):
        try:
            v = fl(mp.mpf(t))
        except (ValueError, ZeroDivisionError, ArithmeticError, TypeError):
            return None
        if isinstance(v, mp.mpc):
            return None if abs(v.imag) > 1e-20 else v.real
        return v
    return g


def _sign_chart(expr, dom, breaks):
    """[(lo, hi, sign)] over the interior components of dom split at breaks (sorted numbers). Sign by an exact
    sample point."""
    pts = sorted(set(breaks))
    comps = []
    dint = _interior(dom)
    parts = list(dint.args) if isinstance(dint, sp.Union) else [dint]
    for comp in parts:
        if not isinstance(comp, sp.Interval):
            raise Reject("redraw", "the domain is not a union of intervals")
        cuts = [comp.start] + [p for p in pts if comp.start < p < comp.end] + [comp.end]
        for lo, hi in zip(cuts, cuts[1:]):
            m = _rationals_between(lo, hi)
            if not (lo < m < hi):
                raise Reject("redraw", "a sample point could not be chosen")
            v = sp.N(_realize(expr).subs(x, m), 30)
            if v.is_real is not True or abs(v) < 1e-12:
                raise Reject("redraw", "the sign could not be determined at a sample point")
            comps.append((lo, hi, 1 if v > 0 else -1))
    return comps


def _merge(chart, joinable):
    out = []
    for lo, hi, s in chart:
        if out and out[-1][2] == s and out[-1][1] == lo and lo in joinable:
            out[-1] = (out[-1][0], hi, s)
        else:
            out.append((lo, hi, s))
    return out


def _iv_sympy(ivs):
    parts = [f"Interval.open({a}, {b})" for a, b in ivs]
    return parts[0] if len(parts) == 1 else "Union(" + ", ".join(parts) + ")"


def _iv_latex(ivs):
    def e(v):
        return "\\infty" if v == sp.oo else "-\\infty" if v == -sp.oo else L(v)
    return " \\cup ".join(f"\\left({e(a)},\\ {e(b)}\\right)" for a, b in ivs)


def _set_answer(vals):
    return {"type": "set", "latex": "\\left\\{" + ",\\ ".join(L(v) for v in vals) + "\\right\\}",
            "sympy": "{" + ", ".join(str(v) for v in vals) + "}", "numeric": None}


def _fx(fe):
    return sp.latex(fe, ln_notation=True)      # the natural logarithm is shown as ln, never as a bare log


def _scan_sign_changes(g, lo, hi, n=GRID_N):
    """Approximate locations (grid midpoints) where g changes sign on [lo, hi]."""
    pts = [lo + (hi - lo) * (i + mp.mpf('0.3711')) / (n + 1) for i in range(n + 1)]      # off the integer grid
    prev, out = None, []
    for t0, t1 in zip(pts, pts[1:]):
        v0, v1 = g(t0), g(t1)
        if v0 is None or v1 is None:
            prev = None
            continue
        if v0 * v1 < 0 and abs(v0) < 1e6 and abs(v1) < 1e6:
            out.append((t0 + t1) / 2)
    return out


def _window(dom, interval):
    """A finite window for numeric scans."""
    if interval is not None:
        return mp.mpf(str(sp.N(interval.start, 20))), mp.mpf(str(sp.N(interval.end, 20)))
    return mp.mpf(-8), mp.mpf(8)


def _check_changes(g, dom, interval, expected, tol=None, what="the derivative"):
    """Every grid sign change of g lies near an expected breakpoint (none missed by the exact solve)."""
    mp.mp.dps = 30
    lo, hi = _window(dom, interval)
    tol = tol or (hi - lo) / 100
    found = _scan_sign_changes(g, lo, hi)
    exp = [mp.mpf(str(sp.N(e, 20))) for e in expected]
    if interval is not None:
        found = [c for c in found if lo + tol < c < hi - tol or any(abs(c - e) <= tol for e in exp)]
    for c in found:
        if not any(abs(c - e) <= tol for e in exp):
            raise Reject("redraw", f"{what} changes sign near x = {mp.nstr(c, 5)}, which the exact solve missed")


def _poly_ok(fe, allowed):
    if _kind(fe) not in allowed:
        raise Reject("redraw", f"f must be one of: {', '.join(allowed)}")


# -- critical numbers ----------------------------------------------------------------------------------------------

def _verify_critical(stem, axes, f, interval="", **_):
    iv = None
    if interval.strip():
        try:
            lo, hi = (_point(s, "interval") for s in interval.split(","))
        except ValueError:
            raise Reject("slip", "interval must be 'a, b'") from None
        if not lo < hi:
            raise Reject("redraw", "the interval must have a < b")
        iv = sp.Interval.open(lo, hi)
    fe, d, dom = _prepare(f, iv)
    kind = _kind(fe)
    if iv is None and kind in ("trig", "trans") and fe.has(sp.sin, sp.cos, sp.tan):
        raise Reject("redraw", "a trigonometric function needs an interval")
    inner = _interior(dom)
    zeros = _zeros(d, inner, "a zero of f'")
    undefined = [v for v in _singular(d, inner) if v not in zeros]
    crit = sorted(set(zeros) | set(undefined), key=float)
    if not 1 <= len(crit) <= 5:
        raise Reject("redraw", "f must have one to five critical numbers")
    _check(axes, kind=kind, und="yes" if undefined else "no")
    g = _fn(d)
    _check_changes(g, dom, iv, crit)
    for z in zeros:
        v = g(mp.mpf(str(sp.N(z, 30))))
        if v is not None and abs(v) > 1e-15:
            raise Reject("redraw", "f' does not vanish at a computed zero")
    dtex = L(d)
    steps = [step("Differentiate.", f"f'(x) = {dtex}", str(d)),
             step("Solve f'(x) = 0.", f"x \\in {_set_answer(zeros)['latex']}", str(zeros))]
    if undefined:
        steps.append(step("Find where f'(x) is undefined but f(x) is defined.", f"x \\in {_set_answer(undefined)['latex']}",
                          str(undefined)))
    ans = _set_answer(crit)
    steps.append(step("The critical numbers are the union.", ans["latex"], ans["sympy"]))
    where = f" on the interval $\\left({L(iv.start)},\\ {L(iv.end)}\\right)$" if iv is not None else ""
    st = f"Find all critical numbers of $f(x) = {_fx(fe)}${where}."
    return finish(stem, fe, f"{interval}", st, ans, steps, kind, axes, exact=True,
                  raw_extra={"kind": kind, "und": "yes" if undefined else "no"})


# -- absolute extrema ----------------------------------------------------------------------------------------------

def _closed(a, b):
    try:
        lo, hi = _point(a, "a"), _point(b, "b")
    except Reject:
        raise
    if not lo < hi:
        raise Reject("redraw", "the interval must have a < b")
    return lo, hi


def _verify_absolute(stem, axes, f, a, b, ask, **_):
    if ask not in ("max", "min", "both"):
        raise Reject("slip", "ask must be max, min or both")
    lo, hi = _closed(a, b)
    fe, d, dom = _prepare(f, sp.Interval(lo, hi))
    if not sp.Interval(lo, hi).is_subset(dom):
        raise Reject("redraw", "f must be continuous on the closed interval")
    kind = _kind(fe)
    inner = sp.Interval.open(lo, hi)
    crit = sorted(set(_zeros(d, inner, "a zero of f'")) | set(_singular(d, inner)), key=float)
    if len(crit) > 5:
        raise Reject("redraw", "too many critical numbers")
    cand = [lo] + crit + [hi]
    vals = [(_short(fe.subs(x, c), "f at a candidate"), c) for c in cand]
    vmax, vmin = max((v for v, _ in vals), key=float), min((v for v, _ in vals), key=float)
    if vmax == vmin:
        raise Reject("redraw", "f is constant on the candidates")
    argmax = [c for v, c in vals if v == vmax]
    argmin = [c for v, c in vals if v == vmin]
    if len(argmax) > 1 or len(argmin) > 1:
        raise Reject("redraw", "the extreme value must be attained at one point")
    interior_hit = int(argmax[0] not in (lo, hi)) + int(argmin[0] not in (lo, hi))
    _check(axes, kind=kind, ask=ask, loc="interior" if interior_hit else "endpoint")
    g = _fn(fe)
    mp.mp.dps = 30
    ys = [g(mp.mpf(str(sp.N(lo, 30))) + (mp.mpf(str(sp.N(hi - lo, 30)))) * i / 4000) for i in range(4001)]
    ys = [v for v in ys if v is not None]
    gmax, gmin = max(ys), min(ys)
    span = float(vmax - vmin)
    if (float(vmax) < float(gmax) - 1e-9 * max(1, span) or float(vmin) > float(gmin) + 1e-9 * max(1, span)
            or float(vmax) - float(gmax) > 0.01 * span or float(gmin) - float(vmin) > 0.01 * span):
        raise Reject("redraw", "the extreme values failed the grid check")
    table = ",\\ ".join(f"f({L(c)}) = {L(v)}" for v, c in vals)
    steps = [step("Differentiate and find the critical numbers inside the interval.", f"f'(x) = {L(d)}"),
             step("Evaluate f at the critical numbers and at both endpoints.", table),
             step("Compare.", f"\\max = {L(vmax)},\\ \\min = {L(vmin)}")]
    if ask == "both":
        ans = {"type": "multi_part", "latex": f"\\max = {L(vmax)},\\ \\min = {L(vmin)}",
               "sympy": "{max: " + str(vmax) + ", min: " + str(vmin) + "}", "numeric": None}
        q = "the absolute maximum value and the absolute minimum value"
    else:
        v = vmax if ask == "max" else vmin
        ans = {"type": "numeric", "latex": L(v), "sympy": str(v), "numeric": float(sp.N(v, 15))}
        q = "the absolute maximum value" if ask == "max" else "the absolute minimum value"
    st = f"Find {q} of $f(x) = {_fx(fe)}$ on the closed interval $\\left[{L(lo)},\\ {L(hi)}\\right]$."
    return finish(stem, fe, f"{lo},{hi}|{ask}", st, ans, steps, kind, axes, exact=True,
                  raw_extra={"kind": kind, "ask": ask, "loc": "interior" if interior_hit else "endpoint"})


# -- increasing and decreasing, concavity -------------------------------------------------------------------------

def _regions(fe, expr, dom, crit, sing, want_sign):
    """Open intervals where `expr` has sign `want_sign`; adjacent regions join across a non-singular breakpoint."""
    chart = _sign_chart(expr, dom, crit + sing)
    chart = _merge(chart, {c for c in crit if c not in sing})
    return [(lo, hi) for lo, hi, s in chart if s == want_sign], chart


def _grid_agree(g, ivs, sign, dom, interval=None):
    """Sampled sign of g agrees with the answer intervals at 400 points of the window."""
    mp.mp.dps = 30
    lo, hi = _window(dom, interval)
    bad = 0
    for i in range(1, 400):
        t = lo + (hi - lo) * i / 400
        v = g(t)
        if v is None or abs(v) < 1e-9:
            continue
        inside = any(float(a) < float(t) < float(b) for a, b in ivs)
        bad += inside != ((v > 0) == (sign > 0))
    return bad == 0


def _verify_increasing(stem, axes, f, ask, **_):
    if ask not in ("increasing", "decreasing"):
        raise Reject("slip", "ask must be increasing or decreasing")
    fe, d, dom = _prepare(f)
    kind = _kind(fe)
    crit = _zeros(d, _interior(dom), "a zero of f'")
    sing = _singular(d, _interior(dom))
    if not 1 <= len(crit + sing) <= 4:
        raise Reject("redraw", "f must have one to four breakpoints")
    inc, chart = _regions(fe, d, dom, crit, sing, 1)
    dec = [(lo, hi) for lo, hi, s in chart if s == -1]
    ivs = inc if ask == "increasing" else dec
    if not ivs:
        raise Reject("redraw", f"f is never {ask}")
    flat = [c for c in crit if c not in sing and any(lo == c or hi == c for lo, hi, _ in chart) and
            len([1 for lo, hi, s in chart if hi == c or lo == c]) == 1]
    _check(axes, kind=kind, ask=ask)
    g = _fn(d)
    _check_changes(g, dom, None, crit + sing)
    if not _grid_agree(g, ivs, 1 if ask == "increasing" else -1, dom):
        raise Reject("redraw", "the sign chart failed the grid check")
    ans = {"type": "interval", "latex": _iv_latex(ivs), "sympy": _iv_sympy([(a, b) for a, b in ivs]), "numeric": None}
    chart_text = ",\\ ".join(f"\\left({L(lo) if lo != -sp.oo else '-\\infty'},\\ {L(hi) if hi != sp.oo else '\\infty'}\\right):"
                             f"\\ {'+' if s > 0 else '-'}" for lo, hi, s in chart)
    steps = [step("Differentiate.", f"f'(x) = {L(d)}", str(d)),
             step("Breakpoints: zeros of f' and points where f' is undefined (inside the domain).",
                  f"x \\in {_set_answer(sorted(set(crit + sing), key=float))['latex']}"),
             step("Sign of f' on each interval.", chart_text),
             step(f"f is {ask} where f' is {'positive' if ask == 'increasing' else 'negative'}.", ans["latex"], ans["sympy"])]
    st = f"Find the open intervals on which $f(x) = {_fx(fe)}$ is {ask}."
    return finish(stem, fe, ask, st, ans, steps, kind, axes, exact=True, raw_extra={"kind": kind, "ask": ask})


def _verify_concavity(stem, axes, f, ask, **_):
    if ask not in ("up", "down", "inflection"):
        raise Reject("slip", "ask must be up, down or inflection")
    fe, d, dom = _prepare(f)
    kind = _kind(fe)
    dd = sp.cancel(sp.together(sp.diff(d, x))) if fe.is_rational_function(x) else sp.diff(d, x)
    inner = _interior(dom)
    zs = _zeros(dd, inner, "a zero of f''")
    sing = _singular(dd, inner)
    if not 1 <= len(zs + sing) <= 4:
        raise Reject("redraw", "f'' must have one to four breakpoints")
    chart = _sign_chart(dd, dom, zs + sing)
    chart_m = _merge(chart, {c for c in zs if c not in sing})
    flips = [c for c in zs if c not in sing and any(chart[i][1] == c and chart[i][2] != chart[i + 1][2]
                                                  for i in range(len(chart) - 1) if chart[i + 1][0] == c)]
    nochange = [c for c in zs if c not in sing and c not in flips]
    _check(axes, kind=kind, ask=ask)
    g = _fn(dd)
    _check_changes(g, dom, None, zs + sing, what="f''")
    steps = [step("Differentiate twice.", f"f''(x) = {L(dd)}", str(dd)),
             step("Candidates: f''(x) = 0 or undefined.", f"x \\in {_set_answer(sorted(set(zs + sing), key=float))['latex']}")]
    if ask == "inflection":
        pts = [c for c in flips if c not in sing]
        if not pts:
            raise Reject("redraw", "f has no inflection point")
        pts = sorted(pts, key=float)
        for c in pts:
            _short(fe.subs(x, c), "f at an inflection point")
        ans = _set_answer(pts)
        steps.append(step("An inflection point needs a sign change of f'' and a defined f.", ans["latex"], ans["sympy"]))
        st = f"Find the $x$-coordinates of all inflection points of $f(x) = {_fx(fe)}$."
        trap = "yes" if nochange else "no"
        _check(axes, trap=trap)
        return finish(stem, fe, "inflection", st, ans, steps, kind, axes, exact=True,
                      raw_extra={"kind": kind, "ask": ask, "trap": trap})
    sign = 1 if ask == "up" else -1
    ivs = [(lo, hi) for lo, hi, s in chart_m if s == sign]
    if not ivs:
        raise Reject("redraw", f"f is never concave {ask}")
    if not _grid_agree(g, ivs, sign, dom):
        raise Reject("redraw", "the sign chart failed the grid check")
    ans = {"type": "interval", "latex": _iv_latex(ivs), "sympy": _iv_sympy(ivs), "numeric": None}
    steps.append(step(f"Concave {ask} where f'' is {'positive' if sign > 0 else 'negative'}.", ans["latex"], ans["sympy"]))
    st = f"Find the open intervals on which the graph of $f(x) = {_fx(fe)}$ is concave {ask}."
    trap = "yes" if nochange else "no"
    return finish(stem, fe, ask, st, ans, steps, kind, axes, exact=True,
                  raw_extra={"kind": kind, "ask": ask, "trap": trap})


# -- relative extrema ----------------------------------------------------------------------------------------------

def _verify_relative(stem, axes, f, ask, **_):
    if ask not in ("maxima", "minima", "both"):
        raise Reject("slip", "ask must be maxima, minima or both")
    fe, d, dom = _prepare(f)
    kind = _kind(fe)
    inner = _interior(dom)
    zs = _zeros(d, inner, "a zero of f'")
    sing = [v for v in _singular(d, inner) if v not in zs]
    crit = sorted(set(zs) | set(sing), key=float)
    if not 1 <= len(crit) <= 4:
        raise Reject("redraw", "f must have one to four critical numbers")
    dd = sp.diff(d, x)
    chart = _sign_chart(d, dom, crit)
    maxima, minima, flat = [], [], []
    for c in crit:
        left = [s for lo, hi, s in chart if hi == c]
        right = [s for lo, hi, s in chart if lo == c]
        if not left or not right:
            continue
        if left[0] > 0 and right[0] < 0:
            maxima.append(c)
        elif left[0] < 0 and right[0] > 0:
            minima.append(c)
        else:
            flat.append(c)
    second_fails = [c for c in maxima + minima if c in zs and canon(dd.subs(x, c)) == 0]
    if not (maxima or minima):
        raise Reject("redraw", "f has no relative extremum")
    want = {"maxima": maxima, "minima": minima, "both": maxima + minima}[ask]
    if not want:
        raise Reject("redraw", f"f has no relative {ask}")
    trap = "yes" if second_fails or flat else "no"
    _check(axes, kind=kind, ask=ask, trap=trap)
    g = _fn(d)
    _check_changes(g, dom, None, crit, what="f'")
    for c in maxima + minima:
        _short(fe.subs(x, c), "f at an extremum")
    steps = [step("Differentiate and find the critical numbers.", f"f'(x) = {L(d)},\\ x \\in {_set_answer(crit)['latex']}"),
             step("Sign of f' on each side of each critical number.",
                  ",\\ ".join(f"x = {L(c)}: " + ("+ \\to -" if c in maxima else "- \\to +" if c in minima else "\\text{no change}")
                              for c in crit))]
    mx, mn = sorted(maxima, key=float), sorted(minima, key=float)
    if ask == "maxima":
        ans = _set_answer(mx)
        q = "relative maximum"
    elif ask == "minima":
        ans = _set_answer(mn)
        q = "relative minimum"
    else:
        ans = {"type": "multi_part",
               "latex": f"\\max:\\ {_set_answer(mx)['latex']},\\ \\min:\\ {_set_answer(mn)['latex']}",
               "sympy": "{max: {" + ", ".join(map(str, mx)) + "}, min: {" + ", ".join(map(str, mn)) + "}}", "numeric": None}
        q = "relative maximum and every relative minimum"
    steps.append(step("A relative maximum is where f' changes from + to -; a minimum from - to +.", ans["latex"], ans["sympy"]))
    st = f"Find the $x$-coordinate of every {q} of $f(x) = {_fx(fe)}$." if ask != "both" else \
        f"Find the $x$-coordinates of every relative maximum and every relative minimum of $f(x) = {_fx(fe)}$."
    return finish(stem, fe, ask, st, ans, steps, kind, axes, exact=True,
                  raw_extra={"kind": kind, "ask": ask, "trap": trap})


# -- Rolle's theorem and the mean value theorem --------------------------------------------------------------------

def _verify_rolle(stem, axes, f, a, b, ask, **_):
    if ask not in ("rolle", "mvt", "applies"):
        raise Reject("slip", "ask must be rolle, mvt or applies")
    lo, hi = _closed(a, b)
    iv = sp.Interval(lo, hi)
    fe = _expr(f, "f")
    if fe.has(sp.Abs, sp.Piecewise) or pool.complexity(fe) > 10:
        raise Reject("redraw", "f must be a smooth, short expression")
    try:
        dom = sp.calculus.util.continuous_domain(fe, x, S.Reals)
    except (NotImplementedError, ValueError, TypeError):
        raise Reject("redraw", "the domain of f could not be found") from None
    d = sp.cancel(sp.together(sp.diff(fe, x))) if fe.is_rational_function(x) else sp.diff(fe, x)
    kind = _kind(fe)
    continuous = iv.is_subset(dom)
    sing = [v for v in _singular(d, sp.Interval.open(lo, hi)) if sp.Interval.open(lo, hi).contains(v) == True]
    differentiable = not sing
    if ask == "applies":
        equal = continuous and canon(fe.subs(x, lo) - fe.subs(x, hi)) == 0
        applies = continuous and differentiable and equal
        why = ("f is not continuous on the closed interval" if not continuous else
               f"f is not differentiable at x = {sing[0]}" if not differentiable else
               "f(a) and f(b) are not equal" if not equal else "all three hypotheses hold")
        _check(axes, kind="hyp", ask=ask)
        ans = {"type": "enum", "latex": "\\text{yes}" if applies else "\\text{no}", "sympy": "yes" if applies else "no",
               "numeric": None}
        steps = [step("Check continuity on [a, b], differentiability on (a, b) and f(a) = f(b).", why)]
        st = (f"Determine whether Rolle's theorem applies to $f(x) = {_fx(fe)}$ on "
              f"$\\left[{L(lo)},\\ {L(hi)}\\right]$. Answer yes or no.")
        return finish(stem, fe, f"{lo},{hi}|applies", st, ans, steps, "hyp", axes, exact=True,
                      raw_extra={"kind": "hyp", "ask": ask})
    if not (continuous and differentiable):
        raise Reject("redraw", "the hypotheses of the theorem must hold")
    fa, fb = canon(fe.subs(x, lo)), canon(fe.subs(x, hi))
    for v in (fa, fb):
        _short(v, "f at an endpoint")
    if ask == "rolle" and fa != fb:
        raise Reject("redraw", "Rolle needs f(a) = f(b)")
    if ask == "mvt" and fa == fb:
        raise Reject("redraw", "use the Rolle recipe when f(a) = f(b)")
    slope = canon((fb - fa) / (hi - lo))
    _short(slope, "the average slope")
    cs = _zeros(d - slope, sp.Interval.open(lo, hi), "a solution of f'(c) = slope")
    if not 1 <= len(cs) <= 3:
        raise Reject("redraw", "there must be one to three values of c")
    mp.mp.dps = 30
    g = _fn(d - slope)
    for c in cs:
        v = g(mp.mpf(str(sp.N(c, 30))))
        if v is None or abs(v) > 1e-15:
            raise Reject("redraw", "f'(c) does not equal the slope at a computed c")
    _check(axes, kind=("rolle" if ask == "rolle" else "mvt_poly" if fe.is_polynomial(x) else "mvt_trans"), ask=ask)
    ans = _set_answer(cs)
    word = "Rolle's theorem" if ask == "rolle" else "the Mean Value Theorem"
    steps = [step("Check the hypotheses: continuous on [a, b], differentiable on (a, b).", ""),
             step("Slope of the secant line." if ask == "mvt" else "f(a) = f(b), so the slope is 0.",
                  f"\\frac{{f({L(hi)}) - f({L(lo)})}}{{{L(hi)} - {L(lo)}}} = {L(slope)}"),
             step("Solve f'(c) = slope inside the open interval.", f"f'(c) = {L(d)} = {L(slope)}"),
             step("Keep the solutions in (a, b).", ans["latex"], ans["sympy"])]
    st = (f"The function $f(x) = {_fx(fe)}$ satisfies the hypotheses of {word} on "
          f"$\\left[{L(lo)},\\ {L(hi)}\\right]$. Find all numbers $c$ in $\\left({L(lo)},\\ {L(hi)}\\right)$ that satisfy its "
          "conclusion.")
    return finish(stem, fe, f"{lo},{hi}|{ask}", st, ans, steps,
                  "rolle" if ask == "rolle" else "mvt_poly" if fe.is_polynomial(x) else "mvt_trans", axes, exact=True,
                  raw_extra={"kind": "rolle" if ask == "rolle" else "mvt_poly" if fe.is_polynomial(x) else "mvt_trans",
                             "ask": ask})


# -- curve sketching -----------------------------------------------------------------------------------------------

def _verify_sketch(stem, axes, f, **_):
    fe, d, dom = _prepare(f)
    kind = _kind(fe)
    if kind not in ("poly", "rational"):
        raise Reject("redraw", "curve sketching is asked for polynomials and rational functions")
    num, den = sp.fraction(sp.cancel(sp.together(fe)))
    vas = _zeros(den, S.Reals, "a vertical asymptote") if den.has(x) else []
    vas = [v for v in vas if sp.limit(fe, x, v, "+") in (sp.oo, -sp.oo) or sp.limit(fe, x, v, "-") in (sp.oo, -sp.oo)]
    ha = canon(sp.limit(fe, x, sp.oo)) if kind == "rational" else None
    if ha is not None and (ha.has(sp.oo, -sp.oo, sp.zoo, sp.nan) or ha.is_real is not True):
        ha = None
    xint = _zeros(num, dom, "an x-intercept") if num.has(x) else []
    inner = _interior(dom)
    crit = _zeros(d, inner, "a critical number")
    dd = sp.cancel(sp.together(sp.diff(d, x)))
    infl_c = _zeros(dd, inner, "a candidate inflection point")
    ch2 = _sign_chart(dd, dom, infl_c + [v for v in vas])
    infl = [c for c in infl_c if any(ch2[i][1] == c and ch2[i][2] != ch2[i + 1][2]
                                     for i in range(len(ch2) - 1) if ch2[i + 1][0] == c)]
    ch1 = _sign_chart(d, dom, crit + vas)
    ext = []
    for c in crit:
        left = [s for lo, hi, s in ch1 if hi == c]
        right = [s for lo, hi, s in ch1 if lo == c]
        if left and right and left[0] != right[0]:
            ext.append((c, "max" if left[0] > 0 else "min", _short(fe.subs(x, c), "f at an extremum")))
    if not (ext or infl or vas):
        raise Reject("redraw", "f has too little structure for a sketch")
    f0 = canon(fe.subs(x, 0)) if dom.contains(0) == True else None
    _check(axes, kind=kind)
    mp.mp.dps = 30
    gd = _fn(d)
    _check_changes(gd, dom, None, crit + vas, what="f'")
    parts = {"vertical asymptotes": _set_answer(sorted(vas, key=float)),
             "x-intercepts": _set_answer(sorted(xint, key=float)),
             "extrema": None}
    ext_tex = ",\\ ".join(f"\\left({L(c)},\\ {L(v)}\\right)\\ \\text{{{t}}}" for c, t, v in ext) or "\\text{none}"
    ha_tex = L(ha) if ha is not None else "\\text{none}"
    y_tex = L(f0) if f0 is not None else "\\text{none}"
    infl_tex = _set_answer(sorted(infl, key=float))["latex"]
    latex = (f"x\\text{{-int}}: {parts['x-intercepts']['latex']};\\ y\\text{{-int}}: {y_tex};\\ "
             f"\\text{{VA}}: {parts['vertical asymptotes']['latex']};\\ \\text{{HA}}: y = {ha_tex};\\ "
             f"\\text{{extrema}}: {ext_tex};\\ \\text{{inflection}}: {infl_tex}")
    sym = ("{x_int: {" + ", ".join(map(str, sorted(xint, key=float))) + "}, y_int: " + str(f0)
           + ", va: {" + ", ".join(map(str, sorted(vas, key=float))) + "}, ha: " + str(ha) + ", extrema: {"
           + ", ".join(f"({c}, {v}): {t}" for c, t, v in ext) + "}, inflection: {"
           + ", ".join(map(str, sorted(infl, key=float))) + "}}")
    ans = {"type": "multi_part", "latex": latex, "sympy": sym, "numeric": None}
    steps = [step("Domain, intercepts and asymptotes.", f"{parts['x-intercepts']['latex']},\\ {parts['vertical asymptotes']['latex']},\\ y = {ha_tex}"),
             step("Critical numbers and the sign of f'.", f"f'(x) = {L(d)}"),
             step("The sign of f'' gives concavity and the inflection points.", f"f''(x) = {L(dd)}"),
             step("Collect the features.", latex, sym)]
    st = (f"For $f(x) = {_fx(fe)}$, find the $x$-intercepts, the $y$-intercept, the vertical asymptotes, the horizontal "
          "asymptote, the relative extrema (with their coordinates) and the $x$-coordinates of the inflection points.")
    return finish(stem, fe, "features", st, ans, steps, kind, axes, exact=True, raw_extra={"kind": kind})


_VERIFY = {"critical_numbers": _verify_critical, "absolute_extrema": _verify_absolute,
           "increasing_decreasing": _verify_increasing, "relative_extrema": _verify_relative, "rolle_mvt": _verify_rolle,
           "concavity_inflection": _verify_concavity, "curve_sketching": _verify_sketch}
