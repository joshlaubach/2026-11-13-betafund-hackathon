"""Offline source of shape-of-a-graph problems (C3 milestone a). Functions come from small generated pools; each
payload goes through app/applications.verify like a model reply."""
import itertools
import random

import sympy as sp

from app import applications

x = sp.Symbol("x")


def _poly(roots, k=1, c=0):
    """k * integral of prod(x - r) plus c, as a plain string (cubic for two roots, quartic for three)."""
    f = sp.integrate(sp.Mul(*[(x - r) for r in roots]) * k, x) + c
    return str(sp.expand(f)).replace("**", "^")


def _cubics():
    out = []
    for r1, r2 in itertools.combinations(range(-3, 5), 2):
        for k in (3, 6):
            for c in (0, 2, -5):
                out.append(_poly([r1, r2], k, c))
    return out


def _quartics():
    out = []
    for rs in itertools.combinations(range(-3, 4), 3):
        for k in (4, 12):
            out.append(_poly(list(rs), k, 1))
    out += [f"x^4-{2 * a}*x^2" for a in (1, 2, 3, 4, 8)] + [f"x^4-{a}*x^3" for a in (4, 8, 12, 16)]
    out += [f"x^4+{a}*x^3" for a in (4, 8)] + [f"{a}*x^5-{b}*x^3" for a in (3, 6) for b in (5, 10)]
    out += [f"x^4-{a}*x^2+{b}" for a in (2, 8, 18) for b in (1, 3)] + [f"x^5-{a}*x^4" for a in (5, 10)]
    return out


def _flat():
    out = [_poly([r1, r1, r2], k, 1) for r1 in range(-2, 4) for r2 in range(-3, 5) if r1 != r2 for k in (3, 6, -3, -6)]
    out += [_poly([r, r, r], k, 0) for r in (-1, 0, 1, 2) for k in (4, 12, -4, -12)]
    return out


def _inflection_flat():
    out = []
    for r1 in range(-2, 3):
        for r2 in range(-3, 4):
            if r1 != r2:
                f = sp.integrate(sp.integrate(12 * (x - r1) ** 2 * (x - r2), x), x)
                out.append(str(sp.expand(f)).replace("**", "^"))
    out += [f"(x-{r})^4+{c}*x" for r in (0, 1, 2) for c in (1, 2, 3)] + [f"x^4+{a}*x" for a in (1, 2, 3, 4)]
    out += [f"x^6-{a}*x^4" for a in (3, 5, 6)]
    return out


CUBICS, QUARTICS, FLAT, IFLAT = _cubics(), _quartics(), _flat(), _inflection_flat()
RATIONAL = ([f"x/(x^2+{a})" for a in (1, 4, 9, 16)] + [f"x^2/(x-{b})" for b in (1, 2, 3, 4)]
            + [f"(x^2+{a})/x" for a in (1, 4, 9)] + [f"x^2/(x^2+{a})" for a in (1, 4)]
            + [f"(x^2-{a})/(x^2+{b})" for a in (1, 4) for b in (1, 2, 4)] + [f"x/(x-{b})^2" for b in (1, 2, 3)]
            + [f"(x+{a})/(x^2+{b})" for a in (1, 2) for b in (3, 8)] + [f"x^3/(x^2-{a})" for a in (1, 4)]
            + [f"{a}*x/(x^2+{b})" for a in (2, 3) for b in (1, 4)] + [f"(x^2-{a}*x)/(x+1)" for a in (1, 3)]
            + [f"(x-{a})^2/(x+1)" for a in (1, 2)] + [f"x^2/(x+{b})" for b in (1, 2, 3)])
ROOTS = ([f"x^(2/3)*(x-{b})" for b in (1, 2, 3, 4, 5, 6, 8, 10, 12)] + [f"x^(2/3)*(x+{b})" for b in (1, 2, 3, 5)]
         + [f"x^(1/3)*(x-{b})" for b in (1, 2, 4, 8)] + [f"{a}*x^(2/3)-x" for a in (2, 3, 5)]
         + [f"x^(4/3)-{a}*x^(1/3)" for a in (2, 3, 5)] + [f"(x+1)^(2/3)*(x-{b})" for b in (1, 2, 3)]
         + [f"x^(2/3)*(x^2-{b})" for b in (1, 4)] + [f"x^(5/3)-{a}*x^(2/3)" for a in (2, 3, 4)] + [f"x^(2/3)*({b}-x)" for b in (1, 5)]
         + [f"x^(1/3)*(x+{b})" for b in (2, 4, 8)] + [f"(x-1)^(2/3)*(x+{b})" for b in (1, 4)]
         + [f"x^(4/3)-{a}*x^(1/3)" for a in (1, 4)] + [f"x*(x-{b})^(2/3)" for b in (1, 2, 3)]
         + [f"x^(5/3)-{a}*x^(2/3)" for a in (1, 5, 10)] + [f"(x^2-{a})^(1/3)" for a in (1, 4)])
TRIG = [(f, iv) for f in ("2*sin(x)+x", "x+2*cos(x)", "x-2*sin(x)", "x-2*cos(x)", "3*x+6*sin(x)", "x/2+sin(x)", "x/2-sin(x)",
                          "2*x-4*cos(x)", "sin(x)+cos(x)", "sin(x)-cos(x)", "sin(x)^2", "cos(x)^2", "sin(2*x)", "cos(2*x)+x",
                          "sin(x)*cos(x)", "2*sin(x)-sin(2*x)")
        for iv in ("0, 2*pi", "0, pi", "-pi, pi")]
TRANS = ([f"x*exp(-{k}*x)" if k != 1 else "x*exp(-x)" for k in (1, 2, 3)] + [f"x^2*exp(-{k}*x)" if k != 1 else "x^2*exp(-x)" for k in (1, 2)]
         + [f"exp(x)*(x-{a})" for a in (1, 2, 3)] + ["ln(x)/x", "x*ln(x)", "x^2*ln(x)", "x-ln(x)", "x^2-ln(x)", "ln(x)-x/2",
                                                     "x*exp(x)", "exp(x)-x", "exp(x)-2*x", "exp(-x^2)", "x*exp(-x^2/2)",
                                                     "exp(x)/x", "x^2*exp(x)", "exp(2*x)-4*x", "exp(x)-3*x",
                                                     "x/exp(x)", "atan(x)-x/2", "x-atan(x)", "ln(x^2+1)-x", "x*ln(x)-x",
                                                     "ln(x)/x^2", "x^2/exp(x)", "exp(-x)*(x^2-1)"])


def _critical():
    out = {}
    out["cn_poly"] = [dict(f=f, interval="") for f in CUBICS[:80] + QUARTICS[:60]]
    out["cn_rational"] = [dict(f=f, interval="") for f in RATIONAL]
    out["cn_root"] = [dict(f=f, interval="") for f in ROOTS]
    out["cn_trig"] = [dict(f=f, interval=iv) for f, iv in TRIG]
    return out


def _intervals(fs, spans):
    return [(f, a, b) for f in fs for a, b in spans]


def _absolute():
    out = {}
    cub = CUBICS
    out["ae_poly"] = [dict(f=f, a=str(a), b=str(b), ask=ask) for f in cub[::2] for a, b in ((-2, 3), (-1, 4), (0, 3), (-3, 2))
                      for ask in ("max", "min", "both")]
    out["ae_trans"] = [dict(f=f, a=str(a), b=str(b), ask=ask) for f in TRANS for a, b in ((1, 4), (0, 3), (1, 3), (0, 2), (1, 5))
                       for ask in ("max", "min", "both")]
    out["ae_trans"] += [dict(f=f, a=a, b=b, ask=ask) for f in ("sin(x)+cos(x)", "x+2*cos(x)", "2*sin(x)+x", "sin(x)*cos(x)",
                                                              "x-2*sin(x)", "cos(x)+x/2", "sin(2*x)+x", "2*cos(x)+x")
                        for a, b in (("0", "pi"), ("0", "2*pi"), ("0", "pi/2"), ("-pi", "pi")) for ask in ("max", "min", "both")]
    out["ae_trans"] += [dict(f=f, a=str(a), b=str(b), ask=ask) for f in RATIONAL + ROOTS
                        for a, b in ((0, 3), (1, 4), (-1, 3), (0, 5)) for ask in ("max", "min", "both")]
    return out


def _graph(asks):
    """Graph-view replies (app/graph_problems.py): two or three roots on half-integers, each of multiplicity 1 except
    at most one double root, and a leading coefficient. The verifier rejects the ones that would not read well."""
    roots = ["-3", "-2", "-3/2", "-1", "0", "1", "3/2", "2", "3"]
    out = []
    for n in (2, 3):
        for rs in itertools.combinations(roots, n):
            for ms in [(1,) * n] + [tuple(2 if i == j else 1 for i in range(n)) for j in range(n)]:
                for lead in ("1/2", "-1/2", "1", "-1", "1/4"):
                    for ask in asks:
                        out.append(dict(f="", ask=ask, view="graph", roots=",".join(rs), mults=",".join(map(str, ms)),
                                        lead=lead))
    return out


def _trig(asks, lifts):
    """Trigonometric graph-view replies: a sine or cosine, an amplitude, a frequency, a lift and a window in multiples
    of pi. The verifier rejects the ones whose features miss a tick or sit on the window's edge."""
    out = []
    for fn in ("sin", "cos"):
        for amp in ("1", "2", "-1", "-2", "3", "1/2"):
            for freq in ("1", "2", "1/2"):
                for window in ("-1,2", "0,2", "-2,2", "-1,1", "0,4", "-2,0", "-1/2,3/2", "1/2,5/2"):
                    for lift in lifts:
                        for ask in asks:
                            out.append(dict(f="", ask=ask, view="trig", trig=fn, amp=amp, freq=freq, lift=lift, window=window))
    return out


def _increasing():
    out = {}
    out["id_graph"] = _graph(("increasing", "decreasing"))
    out["id_trig"] = _trig(("increasing", "decreasing"), ("0",))
    out["id_poly"] = [dict(f=f, ask=ask) for f in CUBICS + QUARTICS for ask in ("increasing", "decreasing")]
    out["id_rational"] = [dict(f=f, ask=ask) for f in RATIONAL for ask in ("increasing", "decreasing")]
    out["id_trans"] = [dict(f=f, ask=ask) for f in TRANS + ROOTS for ask in ("increasing", "decreasing")]
    return out


def _relative():
    out = {}
    out["re_graph"] = _graph(("maxima", "minima", "both"))
    out["re_trig"] = _trig(("maxima", "minima", "both"), ("0", "1", "-1", "2"))
    out["re_poly"] = [dict(f=f, ask=ask) for f in CUBICS for ask in ("maxima", "minima", "both")]
    out["re_flat"] = [dict(f=f, ask=ask) for f in FLAT + QUARTICS for ask in ("maxima", "minima", "both")]
    out["re_rational"] = [dict(f=f, ask=ask) for f in RATIONAL for ask in ("maxima", "minima", "both")]
    out["re_trans"] = [dict(f=f, ask=ask) for f in TRANS + ROOTS for ask in ("maxima", "minima", "both")]
    return out


def _rolle():
    out = {}
    base = ([f"x^2-{k}*x" for k in (2, 4, 6, 8)] + [f"x^3-{k}*x" for k in (1, 4, 9, 16)] + [f"x^3-{k}*x^2" for k in (3, 6)]
            + [f"x^4-{k}*x^2" for k in (2, 8, 18)] + [f"{c}*x^2-{c * k}*x+1" for c in (1, 2, 3) for k in (2, 4, 6)]
            + [f"x^3-3*x^2+{c}" for c in (0, 1)] + ["x^3-6*x^2+9*x", "x^3-6*x^2+9*x+1", "x^3-12*x", "2*x^3-3*x^2",
                                                    "x^4-4*x^3", "x^4-8*x^2+1"])
    rows = []
    for f in base:
        fx = sp.sympify(f.replace("^", "**"), locals={"x": x})
        pairs = [(a, b) for a in range(-6, 8) for b in range(a + 1, 9) if fx.subs(x, a) == fx.subs(x, b)]
        rows += [dict(f=f, a=str(a), b=str(b), ask="rolle") for a, b in pairs[:5]]
    out["rm_rolle"] = rows
    out["rm_mvt_poly"] = [dict(f=f, a=str(a), b=str(b), ask="mvt") for f in
                          [f"x^2+{k}*x" for k in (1, 2, 3)] + [f"x^3+{k}*x" for k in (1, 2, 3)] + ["x^3", "x^3-x^2", "2*x^3-x",
                                                                                                   "x^4", "x^3-3*x", "x^4+x"]
                          for a, b in ((0, 2), (0, 3), (1, 3), (-1, 2), (0, 1), (1, 2), (0, 4), (-2, 1), (-1, 3))]
    out["rm_mvt_trans"] = [dict(f=f, a=a, b=b, ask="mvt") for f, ivs in
                           (("sqrt(x)", (("1", "4"), ("0", "4"), ("1", "9"), ("0", "9"), ("4", "9"))),
                            ("1/x", (("1", "4"), ("1", "9"), ("1", "16"), ("1", "2"), ("4", "9"))),
                            ("exp(x)", (("0", "ln(4)"), ("0", "ln(2)"), ("0", "ln(9)"))),
                            ("ln(x)", (("1", "e"), ("1", "e^2"))), ("x^(2/3)", (("0", "8"), ("1", "8"), ("0", "27"))),
                            ("x+1/x", (("1", "4"), ("1", "9"), ("1", "2"))), ("sqrt(x+1)", (("0", "3"), ("0", "8"), ("3", "8"))),
                            ("x^2+sqrt(x)", (("0", "4"), ("1", "4"))), ("sin(x)", (("0", "pi"), ("0", "pi/2"))),
                            ("cos(x)", (("0", "pi/2"), ("0", "pi"))), ("x^(3/2)", (("0", "4"), ("1", "4"), ("0", "9"))))
                           for a, b in ivs]
    out["rm_applies"] = [dict(f=f, a=a, b=b, ask="applies") for f, ivs in
                         (("x^(2/3)", (("-1", "1"), ("-8", "8"), ("-1", "1"))), ("x^(2/3)-1", (("-1", "1"), ("-8", "8"))),
                          ("1/x^2", (("-1", "1"), ("-2", "2"))), ("x^2-1", (("-1", "1"), ("0", "2"), ("-2", "2"), ("-1", "2"))),
                          ("x^3-x", (("-1", "1"), ("0", "1"), ("-1", "0"), ("-2", "2"), ("0", "2"))),
                          ("1/(x-1)", (("0", "2"), ("-1", "3"))), ("x^2", (("-1", "1"), ("0", "1"), ("1", "2"))),
                          ("(x-1)^(2/3)", (("0", "2"), ("-7", "9"))), ("x^4-2*x^2", (("-2", "2"), ("0", "2"), ("-1", "1"))),
                          ("sin(x)", (("0", "pi"), ("0", "2*pi"), ("-pi", "pi"))), ("cos(x)", (("0", "2*pi"), ("-pi", "pi"))),
                          ("x/(x^2-1)", (("-2", "2"), ("0", "2"))), ("1/(x^2+1)", (("-1", "1"), ("-2", "2"))),
                          ("x^(1/3)", (("-1", "1"), ("-8", "8"))), ("x^3", (("-1", "1"),)),
                          ("x^2-4*x", (("0", "4"), ("1", "3"), ("0", "2"))), ("sqrt(x)-x", (("0", "1"), ("0", "4"))))
                         for a, b in ivs]
    return out


def _concavity():
    out = {}
    asks = ("up", "down", "inflection")
    out["cc_poly"] = [dict(f=f, ask=ask) for f in CUBICS for ask in asks]
    out["cc_trap"] = [dict(f=f, ask=ask) for f in IFLAT + QUARTICS for ask in asks]
    out["cc_rational"] = [dict(f=f, ask=ask) for f in RATIONAL for ask in asks]
    out["cc_trans"] = [dict(f=f, ask=ask) for f in TRANS + ROOTS for ask in asks]
    return out


def _sketch():
    out = {}
    out["cs_poly"] = [dict(f=f) for f in CUBICS[::3] + QUARTICS[::2]]
    out["cs_rational"] = [dict(f=f) for f in RATIONAL + [f"x^2/(x^2-{a})" for a in (1, 4, 9)]
                          + [f"(x^2-{a})/(x^2-{b})" for a in (1, 4) for b in (9, 16)] + [f"{a}*x/(x^2-{b})" for a in (1, 2) for b in (1, 4)]
                          + [f"x^2/(x-{b})^2" for b in (1, 2)] + [f"(x^2+{a})/(x^2-{b})" for a in (1, 2) for b in (1, 4)]
                          + [f"x/(x^2-{b})" for b in (1, 4, 9)] + [f"1/(x^2-{b})" for b in (1, 4)] + [f"x^2/(x^2-{b}*x)" for b in (2, 3)]]
    return out


TABLES = {"critical_numbers": _critical(), "absolute_extrema": _absolute(), "increasing_decreasing": _increasing(),
          "relative_extrema": _relative(), "rolle_mvt": _rolle(), "concavity_inflection": _concavity(),
          "curve_sketching": _sketch()}


def generate(stem: str, recipe: dict, axes: dict, answers: set[str], calculator: str = "none", seed: int = 0,
             limit: int = 150) -> dict | None:
    rng = random.Random(seed)
    rows = list(TABLES[stem].get(recipe["id"], []))
    rng.shuffle(rows)
    full = {"recipe": recipe["id"], **axes}
    for payload in rows[:limit]:
        r = applications.verify(stem, axes=full, calculator=calculator, **payload)
        if r["ok"] and r["answer"]["type"] in answers:
            return {"payload": payload, "result": r}
    return None
