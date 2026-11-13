"""Seeded offline pools for the parametric and polar topics: the replies a good model would give per recipe."""
import random

from app.calc2 import parametric_polar

R = range


def _p(**fields):
    return {k: None if v is None else str(v) for k, v in fields.items()}


def _tangents():
    slope = lambda x, y, t0: _p(x=x, y=y, t0=t0, t1=None, ask="slope")
    line = lambda x, y, t0: _p(x=x, y=y, t0=t0, t1=None, ask="line")
    horizontal = lambda x, y, lo, hi: _p(x=x, y=y, t0=lo, t1=hi, ask="horizontal")
    poly_x = [f"t^2+{a}" for a in R(1, 6)] + [f"{a}*t^2" for a in R(2, 7)]
    poly_y = [f"t^3-{b}*t" for b in R(1, 6)] + [f"{b}*t^3+t" for b in R(1, 6)] + [f"t^2+{b}*t" for b in R(1, 6)]
    return {
        "tn_slope_poly": [slope(x, y, t0) for x in poly_x for y in poly_y for t0 in (1, 2, 3, -1, -2)],
        "tn_line_poly": [line(x, y, t0) for x in [f"t^2-{a}*t" for a in R(1, 5)] + [f"{a}*t+{c}" for a in R(2, 5) for c in R(0, 3)]
                         for y in [f"t^3-{b}*t" for b in R(1, 5)] + [f"{b}*t^2+{c}" for b in R(1, 5) for c in (1, 2)]
                         for t0 in (-1, 2, 3)],
        "tn_horizontal_poly": [horizontal(x, y, 0, hi)
                               for a in R(1, 7) for c in R(1, 7) for hi in (a + 1, a + 2)
                               for x, y in ((f"t^2+{c}", f"t^3-{3 * a * a}*t"), (f"t^3+{c}*t", f"t^2-{2 * a}*t"))],
        "tn_slope_trig": [slope(x, y, t0) for a in R(2, 6) for b in R(2, 7)
                          for x, y in ((f"{a}*cos(t)", f"{b}*sin(t)"),)
                          for t0 in ("pi/6", "pi/4", "pi/3", "2*pi/3", "3*pi/4", "5*pi/6")]
        + [slope(f"{a}*t-sin(t)", f"{a}-cos(t)", t0) for a in R(2, 7) for t0 in ("pi/2", "pi/3", "2*pi/3", "pi", "3*pi/2")],
        "tn_horizontal_trig": [horizontal(f"{a}*cos(t)+{c}", f"{b}*sin(t)", 0, "pi") for a in R(2, 6)
                               for b in R(2, 7) for c in R(0, 4)]
        + [horizontal(f"{a}*sin(t)", f"{b}*cos(t)+{c}", "-pi/2", "pi/2") for a in R(2, 6) for b in R(2, 7) for c in R(0, 3)],
        "tn_slope_exp": [slope(f"exp({a}*t)+t", f"exp({b}*t)-{c}*t", t0) for a in R(1, 4) for b in R(1, 4)
                         for c in R(0, 4) for t0 in (0, "ln(2)", "ln(3)", 1)],
        "tn_slope_rational": [slope(f"{a}*t/(t+{c})", y.format(c=c), t0) for a in R(1, 6) for c in R(1, 5)
                              for y in ("t^2/(t+{c})", "t^3/(t+{c})", "(t+2)/(t+{c})") for t0 in (1, 2, 3)],
        "tn_line_exp": [line(f"t*exp({k}*t)", f"exp({m}*t)+{c}", t0) for k in (1, 2, 3) for m in (1, 2, 3, 4)
                        for c in R(0, 6) for t0 in (0, 1, "ln(2)")],
        "tn_line_exp_trig": [line(f"{a}*exp({k}*t)*cos(t)", f"{a}*exp({k}*t)*sin(t)", t0) for a in R(1, 7) for k in (1, 2, 3)
                             for t0 in (0, "pi/2", "pi", "pi/4", "3*pi/2", "pi/3")],
    }


def _second():
    value = lambda x, y, t0: _p(x=x, y=y, t0=t0, ask="value")
    conc = lambda x, y, t0: _p(x=x, y=y, t0=t0, ask="concavity")
    expr = lambda x, y: _p(x=x, y=y, t0=None, ask="expression")
    poly_x = [f"t^2+{a}" for a in R(0, 4)] + [f"{a}*t^3" for a in R(1, 3)] + ["t^2", "t^3+t"]
    poly_y = [f"t^3+{b}*t" for b in R(1, 5)] + [f"t^4-{b}*t" for b in R(1, 4)] + [f"{b}*t^3" for b in R(1, 4)]
    return {
        "sd_value_linear": [value(f"{a}*t+{c}", f"t^3+{b}*t", t0) for a in R(1, 5) for c in R(0, 3)
                            for b in R(1, 5) for t0 in R(1, 5)],
        "sd_value_poly": [value(x, y, t0) for x in poly_x for y in poly_y for t0 in (1, 2, 3)],
        "sd_concavity_poly": [conc(x, y, t0) for x in poly_x for y in poly_y for t0 in (1, 2, -1, 3)],
        "sd_expression_poly": [expr(x, y) for x in ("t^2", "t^3", "t^2+1", "t^2-t", "t^3+t", "2*t^2", "3*t^2+1", "t^4", "t^2+2*t", "4*t^2", "t^3-t", "t^2+3")
                               for y in ("t^3", "t^4", "t^3-3*t", "t^2+t", "t^3+t^2", "2*t^3", "t^5", "4*t^3", "t^4+t", "t^3+2*t")],
        "sd_value_trig": [value(f"{a}*cos(t)", f"{b}*sin(t)", t0) for a in R(1, 6) for b in R(1, 7)
                          for t0 in ("pi/6", "pi/4", "pi/3", "2*pi/3", "3*pi/4")]
        + [value(f"{a}*(t-sin(t))", f"{a}*(1-cos(t))", t0) for a in R(1, 7) for t0 in ("pi/2", "pi/3", "2*pi/3", "pi/6")],
        "sd_value_exp": [value(f"exp({a}*t)", f"{c}*exp({b}*t)+t", t0) for a in R(1, 4) for b in R(1, 4)
                         for c in R(1, 6) for t0 in (0, "ln(2)", "ln(3)")],
        "sd_expression_trig": [expr(f"{a}*cos(t)", f"{b}*sin(t)") for a in R(1, 10) for b in R(1, 11)]
        + [expr(f"{a}*(t-sin(t))", f"{a}*(1-cos(t))") for a in R(1, 8)] + [expr(f"{a}*sin(t)", f"{b}*cos(t)") for a in R(1, 5) for b in R(1, 5)],
    }


def _area():
    ar = lambda x, y, lo, hi: _p(x=x, y=y, t0=lo, t1=hi)
    return {
        "pa_linear": [ar(f"{a}*t+{c}", y, 0, T) for a in R(1, 5) for c in R(0, 3)
                      for y in [f"t^2+{b}" for b in R(0, 4)] + [f"{b}*t+1" for b in R(1, 4)] for T in R(1, 5)],
        "pa_poly": [ar(x, y, 0, T) for x in [f"t^2+{c}" for c in R(0, 3)] + ["t^3", "t^3+t", "2*t^2", "t^2+t"]
                    for y in [f"{b}*t+{d}" for b in R(1, 4) for d in (1, 2)] + ["t^2+1", "t^3+t", "2*t^2+3"] for T in R(1, 5)],
        "pa_trig": [ar(f"{a}*sin(t)", f"{b}*cos(t)", 0, hi) for a in R(1, 7) for b in R(1, 8) for hi in ("pi/2", "pi/4", "pi/6")]
        + [ar(f"{a}*t", f"{b}*sin(t)", 0, hi) for a in R(1, 6) for b in R(1, 7) for hi in ("pi", "pi/2", "2*pi/3")],
        "pa_cycloid": [ar(f"{a}*(t-sin(t))", f"{a}*(1-cos(t))", 0, hi) for a in R(1, 14) for hi in ("pi", "2*pi", "pi/2", "3*pi/2", "pi/3")],
        "pa_reversed": [ar(f"{a}*cos(t)", f"{b}*sin(t)+{d}", 0, hi) for a in R(1, 6) for b in R(1, 5) for d in R(0, 4)
                        for hi in ("pi", "pi/2")],
    }


def _arc():
    ln = lambda x, y, lo, hi: _p(x=x, y=y, t0=lo, t1=hi)
    triples = ((3, 4), (4, 3), (6, 8), (8, 6), (5, 12), (12, 5), (8, 15), (15, 8))
    rationals = ("3/4", "4/3", "5/12", "12/5", "sqrt(3)", "sqrt(8)", "sqrt(15)", "sqrt(24)")
    return {
        "pl_line": [ln(f"{a}*t+{c}", f"{b}*t+{d}", 0, T) for a, b in triples for c in R(0, 3) for d in R(0, 3) for T in R(1, 5)],
        "pl_pyth": [ln(f"{c}*(t^3/3-{s * s}*t)", f"{c * s}*t^2", lo, T) for c in R(1, 5) for s in R(1, 5)
                    for lo, T in ((0, 1), (0, 2), (0, 3), (1, 3), (0, 4), (1, 4), (2, 5), (0, 5), (1, 5), (2, 4))],
        "pl_semicubical": [ln(f"{k}*t^2/2", f"{k}*t^3/3", 0, T) for k in R(1, 13) for T in rationals],
        "pl_trig": [ln(f"{a}*cos(t)^3", f"{a}*sin(t)^3", 0, "pi/2") for a in R(1, 9)]
        + [ln(f"{a}*(t-sin(t))", f"{a}*(1-cos(t))", 0, hi) for a in R(1, 8) for hi in ("pi", "2*pi", "pi/2")]
        + [ln(f"{a}*cos(t)", f"{a}*sin(t)", lo, hi) for a in R(1, 9) for lo, hi in ((0, "pi/3"), (0, "pi"), ("pi/6", "pi/2"))]
        + [ln(f"{a}*(cos(t)+t*sin(t))", f"{a}*(sin(t)-t*cos(t))", 0, T) for a in R(1, 5) for T in (1, 2, 3, "pi")],
        "pl_spiral": [ln(f"{a}*exp({k}*t)*cos(t)", f"{a}*exp({k}*t)*sin(t)", lo, hi) for a in R(1, 9) for k in (1, 2, 3)
                      for lo, hi in ((0, "ln(2)"), (0, "ln(3)"), (0, "ln(4)"), ("ln(2)", "ln(4)"), (0, "ln(5)"))],
    }


def _surface():
    sa = lambda x, y, lo, hi, axis: _p(x=x, y=y, t0=lo, t1=hi, axis=axis)
    triples = ((3, 4), (4, 3), (6, 8), (8, 6), (5, 12), (12, 5), (8, 15), (15, 8))
    circle_x = (("0", "pi"), ("0", "pi/2"), ("0", "pi/3"), ("pi/6", "pi/2"), ("pi/3", "2*pi/3"), ("pi/2", "pi"))
    circle_y = (("0", "pi/2"), ("0", "pi/3"), ("pi/6", "pi/2"), ("pi/3", "pi/2"), ("-pi/2", "pi/2"))
    return {
        "sa_cone": [sa(f"{a}*t+{c}", f"{b}*t", 0, T, "x") for a, b in triples for c in R(0, 3) for T in R(1, 7)],
        "sa_frustum": [sa(f"{a}*t+{c}", f"{b}*t+{d}", 0, T, "y") for a, b in triples for c in R(0, 3) for d in (0, 1) for T in R(1, 4)],
        "sa_circle": [sa(f"{r}*cos(t)", f"{r}*sin(t)", lo, hi, "x") for r in R(1, 9) for lo, hi in circle_x]
        + [sa(f"{r}*cos(t)", f"{r}*sin(t)", lo, hi, "y") for r in R(1, 9) for lo, hi in circle_y],
        "sa_curved": [sa(f"{a}*cos(t)^3+{c}", f"{a}*sin(t)^3", 0, "pi/2", "x") for a in R(1, 13) for c in R(0, 4)]
        + [sa(f"{a}*cos(t)^3", f"{a}*sin(t)^3+{c}", 0, "pi/2", "y") for a in R(1, 13) for c in R(0, 4)]
        + [sa(f"{a}*(t-sin(t))", f"{a}*(1-cos(t))", 0, hi, "x") for a in R(1, 6) for hi in ("2*pi", "pi", "pi/2")],
    }


def _slopes():
    sl = lambda r, t0: _p(r=r, t0=t0, t1=None, ask="slope")
    ln = lambda r, t0: _p(r=r, t0=t0, t1=None, ask="line")
    hz = lambda r, lo, hi: _p(r=r, t0=lo, t1=hi, ask="horizontal")
    angles = ("pi/6", "pi/4", "pi/3", "pi/2", "2*pi/3", "3*pi/4", "5*pi/6")
    return {
        "ps_circle": [sl(f"{a}*{f}(theta)", t0) for a in R(1, 10) for f in ("cos", "sin")
                      for t0 in ("pi/6", "pi/4", "pi/3", "pi/8", "2*pi/3", "5*pi/6")],
        "ps_cardioid": [sl(f"{a}+{b}*{f}(theta)", t0) for a in R(1, 5) for b in R(1, 5) for f in ("cos", "sin")
                        for t0 in ("pi/2", "pi/3", "pi/4", "pi/6", "2*pi/3")],
        "ps_line": [ln(f"{a}+{b}*{f}(theta)", t0) for a in R(1, 5) for b in R(1, 5) for f in ("cos", "sin")
                    for t0 in ("pi/2", "pi/3", "pi/4", "pi/6")],
        "ps_horizontal": [hz(f"{a}+{a}*cos(theta)", lo, hi) for a in R(1, 9) for lo, hi in
                          ((0, "pi"), (0, "pi/2"), (0, "2*pi/3"), ("pi/6", "pi/2"))]
        + [hz(f"{a}+{a}*sin(theta)", lo, hi) for a in R(1, 9) for lo, hi in
           ((0, "pi"), (0, "2*pi/3"), ("pi/3", "2*pi/3"), ("pi/4", "3*pi/4"))]
        + [hz(f"{2 * a}*cos(theta)", lo, hi) for a in R(1, 6) for lo, hi in ((0, "pi/2"), (0, "pi/3"), ("pi/8", "pi/3"))]
        + [hz(f"{a}*sin(theta)", lo, hi) for a in R(1, 6) for lo, hi in ((0, "pi"), ("pi/3", "2*pi/3"), ("pi/4", "3*pi/4"))],
        "ps_rose": [sl(f"{a}*{f}({n}*theta)", t0) for a in R(1, 5) for f in ("cos", "sin") for n in (2, 3, 4)
                    for t0 in angles + ("pi/12", "pi/8")],
    }


def _polar_area():
    ar = lambda r, lo, hi, r2=None: _p(r=r, t0=lo, t1=hi, r2=r2)
    return {
        "pr_sector": [ar(f"{a}", 0, hi) for a in R(1, 13) for hi in ("pi/6", "pi/4", "pi/3", "pi/2", "pi", "3*pi/2")]
        + [ar(f"{a}*theta", 0, T) for a in R(1, 5) for T in (1, 2, 3, "pi", "2*pi")],
        "pr_cardioid": [ar(f"{a}+{b}*{f}(theta)", 0, "2*pi") for a in R(2, 11) for b in R(1, a + 1) for f in ("cos", "sin")],
        "pr_petal": [ar(f"{a}*cos({n}*theta)", f"-pi/{2 * n}", f"pi/{2 * n}") for a in R(1, 14) for n in R(2, 6)]
        + [ar(f"{a}*sin({n}*theta)", 0, f"pi/{n}") for a in R(1, 14) for n in R(2, 6)],
        "pr_sector_trig": [ar(f"{a}+{b}*{f}(theta)", lo, hi) for a in R(1, 5) for b in R(1, 5) for f in ("cos", "sin")
                           for lo, hi in ((0, "pi/2"), (0, "pi"), ("pi/2", "pi"))],
        "pr_between": [ar(f"{a}+{b}*cos(theta)", lo, hi, f"{a}") for a in R(1, 7) for b in R(1, 7)
                       for lo, hi in (("-pi/2", "pi/2"), (0, "pi/2"), ("-pi/3", "pi/3"))]
        + [ar(f"{3 * s}*cos(theta)", "-pi/3", "pi/3", f"{s}+{s}*cos(theta)") for s in R(1, 9)],
    }


def _polar_arc():
    ln = lambda r, lo, hi: _p(r=r, t0=lo, t1=hi)
    return {
        "pa_circle": [ln(f"{a}", lo, hi) for a in R(1, 13) for lo, hi in
                      ((0, "pi/6"), (0, "pi/4"), (0, "pi/3"), (0, "pi/2"), (0, "pi"), (0, "2*pi"), ("pi/6", "pi/2"), (0, "3*pi/2"))],
        "pa_circle_trig": [ln(f"{a}*{f}(theta)", 0, hi) for a in R(1, 9) for f in ("cos", "sin")
                           for hi in ("pi", "pi/2", "pi/3", "pi/4", "2*pi/3", "3*pi/4")],
        "pa_cardioid": [ln(f"{a}*(1-cos(theta))", lo, hi) for a in R(1, 10)
                        for lo, hi in ((0, "2*pi"), (0, "pi"), ("pi", "2*pi"), (0, "pi/2"), ("pi/2", "pi"), (0, "2*pi/3"))]
        + [ln(f"{a}*(1+cos(theta))", lo, hi) for a in R(1, 10)
           for lo, hi in (("-pi", "pi"), ("-pi", 0), (0, "pi"), (0, "pi/2"), ("-pi/2", "pi/2"), (0, "2*pi/3"))],
        "pa_exp": [ln(f"{a}*exp({k}*theta)", lo, hi) for a in R(1, 9) for k in (1, 2, 3)
                   for lo, hi in ((0, "ln(2)"), (0, "ln(3)"), (0, "ln(4)"), ("ln(2)", "ln(4)"), (0, "ln(5)"))],
        "pa_quadratic": [ln(f"{a}*theta^2/{d}", 0, T) for a in R(1, 8) for d in (1, 2, 3, 4)
                         for T in ("sqrt(5)", "2*sqrt(3)", "sqrt(21)", "4*sqrt(2)", "3/2", "8/3", "5/6", "15/4")],
        "pa_sine_cube": [ln(f"{a}*{f}(theta/3)^3", lo, hi) for a in R(1, 14) for f in ("sin", "cos")
                         for lo, hi in ((0, "pi"), (0, "3*pi/2"), (0, "3*pi/4"), (0, "pi/2"), (0, "2*pi"), ("3*pi/4", "3*pi/2"))],
    }


TABLES = {"tangents": _tangents(), "second_derivatives": _second(), "parametric_area": _area(),
          "parametric_arc_length": _arc(), "parametric_surface_area": _surface(), "slopes": _slopes(),
          "polar_area": _polar_area(), "polar_arc_length": _polar_arc()}


def generate(recipe, axes, answers, calculator="none", seed=0, topic=None, limit=120):
    rows = list(TABLES[topic].get(recipe["id"], ()))
    random.Random(seed).shuffle(rows)
    full_axes = {"recipe": recipe["id"], **axes}
    for payload in rows[:limit]:
        result = parametric_polar.verify(topic, axes=full_axes, calculator=calculator, **payload)
        if result["ok"] and result["answer"]["type"] in answers:
            return {"payload": payload, "result": result}
    return None
