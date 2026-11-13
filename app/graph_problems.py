"""Graph-reading problems for the shape-of-a-graph topics (C3): the student is given a picture, not a formula.

Two kinds, both built from a factored polynomial f' = c * prod (x - r)^m whose roots sit on half-integers, so every
feature can be read off the labelled ticks:
  fprime_inc  the graph of f' is shown; on which open intervals of the window is f increasing (or decreasing)?
  f_extrema   the graph of f is shown; at which x are the relative maxima (minima, both)?

The model proposes structure only (roots, multiplicities, the sign of c, the question). The server builds the
polynomial, derives the answer with an exact sign chart, draws the figure from the same polynomial, and then re-checks
the answer against the sampled curve, which is what the student sees.
"""
import math

import sympy as sp

from app import figures
from app.applications import _iv_latex, _iv_sympy, _set_answer
from app.calculus_core import finish, step
from app.integral_core import L, Reject, x
from app.limits import _expr, _point

KINDS = ("fprime_inc", "f_extrema")
MARGINS = (2, 1)                     # window = the roots plus this many units each side, in whole units
VISIBLE = 0.08                       # a feature must move the curve by this share of the vertical range
LOCAL = 0.02                         # and near a turning point, by this share, within a short distance
S = sp.S


def verify(kind: str, roots: list, mults: list, lead: str, ask: str, axes: dict | None = None, debug: bool = True) -> dict:
    try:
        return _verify(kind, roots, mults, lead, ask, axes or {}, debug)
    except Reject as r:
        return {"ok": False, "cause": r.cause, "reason": r.reason, "cap": r.cap}


def _num(v, what):
    """A rational number from a model's string. Parsed only by app.safe_parse (through app.limits._point), never eval."""
    q = _point(v, what)
    if not q.is_Rational:
        raise Reject("slip", f"{what} must be a rational number")
    return q


def _sign_at(fp, t) -> int:
    v = fp.subs(x, t)
    return 1 if v > 0 else -1


def _chart(fp, roots, lo, hi):
    """[(a, b, sign)] on (lo, hi), with intervals joined across an even-multiplicity root."""
    cuts = [S(lo)] + roots + [S(hi)]
    out = []
    for a, b in zip(cuts, cuts[1:]):
        s = _sign_at(fp, (a + b) / 2)
        if out and out[-1][2] == s:
            out[-1] = (out[-1][0], b, s)
        else:
            out.append((a, b, s))
    return out


def _scan(g, lo, hi, n=1000):
    """x-positions between neighbouring off-grid samples where g changes sign."""
    pts = [lo + (hi - lo) * (i + 0.3711) / (n + 1) for i in range(n + 1)]
    return [(a + b) / 2 for a, b in zip(pts, pts[1:]) if g(a) * g(b) < 0]


def _verify(kind, roots, mults, lead, ask, axes, debug):
    """Try the wider window first; a tighter one makes small features larger."""
    last = None
    for margin in MARGINS:
        try:
            return _build(kind, roots, mults, lead, ask, axes, debug, margin)
        except Reject as r:
            if r.cause != "redraw" or "too small to read" not in r.reason:
                raise
            last = r
    raise last


def _prominence(samp, i):
    """How far the curve moves away from point i on its less eventful side, before it turns round."""
    best = []
    for step_ in (-1, 1):
        j, far = i, 0.0
        while 0 < j + step_ < len(samp) - 1 or j + step_ in (0, len(samp) - 1):
            j += step_
            far = max(far, abs(samp[j] - samp[i]))
            if j in (0, len(samp) - 1) or (samp[j + step_] - samp[j]) * (samp[j] - samp[j - step_]) < 0:
                break
        best.append(far)
    return min(best)


def _build(kind, roots, mults, lead, ask, axes, debug, margin):
    if kind not in KINDS:
        raise Reject("slip", f"kind must be one of {', '.join(KINDS)}")
    if ask not in (("increasing", "decreasing") if kind == "fprime_inc" else ("maxima", "minima", "both")):
        raise Reject("slip", "ask does not belong to this kind")
    rs = [_num(r, "a root") for r in roots]
    ms = [int(m) for m in mults]
    if len(rs) != len(ms) or not 1 <= len(rs) <= 3 or len(set(rs)) != len(rs):
        raise Reject("slip", "give one to three distinct roots, one multiplicity each")
    if any(m not in (1, 2) for m in ms) or all(m == 2 for m in ms):
        raise Reject("redraw", "multiplicities are 1 or 2, and at least one root must change the sign")
    if not figures.on_grid(rs, 0.5) or any(abs(r) > 4 for r in rs):
        raise Reject("redraw", "roots must sit on half-integers with |r| <= 4")
    c = _num(lead, "the leading coefficient")
    if c == 0 or abs(c) > 3:
        raise Reject("redraw", "the leading coefficient must be nonzero and at most 3 in size")
    order = sorted(range(len(rs)), key=lambda i: rs[i])
    rs, ms = [rs[i] for i in order], [ms[i] for i in order]
    lo, hi = math.floor(float(min(rs))) - margin, math.ceil(float(max(rs))) + margin
    while hi - lo < 6:
        lo, hi = lo - 1, hi + 1
    fp = c * sp.Mul(*[(x - r) ** m for r, m in zip(rs, ms)])
    fe = sp.integrate(fp, x) if kind == "f_extrema" else fp
    shown = fe
    # the independent view: what the student sees
    g = figures._fn(fp)
    odd = [r for r, m in zip(rs, ms) if m == 1]
    seen = _scan(g, lo, hi)
    if len(seen) != len(odd) or any(min(abs(s - float(r)) for r in odd) > 0.03 for s in seen):
        raise Reject("redraw", "the sampled sign changes do not match the roots")
    chart = _chart(fp, rs, lo, hi)
    ys = [v for _, v in figures.sample(shown, lo, hi) if v is not None]
    ymin, ymax, ystep = figures.y_window(ys)
    if ymax - ymin > 400:
        raise Reject("redraw", "the graph needs too large a vertical scale")
    span = ymax - ymin
    if kind == "fprime_inc":
        cuts = [lo] + [float(r) for r in rs] + [hi]
        for a, b in zip(cuts, cuts[1:]):
            lobe = max(abs(v) for t, v in figures.sample(shown, a, b, 120) if v is not None)
            if lobe < VISIBLE * span / 2:
                raise Reject("redraw", "a piece of the graph is too small to read")
        want = 1 if ask == "increasing" else -1
        ivs = [(a, b) for a, b, s in chart if s == want]
        if not ivs:
            raise Reject("redraw", f"f is never {ask} here")
        ans = {"type": "interval", "latex": _iv_latex(ivs), "sympy": _iv_sympy(ivs), "numeric": None}
        trap = "yes" if any(m == 2 for m in ms) else "no"
        label, alt = "y = f′(x)", f"The graph of the derivative f′(x) for x from {lo} to {hi}, on a labelled grid.".replace("-", "−")
        st = (f"The figure shows the graph of $y = f'(x)$, the derivative of a function $f$, for ${lo} \\le x \\le {hi}$. "
              f"Find the open intervals within $({lo},\\ {hi})$ on which $f$ is {ask}. Assume the graph shows every zero of $f'$.")
        steps = [step("Read where the graph of f' is above the x-axis (f' > 0) and below it (f' < 0).",
                      ",\\ ".join(f"\\left({L(a)},\\ {L(b)}\\right):\\ {'+' if s > 0 else '-'}" for a, b, s in chart)),
                 step(f"f is {ask} where f' is {'positive' if want > 0 else 'negative'}. A touch of the x-axis without a "
                      "crossing does not change the sign.", ans["latex"], ans["sympy"])]
        points = []
        key = f"{kind}|{ask}"
    else:
        maxima, minima = [], []
        for r, m in zip(rs, ms):
            if m != 1:
                continue
            (maxima if _sign_at(fp, r - sp.Rational(1, 100)) > 0 else minima).append(r)
        # the sampled curve must show the same turning points as the exact chart
        samp = [v for _, v in figures.sample(shown, lo, hi, 1001)]
        turns = [(i, samp[i]) for i in range(1, 1000) if None not in (samp[i - 1], samp[i], samp[i + 1])
                 and ((samp[i] - samp[i - 1]) * (samp[i + 1] - samp[i]) < 0)]
        if len(turns) != len(odd):
            raise Reject("redraw", "the sampled curve does not show the turning points the sign chart has")
        if any(_prominence(samp, i) < VISIBLE * span for i, _ in turns):
            raise Reject("redraw", "a turning point is too small to read at this scale")
        fr = figures._fn(shown)
        for r in odd:                       # near a turning point the curve must visibly leave it, on both sides, or a
            gap = min([abs(float(r) - float(o)) for o in rs if o != r] + [float(r) - lo, hi - float(r)])   # neighbouring
            d, f0 = min(1.0, gap / 2), fr(float(r))                                                       # flat spot blurs it
            near = [fr(float(r) - d), fr(float(r) + d)]
            if f0 is None or None in near or min(abs(v - f0) for v in near) < LOCAL * span:
                raise Reject("redraw", "a turning point is too small to read at this scale")
        want = {"maxima": maxima, "minima": minima, "both": maxima + minima}[ask]
        if not want:
            raise Reject("redraw", f"f has no relative {ask} here")
        mx, mn = sorted(maxima), sorted(minima)
        if ask == "both":
            ans = {"type": "multi_part", "latex": f"\\max:\\ {_set_answer(mx)['latex']},\\ \\min:\\ {_set_answer(mn)['latex']}",
                   "sympy": "{max: {" + ", ".join(map(str, mx)) + "}, min: {" + ", ".join(map(str, mn)) + "}}", "numeric": None}
            q = "every relative maximum and every relative minimum"
        else:
            ans = _set_answer(sorted(want))
            q = "every relative " + ("maximum" if ask == "maxima" else "minimum")
        trap = "yes" if any(m == 2 for m in ms) else "no"      # a flat spot that is not an extremum
        label, alt = "y = f(x)", f"The graph of the function f(x) for x from {lo} to {hi}, on a labelled grid.".replace("-", "−")
        st = (f"The figure shows the graph of $y = f(x)$ for ${lo} \\le x \\le {hi}$. Find the $x$-coordinate of {q} of $f$ "
              "in this window. Assume the graph shows every turning point of $f$.")
        steps = [step("A relative maximum is a peak of the graph and a relative minimum is a valley. Read their x-coordinates "
                      "from the labelled ticks.", ans["latex"], ans["sympy"])]
        points = []
        key = f"{kind}|{ask}"
    spec = figures.graph_spec([figures.curve(shown, lo, hi, ymin, ymax, label, debug, tex=label.replace("′", "'"))], lo, hi, ymin, ymax,
                              1 if all(r.is_Integer for r in rs) else 0.5, ystep, alt, points=points)   # a half-integer feature needs a tick
    res = finish("increasing_decreasing" if kind == "fprime_inc" else "relative_extrema", fp,
                 f"graph|{key}|{sp.srepr(fp)}", st, ans, steps, kind, axes, exact=True,
                 raw_extra={"kind": kind, "ask": ask, "trap": trap, "view": "graph"})
    res["requires_figure"] = True
    res["figure"] = {"spec": spec, "svg": figures.svg(spec), "alt": alt}
    return res


# -- trigonometric graphs ------------------------------------------------------------------------------------------
# f' (or f) = amp * sin(freq x) or amp * cos(freq x) (+ lift for f), on a window given in multiples of pi, with the
# x axis marked in multiples of pi. Same two kinds as above; the zeros and turning points are multiples of pi/(2 freq)
# and the server insists that each sits on a tick.

TRIG_FREQS = (sp.Rational(1, 2), S(1), S(2))


def _zeros_in(name, freq, lo, hi):
    """Zeros of name(freq x) strictly inside (lo, hi), and whether one sits on an edge (lo and hi are multiples of pi)."""
    inside, edge = [], False
    for k in range(-40, 41):
        r = (k * sp.pi if name == "sin" else (2 * k + 1) * sp.pi / 2) / freq
        if lo < r < hi:
            inside.append(r)
        elif r in (lo, hi):
            edge = True
    return sorted(inside, key=float), edge


def _build_trig(kind, ask, fn, amp, freq, lift, window, axes, debug):
    if kind not in KINDS:
        raise Reject("slip", f"kind must be one of {', '.join(KINDS)}")
    if ask not in (("increasing", "decreasing") if kind == "fprime_inc" else ("maxima", "minima", "both")):
        raise Reject("slip", "ask does not belong to this kind")
    if fn not in ("sin", "cos"):
        raise Reject("slip", "trig must be sin or cos")
    a, b, c = _num(amp, "amp"), _num(freq, "freq"), _num(lift or "0", "lift")
    if a == 0 or abs(a) > 3 or not figures.on_grid([a], 0.5):
        raise Reject("redraw", "amp must be a nonzero multiple of 1/2, at most 3 in size")
    if b not in TRIG_FREQS:
        raise Reject("redraw", "freq must be 1/2, 1 or 2")
    if not c.is_Integer or abs(c) > 2 or (kind == "fprime_inc" and c != 0):
        raise Reject("redraw", "lift is a whole number from -2 to 2, and 0 when the graph of f' is shown")
    parts = _list(window, "window")
    if len(parts) != 2:
        raise Reject("slip", "window is two numbers, in multiples of pi, such as -1,2")
    wl, wh = _num(parts[0], "window"), _num(parts[1], "window")
    if not figures.on_grid([wl, wh], 0.5) or not -4 <= wl < wh <= 4 or not 2 <= wh - wl <= 4:
        raise Reject("redraw", "the window is on multiples of pi/2 within [-4 pi, 4 pi], 2 pi to 4 pi wide")
    lo, hi = wl * sp.pi, wh * sp.pi
    trig = getattr(sp, fn)
    shown = a * trig(b * x) + c
    fp = shown if kind == "fprime_inc" else sp.diff(shown, x)
    zname = fn if kind == "fprime_inc" else ("cos" if fn == "sin" else "sin")
    zs, edge = _zeros_in(zname, b, lo, hi)
    if kind == "f_extrema" and edge:
        raise Reject("redraw", "a turning point sits on the edge of the window")
    if not zs:
        raise Reject("redraw", "the window shows no zero of the derivative")
    tick = figures.nice_pi_step(float(hi - lo))
    stq = sp.Rational(tick).limit_denominator(12)
    if any(not (r / sp.pi / stq).is_integer for r in zs):
        raise Reject("redraw", "a feature does not sit on a tick of the pi axis")
    ys = [v for _, v in figures.sample(shown, float(lo), float(hi)) if v is not None]
    ymin, ymax, ystep = figures.y_window(ys)
    g = figures._fn(shown if kind == "f_extrema" else fp)
    if kind == "fprime_inc":                 # what the student sees: the sampled sign changes are the zeros
        seen = _scan(g, float(lo), float(hi))
        if len(seen) != len(zs) or any(min(abs(s - float(r)) for r in zs) > 0.05 for s in seen):
            raise Reject("redraw", "the sampled sign changes do not match the zeros")
        want = 1 if ask == "increasing" else -1
        cuts = [lo] + zs + [hi]
        ivs = [(p, q) for p, q in zip(cuts, cuts[1:]) if _sign_at(fp, (p + q) / 2) == want]
        if not ivs:
            raise Reject("redraw", f"f is never {ask} here")
        ans = {"type": "interval", "latex": _iv_latex(ivs), "sympy": _iv_sympy(ivs), "numeric": None}
        label, what = "y = f′(x)", "the graph of $y = f'(x)$, the derivative of a function $f$,"
        alt = f"The graph of the derivative f′(x) for x from {L(lo)} to {L(hi)}, on a labelled grid marked in multiples of π.".replace("-", "−")
        chart = ",\\ ".join(f"\\left({L(p)},\\ {L(q)}\\right):\\ {'+' if _sign_at(fp, (p + q) / 2) > 0 else '-'}"
                            for p, q in zip(cuts, cuts[1:]))
        st = (f"The figure shows {what} for ${L(lo)} \\le x \\le {L(hi)}$. Find the open intervals within "
              f"$\\left({L(lo)},\\ {L(hi)}\\right)$ on which $f$ is {ask}. Assume the graph shows every zero of $f'$ in this window.")
        steps = [step("Read where the graph of f' is above the x-axis (f' > 0) and below it (f' < 0).", chart),
                 step(f"f is {ask} where f' is {'positive' if want > 0 else 'negative'}.", ans["latex"], ans["sympy"])]
    else:
        samp = [v for _, v in figures.sample(shown, float(lo), float(hi), 1001)]
        xs = [float(lo) + (float(hi) - float(lo)) * i / 1000 for i in range(1001)]
        seen = [xs[i] for i in range(1, 1000) if (samp[i] - samp[i - 1]) * (samp[i + 1] - samp[i]) < 0]
        if len(seen) != len(zs) or any(min(abs(s - float(r)) for r in zs) > 0.05 for s in seen):
            raise Reject("redraw", "the sampled curve does not show the turning points the exact ones give")
        maxima = [r for r in zs if _sign_at(fp, r - sp.Rational(1, 100)) > 0]
        minima = [r for r in zs if r not in maxima]
        want = {"maxima": maxima, "minima": minima, "both": maxima + minima}[ask]
        if not want:
            raise Reject("redraw", f"f has no relative {ask} here")
        if ask == "both":
            ans = {"type": "multi_part", "latex": f"\\max:\\ {_set_answer(maxima)['latex']},\\ \\min:\\ {_set_answer(minima)['latex']}",
                   "sympy": "{max: {" + ", ".join(map(str, maxima)) + "}, min: {" + ", ".join(map(str, minima)) + "}}", "numeric": None}
            q = "every relative maximum and every relative minimum"
        else:
            ans = _set_answer(sorted(want, key=float))
            q = "every relative " + ("maximum" if ask == "maxima" else "minimum")
        label = "y = f(x)"
        alt = f"The graph of the function f(x) for x from {L(lo)} to {L(hi)}, on a labelled grid marked in multiples of π.".replace("-", "−")
        st = (f"The figure shows the graph of $y = f(x)$ for ${L(lo)} \\le x \\le {L(hi)}$. Find the $x$-coordinate of {q} "
              "of $f$ in this window. Assume the graph shows every turning point of $f$.")
        steps = [step("A relative maximum is a peak of the graph and a relative minimum is a valley. Read their x-coordinates "
                      "from the labelled ticks.", ans["latex"], ans["sympy"])]
    spec = figures.graph_spec([figures.curve(shown, float(lo), float(hi), ymin, ymax, label, debug, tex=label.replace("′", "'"))],
                              float(lo), float(hi), ymin, ymax, float(stq), ystep, alt, x_pi=True)
    stem = "increasing_decreasing" if kind == "fprime_inc" else "relative_extrema"
    res = finish(stem, fp, f"trig|{kind}|{ask}|{sp.srepr(shown)}|{wl},{wh}", st, ans, steps, kind, axes, exact=True,
                 raw_extra={"kind": kind, "ask": ask, "trap": "no", "view": "trig"})
    res["requires_figure"] = True
    res["figure"] = {"spec": spec, "svg": figures.svg(spec), "alt": alt}
    return res


# -- holes and jumps -----------------------------------------------------------------------------------------------
# A hollow circle marks a point that is not on the graph; a filled circle marks one that is. The model proposes the
# pieces (polynomials of degree two or less) and where they meet; the server draws them and derives every answer.

DISC_ASKS = ("limit", "value", "classify")


def verify_disc(kind: str, a: str, g: str, h: str, at: str, ask: str, axes: dict | None = None, debug: bool = True) -> dict:
    """kind: hole | jump. a: where the discontinuity is. g: the left piece (the whole curve for a hole); h: the right
    piece. at: for a hole, f(a) as a number or '' (undefined); for a jump, which piece owns x = a (left, right, none)."""
    try:
        return _build_disc(kind, a, g, h, at, ask, axes or {}, debug)
    except Reject as r:
        return {"ok": False, "cause": r.cause, "reason": r.reason, "cap": r.cap}


def _piece(s, what):
    e = _expr(s, what)
    if not e.has(x) or not e.is_polynomial(x) or sp.Poly(e, x).degree() > 2 or any(
            not c.is_Rational for c in sp.Poly(e, x).all_coeffs()):
        raise Reject("redraw", f"{what} must be a polynomial of degree one or two with rational coefficients")
    return e


def _dne():
    return {"type": "enum", "latex": "\\text{does not exist}", "sympy": None, "numeric": None}


def _num_answer(v):
    return {"type": "numeric", "latex": L(v), "sympy": str(v), "numeric": float(v)}


def _build_disc(kind, a, g, h, at, ask, axes, debug):
    if kind not in ("hole", "jump") or ask not in DISC_ASKS:
        raise Reject("slip", "kind is hole or jump; ask is limit, value or classify")
    a = _num(a, "a")
    if not a.is_Integer or abs(a) > 3:
        raise Reject("redraw", "the discontinuity must sit at an integer with |a| <= 3")
    lo, hi = -5, 5
    ge, he = _piece(g, "the left piece"), _piece(h, "the right piece")
    ga, ha = ge.subs(x, a), he.subs(x, a)
    if not figures.on_grid([ga, ha], 0.5) or max(abs(ga), abs(ha)) > 6:
        raise Reject("redraw", "the values at the discontinuity must sit on half-integers, within 6 of the axis")
    if kind == "hole":
        if sp.simplify(ge - he) != 0:
            raise Reject("redraw", "a hole has one piece: g and h must be equal")
        fa = None if str(at).strip() == "" else _num(at, "f(a)")
        if fa is not None and (fa == ga or not figures.on_grid([fa], 0.5) or abs(fa) > 6):
            raise Reject("redraw", "f(a) must differ from the hole and sit on a half-integer")
        owner = None
    else:
        if at not in ("left", "right", "none"):
            raise Reject("slip", "at is left, right or none for a jump")
        if abs(ga - ha) < 1:
            raise Reject("redraw", "a jump needs a gap of at least 1")
        owner, fa = at, None
    # the answer
    if ask == "limit":
        ans, q = (_num_answer(ga) if kind == "hole" else _dne()), f"Find $\\lim_{{x \\to {a}}} f(x)$. If the limit does not exist, say so."
        why = "The two-sided limit is the common value of the one-sided limits." if kind == "jump" else \
              "Near the hole the graph approaches one height from both sides; the point itself does not matter."
    elif ask == "value":
        v = (fa if fa is not None else None) if kind == "hole" else {"left": ga, "right": ha}.get(owner)
        ans = _num_answer(v) if v is not None else {"type": "enum", "latex": "\\text{undefined}", "sympy": None, "numeric": None}
        q, why = f"Find $f({a})$. If $f({a})$ is not defined, say so.", "f(a) is the height of the filled circle at x = a, if there is one."
    else:
        word = "removable" if kind == "hole" else "jump"
        ans = {"type": "enum", "latex": f"\\text{{{word}}}", "sympy": word, "numeric": None}
        q, why = f"Classify the discontinuity at $x = {a}$ as removable or jump.", \
                 "The one-sided limits are equal (removable) or different (jump)."
    # the picture
    pieces = [(ge, lo, hi)] if kind == "hole" else [(ge, lo, a), (he, a, hi)]
    ys = [v for e, p, q_ in pieces for _, v in figures.sample(e, p, q_, 120) if v is not None]
    ymin, ymax, ystep = figures.y_window(ys)
    if ymax - ymin > 40:
        raise Reject("redraw", "the graph needs too large a vertical scale")
    marks = []
    if kind == "hole":
        marks.append(figures.marker(a, ga, hollow=True))
        if fa is not None:
            marks.append(figures.marker(a, fa, hollow=False))
    else:
        marks += [figures.marker(a, ga, hollow=owner != "left"), figures.marker(a, ha, hollow=owner != "right")]
    # the sampled curve must show the limits the answer claims
    cu = figures.pieces_curve(pieces, ymin, ymax, "y = f(x)", debug, tex="y = f(x)")
    near = [p for p in cu["points"] if p is not None and 0 < abs(p[0] - float(a)) < 0.06]
    left, right = [p[1] for p in near if p[0] < a], [p[1] for p in near if p[0] > a]
    if not left or not right or abs(left[-1] - float(ga)) > 0.35 or abs(right[0] - float(ha)) > 0.35:
        raise Reject("redraw", "the drawn curve does not approach the stated heights")
    alt = f"The graph of a function f for x from {lo} to {hi}, on a labelled grid, with open and filled circles.".replace("-", "−")
    if any(not v.is_Integer for v in [ga, ha] + ([fa] if fa is not None else [])):
        ystep = 0.5                                                 # a height on a half-integer needs a tick of its own
        if (ymax - ymin) / ystep > 32:
            raise Reject("redraw", "the graph needs too many ticks to show a half-integer height")
    spec = figures.graph_spec([cu], lo, hi, ymin, ymax, 1, ystep, alt, points=marks)
    st = (f"The figure shows the graph of a function $f$ for ${lo} \\le x \\le {hi}$. A hollow circle marks a point that is not "
          f"on the graph, and a filled circle marks a point that is on it. {q}")
    steps = [step(why, ans["latex"], ans["sympy"])]
    res = finish("classify_discontinuity", ge, f"disc|{kind}|{a}|{he}|{at}|{ask}", st, ans, steps, kind, axes, exact=True,
                 has_disc=True, raw_extra={"kind": kind, "ask": ask})
    res["requires_figure"] = True
    res["figure"] = {"spec": spec, "svg": figures.svg(spec), "alt": alt}
    return res


# -- the topics' entry point ---------------------------------------------------------------------------------------

TOPIC_KIND = {"increasing_decreasing": "fprime_inc", "relative_extrema": "f_extrema"}


def _list(s, what):
    parts = [p.strip() for p in str(s or "").split(",") if p.strip()]
    if not parts:
        raise Reject("slip", f"{what} must be a comma-separated list")
    return parts


def verify_topic(stem: str, axes: dict, ask: str = "", roots: str = "", mults: str = "", lead: str = "", view: str = "graph",
                 trig: str = "", amp: str = "", freq: str = "", lift: str = "", window: str = "", **_) -> dict:
    """A graph-view reply of a topic: roots, multiplicities and the leading coefficient as comma-separated strings."""
    try:
        if stem not in TOPIC_KIND:
            raise Reject("slip", f"{stem} has no graph view")
        if view == "trig":
            return _build_trig(TOPIC_KIND[stem], ask, trig, amp, freq, lift, window, axes, True)
        try:
            ms = [int(m) for m in _list(mults, "mults")]
        except ValueError:
            raise Reject("slip", "mults must be whole numbers") from None
        return _verify(TOPIC_KIND[stem], _list(roots, "roots"), ms, lead, ask, axes, True)
    except Reject as r:
        return {"ok": False, "cause": r.cause, "reason": r.reason, "cap": r.cap}
