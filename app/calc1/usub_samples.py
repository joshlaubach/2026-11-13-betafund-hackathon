"""An offline source of u-substitution problems, for the calibration packet only (it is not registered in
app.offline: u-substitution stays LLM-only in production, DECISIONS D15).

For a recipe and its assigned axes it lists the replies a good model would give (g, R, bounds), tries them in a
seeded order and returns the first one the u-substitution verifier accepts. The verifier is the same one a model
reply goes through, so an invalid candidate is simply skipped. Recipe levels are never touched here.
"""
import itertools
import random

from app.calc1 import usub

_C = ("1", "2", "3", "-1", "-2")
_POLY = {2: ["x^2+1", "x^2+x", "2*x^2+3", "x^2-x+1", "3*x^2+2"], 3: ["x^3+x", "x^3+2", "2*x^3+1", "x^3-x+1"]}
_B = [("0", "1"), ("0", "2"), ("1", "2"), ("-1", "1"), ("0", "3"), ("1", "3")]
_TRIG_B = [("0", "pi/2"), ("0", "pi/4"), ("0", "pi/3"), ("0", "pi/6"), ("0", "pi"), ("pi/6", "pi/3"), ("pi/4", "pi/2")]
_LOG_B = [("1", "4"), ("1", "2"), ("1", "e"), ("1", "9"), ("2", "4"), ("1", "e^2")]
_SQ_B = [("0", "1"), ("0", "2"), ("0", "sqrt(3)"), ("1", "2")]
_HD_BOUNDS = {"sin(x)/x": ("pi/2", "pi"), "cos(x)/x": ("pi/2", "pi"), "exp(x)/x": ("1", "2"), "ln(x)/x": ("1", "e"),
              "x/(x^2+1)": ("0", "1"), "x*exp(-x)": ("0", "1"), "x^x": ("1", "2")}
_LD_BOUNDS = {"sin(x)": ("0", "pi/2"), "cos(x)": ("0", "pi/2"), "exp(x)": ("0", "ln(2)"), "x^2": ("0", "1")}
_PY_BOUNDS = {"cos": ("0", "pi/2"), "sin": ("0", "pi/2"), "tan": ("0", "pi/4"), "sec": ("0", "pi/3")}
_NEST_H = {"u^2": "2*u", "sqrt(u)": "1/(2*sqrt(u))", "1/u": "-1/u^2", "ln(u)": "1/u"}
_NEST_S = ["exp(w)", "sin(w)", "cos(w)", "1/(1+w^2)", "w^2", "w^3", "1/w", "sqrt(w)"]
_FAMILY = {"sin(x), with the singular endpoint at 0 (the other bound is at most pi/2)": ("sin(x)", ["0"], ["pi/2", "pi/4", "pi/6"]),
           "cos(x), with the singular endpoint at pi/2 (the other bound is at least 0)": ("cos(x)", ["pi/2"], ["0", "pi/4", "pi/3"]),
           "ln(x), with the singular endpoint at 1 (the other bound is e or e^2)": ("ln(x)", ["1"], ["e", "e^2"]),
           "exp(x) - 1, with the singular endpoint at 0 (the other bound is ln(2) or ln(3))": ("exp(x)-1", ["0"], ["ln(2)", "ln(3)"]),
           "tan(x), with the singular endpoint at 0 (the other bound is pi/4 or pi/3)": ("tan(x)", ["0"], ["pi/4", "pi/3"])}


def _b(lo, hi):
    return {"lower": lo, "upper": hi}


def _sub(expr: str, var: str, value: str) -> str:
    """Replace the variable `var` (a single letter) by (value) in a string of the recipes' syntax."""
    import re
    return re.sub(rf"\b{var}\b", f"({value})", expr)


def _powers(power: str, c: str) -> str:
    return f"{c}*u^({power})"


def _payloads(rid: str, axes: dict, rec: dict):
    """Yield (g, R, bounds or None, extra axes) for one recipe and its assigned axes."""
    v = axes
    if rid == "linear_g":
        for a, b in itertools.product(("2", "3", "4", "5"), ("0", "1", "-1", "3")):
            g = f"{a}*x+{b}" if b != "0" else f"{a}*x"
            bnds = [None] + [_b(lo, hi) for lo, hi in ((("1", "2"), ("0", "1"), ("0", "2")) if v["outer"] != "1/u" else (("0", "1"),))]
            for bd in bnds:
                yield g, f"({v['outer']})/{a}", bd, {}
    elif rid in ("poly_power_indef", "poly_power_def", "poly_trig_exp_indef"):
        for g, c in itertools.product(_POLY[v["deg"]], _C):
            R = _powers(v["power"], c) if "power" in v else f"{c}*{v['outer']}"
            for bd in ([None] if rid.endswith("indef") else [_b("0", "1"), _b("0", "2"), _b("1", "2")]):
                yield g, R, bd, {}
    elif rid == "trig_inner_power_indef":
        for c in _C:
            yield v["inner"], _powers(v["power"], c), None, {}
    elif rid == "exp_def":
        for g, c in itertools.product(("x^2", "x^3"), _C):
            for lo, hi in (("0", "1"), ("0", "2")):
                yield g, f"{c}*exp(u)", _b(lo, hi), {}
    elif rid in ("log_def", "log_ratio_indef"):
        gs = ["x^2+1", "x^2+x+1", "x^2+3", "x^3+1", "sin(x)", "cos(x)", "exp(x)+1", "x+1"]
        for g, c, n in itertools.product(gs, _C, ("1", "2")):
            R = f"{c}/u" if rid == "log_def" or n == "1" else f"{c}/u^2"
            for bd in ([None] if rid == "log_ratio_indef" else [_b(lo, hi) for lo, hi in _B[:3]] + [_b(lo, hi) for lo, hi in _TRIG_B]):
                yield g, R, bd, {}
    elif rid == "trig_def":
        for g, c in itertools.product(("sin(x)", "cos(x)", "tan(x)"), _C):
            for R in (f"{c}*u^2", f"{c}*u^3", f"{c}*u", f"{c}*exp(u)", f"{c}/(1+u^2)"):
                for lo, hi in _TRIG_B:
                    yield g, R, _b(lo, hi), {}
    elif rid == "inverse_trig":
        for g, c in itertools.product(("x^2", "x^3", "sqrt(x)", "exp(x)"), ("1", "2", "3", "-1")):
            yield g, f"{c}/(1+u^2)", None, {}
            yield g, f"{c}/sqrt(1-u^2)", None, {}
            for lo, hi in (("0", "1"),):
                if g in ("x^2", "x^3"):
                    yield g, f"{c}/(1+u^2)", _b(lo, hi), {}
    elif rid == "composite_exp_trig":
        for g, o, c in itertools.product(("sqrt(x)", "1/x", "ln(x)"), ("exp(u)", "sin(u)", "cos(u)"), _C):
            for lo, hi in (("1", "4"), ("1", "9"), ("1", "2"), ("1", "e"), ("1", "e^2")):
                yield g, f"{c}*{o}", _b(lo, hi), {}
            yield g, f"{c}*{o}", None, {}
    elif rid == "trig_identity_indef":
        for g, o, c in itertools.product(("x^2", "x^3", "sqrt(x)", "exp(x)", "ln(x)"), ("sin(u)^2", "cos(u)^2"), _C):
            yield g, f"{c}*{o}", None, {}
    elif rid == "leftover_x_linear":
        for a, b in itertools.product(("1", "2"), ("1", "-1")):
            g = f"{a}*x+{b}" if a != "1" else f"x+{b}"
            R = f"((u-({b}))/{a})^{v['m']}*u^({v['p']})/{a}"
            yield g, R, None, {}
            for lo, hi in _B:
                yield g, R, _b(lo, hi), {}
    elif rid == "leftover_x_indef":
        n, j, p = v["n"], v["j"], v["p"]
        for a, c in itertools.product((1, 2), (1, -1, 3, 2)):
            yield f"{a}*x^{n}+({c})", f"((u-({c}))/{a})^{j}*u^({p})/({n}*{a})", None, {}
    elif rid == "leftover_x_def":
        n, j, p = v["n"], v["j"], v["p"]
        for a, c, lo, hi in rec["known"][f"{n},{j},{p}"]:
            yield (f"{a}*x^{n}+({c})", f"((u-({c}))/{a})^{j}*u^({p})/({n}*{a})", _b(str(lo), str(hi)),
                   {"a": a, "c": c, "lo": lo, "hi": hi})
    elif rid in ("composite_g_indef", "composite_g_def"):
        for g in ("sqrt(x^2+1)", "ln(x^2+1)", "exp(x^2)", "sin(x)^2", "(x^3+1)^3"):
            outs = ["exp(u)", "sin(u)", "cos(u)"] + (["u^2", "u^3", "1/u", "sqrt(u)"] if g.startswith("ln") else [])
            for o, c in itertools.product(outs, _C):
                if rid.endswith("indef"):
                    yield g, f"{c}*{o}", None, {}
                else:
                    for lo, hi in _B + _TRIG_B:
                        yield g, f"{c}*{o}", _b(lo, hi), {}
    elif rid in ("nested_indef", "nested_def"):
        for g in ("x^2+1", "sin(x)", "cos(x)", "x^3+1", "x^2+x+1", "2*x+1"):
            for h, S, c in itertools.product(_NEST_H, _NEST_S, ("1", "2", "3")):
                R = f"{c}*({_sub(S, 'w', h)})*({_NEST_H[h]})"
                if rid.endswith("indef"):
                    yield g, R, None, {}
                else:
                    for lo, hi in _B + _TRIG_B + _LOG_B:
                        yield g, R, _b(lo, hi), {}
    elif rid == "trap_pole_inside":
        gs = [("sin(x)", ("-pi/2", "pi/2")), ("sin(x)", ("-pi/4", "pi/4")), ("x-1", ("0", "2")), ("x-1", ("0", "3")),
              ("cos(x)", ("0", "pi")), ("x^2-1", ("0", "2")), ("exp(x)-1", ("-1", "1")), ("ln(x)", ("1/2", "2"))]
        for (g, (lo, hi)), p, c in itertools.product(gs, ("1", "2"), ("1", "2", "3")):
            yield g, f"{c}/u^{p}" if p != "1" else f"{c}/u", _b(lo, hi), {}
    elif rid == "trap_endpoint":
        g, ends, others = _FAMILY[v["family"]]
        for c, other in itertools.product(("1", "2", "3", "-1"), others):
            R = f"{c}/u^({v['p']})"
            yield g, R, _b(ends[0], other), {}
            yield g, R, _b(other, ends[0]), {}
    elif rid in ("pythagorean_trig_indef", "pythagorean_trig_def"):
        fam, k, n = v["family"], v["k"], v["n"]
        R0 = {"cos": f"(1-u^2)^{k}*u^{n}", "sin": f"(1-u^2)^{k}*u^{n}", "tan": f"(1+u^2)^{k}*u^{n}",
              "sec": f"(u^2-1)^{k}*u^({n - 1})"}[fam]
        for c in _C:
            yield fam + "(x)", f"{c}*{R0}", None if rid.endswith("indef") else _b(*_PY_BOUNDS[fam]), {}
    elif rid in ("complete_square_indef", "complete_square_def"):
        k, s, kind = v["k"], v["s"], v["kind"]
        core = f"(u^2+{s ** 2})" if kind == "arctan" else f"sqrt({s ** 2}-u^2)"
        for c in _C:
            if rid.endswith("indef"):
                yield f"x+({k})", f"{c}/{core}", None, {}
            else:
                yield f"x+({k})", f"{c}/{core}", _b(str(-k), str(-k + s)), {"lo": -k, "hi": -k + s}
    elif rid in ("long_division_indef", "long_division_def"):
        m, c0 = v["m"], v["c"]
        for kk, lead, mid, const in itertools.product(("1", "2", "-1"), ("1", "2"), ("0", "1", "-1"), ("1", "2", "-3")):
            N = {2: f"{lead}*u^2+({mid})*u+({const})", 3: f"{lead}*u^3+({mid})*u+({const})"}[m]
            R = f"{kk}*({N})/(u+{c0})"
            yield v["g"], R, None if rid.endswith("indef") else _b(*_LD_BOUNDS[v["g"]]), {}
    elif rid in ("hidden_derivative_indef", "hidden_derivative_def"):
        for kk in ("1", "2", "3", "-1"):
            R = kk if v["R"] == "1" else f"{kk}*{v['R']}"
            yield v["g"], R, None if rid.endswith("indef") else _b(*_HD_BOUNDS[v["g"]]), {}


def generate(recipe: dict, axes: dict, answers: set[str], calculator: str = "none", seed: int = 0,
             limit: int = 150) -> dict | None:
    """The first verified problem for this recipe's axes, trying the candidate replies in a seeded order.
    Returns {"payload", "result"} or None when none of the candidates passes."""
    rng = random.Random(seed)
    cands = list(_payloads(recipe["id"], axes, recipe))
    rng.shuffle(cands)
    full = {"recipe": recipe["id"], **axes} if axes else None
    for g, R, bounds, extra in cands[:limit]:
        r = usub.verify(g, R, [bounds["lower"], bounds["upper"]] if bounds else None, bool(recipe.get("trap")),
                        {**full, **extra} if full else None)
        if r["ok"] and r["answer"]["type"] in answers:
            return {"payload": {"g": g, "R": R, "bounds": bounds}, "result": r}
    return None
