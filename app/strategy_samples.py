"""Offline source of mixed-strategy problems: for each recipe a table of (technique, structure, bounds) rows, each
solved by the verifier of its own technique through app/strategy.py, so every row is checked."""
import random

from app import strategy

US, BP, PF, TI, TS, HY = ("u_substitution", "by_parts", "partial_fractions", "trig_integrals",
                          "trig_substitution", "hyperbolic")


def _us(g, R, b=None):
    return (US, {"g": g, "R": R}, b)


def _bp(u, dv, b=None, rest=None, g=None):
    return (BP, {"u": u, "dv": dv, "rest": rest, "g": g}, b)


def _pf(d, b=None):
    return (PF, {"decomposition": d}, b)


def _ti(f, b=None):
    return (TI, {"f": f}, b)


def _ts(kind, a, num, p, b=None, h=None):
    return (TS, {"kind": kind, "a": a, "num": num, "p": p, "h": h}, b)


def _hy(f, b=None):
    return (HY, {"f": f}, b)


TABLE = {
    "recog_basic": [_us("3*x+1", "u^4"), _us("2*x", "cos(u)"), _us("x^2+1", "u^3"), _us("sin(x)", "u^2"),
                    _bp("x", "exp(x)"), _bp("x", "sin(x)"), _bp("x", "cos(2*x)"), _bp("ln(x)", "1"),
                    _us("4*x", "exp(u)"), _bp("x", "exp(-x)", ["0", "1"])],
    "recog_plain_pair": [_bp("ln(x)", "x"), _bp("ln(x)", "x^2", ["1", "e"]), _pf("3/(x-1) - 2/(x+2)"),
                         _pf("1/x + 2/(x+1)"), _ti("sin(x)^2", ["0", "pi"]), _ti("cos(x)^2"), _us("x^3", "sin(u)/3"),
                         _bp("atan(x)", "1"), _pf("2/(x-1) + 3/(x-1)^2"), _ti("tan(x)^2", ["0", "pi/4"]),
                         _pf("1/(x-2) + 1/(x+3)"), _ti("cos(x)^2", ["0", "pi/2"]), _bp("ln(x)", "x^(-2)"),
                         _pf("2/x - 1/(x+1)", ["1", "3"]), _bp("x", "sin(3*x)")],
    "recog_decoy": [_us("x^2", "exp(u)/2"), _us("ln(x)", "u"), _us("x^2", "sin(u)/2"), _us("atan(x)", "u"),
                    _bp("x^2", "exp(x)"), _bp("x", "sec(x)^2", ["0", "pi/4"]), _bp("ln(x)", "x^3"),
                    _us("exp(x)", "1/(1+u^2)"), _us("cos(x)", "u^2"), _bp("atan(x)", "x")],
    "recog_rational": [_pf("3/(x-1) - 2/(x+2)", ["3", "5"]), _us("x^2+1", "1/u"), _us("x^2-1", "1/u"),
                       _pf("1/(x-1) - 1/(x+1)"), _pf("x + 1 + 3/(x-2) + 1/(x+1)"),
                       _pf("2/(x-1) + (x+1)/(x^2+1)"), _us("x^2+4", "1/(2*u)"), _us("x^2", "1/(1+u^2)/2"),
                       _pf("1/x + 1/(x^2+1)"), _pf("1/(x-1) + 1/(x+1) + 1/(x-3)")],
    "recog_radical": [_us("x^2+4", "sqrt(u)/2"), _ts("a2-x2", "2", "1", "-3"), _ts("a2+x2", "3", "1", "-1"),
                      _us("4-x^2", "-1/(2*sqrt(u))"), _ts("a2-x2", "2", "x^2", "-1"), _ts("x2-a2", "2", "1", "-3"),
                      _us("x^2+1", "sqrt(u)/2"), _ts("a2+x2", "2", "1", "-3", ["0", "2"]),
                      _ts("a2-x2", "1", "1", "3", ["0", "1"]), _ts("x2-a2", "3", "1", "-1")],
    "recog_trig": [_ti("sin(x)^3*cos(x)^2"), _us("sin(x)", "u^2"), _ti("sin(x)^2*cos(x)^2", ["0", "pi/2"]),
                   _bp("x", "sin(x)"), _ti("sec(x)^3"), _ti("tan(x)^3*sec(x)"), _us("tan(x)", "u^2"),
                   _ti("sin(2*x)*cos(3*x)"), _bp("x", "cos(x)^2"), _ti("tan(x)^2*sec(x)^2")],
    "recog_hyp": [_hy("sinh(x)*cosh(x)^2"), _hy("tanh(x)^2*sech(x)^2"), _hy("1/sqrt(x^2+4)"), _bp("x", "cosh(x)"),
                  _us("exp(x)", "u^2"), _hy("sinh(x)^2", ["0", "ln(2)"]), _hy("1/(4-x^2)", ["0", "1"]),
                  _bp("x", "sinh(x)", ["0", "ln(2)"]), _hy("tanh(x)^3"), _us("cosh(x)", "u^3")],
    "recog_two_step": [_bp("u", "exp(u)/2", None, None, "x^2"), _bp("u", "(2*sin(u))", ["0", "pi^2"], None, "sqrt(x)"),
                       _ts("a2+x2", "2", "1", "-3", None, "1"), _bp("u", "exp(u)/3", None, None, "x^3"),
                       _pf("x + 2 + 3/(x-1) + (x+1)/(x^2+1)"), _bp("x*exp(x)", "1/(x+1)^2"),
                       _bp("ln(x)", "exp(x)", None, "exp(x)/x"), _ts("a2-x2", "2", "x^4", "-1"),
                       _bp("asin(x)^2", "1", ["0", "1"]), _bp("sin(ln(x))", "1")],
}


def generate(recipe: dict, axes: dict, answers: set[str], calculator: str = "none", seed: int = 0,
             limit: int = 40) -> dict | None:
    rng = random.Random(seed)
    rows = list(TABLE.get(recipe["id"], []))
    rng.shuffle(rows)
    full = {"recipe": recipe["id"], **axes}
    for technique, fields, bounds in rows[:limit]:
        if "technique" in axes and axes["technique"] != technique:
            continue
        r = strategy.verify(technique, bounds, full, calculator, **fields)
        if r["ok"] and r["answer"]["type"] in answers:
            return {"payload": {"technique": technique, **fields,
                                "bounds": {"lower": bounds[0], "upper": bounds[1]} if bounds else None}, "result": r}
    return None
