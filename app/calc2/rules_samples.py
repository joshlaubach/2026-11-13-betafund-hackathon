"""Offline source of numerical-rule problems (midpoint, trapezoid, Simpson) and of error-bound problems: each
recipe has a table of choices; they are tried in a seeded order through the same verifier a model reply uses."""
import random

from app.calc2 import error_bounds, rules

# recipe id -> (f, rule, n, ask, values, lower, upper)
RULES = {
    "r_trap_poly": [("x^2", "trapezoid", "2", "approx", None, "0", "2"), ("x^2", "trapezoid", "4", "approx", None, "0", "2"),
                    ("x^2+1", "trapezoid", "4", "approx", None, "0", "2"), ("x^3", "trapezoid", "2", "approx", None, "0", "2"),
                    ("2*x^2", "trapezoid", "4", "approx", None, "0", "1"), ("x^2", "trapezoid", "3", "approx", None, "0", "3"),
                    ("x^2-x", "trapezoid", "4", "approx", None, "0", "2"), ("x^2", "trapezoid", "4", "approx", None, "1", "3")],
    "r_mid_poly": [("x^2", "midpoint", "2", "approx", None, "0", "2"), ("x^2", "midpoint", "4", "approx", None, "0", "2"),
                   ("x^2+1", "midpoint", "4", "approx", None, "0", "2"), ("x^3", "midpoint", "2", "approx", None, "0", "2"),
                   ("2*x^2", "midpoint", "4", "approx", None, "0", "1"), ("x^2", "midpoint", "3", "approx", None, "0", "3"),
                   ("x^2-x", "midpoint", "4", "approx", None, "0", "2"), ("x^2", "midpoint", "4", "approx", None, "1", "3")],
    "r_simpson_poly": [("x^2", "simpson", "2", "approx", None, "0", "2"), ("x^3", "simpson", "4", "approx", None, "0", "2"),
                       ("x^4", "simpson", "2", "approx", None, "0", "2"), ("x^4", "simpson", "4", "approx", None, "0", "2"),
                       ("x^3+x", "simpson", "4", "approx", None, "0", "2"), ("x^4", "simpson", "4", "approx", None, "0", "1"),
                       ("x^5", "simpson", "2", "approx", None, "0", "2"), ("x^4+1", "simpson", "2", "approx", None, "0", "2")],
    "r_trap_rational": [("1/x", "trapezoid", "4", "approx", None, "1", "3"), ("1/x", "trapezoid", "2", "approx", None, "1", "3"),
                        ("1/x", "trapezoid", "4", "approx", None, "1", "2"), ("1/x^2", "trapezoid", "4", "approx", None, "1", "3"),
                        ("1/(x+1)", "trapezoid", "4", "approx", None, "0", "2"), ("1/x", "trapezoid", "3", "approx", None, "1", "4"),
                        ("1/(1+x^2)", "trapezoid", "2", "approx", None, "0", "2")],
    "r_table": [(None, "trapezoid", "4", "table", "1,3/2,2,5/2,3", "0", "2"), (None, "trapezoid", "4", "table", "0,1,4,9,16", "0", "4"),
                (None, "trapezoid", "3", "table", "2,3,5,8", "0", "3"), (None, "trapezoid", "5", "table", "1,2,4,7,11,16", "0", "5"),
                (None, "simpson", "4", "table", "1,3/2,2,5/2,4", "0", "2"), (None, "simpson", "4", "table", "2,5,3,6,8", "1", "5"),
                (None, "simpson", "2", "table", "1,4,9", "0", "2"), (None, "simpson", "4", "table", "0,1,4,9,16", "0", "4")],
    "r_simpson_rational": [("1/x", "simpson", "4", "approx", None, "1", "3"), ("1/x", "simpson", "2", "approx", None, "1", "3"),
                           ("1/x", "simpson", "4", "approx", None, "1", "2"), ("1/(1+x^2)", "simpson", "2", "approx", None, "0", "2"),
                           ("1/x", "simpson", "4", "approx", None, "2", "4"), ("1/(x+1)", "simpson", "4", "approx", None, "0", "2")],
    "r_mid_rational": [("1/x", "midpoint", "4", "approx", None, "1", "3"), ("1/x", "midpoint", "2", "approx", None, "1", "3"),
                       ("1/x", "midpoint", "4", "approx", None, "1", "2"), ("1/(1+x^2)", "midpoint", "2", "approx", None, "0", "2"),
                       ("1/x^2", "midpoint", "4", "approx", None, "1", "3"), ("1/(x+1)", "midpoint", "4", "approx", None, "0", "2")],
    "r_root": [("sqrt(x)", "trapezoid", "4", "approx", None, "0", "4"), ("sqrt(x)", "midpoint", "2", "approx", None, "0", "4"),
               ("sqrt(x)", "simpson", "4", "approx", None, "0", "4"), ("sqrt(x)", "trapezoid", "2", "approx", None, "1", "9"),
               ("sqrt(x)", "simpson", "2", "approx", None, "0", "4"), ("sqrt(x+1)", "trapezoid", "3", "approx", None, "0", "3")],
    "r_n6_simpson": [("x^2", "simpson", "6", "approx", None, "0", "3"), ("x^2+1", "simpson", "6", "approx", None, "0", "3"),
                     ("x^2", "simpson", "6", "approx", None, "0", "6"), ("x^2-x", "simpson", "6", "approx", None, "0", "3"),
                     ("2*x^2", "simpson", "6", "approx", None, "0", "3")],
    "r_n6_trap": [("x^3", "trapezoid", "6", "approx", None, "0", "3"), ("x^3", "trapezoid", "6", "approx", None, "0", "2"),
                  ("x^3+x", "trapezoid", "6", "approx", None, "0", "3"), ("2*x^3", "trapezoid", "6", "approx", None, "0", "3"),
                  ("x^3", "trapezoid", "6", "approx", None, "1", "4")],
    "r_error_poly": [("x^3", "trapezoid", "4", "error", None, "0", "2"), ("x^3", "midpoint", "4", "error", None, "0", "2"),
                     ("x^4", "simpson", "2", "error", None, "0", "2"), ("x^2", "trapezoid", "4", "error", None, "0", "2"),
                     ("x^3", "trapezoid", "2", "error", None, "0", "2"), ("x^4", "trapezoid", "4", "error", None, "0", "2"),
                     ("x^3", "midpoint", "2", "error", None, "0", "2")],
    "r_trig": [("sin(x)", "simpson", "4", "approx", None, "0", "pi"), ("sin(x)", "trapezoid", "4", "approx", None, "0", "pi"),
               ("sin(x)", "midpoint", "4", "approx", None, "0", "pi"), ("cos(x)", "trapezoid", "2", "approx", None, "0", "pi"),
               ("sin(x)", "simpson", "2", "approx", None, "0", "pi"), ("cos(x)", "simpson", "4", "approx", None, "0", "pi")],
    "r_error_rational": [("1/x", "simpson", "4", "error", None, "1", "3"), ("1/x", "trapezoid", "4", "error", None, "1", "3"),
                         ("1/x", "midpoint", "2", "error", None, "1", "3"), ("1/x", "trapezoid", "2", "error", None, "1", "2"),
                         ("1/x", "simpson", "2", "error", None, "1", "3"), ("1/x", "midpoint", "4", "error", None, "1", "2"),
                         ("1/x", "simpson", "4", "error", None, "1", "2")],
    "r_error_misc": [("1/(1+x^2)", "trapezoid", "2", "error", None, "0", "1"), ("1/(1+x^2)", "midpoint", "2", "error", None, "0", "1"),
                     ("1/(1+x^2)", "simpson", "2", "error", None, "0", "1"), ("1/(1+x^2)", "simpson", "4", "error", None, "0", "1"),
                     ("sin(x)", "trapezoid", "2", "error", None, "0", "pi"), ("sin(x)", "midpoint", "2", "error", None, "0", "pi"),
                     ("sin(x)", "simpson", "2", "error", None, "0", "pi"), ("exp(x)", "trapezoid", "2", "error", None, "0", "2"),
                     ("exp(x)", "midpoint", "2", "error", None, "0", "2"), ("1/x^2", "midpoint", "2", "error", None, "1", "3"),
                     ("sqrt(x)", "midpoint", "2", "error", None, "0", "4"), ("1/x", "midpoint", "2", "error", None, "1", "2")],
    "r_error_ln": [("ln(x)", "trapezoid", "2", "error", None, "1", "3"), ("ln(x)", "simpson", "2", "error", None, "1", "3"),
                   ("ln(x)", "midpoint", "2", "error", None, "1", "3"), ("1/(1+x^2)", "trapezoid", "2", "error", None, "0", "1"),
                   ("sqrt(x)", "trapezoid", "2", "error", None, "0", "4"), ("sqrt(x)", "simpson", "4", "error", None, "0", "4"),
                   ("1/x^2", "trapezoid", "2", "error", None, "1", "3")],
}

def _grid(fs, rules, ns, ivs, ask="bound"):
    return [(f, r, str(n), ask, None, lo, hi) for f in fs for r in rules for n in ns for lo, hi in ivs]


def _min_n(fs, rules, eps, ivs):
    return [(f, r, None, "min_n", e, lo, hi) for f in fs for r in rules for e in eps for lo, hi in ivs]


_POLY2 = ["x^2", "3*x^2", "x^2+x", "x^2-x", "2*x^2+1", "x^2/2", "(x+1)^2", "5-x^2", "x^2+3*x+2", "4*x^2"]
_IV = [("0", "1"), ("0", "2"), ("0", "3"), ("1", "3"), ("-1", "1"), ("1", "2")]

# recipe id -> (f, rule, n, ask, eps, lower, upper). Wide pools: a packet of ten at one level should not repeat a
# problem that differs only in an interval or a coefficient.
BOUNDS = {
    "e_poly2_trap": _grid(_POLY2, ["trapezoid"], [2, 3, 4, 5, 8, 10], _IV),
    "e_poly2_mid": _grid(_POLY2, ["midpoint"], [2, 4, 5, 10], _IV),
    "e_poly3": _grid(["x^3", "x^3+x", "2*x^3", "x^3-x", "x^3+x^2", "x^3-3*x"], ["trapezoid", "midpoint"], [2, 4, 5, 10],
                     [("0", "1"), ("0", "2"), ("1", "3"), ("1", "2"), ("0", "3")]),
    "e_poly4_endpoint": _grid(["x^4", "x^4+x", "2*x^4", "x^4+x^2", "x^4-x^2"], ["trapezoid", "midpoint"], [2, 4, 5],
                              [("0", "1"), ("0", "2"), ("1", "2")]),
    "e_exp": _grid(["exp(x)", "exp(-x)", "exp(2*x)", "exp(x/2)", "3*exp(x)"], ["trapezoid", "midpoint"], [2, 4, 5, 10],
                   [("0", "1"), ("0", "2"), ("-1", "1")]),
    "e_log_root": (_grid(["ln(x)", "ln(x+1)", "2*ln(x)"], ["trapezoid", "midpoint"], [2, 4, 5],
                         [("1", "2"), ("1", "3"), ("1", "4"), ("0", "2")])
                   + _grid(["sqrt(x)", "2*sqrt(x)"], ["trapezoid", "midpoint"], [2, 4, 5],
                           [("1", "4"), ("1", "9"), ("1", "2")])),
    "e_simpson_poly": _grid(["x^4", "2*x^4", "x^4+x^2", "x^4-x^3", "x^4+x", "3*x^4+1"], ["simpson"], [2, 4],
                            [("0", "1"), ("0", "2"), ("1", "2"), ("0", "3")]),
    "e_rational": _grid(["1/x", "1/x^2", "1/(x+1)", "2/x", "1/(x+2)", "1/(2*x)"], ["trapezoid", "midpoint"], [2, 4, 5, 10],
                        [("1", "3"), ("1", "2"), ("2", "4"), ("1", "4")]),
    "e_interior": (_grid(["sin(x)", "cos(x)"], ["trapezoid", "midpoint"], [4, 6, 10], [("0", "3"), ("0", "pi")])
                   + _grid(["sin(x)", "cos(x)"], ["simpson"], [2, 4], [("0", "3"), ("0", "pi")])
                   + _grid(["x*exp(-x)", "exp(-x^2)"], ["trapezoid", "midpoint"], [4, 5, 10],
                           [("0", "4"), ("-1", "1"), ("-2", "2")])
                   + _grid(["1/(1+x^2)"], ["trapezoid", "midpoint"], [2, 4, 5, 10], [("-1", "1"), ("-2", "2"), ("0", "1")])),
    "e_simpson_exp": [("exp(x)", "simpson", "4", "bound", None, "0", "1"), ("exp(x)", "simpson", "2", "bound", None, "0", "2"),
                      ("exp(-x)", "simpson", "4", "bound", None, "0", "2"), ("1/x", "simpson", "4", "bound", None, "1", "3"),
                      ("ln(x)", "simpson", "4", "bound", None, "1", "2"), ("sqrt(x)", "simpson", "4", "bound", None, "1", "4")],
    "e_gap": (_grid(["x^3", "x^3+x", "2*x^3", "x^3-x"], ["trapezoid", "midpoint"], [2, 4], [("0", "1"), ("0", "2"), ("1", "3")], "gap")
              + _grid(["x^4", "x^4+x", "x^4-x^2"], ["trapezoid", "midpoint"], [2, 4], [("0", "1"), ("0", "2")], "gap")
              + _grid(["x^5", "x^6", "x^5+x", "x^6-x"], ["simpson"], [2, 4], [("0", "1"), ("0", "2")], "gap")
              + _grid(["1/x", "1/x^2", "1/(x+1)"], ["trapezoid", "midpoint"], [2, 4], [("1", "2"), ("1", "3")], "gap")),
    "e_min_n_trap": [("exp(x)", "trapezoid", None, "min_n", "1/1000", "0", "1"), ("x^2", "trapezoid", None, "min_n", "1/100", "0", "2"),
                     ("x^3", "midpoint", None, "min_n", "1/1000", "0", "2"), ("1/x", "trapezoid", None, "min_n", "1/100", "1", "3"),
                     ("exp(x)", "midpoint", None, "min_n", "1/10000", "0", "1"), ("x^2", "midpoint", None, "min_n", "1/1000", "0", "3"),
                     ("1/x", "midpoint", None, "min_n", "1/1000", "1", "2")],
    "e_min_n_simpson": [("exp(x)", "simpson", None, "min_n", "1/10000", "0", "1"), ("x^4", "simpson", None, "min_n", "1/1000", "0", "2"),
                        ("1/x", "simpson", None, "min_n", "1/100000", "1", "2"), ("exp(-x)", "simpson", None, "min_n", "1/10000", "0", "2"),
                        ("x^5", "simpson", None, "min_n", "1/10000", "0", "1"), ("1/x", "simpson", None, "min_n", "1/10000", "1", "3")],
    # an interior maximum of the derivative with no power of pi to estimate by hand; the last three rows have pi in
    # the interval and are used at the scientific tier only
    "e_min_n_interior": (_min_n(["exp(-x^2)", "1/(1+x^2)"], ["trapezoid", "midpoint"], ["1/100", "1/1000"], [("-1", "1")])
                         + _min_n(["1/(1+x^2)", "exp(-x^2)", "x^4-x^6/10"], ["simpson"], ["1/1000", "1/10000"],
                                  [("-1", "1")])
                         + [("exp(-x^2)", "trapezoid", None, "min_n", "1/1000", "0", "2"),
                            ("x*exp(-x)", "trapezoid", None, "min_n", "1/1000", "0", "4"),
                            ("sin(x)", "midpoint", None, "min_n", "1/1000", "0", "3"),
                            ("sin(x)", "trapezoid", None, "min_n", "1/100", "0", "3"),
                            ("sin(x)", "simpson", None, "min_n", "1/10000", "0", "3"),
                            ("sin(x)", "trapezoid", None, "min_n", "1/1000", "0", "pi"),
                            ("cos(x)", "midpoint", None, "min_n", "1/10000", "0", "pi"),
                            ("sin(x)", "simpson", None, "min_n", "1/100000", "0", "pi")]),
}


def _run(table, verify, recipe, axes, answers, calculator, seed, limit):
    rng = random.Random(seed)
    rows = list(table.get(recipe["id"], []))
    rng.shuffle(rows)
    full = {"recipe": recipe["id"], **axes}
    for f, rule, n, ask, extra, lo, hi in rows[:limit]:
        r = verify(f, rule, n, ask, extra, [lo, hi], full, calculator)
        if r["ok"] and r["answer"]["type"] in answers:
            return {"payload": {"f": f or "", "rule": rule, "n": n or "", "ask": ask, "extra": extra,
                                "bounds": {"lower": lo, "upper": hi}}, "result": r}
    return None


def generate(recipe: dict, axes: dict, answers: set[str], calculator: str = "none", seed: int = 0,
             limit: int = 60) -> dict | None:
    """Numerical rules (topic numerical_integration.rules)."""
    return _run(RULES, rules.verify, recipe, axes, answers, calculator, seed, limit)


def generate_bounds(recipe: dict, axes: dict, answers: set[str], calculator: str = "none", seed: int = 0,
                    limit: int = 60) -> dict | None:
    """Error bounds (topic numerical_integration.error_bounds): eps is the 'extra' field of the row."""
    return _run(BOUNDS, lambda f, rule, n, ask, eps, b, ax, calc: error_bounds.verify(f, rule, n, ask, eps, b, ax, calc),
                recipe, axes, answers, calculator, seed, limit)
