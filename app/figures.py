"""Figures for graph-reading problems. One JSON spec is the single source; the SVG is drawn from it, so the two cannot
disagree. Only server code builds a spec or an SVG: the model never supplies either, and every string that reaches the
SVG is escaped.

A spec holds sampled points, not formulas. The formula of a graph-only problem would give the answer away, so it goes
in `expr` and `public_spec` drops it unless debug is on (the way `answer.sympy` is handled).

    spec = {"version": 1, "kind": "function_graph", "viewport": {"xmin", "xmax", "ymin", "ymax"},
            "ticks": {"x", "y"}, "curves": [{"label", "points": [[x, y] | null, ...], "expr"}],
            "points": [{"x", "y", "style": "closed" | "open"}], "asymptotes": [{"axis": "x" | "y", "value"}],
            "alt": "..."}

A null inside `points` is a break: lift the pen (a jump, an asymptote, a point outside the window).
"""
import hashlib
import json
import math
from fractions import Fraction
from xml.sax.saxutils import escape

import sympy as sp

from app.figure_labels import GLYPHS

x = sp.Symbol("x")
VERSION = 1
SAMPLES = 481
STEPS = (0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000)


PI_STEPS = (Fraction(1, 6), Fraction(1, 4), Fraction(1, 3), Fraction(1, 2), Fraction(1), Fraction(2), Fraction(4))


def nice_pi_step(span: float, most: int = 8) -> float:
    """A tick step in units of pi (pi/6, pi/4, pi/3, pi/2, pi, ...) giving at most `most` intervals over `span` radians."""
    return float(next((q for q in PI_STEPS if span / math.pi / float(q) <= most), PI_STEPS[-1]))


def nice_step(span: float, most: int = 10) -> float:
    """The smallest tick step in STEPS that gives at most `most` intervals over `span`."""
    return next((s for s in STEPS if span / s <= most), STEPS[-1])


def _fn(expr):
    fl = sp.lambdify(x, expr, "math")

    def g(t):
        try:
            v = fl(t)
        except (ValueError, ZeroDivisionError, OverflowError, TypeError):
            return None
        if isinstance(v, complex) or v is None or not math.isfinite(v):
            return None
        return float(v)
    return g


def sample(expr, xmin: float, xmax: float, n: int = SAMPLES) -> list[tuple[float, float]]:
    """(x, y) on an even grid; None where f is undefined or not finite."""
    g = _fn(expr)
    xmin, xmax = float(xmin), float(xmax)          # plain floats, so a spec is always pure JSON
    out = []
    for i in range(n):
        t = xmin + (xmax - xmin) * i / (n - 1)
        v = g(t)
        out.append((t, v))
    return out


def y_window(ys: list[float], pad: float = 0.12) -> tuple[float, float, float]:
    """(ymin, ymax, step): the data range padded, snapped outward to the tick step, and always containing 0."""
    lo, hi = min(min(ys), 0.0), max(max(ys), 0.0)
    span = (hi - lo) or 1.0
    lo, hi = lo - pad * span, hi + pad * span
    step = nice_step(hi - lo, 8)
    return math.floor(lo / step) * step, math.ceil(hi / step) * step, step


def curve(expr, xmin: float, xmax: float, ymin: float, ymax: float, label: str, debug: bool = True,
          tex: str | None = None) -> dict:
    """A curve for the window. Points far outside the window become breaks, so a pole is not joined across."""
    far = 0.6 * (ymax - ymin)
    pts, prev_out = [], True
    for t, v in sample(expr, xmin, xmax):
        if v is None or v > ymax + far or v < ymin - far:
            if not prev_out:
                pts.append(None)
            prev_out = True
            continue
        pts.append([round(t, 4), round(v, 4)])
        prev_out = False
    while pts and pts[-1] is None:
        pts.pop()
    c = {"label": label, "points": pts}
    if tex:
        c["tex"] = tex                                  # the label's LaTeX source, for clients that typeset it themselves
    if debug:
        c["expr"] = str(expr)
    return c


def pieces_curve(pieces, ymin: float, ymax: float, label: str, debug: bool = True, tex: str | None = None) -> dict:
    """One curve made of pieces [(expr, x0, x1), ...], each sampled exactly from x0 to x1 with a break between pieces,
    so a jump leaves a gap and a hole leaves the curve running through it (the hollow marker is drawn on top)."""
    far = 0.6 * (ymax - ymin)
    pts, exprs = [], []
    for expr, a, b in pieces:
        if pts and pts[-1] is not None:
            pts.append(None)
        for t, v in sample(expr, a, b, max(60, int(SAMPLES * (b - a) / 10))):
            if v is None or v > ymax + far or v < ymin - far:
                if pts and pts[-1] is not None:
                    pts.append(None)
                continue
            pts.append([round(t, 4), round(v, 4)])
        exprs.append(f"{expr} on [{a}, {b}]")
    while pts and pts[-1] is None:
        pts.pop()
    c = {"label": label, "points": pts}
    if tex:
        c["tex"] = tex
    if debug:
        c["expr"] = "; ".join(exprs)
    return c


def marker(x_: float, y_: float, hollow: bool) -> dict:
    """hollow: the point is NOT on the graph (a hole, or the open end of a piece); filled: it is."""
    return {"x": float(x_), "y": float(y_), "style": "open" if hollow else "closed"}


def graph_spec(curves: list[dict], xmin: float, xmax: float, ymin: float, ymax: float, xstep: float, ystep: float,
               alt: str, points: list[dict] | None = None, asymptotes: list[dict] | None = None,
               x_pi: bool = False) -> dict:
    """With x_pi the x axis is marked in multiples of pi: `xstep` is in units of pi (0.5 puts a tick at every pi/2) and
    the viewport stays in plain numbers, so a window from 0 to 2*pi is xmin = 0, xmax = 6.2832."""
    return {"version": VERSION, "kind": "function_graph",
            "viewport": {"xmin": xmin, "xmax": xmax, "ymin": ymin, "ymax": ymax},
            "ticks": {"x": xstep, "y": ystep, **({"x_unit": "pi"} if x_pi else {})}, "curves": curves,
            "points": points or [], "asymptotes": asymptotes or [], "alt": alt}


def public_spec(spec: dict, debug: bool) -> dict:
    """The spec a client may see. `expr` is the exact formula, so it is debug-only."""
    if debug:
        return spec
    return {**spec, "curves": [{k: v for k, v in c.items() if k != "expr"} for c in spec["curves"]]}


def on_grid(values, step: float = 0.5, tol: float = 1e-9) -> bool:
    """Every value sits on a multiple of `step`: a student can read it off labelled ticks."""
    return all(abs(v / step - round(v / step)) < tol for v in (float(v) for v in values))


# -- SVG -----------------------------------------------------------------------------------------------------------

W, H = 480, 340
ML, MR, MT, MB = 38, 14, 12, 26
MB_PI = 42                           # the bottom margin when the x axis is marked in multiples of pi
TICK = 13                            # tick label size in px
INK, GRID, CURVE, ASYM = "#1b2430", "#dde3ea", "#1f5fbf", "#b3412f"
LINE_W = 2.0                         # curve thickness
MARK_R, MARK_W = 2.4, 1.3            # marker: centre-line radius and ring thickness; outer diameter is about 3x the line
HALO = 'stroke="#ffffff" stroke-width="3" paint-order="stroke"'      # keeps tick labels readable over a curve


def _ticks(lo: float, hi: float, step: float):
    k = math.ceil(lo / step - 1e-9)
    while k * step <= hi + 1e-9:
        yield round(k * step, 10)
        k += 1


def _fmt(v: float) -> str:
    t = str(int(v)) if float(v).is_integer() else f"{v:g}"
    return t.replace("-", "\u2212")          # a real minus sign (the text fallback)


GAP = 0.07            # space between two glyphs, in em
SUB = 0.88            # numerator and denominator are this fraction of the size of the line they sit in


class _Glyphs:
    """The LaTeX outlines one SVG uses: each is defined once in <defs> and drawn with <use>. Ids carry the figure's own
    prefix, because several figures sit in one HTML page and an id must mean the same thing across all of them."""

    def __init__(self, uid: str):
        self.uid = uid
        self.ids: dict[str, str] = {}

    def use(self, key: str, x: float, y: float, size: float, fill: str, halo: bool = False) -> str | None:
        if key not in GLYPHS:
            return None
        gid = self.ids.setdefault(key, f"{self.uid}-g{len(self.ids)}")
        ring = (f' stroke="#ffffff" stroke-width="{3 / size:.3f}" stroke-linejoin="round" paint-order="stroke"'
                if halo else "")
        return f'<use href="#{gid}" transform="translate({x:.1f} {y:.1f}) scale({size:g} {-size:g})" fill="{fill}"{ring}/>'

    def defs(self) -> str:
        return "<defs>" + "".join(f'<path id="{gid}" d="{GLYPHS[k]["d"]}"/>' for k, gid in self.ids.items()) + "</defs>"


def _width(keys: list[str], size: float) -> float:
    return sum(GLYPHS[k]["w"] * size for k in keys) + GAP * size * max(0, len(keys) - 1)


def _run(g: _Glyphs, keys: list[str], x: float, y: float, size: float, fill: str, halo: bool = False) -> list[str] | None:
    """A row of glyphs from x on the baseline y; None if any glyph has no outline."""
    if any(k not in GLYPHS for k in keys):
        return None
    out = []
    for k in keys:
        out.append(g.use(k, x, y, size, fill, halo))
        x += GLYPHS[k]["w"] * size + GAP * size
    return out


def _num_keys(v: float) -> list[str]:
    return ["-" if ch == "-" else ch for ch in (str(int(v)) if float(v).is_integer() else f"{v:g}")]


def _number(g: _Glyphs, v: float, x: float, y: float, size: float, fill: str, end: bool = False, mid: bool = False):
    """A tick number in Computer Modern, right-aligned at x (end) or centred on it (mid); None for text fallback."""
    keys = _num_keys(v)
    w = _width(keys, size) if all(k in GLYPHS for k in keys) else 0
    return _run(g, keys, x - w if end else x - w / 2 if mid else x, y, size, fill, halo=True)


def pi_multiple(k: float) -> tuple[int, int, int]:
    """(sign, numerator, denominator) of k as a fraction: k = sign * numerator / denominator (k in units of pi)."""
    f = Fraction(k).limit_denominator(12)
    return (-1 if f < 0 else 1), abs(f.numerator), f.denominator


def _pi_label(g: _Glyphs, k: float, x: float, axis_y: float, size: float, fill: str) -> list[str] | None:
    """A multiple of pi under the x axis: pi, 2 pi, and a stacked fraction such as 3 pi over 2, centred on the tick."""
    sign, m, d = pi_multiple(k)
    top = axis_y + 7                                              # the top of the label, below the axis
    coeff = [] if m == 1 else _num_keys(m)
    minus = ["-"] if sign < 0 else []
    if d == 1:
        keys = minus + coeff + ["\\pi"]
        return _run(g, keys, x - _width(keys, size) / 2, top + 0.68 * size, size, fill, halo=True)
    s2 = size * SUB
    num, den = coeff + ["\\pi"], _num_keys(d)
    if any(c not in GLYPHS for c in num + den + minus):
        return None
    block = max(_width(num, s2), _width(den, s2)) + 0.25 * size
    lead = (_width(minus, size) + GAP * size) if minus else 0
    x0 = x - (lead + block) / 2
    bar = top + 0.68 * s2 + 0.20 * s2
    out = _run(g, minus, x0, bar + 0.25 * size, size, fill, halo=True) if minus else []     # the minus sits on the bar
    xb = x0 + lead
    out += _run(g, num, xb + (block - _width(num, s2)) / 2, top + 0.68 * s2, s2, fill, halo=True)
    out += _run(g, den, xb + (block - _width(den, s2)) / 2, bar + 1.6 + 0.68 * s2, s2, fill, halo=True)
    out.append(f'<line x1="{xb + 0.05 * size:.1f}" y1="{bar:.1f}" x2="{xb + block - 0.05 * size:.1f}" y2="{bar:.1f}" '
               f'stroke="{fill}" stroke-width="0.9"/>')
    return out


def svg(spec: dict) -> str:
    vp, tk = spec["viewport"], spec["ticks"]
    x0, x1, y0, y1 = vp["xmin"], vp["xmax"], vp["ymin"], vp["ymax"]
    pi = tk.get("x_unit") == "pi"
    mb = MB_PI if pi else MB                                      # stacked fractions need more room under the axis
    pw, ph = W - ML - MR, H - MT - mb
    uid = "f" + hashlib.sha1(json.dumps(spec, sort_keys=True).encode()).hexdigest()[:8]    # same spec, same ids
    clip = f"{uid}-plot"
    g = _Glyphs(uid)

    def px(v):
        return ML + (v - x0) / (x1 - x0) * pw

    def py(v):
        return MT + (y1 - v) / (y1 - y0) * ph

    def xticks():                                                  # (position, value shown): the value is in pi if pi
        if pi:
            for k in _ticks(x0 / math.pi, x1 / math.pi, tk["x"]):
                yield k * math.pi, k
        else:
            for t in _ticks(x0, x1, tk["x"]):
                yield t, t

    axis_y = py(0) if y0 <= 0 <= y1 else py(y0)           # where the x-axis is drawn
    axis_x = px(0) if x0 <= 0 <= x1 else px(x0)
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
         f'font-family="Helvetica, Arial, sans-serif" aria-label="{escape(spec["alt"], {chr(34): "&quot;"})}">',
         f"<title>{escape(spec['alt'])}</title>",
         f'<defs><clipPath id="{clip}"><rect x="{ML}" y="{MT}" width="{pw}" height="{ph}"/></clipPath></defs>',
         f'<rect width="{W}" height="{H}" fill="#ffffff"/>']
    for pos, _ in xticks():
        o.append(f'<line x1="{px(pos):.1f}" y1="{MT}" x2="{px(pos):.1f}" y2="{MT + ph}" stroke="{GRID}" stroke-width="1"/>')
    for t in _ticks(y0, y1, tk["y"]):
        o.append(f'<line x1="{ML}" y1="{py(t):.1f}" x2="{ML + pw}" y2="{py(t):.1f}" stroke="{GRID}" stroke-width="1"/>')
    o.append(f'<line x1="{ML}" y1="{axis_y:.1f}" x2="{ML + pw}" y2="{axis_y:.1f}" stroke="{INK}" stroke-width="1.4"/>')
    o.append(f'<line x1="{axis_x:.1f}" y1="{MT}" x2="{axis_x:.1f}" y2="{MT + ph}" stroke="{INK}" stroke-width="1.4"/>')
    tl: list[str] = []                                             # tick labels: drawn after the curve, over it
    for pos, val in xticks():
        if abs(val) > 1e-9:
            glyphs = (_pi_label(g, val, px(pos), MT + ph, TICK, INK) if pi
                      else _number(g, val, px(pos), axis_y + 15, TICK, INK, mid=True))
            tl += glyphs or [f'<text x="{px(pos):.1f}" y="{min(axis_y + 14, H - 6):.1f}" font-size="11" '
                            f'text-anchor="middle" fill="{INK}" {HALO}>{_fmt(val)}</text>']
    for t in _ticks(y0, y1, tk["y"]):
        if t != 0:
            tl += _number(g, t, axis_x - 5, py(t) + 4, TICK, INK, end=True) or [
                f'<text x="{axis_x - 5:.1f}" y="{py(t) + 4:.1f}" font-size="11" text-anchor="end" '
                f'fill="{INK}" {HALO}>{_fmt(t)}</text>']
    o.append(_axis_letter(g, "x", ML + pw - 3, axis_y - 6, True) or
             f'<text x="{ML + pw - 2}" y="{axis_y - 5:.1f}" font-size="12" font-style="italic" text-anchor="end" '
             f'fill="{INK}">x</text>')
    o.append(_axis_letter(g, "y", axis_x + 6, MT + 12, False) or
             f'<text x="{axis_x + 6:.1f}" y="{MT + 11}" font-size="12" font-style="italic" fill="{INK}">y</text>')
    for a in spec["asymptotes"]:
        d = (f'M{px(a["value"]):.1f},{MT} V{MT + ph}' if a["axis"] == "x" else f'M{ML},{py(a["value"]):.1f} H{ML + pw}')
        o.append(f'<path d="{d}" stroke="{ASYM}" stroke-width="1.4" stroke-dasharray="6 4" fill="none" '
                 f'clip-path="url(#{clip})"/>')
    for c in spec["curves"]:
        segs, cur = [], []
        for p in c["points"] + [None]:
            if p is None:
                if len(cur) > 1:
                    segs.append("M" + " L".join(f"{px(a):.1f},{py(b):.1f}" for a, b in cur))
                cur = []
            else:
                cur.append(p)
        o.append(f'<path d="{" ".join(segs)}" fill="none" stroke="{CURVE}" stroke-width="{LINE_W}" stroke-linejoin="round" '
                 f'clip-path="url(#{clip})"/>')
        if c.get("label"):
            lx = ML + 8 if axis_x - ML > 110 else axis_x + 28          # clear of the y axis letter when the axis is at the edge
            o.append(g.use(c.get("tex", ""), lx, MT + 17, 17, CURVE) or
                     f'<text x="{lx}" y="{MT + 14}" font-size="13" fill="{CURVE}" '
                     f'font-weight="600">{escape(c["label"])}</text>')
    o += tl
    for p in spec["points"]:
        fill = CURVE if p.get("style", "closed") == "closed" else "#ffffff"      # filled = a point; hollow = a hole
        o.append(f'<circle cx="{px(p["x"]):.1f}" cy="{py(p["y"]):.1f}" r="{MARK_R}" fill="{fill}" stroke="{CURVE}" '
                 f'stroke-width="{MARK_W}"/>')
    o.insert(3, g.defs())
    o.append("</svg>")
    return "\n".join(o)


def _axis_letter(g: _Glyphs, key: str, x: float, y: float, end: bool) -> str | None:
    w = GLYPHS[key]["w"] * 15 if key in GLYPHS else 0
    return g.use(key, x - w if end else x, y, 15, INK)
