"""Offline source of modelling problems that need no story (C3 milestone b, first half). Pools of replies a good model
would give for each recipe; each payload goes through app/applications_b.verify like a model reply, so a pool entry
the verifier rejects is simply never served."""
import itertools
import random

import sympy as sp

from app import applications_b

t = sp.Symbol("t")


def _txt(e):
    return str(sp.expand(e)).replace("**", "^")


def _estimates(fns, steps):
    """(f, a, x1) estimate rows and (f, a, dx) differential rows for functions given as (f, [a, ...])."""
    rows = []
    for f, points in fns:
        for a in points:
            for h in steps:
                x1 = sp.Rational(str(a)) + sp.Rational(str(h))
                rows.append(dict(f=f, a=str(a), x1=str(float(x1)).rstrip("0").rstrip("."), dx="", ask="estimate"))
                rows.append(dict(f=f, a=str(a), x1="", dx=str(h), ask="differential"))
    return rows


def _linear():
    steps = (0.1, 0.2, 0.5, -0.1, -0.2)
    out = {}
    out["la_root"] = _estimates([("sqrt(x)", (4, 9, 16, 25, 36, 49, 64, 81, 100)), ("x^(1/3)", (8, 27, 64, 125)),
                                 ("x^(1/4)", (16, 81)), ("sqrt(1+x)", (0,)), ("(1+x)^(1/3)", (0,)),
                                 ("x^(2/3)", (8, 27)), ("sqrt(x^2+9)", (4,)), ("sqrt(2*x+1)", (4, 12))], steps)
    out["la_rational"] = _estimates([("1/x", (1, 2, 4, 5, 10)), ("1/x^2", (1, 2)), ("x/(x+1)", (1, 2, 3)),
                                     ("1/(1+x)", (0,)), ("1/(x+2)", (2, 3)), ("x^2/(x+1)", (1, 3))], steps)
    out["la_trans"] = _estimates([("exp(x)", (0, 1, 2)), ("ln(x)", (1,)), ("exp(2*x)", (0,)), ("atan(x)", (0,)),
                                  ("x*exp(x)", (1, 0)), ("exp(-x)", (0,)), ("ln(1+x)", (0,)), ("tan(x)", (0,)),
                                  ("exp(3*x)", (0,)), ("exp(-2*x)", (0,)), ("atan(2*x)", (0,)), ("ln(1+2*x)", (0,)),
                                  ("sin(2*x)", (0,)), ("tan(2*x)", (0,)), ("exp(x/2)", (0,)), ("x*ln(x)", (1,))], steps)
    return out


def _lhopital():
    out = {"lh_quot0": [], "lh_quotinf": [], "lh_product": [], "lh_power": []}
    z = out["lh_quot0"]
    for k, m in itertools.product((1, 2, 3, 4), (1, 2, 3)):
        z += [dict(f=f"sin({k}*x)/({m}*x)", a="0", side=""), dict(f=f"(exp({k}*x)-1)/({m}*x)", a="0", side=""),
              dict(f=f"tan({k}*x)/({m}*x)", a="0", side=""), dict(f=f"(1-cos({k}*x))/({m}*x^2)", a="0", side=""),
              dict(f=f"({k}*x-sin({k}*x))/({m}*x^3)", a="0", side="")]
    z += [dict(f="ln(1+x)/x", a="0", side=""), dict(f="(exp(x)-1-x)/x^2", a="0", side=""), dict(f="(x-sin(x))/x^3", a="0", side=""),
          dict(f="(exp(x)-exp(-x))/(2*x)", a="0", side=""), dict(f="(exp(x)-1-x-x^2/2)/x^3", a="0", side=""),
          dict(f="(sin(x)-x)/x^3", a="0", side=""), dict(f="(1-cos(x))/x^2", a="0", side=""),
          dict(f="(exp(x)-cos(x))/x", a="0", side=""), dict(f="ln(x)/(x-1)", a="1", side=""),
          dict(f="(x^2-9)/(x-3)", a="3", side=""), dict(f="(x^2+x-6)/(x^2-4)", a="2", side=""),
          dict(f="(sqrt(x)-2)/(x-4)", a="4", side=""), dict(f="(x^3-8)/(x-2)", a="2", side="")]
    z = out["lh_quotinf"]
    for k in (1, 2, 3):
        z += [dict(f=f"x^{k}/exp(x)", a="oo", side=""), dict(f=f"ln(x)/x^{k}", a="oo", side=""),
              dict(f=f"(ln(x))^{k}/x", a="oo", side="")]
    z += [dict(f="ln(x)/sqrt(x)", a="oo", side=""), dict(f="(3*x^2+2)/(5*x^2-1)", a="oo", side=""),
          dict(f="(x^2+1)/(2*x^2)", a="oo", side=""), dict(f="(2*x+ln(x))/x", a="oo", side=""),
          dict(f="x/exp(2*x)", a="oo", side=""), dict(f="(2*x^2+x)/(x^2+3)", a="oo", side=""),
          dict(f="ln(2*x)/ln(3*x)", a="oo", side=""), dict(f="(x^3+1)/(4*x^3)", a="oo", side="")]
    z = out["lh_product"]
    for k in (1, 2, 3):
        z += [dict(f=f"x^{k}*ln(x)", a="0", side="+"), dict(f=f"x^{k}*exp(-x)", a="oo", side=""),
              dict(f=f"x^{k}*exp(-{k}*x)", a="oo", side="")]
    z += [dict(f="sqrt(x)*ln(x)", a="0", side="+"), dict(f="x*sin(1/x)", a="oo", side=""),
          dict(f="x*ln(1+1/x)", a="oo", side=""), dict(f="(x-1)*ln(x-1)", a="1", side="+"),
          dict(f="x*(exp(1/x)-1)", a="oo", side=""), dict(f="x^2*sin(1/x^2)", a="oo", side="")]
    z = out["lh_power"]
    for k in (1, 2, 3, 4, 5):
        z += [dict(f=f"(1+{k}/x)^x", a="oo", side=""), dict(f=f"(1+{k}*x)^(1/x)", a="0", side="+")]
    z += [dict(f="x^x", a="0", side="+"), dict(f="x^(1/x)", a="oo", side=""), dict(f="x^(sin(x))", a="0", side="+"),
          dict(f="(cos(x))^(1/x^2)", a="0", side=""), dict(f="(1+x)^(1/x)", a="0", side="+"),
          dict(f="(1-x)^(1/x)", a="0", side="+"), dict(f="(sin(x)/x)^(1/x^2)", a="0", side=""),
          dict(f="x^(2*x)", a="0", side="+"), dict(f="(x+exp(x))^(1/x)", a="0", side="+")]
    for k in (6, 7, 8, 9):
        z += [dict(f=f"(1+{k}/x)^x", a="oo", side=""), dict(f=f"(1+{k}*x)^(1/x)", a="0", side="+")]
    for k in (1, 2, 3, 4):
        z += [dict(f=f"x^({k}*x)", a="0", side="+"), dict(f=f"x^({k}/ln(x))", a="oo", side=""),
              dict(f=f"(cos({k}*x))^(1/x^2)", a="0", side=""), dict(f=f"(1+{k}*x^2)^(1/x^2)", a="0", side="")]
    for k in (2, 3):
        z += [dict(f=f"(1+x^2)^({k}/x^2)", a="0", side=""), dict(f=f"(cos(x))^({k}/x^2)", a="0", side="")]
    z = out["lh_product"]
    for k, m in itertools.product((1, 2, 3), (1, 2, 3)):
        z += [dict(f=f"x^{k}*exp(-{m}*x)", a="oo", side="")]
    for m in (1, 2, 3, 4):
        z += [dict(f=f"x*sin({m}/x)", a="oo", side=""), dict(f=f"x*ln(1+{m}/x)", a="oo", side=""),
              dict(f=f"x*(exp({m}/x)-1)", a="oo", side=""), dict(f=f"x^2*(exp({m}/x^2)-1)", a="oo", side=""),
              dict(f=f"x^{m}*ln(x)", a="0", side="+")]
    z += [dict(f="(x-2)*ln(x-2)", a="2", side="+"), dict(f="x*ln(x)^2", a="0", side="+"), dict(f="x^(1/2)*ln(x)", a="0", side="+")]
    z = out["lh_quotinf"]
    for k, m in itertools.product((1, 2, 3, 4), (1, 2, 3)):
        z += [dict(f=f"({k}*x^2+x)/({m}*x^2+1)", a="oo", side=""), dict(f=f"ln({k}*x)/ln({m + 1}*x)", a="oo", side=""),
              dict(f=f"({k}*x+ln(x))/({m}*x)", a="oo", side="")]
    return out


def _newton():
    out = {"nm_quad": [], "nm_cubic": [], "nm_rational": []}
    for c, x0, n in itertools.product((2, 3, 5, 6, 7, 10, 11), (1, 2, 3, 4), (1, 2, 3)):
        out["nm_quad"].append(dict(f=f"x^2-{c}", x0=str(x0), n=str(n)))
    for a, c, x0, n in itertools.product((1, 2, 3), (1, 2, 5, 7), (1, 2, 3), (1, 2)):
        out["nm_quad"].append(dict(f=f"{a}*x^2-{c}*x-1", x0=str(x0), n=str(n)))
    for c, x0, n in itertools.product((2, 3, 4, 5, 6, 7, 9, 10), (1, 2, 3), (1, 2)):
        out["nm_cubic"].append(dict(f=f"x^3-{c}", x0=str(x0), n=str(n)))
    for b, c, x0, n in itertools.product((1, 2, 3, 4), (1, 2, 3, 5), (1, 2), (1, 2)):
        out["nm_cubic"].append(dict(f=f"x^3-{b}*x-{c}", x0=str(x0), n=str(n)))
        out["nm_cubic"].append(dict(f=f"x^3+{b}*x-{c}", x0=str(x0), n=str(n)))
    for c, x0, n in itertools.product((2, 3, 4, 5), ("0.2", "0.3", "0.4", "0.5", "1"), (1, 2)):
        out["nm_rational"].append(dict(f=f"1/x-{c}", x0=str(x0), n=str(n)))
    for c, x0, n in itertools.product((1, 2, 3), (1, 2, 3), (1, 2)):
        out["nm_rational"].append(dict(f=f"x-{c}/x", x0=str(x0), n=str(n)))
        out["nm_rational"].append(dict(f=f"x^2-{c}/x-1", x0=str(x0), n=str(n)))
    return out


def _motion():
    out = {"mo_poly": [], "mo_interval": [], "mo_trig": []}
    cubics = []
    for a, b in itertools.combinations(range(1, 6), 2):
        for k in (1, 2):
            cubics.append(_txt(k * (2 * t ** 3 - 3 * (a + b) * t ** 2 + 6 * a * b * t)))
    cubics += ["t^3-6*t^2+9*t", "t^3-9*t^2+24*t", "t^3-12*t", "2*t^3-9*t^2+12*t", "t^4-4*t^3", "t^3-3*t^2-9*t+5"]
    quads = [f"{k}*t^2-{m}*t+{c}" for k in (1, 2, 3, 4) for m in (4, 8, 12) for c in (0, 1, 5)]
    for s in cubics + quads:
        for at in range(0, 6):
            for ask in ("velocity", "acceleration", "speed"):
                out["mo_poly"].append(dict(s=s, at=str(at), a="", b="", ask=ask))
    for s in cubics:
        for lo, hi in ((0, 4), (0, 5), (0, 6), (1, 5), (0, 3), (2, 6)):
            for ask in ("displacement", "total_distance", "at_rest"):
                out["mo_interval"].append(dict(s=s, at="", a=str(lo), b=str(hi), ask=ask))
    trigs = ["sin(t)", "cos(t)", "2*sin(t)", "3*cos(t)", "t-2*sin(t)", "t+2*cos(t)", "2*t-4*sin(t)", "sin(t)+cos(t)",
             "t*cos(t)", "sin(2*t)", "cos(2*t)", "t-sin(t)"]
    for s in trigs:
        for at in ("0", "pi/6", "pi/4", "pi/3", "pi/2", "pi", "3*pi/2", "2*pi"):
            for ask in ("velocity", "acceleration", "speed"):
                out["mo_trig"].append(dict(s=s, at=at, a="", b="", ask=ask))
        for lo, hi in (("0", "2*pi"), ("0", "pi"), ("0", "4*pi"), ("pi/2", "2*pi")):
            for ask in ("displacement", "total_distance", "at_rest"):
                out["mo_trig"].append(dict(s=s, at="", a=lo, b=hi, ask=ask))
    return out


def _marginal():
    out = {"ma_cost": [], "ma_profit": [], "ma_opt": []}
    costs = [f"{k}*q^3-{m}*q^2+{c}*q+{f}" for k in (1, 2) for m in (3, 6, 9) for c in (12, 15, 20, 30) for f in (10, 50, 100)]
    costs += [f"{a}*q^2+{b}*q+{f}" for a in (1, 2, 3, 5) for b in (4, 10, 20) for f in (50, 100, 200)]
    for C in costs:
        for q0 in (1, 2, 3, 5, 10, 20):
            for ask in ("marginal_cost", "next_unit"):
                out["ma_cost"].append(dict(C=C, p="", q0=str(q0), ask=ask))
    quad = [f"{a}*q^2+{b}*q+{f}" for a in (1, 2, 3, 5) for b in (4, 10, 20) for f in (50, 100, 200)]
    prices = [f"{d}-{e}*q" for d in (60, 80, 90, 120, 200) for e in (1, 2, 3, 4)]
    for C in quad + costs[:60]:
        for p in prices:
            for q0 in (2, 5, 10, 15):
                out["ma_profit"].append(dict(C=C, p=p, q0=str(q0), ask="marginal_profit"))
            out["ma_opt"].append(dict(C=C, p=p, q0="", ask="max_profit"))
    for a in (1, 2, 3, 5):
        for c in (25, 36, 49, 64, 100, 144, 225, 400):
            for b in (0, 4, 10):
                out["ma_opt"].append(dict(C=f"{a}*q^2+{b}*q+{a * c}", p="", q0="", ask="min_average_cost"))
    return out


TABLES = {"linear_approximation": _linear(), "lhopital": _lhopital(), "newtons_method": _newton(),
          "motion": _motion(), "marginal_analysis": _marginal()}


def generate(stem: str, recipe: dict, axes: dict, answers: set[str], calculator: str = "none", seed: int = 0,
             limit: int = 150) -> dict | None:
    rng = random.Random(seed)
    rows = list(TABLES[stem].get(recipe["id"], []))
    rng.shuffle(rows)
    full = {"recipe": recipe["id"], **axes}
    for payload in rows[:limit]:
        r = applications_b.verify(stem, axes=full, calculator=calculator, **payload)
        if r["ok"] and r["answer"]["type"] in answers:
            return {"payload": payload, "result": r}
    return None
