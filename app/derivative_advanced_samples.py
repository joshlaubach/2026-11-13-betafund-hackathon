"""Offline source of implicit, logarithmic, inverse-function and higher-order problems (C2 milestone c). Payloads are
tried through app/derivative_advanced.verify like a model reply."""
import random

import sympy as sp

from app import derivative_advanced
from app.safe_parse import safe_parse

X, Y = sp.Symbol("x"), sp.Symbol("y", real=True)


def _curve(lhs, pts, asks):
    """One payload per point and question; the right side (the left side at the point) is filled in when used."""
    return [dict(lhs=lhs, rhs=None, point=f"{x0}, {y0}", ask=ask) for x0, y0 in pts for ask in asks]


def _rhs(lhs, point):
    x0, y0 = (safe_parse(s) for s in point.split(","))
    e = safe_parse(lhs, {"x": X, "y": Y})
    return str(sp.nsimplify(sp.simplify(e.subs({X: x0, Y: y0}))))


def _implicit():
    out = {}
    circ = [(a, b, x0, y0) for a in (1, 2, 3) for b in (1, 2, 3, 4) for x0 in (1, 2, -1, -2) for y0 in (1, 2, 3, -1, -2)]
    out["im_poly"] = [p for a, b, x0, y0 in circ for p in _curve(f"{a}*x^2 + {b}*y^2", [(x0, y0)], ("expression", "point"))]
    out["im_poly"] += [p for k in (2, 3, 4) for p in _curve(f"x^2 - {k}*y^2", [(3, 1), (5, 2), (4, 1)], ("expression", "point"))]
    out["im_product"] = [p for a, b in ((1, 1), (1, 2), (2, 1), (3, 1)) for p in
                         _curve(f"{a}*x^2*y + {b}*x*y^2", [(1, 1), (1, 2), (2, 1), (-1, 2), (2, -1)], ("expression", "point", "tangent"))]
    out["im_product"] += [p for c in (1, 2, 3) for p in _curve(f"x^3 + y^3 - {c}*x*y", [(1, 1), (2, 2), (0, 0)][:2], ("expression", "point", "tangent"))]
    out["im_product"] += [p for k in (1, 2, 3, 4) for p in _curve(f"x*y + {k}*y^2", [(1, 1), (2, 1), (3, 1), (1, 2), (-1, 1)], ("expression", "point", "tangent"))]
    out["im_trans"] = [p for k in (1, 2, 3, 4) for p in _curve(f"x^{n} + {k}*exp(y)" if False else f"{k}*x^2 + exp(y)", [(1, 0), (2, 0), (-1, 0), (1, "ln(2)")],
                                                                ("expression", "point", "tangent")) for n in (2,)]
    out["im_trans"] += [p for k in (1, 2, 3) for p in _curve(f"x^2 + {k}*sin(y)", [(1, "pi/6"), (2, "pi/6"), (0, "pi/3"), (1, "pi/4")],
                                                             ("expression", "point", "tangent"))]
    out["im_trans"] += [p for k in (1, 2, 3) for p in _curve(f"y^3 + {k}*cos(x)", [(0, 1), (0, 2), (0, -1), ("pi/3", 1), ("pi/2", 1)],
                                                             ("expression", "point", "tangent"))]
    out["im_trans"] += [p for k in (1, 2, 3, 4) for p in _curve(f"{k}*x^2 + ln(y)", [(1, 1), (2, 1), (-1, 1), (1, "e")],
                                                                ("expression", "point", "tangent"))]
    out["im_mixed"] = [p for k in (1, 2, 3) for p in _curve(f"x*sin(y) + {k}*y", [(1, "pi/2"), (2, "pi/2"), (0, "pi/2"), (-1, "pi/2")],
                                                            ("point", "tangent"))]
    out["im_mixed"] += [p for k in (1, 2, 3) for p in _curve(f"x*exp(y) + {k}*y", [(1, 0), (2, 0), (-1, 0), (3, 0)], ("point", "tangent"))]
    out["im_mixed"] += [p for k in (1, 2, 3) for p in _curve(f"y*exp(x) + {k}*x^2*y", [(0, 1), (0, 2), (0, 3), (0, -1)], ("point", "tangent"))]
    out["im_mixed"] += [p for k in (1, 2, 3) for p in _curve(f"x^2*cos(y) + {k}*y", [(1, 0), (2, 0), (3, 0), (-1, 0)], ("point", "tangent"))]
    out["im_mixed"] += [p for k in (1, 2, 3) for p in _curve(f"x*y + {k}*ln(y)", [(1, 1), (2, 1), (3, 1), (-1, 1)], ("point", "tangent"))]
    out["im_second"] = [p for p in _curve("x^2 + y^2", [(3, 4), (4, 3), (0, 5), (-3, 4), (5, 12), (6, 8)], ("second",))]
    out["im_second"] += [p for k in (2, 3, 4) for p in _curve(f"x^2 + {k}*y^2", [(1, 1), (2, 1), (1, 2), (-2, 1), (3, 1)], ("second",))]
    out["im_second"] += [p for p in _curve("x*y", [(1, 1), (2, 3), (3, 2), (-1, 4), (2, 1)], ("second",))]
    out["im_second"] += [p for c in (1, 2) for p in _curve(f"x^3 + y^3 - {c}*x*y", [(1, 1), (2, 2)], ("second",))]
    out["im_second"] += [p for p in _curve("x^2*y + y^3", [(1, 1), (1, 2), (2, 1), (-1, 2)], ("second",))]
    out["im_second"] += [p for p in _curve("y^2 - x^3", [(1, 1), (4, 8), (9, 27), (1, -1)], ("second",))]
    return out


def _logarithmic():
    out = {}
    pts = ("x", "1", "2", "0", "3")
    out["lg_product"] = [(f"x^{a}*(x+{b})^{c}*(x-{d})^{e}", at) for a in (2, 3) for b in (1, 2) for c in (2, 3) for d in (1, 3)
                         for e in (2, 4) for at in ("x", "2", "4")]
    out["lg_product"] += [(f"({p})^{a}*(x+{b})^{c}*x^{d}", at) for p in ("x^2+1", "x^2+x+1", "2*x+1") for a in (2, 3)
                          for b in (1, 2) for c in (2, 3) for d in (1, 2) for at in ("x", "0", "1")]
    out["lg_product"] += [(f"x*(x+{b})^{c}*(x+{d})^{e}", at) for b in (1, 2) for c in (2, 3) for d in (3, 4) for e in (2, 3)
                          for at in ("x", "0", "1")]
    out["lg_quotient"] = [(f"x^{a}*(x+{b})^{c}/(x-{d})^{e}", at) for a in (2, 3) for b in (1, 2) for c in (2, 3) for d in (1, 2)
                          for e in (2, 3) for at in ("x", "3", "4")]
    out["lg_quotient"] += [(f"(x^2+1)^{a}*(x+{b})^{c}/sqrt(x+{d})", at) for a in (2, 3) for b in (1, 2) for c in (2, 3)
                           for d in (1, 3, 8) for at in ("x", "0", "1")]
    out["lg_quotient"] += [(f"x^{a}*sqrt(x+{b})/(x^2+1)^{c}", at) for a in (2, 3) for b in (1, 3, 8) for c in (2, 3)
                           for at in ("x", "0", "1")]
    out["lg_variable"] = [(f, at) for f in ("x^x", "x^(2*x)", "x^(1/x)", "x^(sin(x))", "(x^2+1)^x", "x^(x^2)", "(x+1)^x",
                                            "x^(exp(x))", "x^(ln(x))", "(2*x)^x", "(x+2)^(x-1)", "x^(x+1)", "(1+x^2)^(2*x)",
                                            "(x^2)^(x)", "x^(3*x)", "(3*x)^(2*x)")
                          for at in ("x", "1", "2", "e")]
    out["lg_variable"] += [(f, at) for f in ("(sin(x))^x", "(cos(x))^x", "(ln(x))^x", "x^(cos(x))", "(exp(x))^x" if False else
                                              "(atan(x))^x", "(tan(x))^(x)", "(sin(x))^(cos(x))", "x^(atan(x))")
                           for at in ("x", "pi/4", "pi/2", "1")]
    out["lg_mixed"] = [(f"{t}^{a}*(x^2+1)^{b}/{d}", at) for t in ("sin(x)", "cos(x)", "exp(x)") for a in (2, 3) for b in (2, 3)
                       for d in ("x", "x^2", "(x+1)") for at in ("x", "0", "1", "pi/2", "pi/4")]
    out["lg_mixed"] += [(f"x^{a}*exp({k}*x)*sin(x)", at) for a in (2, 3) for k in (1, 2) for at in ("x", "0", "1", "pi/2")]
    out["lg_mixed"] += [(f"x^{a}*sqrt({p})/{t}" , at) for a in (2, 3) for p in ("x^2+1", "x+1", "x^2+3") for t in
                        ("sin(x)", "cos(x)", "exp(x)") for at in ("x", "0", "1")]
    out["lg_mixed"] += [(f"(x^2+1)^{a}*{t}*{s}", at) for a in (2, 3) for t, s in (("sin(x)", "exp(x)"), ("cos(x)", "exp(x)"),
                                                                              ("sin(x)", "cos(x)"), ("ln(x)", "exp(x)"))
                        for at in ("x", "1", "pi/2")]
    return {k: [dict(f=f, at=at) for f, at in v] for k, v in out.items()}


def _inverse():
    poly = [("x^3+x", ("1", "2", "-1", "3", "0")), ("x^3+2*x", ("1", "2", "-1", "0")), ("x^3+3*x+1", ("1", "2", "0")),
            ("x^5+x", ("1", "-1", "2")), ("2*x^3+x", ("1", "2", "-1")), ("x^3+x^2+x", ("1", "2", "-1", "-2")),
            ("x^3+4*x", ("1", "2", "-1")), ("x^5+x^3+x", ("1", "-1")), ("x^3+5*x-2", ("1", "2", "0")),
            ("3*x^3+x", ("1", "2", "-1")), ("x^3+x+5", ("1", "2", "-1")), ("4*x^3+x", ("1", "-1")),
            ("8*x^3+x", ("1/2", "-1/2")), ("x^3+6*x", ("1", "2")), ("x^5+2*x", ("1", "-1")),
            ("2*x^5+x", ("1", "-1")), ("x^3+x^2+2*x", ("1", "2", "-1"))]
    trans = [("x+exp(x)", ("0",)), ("2*x+exp(x)", ("0",)), ("x^3+exp(x)", ("0",)), ("exp(2*x)+x", ("0",)),
             ("x+exp(x)+1", ("0",)), ("3*x+exp(x)", ("0",)), ("x^3+x+exp(x)", ("0",)),
             ("x+ln(x)", ("1",)), ("2*x+ln(x)", ("1",)), ("x^3+ln(x)", ("1",)), ("x^2+ln(x)", ("1",)),
             ("3*x+ln(x)", ("1",)), ("x^3+x+ln(x)", ("1",)), ("sqrt(x)+x", ("1", "4", "9", "16")),
             ("sqrt(x)+x^2", ("1", "4", "9")), ("2*sqrt(x)+x", ("1", "4", "9")), ("sqrt(x)+x^3", ("1", "4")),
             ("x+sqrt(x)+1", ("1", "4", "9", "16")), ("x^2+sqrt(x)", ("1", "4", "9", "16")),
             ("5*x+exp(x)", ("0",)), ("x^3+2*x+exp(x)", ("0",)), ("x+2*exp(x)", ("0",)), ("x^3+exp(x)+1", ("0",)),
             ("4*x+exp(x)", ("0",)), ("x+exp(2*x)", ("0",)), ("x^5+exp(x)", ("0",)), ("x+exp(3*x)", ("0",)),
             ("x+2*ln(x)", ("1",)), ("x^3+2*ln(x)", ("1",)), ("4*x+ln(x)", ("1",)), ("x^2+2*ln(x)", ("1",)),
             ("3*sqrt(x)+x", ("1", "4", "9")), ("sqrt(x)+2*x", ("1", "4", "9")), ("sqrt(x)+x^3+x", ("1", "4")),
             ("3*sqrt(x)+x^2", ("1", "4", "9")), ("sqrt(x)+5*x", ("1", "4", "9", "16"))]
    hard = [("x^3+x", ("-3", "4", "5", "-4")), ("x^3+x^2+x", ("3", "-3", "4")), ("2*x^3+x", ("-2", "3", "4")),
            ("x^5+x", ("-2", "3")), ("x^3+2*x", ("3", "-3", "4")), ("3*x^3+x", ("-2", "3")), ("x^3+x+7", ("3", "-3", "4")),
            ("8*x^3+x", ("3/2", "-3/2")), ("x^3+3*x", ("-3", "4")), ("27*x^3+x", ("1/3", "-1/3", "2/3")),
            ("x^3+x/2" if False else "2*x^3+3*x", ("-2", "3")), ("4*x^3+x", ("-2", "3")), ("x^3+4*x+3", ("-3", "4"))]
    def rows(spec, ask, extra=None):
        dom = lambda f: "positive" if ("ln(x)" in f or "sqrt(x)" in f) else "all"
        return [dict(f=f, a=a, ask=ask, dom=dom(f)) for f, pts in spec for a in pts]
    return {"if_poly": rows(poly, "first"), "if_trans": rows(trans, "first"), "if_hard": rows(hard, "first"),
            "if_second": rows(poly[:10] + trans, "second")}


def _higher():
    out = {}
    out["ho_poly"] = [(f"{a}*x^{n}+{b}*x^{m}+{c}", str(k), at) for a in (1, 2, 3) for b in (1, 4, 5) for c in (2, -3)
                      for n, m in ((5, 3), (6, 2), (4, 2), (7, 3), (5, 2)) for k in (2, 3, 4) for at in ("x", "1", "2")
                      if k <= n]
    out["ho_trans"] = [(f"{c}*{fn}", str(k), at) for c in (1, 2, 3) for fn in
                       ("sin(x)", "cos(x)", "exp(x)", "exp(2*x)", "exp(-x)", "ln(x)", "sqrt(x)", "1/x", "cos(3*x)", "sin(2*x)",
                        "exp(3*x)", "atan(x)", "tan(x)")
                       for k in (2, 3, 4) for at in ("x", "0", "1", "pi/2", "pi/4")]
    out["ho_product"] = [(f"{p}*{t}", str(k), at) for p in ("x", "x^2", "x^3", "x+1", "x^2+1") for t in
                         ("exp(x)", "sin(x)", "cos(x)", "exp(2*x)", "ln(x)", "exp(-x)", "sin(2*x)") for k in (2, 3, 4)
                         for at in ("x", "0", "1", "pi/2")]
    out["ho_pattern"] = [(f"{c}*{fn}", str(k), at) for c in (1, 2, 3) for fn in
                         ("sin(x)", "cos(x)", "exp(x)", "exp(2*x)", "sin(2*x)", "cos(3*x)", "exp(-x)", "ln(x)", "1/x",
                          "1/(x+1)", "1/(1-x)", "sin(3*x)", "exp(3*x)", "1/(2*x+1)", "cos(2*x)")
                         for k in (6, 7, 8, 9, 10) for at in ("x", "0", "1", "pi/2", "pi/4", "pi/8", "pi")]
    return {k: [dict(f=f, n=n, at=at) for f, n, at in v] for k, v in out.items()}


TABLES = {"implicit": _implicit(), "logarithmic": _logarithmic(), "inverse_functions": _inverse(), "higher_order": _higher()}


def generate(stem: str, recipe: dict, axes: dict, answers: set[str], calculator: str = "none", seed: int = 0,
             limit: int = 150) -> dict | None:
    rng = random.Random(seed)
    rows = list(TABLES[stem].get(recipe["id"], []))
    rng.shuffle(rows)
    full = {"recipe": recipe["id"], **axes}
    for payload in rows[:limit]:
        if payload.get("rhs", "") is None:
            payload = {**payload, "rhs": _rhs(payload["lhs"], payload["point"])}
        r = derivative_advanced.verify(stem, axes=full, calculator=calculator, **payload)
        if r["ok"] and r["answer"]["type"] in answers:
            return {"payload": payload, "result": r}
    return None
