"""Offline source of derivative problems (milestone a of C2). Each recipe has a pool of payloads (the reply a good
model would give for the recipe's assigned axes); they are tried in a seeded order through app/calc1/derivatives.verify,
the same verifier a model reply goes through. Pools are grids, so a packet of ten does not repeat a problem that
differs only in a coefficient."""
import itertools
import random

from app.calc1 import derivatives

R = range
PTS = ("0", "1", "2", "-1", "3", "1/2", "4", "9")


def _t(c, body):
    """c*body without a leading 1*."""
    return body if c == 1 else f"{c}*{body}"


def _sum(*terms):
    return "+".join(terms).replace("+-", "-")


def _power_rule():
    out = {}
    out["pr_mono"] = [(_t(c, f"x^{n}"), "x") for n in R(2, 9) for c in (1, 2, 3, 5, -4)]
    out["pr_mono"] += [(_sum(f"x^{n}", f"{c}*x"), "x") for n in R(2, 8) for c in (2, 3, 5, 7)]
    out["pr_poly"] = [(_sum(_t(a, f"x^{n}"), f"{b}*x^{m}", str(c)), at)
                      for n in (4, 5, 6) for m in (2, 3) for a in (1, 2, 3) for b in (-2, 3, 5) for c in (7, -1)
                      for at in ("x", "1", "2", "-1")]
    out["pr_poly"] += [(_sum(f"{a}*x^3", f"{b}*x^2", f"{c}*x", str(d)), at)
                       for a in (1, 2, 4) for b in (-3, 5) for c in (2, -6) for d in (1, 9) for at in ("x", "1", "-2")]
    out["pr_root"] = [(_sum(_t(c, "sqrt(x)"), f"{b}*x"), at) for c in (1, 2, 3, 6) for b in (1, 4, -5)
                      for at in ("x", "4", "9", "1")]
    out["pr_root"] += [(_sum(_t(c, f"1/x^{n}"), f"{b}*x^2"), at) for c in (1, 2, 3, 5) for n in (1, 2, 3) for b in (1, -3)
                       for at in ("x", "1", "2", "-1")]
    out["pr_root"] += [(f"{c}/sqrt(x)", at) for c in (1, 2, 4, 6) for at in ("x", "4", "1", "9")]
    out["pr_mixed"] = [(_sum(f"{a}*x^(3/2)", f"{b}/x", f"{c}*sqrt(x)"), at) for a in (2, 4, 6) for b in (1, 3, -2)
                       for c in (1, 5, 8) for at in ("x", "4", "1", "9")]
    out["pr_mixed"] += [(_sum(f"{a}*x^(2/3)", f"{b}/x^2", f"{c}*x^3"), at) for a in (3, 6) for b in (1, 2, -4)
                        for c in (1, 2, 5) for at in ("x", "1", "8")]
    out["pr_mixed"] += [(_sum(f"x^(5/2)", f"{a}/x^3", f"{b}*sqrt(x)", f"{c}"), at) for a in (2, 3, 5) for b in (2, 4, 6)
                        for c in (1, 7) for at in ("x", "4", "1")]
    return {k: [dict(f=f, at=at) for f, at in v] for k, v in out.items()}


def _trig():
    out = {}
    out["tr_basic"] = [(_sum(_t(a, "sin(x)"), _t(b, "cos(x)")), "x") for a in (1, 2, 3, 5, -4) for b in (1, 2, 3, -2, 4)]
    out["tr_basic"] += [(_t(a, "sin(x)"), "x") for a in (1, 2, 3, 7, -5)] + [(_t(a, "cos(x)"), "x") for a in (1, 2, 3, 7, -5)]
    out["tr_sum"] = [(_sum(_t(a, "sin(x)"), f"{b}*x^2", _t(c, "cos(x)")), at) for a in (1, 2, 3) for b in (1, 4, -3)
                     for c in (1, 2, 5) for at in ("x", "0", "pi/2", "pi")]
    out["tr_sum"] += [(_sum(_t(a, "tan(x)"), f"{b}*x"), at) for a in (1, 2, 3, 5) for b in (1, 2, 4, -3)
                      for at in ("x", "0", "pi/4")]
    out["tr_other"] = [(_sum(_t(a, "sec(x)"), _t(b, "tan(x)")), at) for a in (1, 2, 3) for b in (1, 2, 4, -3)
                       for at in ("x", "0", "pi/4", "pi/3")]
    out["tr_other"] += [(_sum(_t(a, "csc(x)"), _t(b, "cot(x)")), at) for a in (1, 2, 3) for b in (1, 2, 4, -3)
                        for at in ("x", "pi/2", "pi/4", "pi/6")]
    out["tr_other"] += [(_sum(_t(a, "cot(x)"), f"{b}*x^2"), at) for a in (1, 2, 3) for b in (1, 2, 5)
                        for at in ("x", "pi/4", "pi/2")]
    ks = (2, 3, 4, 5)
    out["tr_arg"] = [(_t(a, f"sin({k}*x)"), at) for a in (1, 2, 3, -2) for k in ks for at in ("x", "0", "pi/6")]
    out["tr_arg"] += [(_sum(_t(a, f"cos({k}*x)"), f"{b}*x"), at) for a in (1, 3, 5) for k in ks for b in (2, -1)
                      for at in ("x", "0", "pi/4")]
    out["tr_arg"] += [(_t(a, f"tan({k}*x)"), at) for a in (1, 2, 3) for k in (2, 3, 4) for at in ("x", "0", "pi/8")]
    out["tr_arg"] += [(_sum(f"sec({k}*x)", f"{b}*sin(x)"), at) for k in (2, 3) for b in (1, 2, 4) for at in ("x", "0", "pi/6")]
    out["tr_arg"] += [(_sum(_t(a, f"cot({k}*x)"), f"{b}*x"), at) for a in (1, 2, 3) for k in (2, 3, 4) for b in (1, 3)
                      for at in ("x", "pi/8", "pi/4")]
    out["tr_arg"] += [(_t(a, f"csc({k}*x)"), at) for a in (1, 2, 3) for k in (2, 3, 4) for at in ("x", "pi/6", "pi/4")]
    out["tr_arg"] += [(_sum(f"csc({k}*x)", f"{b}*x^2"), at) for k in (2, 3) for b in (1, 4, -3) for at in ("x", "pi/6")]
    out["tr_mixed"] = [(_sum(f"{a}*sin({k}*x)", f"{b}*tan(x)", f"{c}*cos({m}*x)", f"x^{n}"), at)
                       for a in (2, 3) for k in (2, 3) for b in (1, 2) for c in (1, 4, -2) for m in (2, 5) for n in (2, 3)
                       for at in ("x", "0", "pi/4")]
    out["tr_mixed"] += [(_sum(f"{a}*sec({k}*x)", f"{b}*cot(x)", f"{c}*x^2", f"{d}*sin(x)"), at)
                        for a in (1, 2, 3) for k in (2, 3) for b in (1, 4) for c in (3, -2) for d in (1, 5)
                        for at in ("x", "pi/4", "pi/6")]
    return {k: [dict(f=f, at=at) for f, at in v] for k, v in out.items()}


def _exp_log():
    out = {}
    out["el_basic"] = [(_sum(_t(a, "exp(x)"), f"{b}*x^2"), at) for a in (1, 2, 3, 5, -2) for b in (1, 3, -4)
                       for at in ("x", "0", "1")]
    out["el_basic"] += [(_sum(_t(a, "ln(x)"), f"{b}*x"), at) for a in (1, 2, 3, 5, -2) for b in (1, 4, -3)
                        for at in ("x", "1", "2", "e")]
    out["el_basic"] += [(_sum(_t(a, "exp(x)"), _t(b, "ln(x)")), at) for a in (1, 2, 4) for b in (1, 3, 5) for at in ("x", "1")]
    out["el_base"] = [(_sum(_t(a, f"{b}^x"), f"{c}*x"), at) for a in (1, 2, 3) for b in (2, 3, 5, 10) for c in (1, -2, 4)
                      for at in ("x", "0", "1")]
    out["el_logb"] = [(_sum(_t(a, f"log(x)/log({b})"), f"{c}*x^2"), "x") for a in (1, 2, 5) for b in (2, 3, 10) for c in (1, 3)]
    out["el_logb"] += [(_sum(_t(a, f"log(x)/log({b})"), f"{c}*x"), "x") for a in (1, 3, 4) for b in (2, 3, 5, 10) for c in (1, -2, 5)]
    out["el_arg"] = [(_t(a, f"exp({k}*x)"), at) for a in (1, 2, 3, -5) for k in (2, 3, 4, -1, 5) for at in ("x", "0", "1")]
    out["el_arg"] += [(_sum(_t(a, f"ln({k}*x)"), f"{b}*x"), at) for a in (2, 3, 5) for k in (2, 3, 4) for b in (1, -2)
                      for at in ("x", "1", "2")]
    out["el_arg"] += [(_sum(f"{a}^({k}*x)", f"{b}*x"), at) for a in (2, 3, 5) for k in (2, 3) for b in (1, 4)
                      for at in ("x", "0", "1")]
    out["el_mixed"] = [(_sum(f"{a}*exp({k}*x)", f"{b}*ln(x)", f"{c}^x", f"{d}*x^2"), at)
                       for a in (2, 3) for k in (2, 3) for b in (1, 4, 5) for c in (2, 3) for d in (1, 5)
                       for at in ("x", "0", "1")]
    out["el_mixed"] += [(_sum(f"{a}*exp(x)", f"{b}*ln(x)", f"{c}^x", f"{d}*x^2"), at) for a in (1, 2, 3, 5)
                        for b in (1, 4, 5) for c in (2, 3, 5) for d in (1, 5, -2) for at in ("x", "0", "1")]
    out["el_mixed"] += [(_sum(f"{a}*exp(x)", f"{b}*log(x)/log({c})", f"{d}*ln({k}*x)"), at)
                        for a in (1, 3) for b in (1, 2) for c in (2, 3, 5) for d in (2, 4) for k in (2, 3)
                        for at in ("x", "1")]
    return {k: [dict(f=f, at=at) for f, at in v] for k, v in out.items()}


def _inverse_trig():
    out = {}
    out["it_basic"] = [(_sum(_t(a, "asin(x)"), f"{b}*x"), at) for a in (1, 2, 3, 5, -2) for b in (1, 2, -3)
                       for at in ("x", "0", "1/2")]
    out["it_basic"] += [(_sum(_t(a, "atan(x)"), f"{b}*x^2"), at) for a in (1, 2, 3, 5, -4) for b in (1, 3, -2)
                        for at in ("x", "0", "1", "-1")]
    out["it_basic"] += [(_sum(_t(a, "acos(x)"), f"{b}*x"), at) for a in (1, 2, 4) for b in (1, -5) for at in ("x", "0", "1/2")]
    out["it_basic"] += [(_sum(_t(a, "acot(x)"), f"{b}*x"), at) for a in (1, 3, 4) for b in (2, -1) for at in ("x", "1", "0")]
    out["it_arg"] = [(_t(a, f"atan({k}*x)"), at) for a in (1, 2, 3, 6) for k in (2, 3, 4, 5) for at in ("x", "0", "1")]
    out["it_arg"] += [(_sum(_t(a, f"asin({k}*x)"), f"{b}*x"), at) for a in (1, 2, 3) for k in (2, 3) for b in (1, -2)
                      for at in ("x", "0", "1/6", "1/4")]
    out["it_arg"] += [(_sum(_t(a, f"acos({k}*x)"), f"{b}*x^2"), at) for a in (1, 2, 4) for k in (2, 3) for b in (1, 5)
                      for at in ("x", "0", "1/4")]
    out["it_mixed"] = [(_sum(f"{a}*asin(x)", f"{b}*atan({k}*x)", f"{c}*x^2"), at) for a in (2, 3, 5) for b in (1, 4)
                       for k in (2, 3) for c in (1, -3) for at in ("x", "0", "1/2")]
    out["it_mixed"] += [(_sum(f"{a}*asin(x)", f"{b}*atan(x)", f"{c}*x^2"), at) for a in (1, 2, 3, 5) for b in (1, 2, 4)
                        for c in (1, -3, 4) for at in ("x", "0", "1/2")]
    out["it_mixed"] += [(_sum(f"{a}*acos({k}*x)", f"{b}*acot(x)", f"{c}*exp(x)"), at) for a in (1, 3) for k in (2, 3)
                        for b in (2, 5) for c in (1, 4) for at in ("x", "0")]
    return {k: [dict(f=f, at=at) for f, at in v] for k, v in out.items()}


def _hyperbolic():
    out = {}
    out["hy_basic"] = [(_sum(_t(a, "sinh(x)"), _t(b, "cosh(x)")), at) for a in (1, 2, 3, 5, -2) for b in (1, 2, 4, -3)
                       for at in ("x", "0", "1")]
    out["hy_basic"] += [(_sum(_t(a, "cosh(x)"), f"{b}*x^2"), at) for a in (1, 2, 3, 7) for b in (1, -3, 5) for at in ("x", "0")]
    out["hy_tanh"] = [(_sum(_t(a, "tanh(x)"), f"{b}*x"), at) for a in (1, 2, 3, 5) for b in (1, 2, 4, -3) for at in ("x", "0")]
    out["hy_tanh"] += [(_sum(_t(a, "coth(x)"), f"{b}*x"), at) for a in (1, 2, 3) for b in (1, 4, -2) for at in ("x", "1")]
    out["hy_tanh"] += [(_sum(_t(a, "tanh(x)"), _t(b, "sinh(x)")), at) for a in (1, 2, 5) for b in (1, 3, 4) for at in ("x", "0")]
    out["hy_other"] = [(_sum(_t(a, "sech(x)"), f"{b}*x"), at) for a in (1, 2, 3, 5) for b in (1, 3, -2) for at in ("x", "0")]
    out["hy_other"] += [(_sum(_t(a, "csch(x)"), f"{b}*x"), at) for a in (1, 2, 3) for b in (1, 4, -3) for at in ("x", "1")]
    out["hy_other"] += [(_sum(_t(a, "sech(x)"), _t(b, "coth(x)")), at) for a in (1, 2, 3) for b in (1, 2, 5) for at in ("x", "1")]
    out["hy_arg"] = [(_t(a, f"sinh({k}*x)"), at) for a in (1, 2, 3, -4) for k in (2, 3, 4, 5) for at in ("x", "0")]
    out["hy_arg"] += [(_sum(_t(a, f"cosh({k}*x)"), f"{b}*x"), at) for a in (1, 2, 5) for k in (2, 3, 4) for b in (1, -2)
                      for at in ("x", "0")]
    out["hy_arg"] += [(_sum(_t(a, f"tanh({k}*x)"), f"{b}*sinh(x)"), at) for a in (1, 2, 3) for k in (2, 3) for b in (1, 4)
                      for at in ("x", "0")]
    out["hy_arg"] += [(_sum(f"sech({k}*x)", f"{a}*cosh(x)", f"{b}*x^2"), at) for k in (2, 3, 4) for a in (1, 2, 3)
                      for b in (1, 5) for at in ("x", "0")]
    return {k: [dict(f=f, at=at) for f, at in v] for k, v in out.items()}


def _difference_quotient():
    out = {}
    forms = ("h", "2", "1", "3", "-1")
    out["dq_poly1"] = [(f"{m}*x+{b}", fm) for m in (2, 3, 5, 7, -4) for b in (1, 5, -3) for fm in ("h", "h", "2")]
    out["dq_poly1"] += [(_t(c, "x^2"), fm) for c in (1, 2, 3, 5, -1) for fm in forms]
    out["dq_poly1"] += [(_sum("x^2", f"{b}*x"), fm) for b in (1, 2, 3, 5, -4) for fm in ("h", "1", "2", "-1")]
    out["dq_poly2"] = [(_sum(f"{a}*x^2", f"{b}*x", str(c)), fm) for a in (1, 2, 3, -2) for b in (1, 4, -5) for c in (1, 6)
                       for fm in ("h", "1", "2")]
    out["dq_poly2"] += [(_sum(_t(a, "x^3"), f"{b}*x"), fm) for a in (1, 2, 3) for b in (1, -2, 5) for fm in ("h", "1", "2")]
    out["dq_poly2"] += [(_sum("x^3", f"{a}*x^2"), fm) for a in (1, 2, 3, -1) for fm in ("h", "1", "2")]
    out["dq_recip"] = [(f"{c}/x", fm) for c in (1, 2, 3, 5) for fm in ("h", "1", "2", "3")]
    out["dq_recip"] += [(f"1/(x+{b})", fm) for b in (1, 2, 3, 5) for fm in ("h", "1", "2")]
    out["dq_recip"] += [(f"1/(x-{b})", fm) for b in (1, 2, 3) for fm in ("h", "-1", "5")]
    out["dq_recip"] += [(f"{c}/x^2", fm) for c in (1, 2, 3) for fm in ("h", "1", "2")]
    out["dq_root"] = [(_t(c, "sqrt(x)"), fm) for c in (1, 2, 3, 5) for fm in ("h", "1", "4", "9")]
    out["dq_root"] += [(f"sqrt(x+{b})", fm) for b in (1, 2, 3, 5) for fm in ("h", "1", "2")]
    out["dq_root"] += [(f"sqrt({k}*x+1)", fm) for k in (2, 3, 4) for fm in ("h", "1", "2")]
    out["dq_root"] += [(f"sqrt(x)+{b}*x", fm) for b in (1, 2, 3) for fm in ("h", "4", "1")]
    out["dq_rational"] = [(f"x/(x+{b})", fm) for b in (1, 2, 3, 4) for fm in ("h", "1", "2")]
    out["dq_rational"] += [(f"(x+{a})/(x-{b})", fm) for a in (1, 2, 3) for b in (1, 2, 4) for fm in ("h", "0", "3")]
    out["dq_rational"] += [(f"{a}*x/(x^2+1)" if False else f"1/(x^2+{b})", fm) for b in (1, 2, 4) for fm in ("h", "1", "2")]
    out["dq_rational"] += [(f"(2*x+{a})/(x+{b})", fm) for a in (1, 3, 5) for b in (1, 2) for fm in ("h", "1")]
    return {k: [dict(f=f, at=at) for f, at in v] for k, v in out.items()}


def _rate_of_change():
    out = {}
    out["roc_avg"] = [(_sum(f"{a}*x^2", f"{b}*x"), str(lo), str(lo + w), "average") for a in (1, 2, 3) for b in (1, -2, 4)
                      for lo in (0, 1, 2) for w in (1, 2, 3)]
    out["roc_avg"] += [(f"{c}/x", str(lo), str(lo + w), "average") for c in (1, 2, 6, 12) for lo in (1, 2) for w in (1, 2, 4)]
    out["roc_avg"] += [(_sum("x^3", f"{b}*x"), str(lo), str(lo + w), "average") for b in (1, -1, 3) for lo in (0, 1) for w in (1, 2, 3)]
    out["roc_inst"] = [(_sum(f"{a}*x^2", f"{b}*x"), str(p), "", "instantaneous") for a in (1, 2, 3, -1) for b in (1, 4, -3)
                       for p in (0, 1, 2, 3)]
    out["roc_inst"] += [(f"{c}/x", str(p), "", "instantaneous") for c in (1, 2, 4, 6) for p in (1, 2, 3, 4)]
    out["roc_inst"] += [(_t(c, "sqrt(x)"), str(p), "", "instantaneous") for c in (1, 2, 3) for p in (1, 4, 9, 16)]
    out["roc_inst_hard"] = [(f"sqrt(x+{b})", str(p), "", "instantaneous") for b in (1, 2, 3, 5) for p in (0, 1, 2, 6)]
    out["roc_inst_hard"] += [(f"x/(x+{b})", str(p), "", "instantaneous") for b in (1, 2, 3) for p in (0, 1, 2, 3)]
    out["roc_inst_hard"] += [(f"1/(x^2+{b})", str(p), "", "instantaneous") for b in (1, 2, 3) for p in (0, 1, 2)]
    out["roc_inst_hard"] += [(f"(x+{a})/(x-{b})", str(p), "", "instantaneous") for a in (1, 3) for b in (1, 2) for p in (3, 4, 5)]
    out["roc_avg_hard"] = [(f"sqrt(x)", str(lo * lo), str((lo + w) ** 2), "average") for lo in (0, 1, 2, 3) for w in (1, 2)]
    out["roc_avg_hard"] += [(f"x/(x+{b})", str(lo), str(lo + w), "average") for b in (1, 2, 3) for lo in (0, 1) for w in (1, 2, 3)]
    out["roc_avg_hard"] += [(f"1/(x^2+{b})", str(lo), str(lo + w), "average") for b in (1, 2) for lo in (0, 1) for w in (1, 2)]
    return {k: [dict(f=f, a=a, b=b, ask=ask) for f, a, b, ask in v] for k, v in out.items()}


def _limit_definition():
    out = {}
    ats = ("x", "x", "1", "2", "-1")
    out["ld_poly"] = [(_sum(_t(a, "x^2"), f"{b}*x"), at) for a in (1, 2, 3, -1) for b in (1, -3, 4) for at in ats]
    out["ld_poly"] += [(f"{a}*x+{b}", at) for a in (2, 3, 5) for b in (1, -4) for at in ("x", "2")]
    out["ld_poly"] += [(_sum("x^3", f"{b}*x"), at) for b in (1, -2, 5) for at in ("x", "1", "2")]
    out["ld_recip"] = [(f"{c}/x", at) for c in (1, 2, 3, 4) for at in ("x", "1", "2", "-1")]
    out["ld_recip"] += [(f"1/(x+{b})", at) for b in (1, 2, 3) for at in ("x", "1", "2")]
    out["ld_recip"] += [(f"1/x^2", at) for at in ("x", "1", "2")]
    out["ld_root"] = [(_t(c, "sqrt(x)"), at) for c in (1, 2, 3, 4) for at in ("x", "1", "4", "9")]
    out["ld_root"] += [(f"sqrt(x+{b})", at) for b in (1, 2, 3, 5) for at in ("x", "1", "2")]
    out["ld_root"] += [(f"sqrt({k}*x+1)", at) for k in (2, 3, 4) for at in ("x", "1", "4")]
    out["ld_rational"] = [(f"x/(x+{b})", at) for b in (1, 2, 3) for at in ("x", "1", "2")]
    out["ld_rational"] += [(f"(x+{a})/(x-{b})", at) for a in (1, 2, 3) for b in (1, 2) for at in ("x", "3", "4")]
    out["ld_rational"] += [(f"1/(x^2+{b})", at) for b in (1, 2, 3) for at in ("x", "1", "2")]
    return {k: [dict(f=f, at=at) for f, at in v] for k, v in out.items()}


def _differentiability():
    out = {}
    cl = lambda f, a: (f, "", str(a), "classify")
    out["df_abs"] = [cl(_t(c, f"Abs(x-{a})"), a) for c in (1, 2, 3, 4, 5, 6) for a in (-4, -3, -2, -1, 0, 1, 2, 3, 4, 5)]
    out["df_abs"] += [cl(f"Abs(x+{a})+{b}", -a) for a in (1, 2, 3, 5) for b in (1, 2, -3)]
    out["df_piece"] = [cl(f"Piecewise((x^2, x<{a}), ({2 * a}*x-{a * a}, x>={a}))", a) for a in (1, 2, 3, -1, 4)]
    out["df_piece"] += [cl(f"Piecewise((x^2, x<{a}), ({m}*x, x>={a}))", a) for a in (1, 2, 3) for m in (2, 3, 5)
                        if m * a != a * a]
    out["df_piece"] += [cl(f"Piecewise(({m}*x+{b}, x<{a}), ({m}*x+{b + c}, x>={a}))", a)
                        for a in (0, 1, 2) for m in (1, 2, 3) for b in (1, 2) for c in (1, 3)]
    out["df_piece"] += [cl(f"Piecewise(({m}*x+{b}, x<{a}), ({n}*x+{m * a + b - n * a}, x>={a}))", a)
                        for a in (0, 1, 2, 3) for m in (1, 2) for n in (3, 4, 5) for b in (1, 2)]
    out["df_power"] = [cl(f"Abs(x)^({p})", 0) for p in ("2/3", "1/2", "3/2", "4/3", "5/3", "1/3")]
    out["df_power"] += [cl(f"sign(x)*Abs(x)^(1/3)", 0), cl("sign(x)*Abs(x)^(1/5)", 0)]
    out["df_power"] += [cl(f"{c}*Abs(x-{a})^({p})", a) for c in (1, 2, 3) for a in (1, 2, -1, 3) for p in ("2/3", "3/2", "1/2")]
    out["df_power"] += [cl(f"Abs(x-{a})^({p})+{b}", a) for a in (1, 2) for p in ("2/3", "3/2", "1/2") for b in (1, 4)]
    out["df_param_one"] = [(f"Piecewise((x^2, x<{a}), ({2 * a}*x+k, x>={a}))", "k", "", "params") for a in (1, 2, 3, -1, 4, 5, -2)]
    out["df_param_one"] += [(f"Piecewise(({c}*x^2, x<{a}), ({2 * c * a}*x+k, x>={a}))", "k", "", "params")
                            for a in (1, 2, 3, -1, -2) for c in (1, 2, 3, 4, 5)]
    out["df_param_one"] += [(f"Piecewise((x^3, x<{a}), ({3 * a * a}*x+k, x>={a}))", "k", "", "params") for a in (1, 2, -1, 3, -2)]
    out["df_param_two"] = [(f"Piecewise((a*x+b, x<{p}), (x^2, x>={p}))", "a,b", "", "params") for p in (1, 2, 3, -1, -2)]
    out["df_param_two"] += [(f"Piecewise((x^2, x<{p}), (a*x^2+b*x, x>={p}))", "a,b", "", "params") for p in (1, 2, 3)]
    out["df_param_two"] += [(f"Piecewise((a*x^2+b, x<{p}), ({c}*x+{d}, x>={p}))", "a,b", "", "params")
                            for p in (1, 2, 3) for c in (2, 3, 5) for d in (1, 4)]
    out["df_param_two"] += [(f"Piecewise((a*x^2+b*x, x<{p}), (x^3+{d}, x>={p}))", "a,b", "", "params")
                            for p in (1, 2) for d in (1, 2, 3)]
    out["df_param_trans"] = [(f"Piecewise((exp({k}*x), x<0), (a*x+b, x>=0))", "a,b", "", "params") for k in (1, 2, 3, 4)]
    out["df_param_trans"] += [(f"Piecewise((a*x+b, x<0), ({c}*cos(x)+{d}*sin(x), x>=0))", "a,b", "", "params")
                              for c in (1, 2, 3) for d in (1, 2, 4)]
    out["df_param_trans"] += [(f"Piecewise((sin({k}*x)+{c}, x<0), (a*x^2+b*x+{c}, x>=0))", "a,b", "", "params")
                              for k in (1, 2, 3) for c in (1, 2, 3)]
    out["df_param_trans"] += [(f"Piecewise((a*x+b, x<1), (ln(x)+{c}*x, x>=1))", "a,b", "", "params") for c in (1, 2, 3, 4)]
    return {k: [dict(f=f, params=pa, a=a, ask=ask) for f, pa, a, ask in v] for k, v in out.items()}


TABLES = {"power_rule": _power_rule(), "trig": _trig(), "exponential_log": _exp_log(), "inverse_trig": _inverse_trig(),
          "dhyperbolic": _hyperbolic(), "difference_quotient": _difference_quotient(),
          "rate_of_change": _rate_of_change(), "limit_definition": _limit_definition(),
          "differentiability": _differentiability()}


def generate(stem: str, recipe: dict, axes: dict, answers: set[str], calculator: str = "none", seed: int = 0,
             limit: int = 150) -> dict | None:
    rng = random.Random(seed)
    rows = list(TABLES[stem].get(recipe["id"], []))
    rng.shuffle(rows)
    full = {"recipe": recipe["id"], **axes}
    for payload in rows[:limit]:
        r = derivatives.verify(stem, axes=full, calculator=calculator, **payload)
        if r["ok"] and r["answer"]["type"] in answers:
            return {"payload": payload, "result": r}
    return None
