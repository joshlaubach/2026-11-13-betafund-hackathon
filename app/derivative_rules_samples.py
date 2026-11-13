"""Offline source of combining-rule problems (C2 milestone b). Factors are drawn from small pools per family, then
combined; each payload goes through app/derivative_rules.verify like a model reply."""
import itertools
import random

from app import derivative_rules

R = range

POLY = ["x+1", "x-2", "x^2+1", "x^2-3", "2*x+3", "3*x-1", "x^2+x", "x^3", "x^2", "x^2-2*x+1", "4*x-5", "x^3-x"]
TRANS = ["sin(x)", "cos(x)", "exp(x)", "ln(x)", "atan(x)", "tan(x)", "sinh(x)", "cosh(x)", "2^x", "sec(x)", "asin(x)",
         "exp(2*x)", "sin(2*x)", "cos(3*x)"]
PTS_P = ("x", "0", "1", "2", "-1")
PTS_T = ("x", "0", "1", "pi/2", "pi", "pi/4")


def _at(f, extra=()):
    """Points to try for f: transcendental points when it has a trig function, plain ones otherwise."""
    return PTS_T if any(k in f for k in ("sin", "cos", "tan", "sec")) else PTS_P


def _product():
    out = {}
    out["pd_poly"] = [(f"({a})*({b})", at) for a, b in itertools.permutations(POLY, 2) for at in ("x", "1", "2")
                      if a < b][:240]
    out["pd_poly"] += [(f"{c}*x^{n}*({b})", at) for c in (1, 2, 3) for n in (2, 3, 4) for b in POLY[:8]
                       for at in ("x", "1")]
    out["pd_trans"] = [(f"({a})*{t}", at) for a in POLY[:8] + ["x"] for t in TRANS[:9] for at in _at(t)]
    out["pd_trans"] += [(f"x^{n}*{t}", at) for n in (2, 3) for t in TRANS for at in _at(t)]
    out["pd_trans"] += [(f"sqrt(x)*{t}", at) for t in TRANS[:8] for at in ("x", "1", "4")]
    out["pd_trans2"] = [(f"{a}*{b}", at) for a, b in itertools.combinations(TRANS, 2) for at in _at(a + b)]
    out["pd_three"] = [(f"x*{a}*{b}", at) for a, b in itertools.combinations(TRANS[:9], 2) for at in _at(a + b)]
    out["pd_three"] += [(f"({p})*{a}*{b}", at) for p in ("x^2", "x+1", "x^2+1") for a, b in itertools.combinations(TRANS[:7], 2)
                        for at in ("x", "0", "1")]
    return {k: [dict(f=f, at=at) for f, at in v] for k, v in out.items()}


def _quotient():
    out = {}
    out["qr_poly"] = [(f"({a})/({b})", at) for a in POLY[:10] + ["1", "x"] for b in POLY[:10] if a != b for at in ("x", "0", "1", "2")][:300]
    out["qr_trans"] = [(f"{t}/({p})", at) for t in TRANS[:9] for p in POLY[:8] + ["x"] for at in _at(t)]
    out["qr_trans"] += [(f"({p})/{t}", at) for t in TRANS[:9] for p in POLY[:8] + ["x"] for at in _at(t)]
    out["qr_trans2"] = [(f"{a}/{b}", at) for a, b in itertools.permutations(TRANS[:10], 2) for at in _at(a + b)]
    out["qr_prod"] = [(f"({p})*{t}/({q})", at) for p in ("x", "x^2", "x+1") for t in TRANS[:6] for q in POLY[:6]
                      for at in _at(t)]
    out["qr_prod"] += [(f"{t}/(({p})*{s})", at) for t in TRANS[:5] for p in ("x", "x+1") for s in TRANS[:5] if s != t
                       for at in _at(t + s)]
    return {k: [dict(f=f, at=at) for f, at in v] for k, v in out.items()}


def _chain():
    out = {}
    out["cr_linear"] = [(f"({a}*x+{b})^{n}", at) for a in (2, 3, 4, 5) for b in (1, 3, -2) for n in (3, 4, 5, 6)
                        for at in ("x", "0", "1")]
    out["cr_linear"] += [(f"{c}*{fn}({a}*x)", at) for c in (1, 2, 3) for fn in ("sin", "cos", "exp", "tan", "sinh")
                         for a in (2, 3, 5) for at in _at(fn)]
    out["cr_poly"] = [(f"({a}*x^2+{b})^{n}", at) for a in (1, 2, 3) for b in (1, 2, -1) for n in (3, 4, 5) for at in ("x", "0", "1")]
    out["cr_poly"] += [(f"sqrt({a}*x^2+{b})", at) for a in (1, 2, 3) for b in (1, 3, 5) for at in ("x", "1", "2")]
    out["cr_poly"] += [(f"({a}*x^3-{b}*x)^{n}", at) for a in (1, 2) for b in (1, 3) for n in (3, 4) for at in ("x", "1")]
    out["cr_poly"] += [(f"1/({a}*x^2+{b})^{n}" if False else f"({a}*x^2+{b})^(-{n})", at) for a in (1, 2) for b in (1, 3)
                       for n in (1, 2, 3) for at in ("x", "0", "1")]
    out["cr_fn"] = [(f"{c}*{fn}({p})", at) for c in (1, 2, 3) for fn in ("sin", "cos", "exp", "ln", "atan", "tan")
                    for p in ("x^2", "x^2+1", "3*x^2", "x^3", "x^2-x") for at in _at(fn) + ("1",)]
    out["cr_fn"] += [(f"sqrt({fn}({a}*x))" if False else f"({fn}(x))^{n}", at) for fn in ("sin", "cos", "tan", "exp", "ln")
                     for n in (2, 3, 4) for at in _at(fn)]
    out["cr_two"] = [(f"{o}({i})", at) for o in ("sin", "cos", "exp", "ln", "atan") for i in ("exp(x)", "sin(x)", "cos(x)", "ln(x)",
                                                                                          "atan(x)", "sqrt(x)")
                     if not (o == "ln" and i in ("sin(x)", "cos(x)", "ln(x)")) and not (o == "exp" and i == "exp(x)")
                     for at in _at(o + i)]
    out["cr_two"] += [(f"sqrt(1+{t})", at) for t in ("exp(x)", "sin(x)^2", "cos(x)^2", "x^2") for at in _at(t)]
    out["cr_two"] += [(f"({t})^{n}", at) for t in ("sin(x)+1", "exp(x)+1", "ln(x)+x", "cos(x)+2") for n in (3, 4)
                      for at in _at(t)]
    out["cr_three"] = [(f"{o}({m}({i}))", at) for o in ("exp", "sin", "cos", "ln") for m in ("sin", "cos", "exp", "atan")
                       for i in ("x^2", "x^2+1", "sqrt(x)", "x^3")
                       if o != m and not (o == "ln" and m in ("sin", "cos", "atan"))
                       for at in _at(o + m)]
    out["cr_three"] += [(f"sin(sqrt(x^2+{b}))", at) for b in (1, 2, 3) for at in ("x", "0", "1")]
    out["cr_three"] += [(f"exp(({a}*x^2+1)^2)" if False else f"sqrt(exp({a}*x^2)+1)", at) for a in (1, 2, 3) for at in ("x", "0")]
    # table problems: f is the outer polynomial, g the inner polynomial, at the point (the level-5 family)
    cands = [(f, g, a) for f in ("x^2+1", "x^3+x", "2*x^2-3", "x^2+x", "x^3-2", "x^2-3*x", "3*x^2+1", "x^3+2*x", "2*x^3-x")
             for g in ("2*x-1", "x^2-1", "x+2", "3*x-2", "x^2+x", "2*x+1", "x^2", "x^2-2*x", "4-x", "x^3-x")
             for a in (0, 1, 2, -1, 3)]
    table = [dict(f=f, at=str(a), g=g, ask="table") for f, g, a in cands]
    return {"expr": {k: [dict(f=f, at=at, g="", ask="expression") for f, at in v] for k, v in out.items()},
            "table": {"cr_table": table}}


def _tangent():
    out = {}
    out["tl_poly"] = [(f"x^2+{b}*x+{c}", str(a), "tangent") for b in (1, -2, 3, -4) for c in (1, 5, -3) for a in (1, 2, -1, 0, 3)]
    out["tl_poly"] += [(f"x^3-{b}*x", str(a), "tangent") for b in (1, 2, 3, 6) for a in (1, 2, -1, 0, 3)]
    out["tl_poly"] += [(f"{c}*x^2-x^3", str(a), "tangent") for c in (2, 3, 5) for a in (1, 2, -1, 3)]
    out["tl_trans"] = [(f"{c}*{t}", a, "tangent") for c in (1, 2, 3) for t, pts in
                       (("sin(x)", ("0", "pi/2", "pi", "pi/6")), ("cos(x)", ("0", "pi/2", "pi/3", "pi")),
                        ("exp(x)", ("0", "1", "2")), ("ln(x)", ("1", "2", "e")), ("atan(x)", ("0", "1", "-1")),
                        ("sqrt(x)", ("1", "4", "9", "16")), ("exp(2*x)", ("0", "1")), ("tan(x)", ("0", "pi/4")))
                       for a in pts]
    out["tl_trans"] += [(f"x*{t}", a, "tangent") for t, pts in (("exp(x)", ("0", "1", "-1")), ("ln(x)", ("1", "e")),
                                                              ("sin(x)", ("0", "pi/2", "pi")), ("cos(x)", ("0", "pi")))
                        for a in pts]
    out["tl_normal"] = [(f"x^2+{b}*x+{c}", str(a), "normal") for b in (1, -2, 3) for c in (1, -3) for a in (1, 2, -1, 3)]
    out["tl_normal"] += [(f"x^3-{b}*x", str(a), "normal") for b in (1, 2, 5) for a in (1, 2, -2, 3)]
    out["tl_normal"] += [(f"{c}*{t}", a, "normal") for c in (1, 2) for t, pts in
                         (("sin(x)", ("0", "pi/3", "pi/6")), ("exp(x)", ("0", "1")), ("ln(x)", ("1", "2")),
                          ("sqrt(x)", ("1", "4", "9")), ("atan(x)", ("1", "-1")), ("cos(x)", ("pi/2", "pi/6")))
                         for a in pts]
    out["tl_horizontal"] = [(f"x^3-{3 * k}*x", "", "horizontal") for k in (1, 2, 3, 4, 5)]
    out["tl_horizontal"] += [(f"x^3-{c}*x^2", "", "horizontal") for c in (3, 6, 9, 12)]
    out["tl_horizontal"] += [(f"x^4-{c}*x^2", "", "horizontal") for c in (2, 4, 8, 18)]
    out["tl_horizontal"] += [(f"x^3+{a}*x^2-{b}*x", "", "horizontal") for a in (3, 6) for b in (9, 24, 12, 15)]
    out["tl_horizontal"] += [(f"x/(x^2+{b})", "", "horizontal") for b in (1, 4, 9, 16)]
    out["tl_horizontal"] += [(f"(x^2+{a})/(x-{b})", "", "horizontal") for a in (1, 3, 5, 8) for b in (1, 2, 3)]
    out["tl_horizontal"] += [(f"x/(x^2+{b}*x+{c})", "", "horizontal") for b in (0, 2, 4) for c in (1, 4, 9)]
    return {k: [dict(f=f, a=a, ask=ask) for f, a, ask in v] for k, v in out.items()}


_CHAIN = _chain()
TABLES = {"product_rule": _product(), "quotient_rule": _quotient(),
          "chain_rule": {**_CHAIN["expr"], **_CHAIN["table"]}, "tangent_normal_lines": _tangent()}


def generate(stem: str, recipe: dict, axes: dict, answers: set[str], calculator: str = "none", seed: int = 0,
             limit: int = 150) -> dict | None:
    rng = random.Random(seed)
    rows = list(TABLES[stem].get(recipe["id"], []))
    rng.shuffle(rows)
    full = {"recipe": recipe["id"], **axes}
    for payload in rows[:limit]:
        r = derivative_rules.verify(stem, axes=full, calculator=calculator, **payload)
        if r["ok"] and r["answer"]["type"] in answers:
            return {"payload": payload, "result": r}
    return None
