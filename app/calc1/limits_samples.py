"""Offline source of limits and continuity problems. Each recipe has a pool of payloads (the reply a good model
would give for the recipe's assigned axes); they are tried in a seeded order through app/calc1/limits.verify, the same
verifier a model reply goes through. The pools are built from small grids so a packet of ten at one level does
not repeat a problem that differs only in a coefficient."""
import itertools
import random

from app.calc1 import limits

R = range


def _alg_factor_lin():
    out = [(f"(x^2-{a * a})/(x-{a})", str(a)) for a in R(1, 8)]
    out += [(f"(x^2-{a + b}*x+{a * b})/(x-{a})", str(a)) for a in R(1, 7) for b in R(1, 7) if b != a]
    out += [(f"({k}*x^2-{k * a * a})/(x-{a})", str(a)) for a in R(1, 6) for k in (2, 3, 5)]
    return out


def _alg_factor_quad():
    out = [(f"(x^2-{a + b}*x+{a * b})/(x^2-{a + c}*x+{a * c})", str(a))
           for a in R(1, 6) for b in R(1, 6) for c in R(1, 6) if len({a, b, c}) == 3 and b < c]
    out += [(f"(x^3-{a ** 3})/(x-{a})", str(a)) for a in R(1, 6)]
    out += [(f"(x^3-{a ** 3})/(x^2-{a * a})", str(a)) for a in R(1, 6)]
    out += [(f"(x^2+{a}*x)/(x^2-{a * a})", str(-a)) for a in R(1, 7)]
    return out


def _alg_conjugate():
    out = [(f"(sqrt(x+{m * m - a})-{m})/(x-{a})", str(a)) for m in R(2, 6) for a in R(-3, 6)
           if a != 0 and m * m - a > 0 and m * m - a < 30 and a * 1 + (m * m - a) == m * m]
    out += [(f"(sqrt(x+{m * m})-{m})/x", "0") for m in R(2, 7)]
    out += [(f"(x-{m * m})/(sqrt(x)-{m})", str(m * m)) for m in R(2, 7)]
    out += [(f"({m}-sqrt({m * m}-x))/x", "0") for m in R(2, 7)]
    out += [(f"(sqrt(x^2+{m * m - a * a})-{m})/(x-{a})", str(a)) for m in R(3, 7) for a in R(1, 4) if m * m > a * a]
    return out


def _alg_complex():
    out = [(f"(1/x-1/{a})/(x-{a})", str(a)) for a in R(1, 9)]
    out += [(f"(1/(x+{h})-1/{h + a})/(x-{a})", str(a)) for h in R(1, 4) for a in R(1, 6)]
    out += [(f"(1/(x+{h})-1/{h})/x", "0") for h in R(1, 9)]
    out += [(f"({a}/x-1)/(x-{a})", str(a)) for a in R(2, 9)]
    return out


def _alg_conj_two():
    out = [(f"(sqrt(x+{p})-sqrt({q}*x+{r}))/(x-{a})", str(a)) for a in R(1, 6) for q in (2, 3) for p in R(1, 9)
           for r in [a + p - q * a] if r > 0 and p != r]
    out += [(f"(sqrt(x+{m * m - a})-{m})/(x^2-{a * a})", str(a)) for m in R(2, 6) for a in R(1, 5) if m * m > a]
    return out


def _alg_complex_deep():
    out = [(f"(1/({k}+x)^2-1/{k * k})/x", "0") for k in R(1, 7)]
    out += [(f"(1/sqrt(x+{m * m - a})-1/{m})/(x-{a})", str(a)) for m in R(2, 6) for a in R(1, 5) if m * m > a]
    out += [(f"(1/(x+{k})-1/{k + 1})/(x^2-1)", "1") for k in R(1, 6)]
    out += [(f"({k}/(x+1)-{k}/2)/(x-1)", "1") for k in R(1, 8)]
    return out


ALGEBRAIC = {"a_factor_lin": _alg_factor_lin(), "a_factor_quad": _alg_factor_quad(), "a_conjugate": _alg_conjugate(),
             "a_complex": _alg_complex(), "a_conj_two": _alg_conj_two(), "a_complex_deep": _alg_complex_deep()}


def _rows(recipes: dict, names: tuple, kw=None):
    return {k: [dict(zip(names, r)) for r in v] for k, v in recipes.items()}


def _a(f, a):
    return {"f": f, "a": a}


ASKS_LR = ("left", "right")


def _one_sided():
    out = {}
    out["os_abs"] = [(f"Abs(x-{a})/(x-{a})", str(a), ask) for a in R(-3, 6) for ask in ("left", "right", "pair")]
    out["os_abs"] += [(f"{k}*Abs(x-{a})/(x-{a})", str(a), ask) for a in R(-2, 5) for k in (2, 3) for ask in ("left", "right", "pair")]
    out["os_piece"] = [(f"Piecewise(({m}*x+{c}, x<{a}), ({d}-x, x>={a}))", str(a), ask)
                       for a in R(0, 5) for m in (1, 2, 3) for c in (1, -1) for d in (4, 7) for ask in ASKS_LR + ("pair", "two_sided")]
    out["os_root"] = [(f"sqrt(x-{a})", str(a), "right") for a in R(1, 9)]
    out["os_root"] += [(f"sqrt({a}-x)", str(a), "left") for a in R(1, 9)]
    out["os_root"] += [(f"{k}*sqrt(x+{a})-1", str(-a), "right") for a in R(1, 6) for k in (2, 3)]
    out["os_rational"] = [(f"1/(x-{a})", str(a), ask) for a in R(-3, 6) for ask in ("left", "right", "two_sided")]
    out["os_rational"] += [(f"{k}/(x-{a})", str(a), ask) for a in R(-2, 5) for k in (2, 3, 5) for ask in ("left", "right")]
    out["os_rational"] += [(f"-1/(x-{a})", str(a), ask) for a in R(-2, 5) for ask in ("left", "right", "two_sided")]
    out["os_abs_ratio"] = [(f"Abs(x^2-{a * a})/(x-{a})", str(a), ask) for a in R(1, 7) for ask in ("left", "right", "pair", "two_sided")]
    out["os_abs_ratio"] += [(f"Abs({k}*x-{k * a})/(x^2-{a * a})", str(a), ask)
                            for a in R(1, 6) for k in (1, 2, 3) for ask in ("left", "right", "pair")]
    return {k: [dict(zip(("f", "a", "ask"), r)) for r in v] for k, v in out.items()}


def _infinite():
    out = {}
    out["inf_simple"] = [(f"{n}/(x-{a})", str(a), ask) for a in R(-3, 6) for n in (1, 2, 3, -1) for ask in ("left", "right", "two_sided")]
    out["inf_simple"] += [(f"(x+{c})/(x-{a})", str(a), ask) for a in R(1, 6) for c in R(1, 5) for ask in ("left", "right", "two_sided")]
    out["inf_squared"] = [(f"{n}/(x-{a})^2", str(a), "two_sided") for a in R(-3, 6) for n in (1, 2, 3, -1, -2)]
    out["inf_squared"] += [(f"(x+{c})/(x-{a})^2", str(a), "two_sided") for a in R(1, 6) for c in R(1, 5)]
    out["inf_two_limit"] = [(f"x/((x-{a})*(x+{b}))", str(a), ask) for a in R(1, 6) for b in R(1, 6) for ask in ("left", "right", "two_sided")]
    out["inf_two_limit"] += [(f"({c}-x)/((x-{a})*(x+{b}))", str(-b), ask)
                             for a in R(1, 5) for b in R(1, 5) for c in (1, 2, 6) for ask in ("left", "right")]
    out["inf_asym_two"] = [(f"x/((x-{a})*(x+{b}))", "0", "asymptotes") for a in R(1, 7) for b in R(1, 7) if a != b]
    out["inf_asym_two"] += [(f"1/(x^2-{a * a})", "0", "asymptotes") for a in R(1, 8)]
    out["inf_asym_two"] += [(f"(x+{c})/(x^2-{a + b}*x+{a * b})", "0", "asymptotes") for a in R(1, 5) for b in R(1, 5) for c in R(1, 4) if a < b]
    out["inf_hole"] = [(f"(x-{a})/((x-{a})*(x+{b}))", "0", "asymptotes") for a in R(1, 7) for b in R(1, 6)]
    out["inf_hole"] += [(f"(x^2-{a * a})/((x-{a})*(x+{b}))", "0", "asymptotes") for a in R(1, 6) for b in R(1, 6) if b != a]
    out["inf_hole"] += [(f"(x+{a})/((x+{a})*(x-{b})^2)", "0", "asymptotes") for a in R(1, 6) for b in R(1, 6) if a != -b]
    return {k: [dict(zip(("f", "a", "ask"), r)) for r in v] for k, v in out.items()}


def _at_infinity():
    out = {}
    dirs = ("oo", "-oo")
    out["ai_lower"] = [(f"({a}*x+{b})/(x^2+{c})", d, "limit") for a in R(1, 6) for b in R(1, 4) for c in R(1, 4) for d in dirs]
    out["ai_lower"] += [(f"{a}/(x-{b})", d, "limit") for a in R(1, 6) for b in R(1, 6) for d in dirs]
    out["ai_same"] = [(f"({a}*x^2+{b})/({c}*x^2-{e})", d, "limit") for a in R(1, 6) for c in R(1, 6) for b in (1, 5) for e in (1, 3) for d in dirs]
    out["ai_same"] += [(f"({a}*x+1)/({c}*x-2)", d, "limit") for a in R(1, 8) for c in R(1, 8) for d in dirs]
    out["ai_higher"] = [(f"({a}*x^3+{b})/({c}*x^2+1)", d, "limit") for a in R(1, 5) for c in R(1, 5) for b in (1, 4) for d in dirs]
    out["ai_higher"] += [(f"(x^2+{b}*x)/({c}*x+1)", d, "limit") for b in R(1, 5) for c in R(1, 5) for d in dirs]
    out["ai_radical"] = [(f"({a}*x+{b})/sqrt({c}*x^2+{e})", d, "limit")
                         for a in R(1, 5) for b in (1, 3) for c in (1, 4, 9) for e in (1, 2) for d in dirs]
    out["ai_radical"] += [(f"sqrt({c}*x^2+1)/(x+{b})", d, "limit") for c in (1, 4, 9) for b in R(1, 5) for d in dirs]
    out["ai_conjugate"] = [(f"sqrt(x^2+{a}*x)-x", "oo", "limit") for a in R(1, 9)]
    out["ai_conjugate"] += [(f"sqrt(x^2+{a}*x+{b})-sqrt(x^2+{c}*x)", "oo", "limit") for a in R(1, 6) for b in (1, 2) for c in R(1, 5) if a != c]
    out["ai_conjugate"] += [(f"x-sqrt(x^2-{a}*x)", "oo", "limit") for a in R(1, 9)]
    out["ai_horizontal"] = [(f"({a}*x+{b})/sqrt(x^2+{c})", "oo", "horizontal") for a in R(1, 6) for b in (1, 3) for c in (1, 2, 5)]
    out["ai_horizontal"] += [(f"({a}*x^2+1)/({c}*x^2-1)", "oo", "horizontal") for a in R(1, 6) for c in R(1, 6)]
    out["ai_horizontal"] += [(f"{a}*atan(x)+{b}", "oo", "horizontal") for a in R(1, 5) for b in R(1, 4)]
    out["ai_horizontal"] += [(f"(exp(x)-{a}*exp(-x))/(exp(x)+exp(-x))", "oo", "horizontal") for a in R(1, 6)]
    out["ai_exp"] = [(f"({a}*exp(x)+{b})/(exp(x)+{c})", d, "limit") for a in R(1, 5) for b in (1, 2) for c in (1, 3) for d in dirs]
    out["ai_exp"] += [(f"({a}+exp(-x))/({c}+{e}*exp(-x))", "oo", "limit") for a in R(1, 5) for c in R(1, 5) for e in (1, 2)]
    return {k: [dict(zip(("f", "direction", "ask"), r)) for r in v] for k, v in out.items()}


def _squeeze():
    out = {}
    out["sq_basic"] = [(f"x^{n}", o, "0", "0", "given") for n in (1, 2, 3, 4) for o in ("sin(1/x)", "cos(1/x)")]
    out["sq_basic"] += [(f"{k}*x^2", o, "0", c, "given") for k in (2, 3, 5) for o in ("sin(1/x)", "cos(1/x)") for c in ("0", "1")]
    out["sq_basic"] += [(p_, o, "oo", c, "given") for p_ in ("1/x", "2/x", "3/x", "1/x^2", "5/x") for o in ("sin(x)", "cos(x)", "sin(2*x)", "cos(3*x)")
                        for c in ("0", "1")]
    out["sq_find"] = [(f"x^{n}", o, "0", "0", "find") for n in (1, 2, 3, 4) for o in ("sin(1/x)", "cos(1/x)", "sin(1/x^2)", "cos(2/x)")]
    out["sq_find"] += [(f"x^{n}", o, "0", str(c), "find") for n in (1, 2) for o in ("sin(1/x)", "cos(1/x)") for c in (1, 2, 5)]
    out["sq_find"] += [(f"x^{n}*{k}", o, "0", "0", "find") for n in (2, 3) for k in (2, 3) for o in ("sin(1/x)", "cos(1/x)")]
    out["sq_square"] = [(f"x^{n}", o, "0", c, "find") for n in (1, 2, 3, 4) for o in ("sin(1/x)^2", "cos(1/x)^2", "sin(1/x^2)^2")
                        for c in ("0", "1", "3")]
    out["sq_infinity"] = [(p_, o, d, "0", "find") for p_ in ("1/x", "1/x^2", "2/x", "1/x^3") for o in ("sin(x)", "cos(x)", "sin(x^2)", "cos(2*x)", "sin(x)^2", "cos(x)^2")
                          for d in ("oo", "-oo")]
    out["sq_infinity"] += [(p_, o, "oo", str(c), "find") for p_ in ("1/x", "1/x^2", "3/x") for o in ("sin(x)", "cos(x)", "cos(5*x)", "sin(x)^2")
                           for c in (1, 2, 4)]
    return {k: [dict(zip(("p", "osc", "a", "c", "ask"), r)) for r in v] for k, v in out.items()}


def _epsilon_delta():
    out = {}
    out["ed_linear"] = [(f"{m}*x+{b}", str(a), e) for m in (2, 3, 4, 5, -2, -3) for b in (1, -1, 4) for a in (1, 2, 3, -1)
                        for e in ("1/2", "1/5", "1/10", "3/10", "1/100")]
    out["ed_quadratic"] = [(f"x^2+{b}", str(a), e) for a in (1, 2, 3, 4) for b in (0, 1, 3) for e in ("1/2", "1/4", "1/10", "1/100", "3/10")]
    out["ed_quadratic"] += [(f"{k}*x^2", str(a), e) for k in (2, 3) for a in (1, 2) for e in ("1/2", "1/10", "1/100")]
    out["ed_root"] = [(f"sqrt(x+{b})", str(a), e) for b in (0, 1, 2, 5) for a in (0, 1, 2, 4, 7) for e in ("1/2", "1/4", "1/10", "1/100")
                      if int((a + b) ** 0.5) ** 2 == a + b and a + b > 0]
    out["ed_root"] += [(f"sqrt({k}*x+1)", str(a), e) for k in (2, 3, 4) for a in (0, 1, 2, 4, 12) for e in ("1/2", "1/10", "1/4")
                       if int((k * a + 1) ** 0.5) ** 2 == k * a + 1]
    out["ed_rational"] = [(f"1/(x+{b})", str(a), e) for b in (0, 1, 2) for a in (1, 2, 3, 4) for e in ("1/2", "1/4", "1/10", "1/100")]
    out["ed_rational"] += [(f"{k}/x", str(a), e) for k in (2, 3, 4) for a in (1, 2, 4) for e in ("1/2", "1/4", "1/10", "1/20")]
    return {k: [dict(zip(("f", "a", "eps"), r)) for r in v] for k, v in out.items()}


def _classify():
    out = {}
    out["cl_hole"] = [(f"(x^2-{a * a})/(x-{a})", str(a)) for a in R(-5, 7) if a != 0]
    out["cl_hole"] += [(f"(x^2+{a + b}*x+{a * b})/(x+{a})", str(-a)) for a in R(1, 6) for b in R(1, 6) if a != b]
    out["cl_hole"] += [(f"(x-{a})/(x^2-{a * a})", str(a)) for a in R(1, 8)]
    out["cl_pole"] = [(f"{n}/(x-{a})", str(a)) for a in R(-4, 6) for n in (1, 2, 5)]
    out["cl_pole"] += [(f"(x+{c})/(x-{a})^2", str(a)) for a in R(1, 6) for c in (1, 2, 3)]
    out["cl_pole"] += [(f"x/(x^2-{a * a})", str(a)) for a in R(1, 7)]
    out["cl_jump"] = [(f"Piecewise(({m}*x+{c}, x<{a}), ({d}-x, x>={a}))", str(a))
                      for a in R(0, 5) for m in (1, 2, 3) for c in (1, -2) for d in (4, 9)]
    out["cl_abs"] = [(f"{k}*Abs(x-{a})/(x-{a})", str(a)) for a in R(-3, 6) for k in (1, 2, 3, 5)]
    out["cl_abs"] += [(f"Abs(x-{a})/(x-{a})+{c}", str(a)) for a in R(-2, 5) for c in (1, 2, 3)]
    out["cl_abs"] += [(f"(x^2-{a * a})/Abs(x-{a})", str(a)) for a in R(1, 7)]
    out["cl_redefined"] = [(f"Piecewise((x+{c}, x<{a}), ({v}, Eq(x, {a})), (x+{c}, x>{a}))", str(a))
                           for a in R(-2, 5) for c in (1, 2, 3) for v in (0, 7, 10) if v != a + c]
    out["cl_redefined"] += [(f"Piecewise(((x^2-{a * a})/(x-{a}), x<{a}), ({v}, Eq(x, {a})), ({2 * a}*x/{a}, x>{a}))", str(a))
                            for a in R(1, 6) for v in (1, 3, 11) if v != 2 * a]
    poles = ["1/(x-{a})", "1/(x-{a})^2", "x/(x-{a})", "(x+1)/(x-{a})", "1/(x-{a})^3"]
    others = ["{n}", "x+{n}", "x^2+{n}", "{n}*x", "Abs(x)+{n}"]
    out["cl_mixed"] = [(f"Piecewise(({pl.format(a=a)}, x<{a}), ({ot.format(n=n)}, x>={a}))", str(a))
                       for pl in poles for ot in others for a in R(1, 5) for n in (1, 3)]
    out["cl_mixed"] += [(f"Piecewise(({ot.format(n=n)}, x<{a}), ({pl.format(a=a)}, x>{a}))", str(a))
                        for pl in poles for ot in others for a in R(1, 5) for n in (2,)]
    return {k: [dict(zip(("f", "a"), r)) for r in v] for k, v in out.items()}


def _make_continuous():
    out = {}
    out["mc_linear"] = [(f"Piecewise((k*x+{b}, x<{a}), (x^2-{c}, x>={a}))", "k") for a in (1, 2, 3, -1, -2) for b in (1, 2, -1, 3)
                        for c in (1, 2, 5, 7)] + [(f"Piecewise((x+{b}, x<{a}), (k*x^2, x>={a}))", "k")
                                                  for a in (1, 2, 3) for b in (1, 2, 3, 5)]
    out["mc_hole"] = [(f"Piecewise(((x^2-{a * a})/(x-{a}), x<{a}), (k*x+{b}, x>={a}))", "k") for a in (1, 2, 3, 4, 5) for b in (1, 2, 3, -1)]
    out["mc_hole"] += [(f"Piecewise(((x^2-{a + b}*x+{a * b})/(x-{a}), x<{a}), (k, x>={a}))", "k") for a in (1, 2, 3, 4) for b in (1, 2, 5, 6) if b != a]
    out["mc_hole"] += [(f"Piecewise((k, x<{a}), ((x^3-{a ** 3})/(x-{a}), x>={a}))", "k") for a in (1, 2, 3)]
    out["mc_trig_exp"] = [(f"Piecewise((sin({c}*x)/x, x<0), (k+{d}, x>=0))", "k") for c in (2, 3, 5) for d in (1, 2)]
    out["mc_trig_exp"] += [(f"Piecewise((k*exp(x), x<0), ({c}*x+{d}, x>=0))", "k") for c in (1, 2, 3) for d in (2, 3, 5)]
    out["mc_trig_exp"] += [(f"Piecewise(({c}*cos(x), x<0), (k*x+{d}, x>=0))", "k") for c in (1, 2, 3) for d in (1, 2, 4)]
    out["mc_two"] = [(f"Piecewise((k*x+{b}, x<1), (x^2+m, x<{c}), ({d}*x-{e}, x>={c}))", "k,m")
                     for b in (1, 2) for c in (2, 3) for d in (2, 3) for e in (1, 2, 5)]
    out["mc_two"] += [(f"Piecewise((x+{b}, x<0), (k*x+m, x<2), ({d}-x, x>=2))", "k,m") for b in (1, 2, 3) for d in (5, 7, 9)]
    return {k: [dict(zip(("f", "params"), r)) for r in v] for k, v in out.items()}


def _ivt():
    out = {}
    out["ivt_cubic"] = [(f"x^3+{b}*x-{c}", str(lo), str(lo + w)) for b in (1, 2, 3) for c in (1, 2, 4, 5, 7) for lo in (0, -1, 1)
                        for w in (2, 3)]
    out["ivt_cubic"] += [(f"x^3-{b}*x-{c}", "0", str(w)) for b in (1, 2) for c in (3, 5, 10) for w in (3, 4)]
    out["ivt_quartic"] = [(f"x^4+{b}*x-{c}", "0", str(w)) for b in (1, 2, 3) for c in (2, 5, 10, 20) for w in (3, 4)]
    out["ivt_quartic"] += [(f"x^4-{b}*x^2-{c}", "0", str(w)) for b in (1, 2, 3) for c in (3, 7, 12) for w in (3, 4)]
    out["ivt_exp"] = [(f"exp(x)-{c}*x-{d}", "0", str(w)) for c in (1, 2) for d in (3, 5, 8) for w in (2, 3, 4)]
    out["ivt_exp"] += [(f"exp(x)-{c}", "0", str(w)) for c in (2, 3, 5, 10, 15, 30) for w in (2, 3, 4)]
    out["ivt_exp"] += [(f"x*exp(x)-{c}", "0", str(w)) for c in (1, 2, 5, 10) for w in (2, 3, 4)]
    out["ivt_trig"] = [(f"cos(x)-{c}*x", "0", str(w)) for c in (1, 2, 3) for w in (1, 2)]
    out["ivt_trig"] += [(f"sin(x)-x+{c}", "0", str(w)) for c in (1, 2, 3) for w in (2, 3, 4)]
    out["ivt_trig"] += [(f"x-{c}*cos(x)", "0", str(w)) for c in (2, 3) for w in (2, 3)]
    out["ivt_trig"] += [(f"x^2-{c}*sin(x)-1", "0", str(w)) for c in (1, 2, 3) for w in (2, 3)]
    out["ivt_trig"] += [(f"x+{c}*sin(x)-{d}", "0", str(w)) for c in (1, 2) for d in (2, 3, 5) for w in (1, 2, 3, 4)]
    return {k: [dict(zip(("f", "lo", "hi"), r)) for r in v] for k, v in out.items()}


TABLES = {"algebraic": {k: [dict(zip(("f", "a"), r)) for r in v] for k, v in ALGEBRAIC.items()},
          "one_sided": _one_sided(), "infinite": _infinite(), "at_infinity": _at_infinity(), "squeeze": _squeeze(),
          "epsilon_delta": _epsilon_delta(), "classify_discontinuity": _classify(),
          "make_continuous": _make_continuous(), "ivt": _ivt()}


def generate(stem: str, recipe: dict, axes: dict, answers: set[str], calculator: str = "none", seed: int = 0,
             limit: int = 120) -> dict | None:
    rng = random.Random(seed)
    rows = list(TABLES[stem].get(recipe["id"], []))
    rng.shuffle(rows)
    full = {"recipe": recipe["id"], **axes}
    for payload in rows[:limit]:
        r = limits.verify(stem, axes=full, calculator=calculator, **payload)
        if r["ok"] and r["answer"]["type"] in answers:
            return {"payload": payload, "result": r}
    return None
