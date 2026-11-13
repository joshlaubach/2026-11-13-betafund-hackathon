"""Seeded offline pools for the C9 power-series topics (the same payloads a good model would write)."""
import itertools
import random
from fractions import Fraction

from app.calc2 import power_series

R = range
_SHIFTED = tuple(("1", str(s)) for s in (-4, -3, -2, -1, 1, 2, 3, 4))
_SCALED = tuple((str(m), str(s)) for m in (2, 3, 4) for s in (0, -1, 1, 2, -2))
_PAIRS = {"plain": (("1", "0"),), "shifted": _SHIFTED, "scaled": _SCALED, "moved": _SHIFTED + _SCALED}


def grid(fields, **ranges):
    """Every payload from field templates: each {name} is formatted over the values given for it."""
    names = list(ranges)
    rows = []
    for combo in itertools.product(*(ranges[name] for name in names)):
        values = dict(zip(names, combo))
        rows.append({key: (val.format(**values) if isinstance(val, str) else val) for key, val in fields.items()})
    return rows


def _series(terms, form, start="1", **ranges):
    rows = []
    for term in terms:
        for m, s in _PAIRS[form]:
            rows += grid({"term": term, "start": start, "m": m, "s": s}, **{k: v for k, v in ranges.items() if "{" + k + "}" in term})
    return rows


def _radius():
    a, k, b, d, c = R(1, 4), R(1, 4), R(2, 8), R(1, 6), R(1, 5)
    exp_none = ("{a}*n^{k}/{b}^n", "(-1)^n*n^{k}/{b}^n", "{a}*n^{k}*{b}^n", "(n+{d})*{b}^n")
    exp_one = ("(-1)^n/(n*{b}^n)", "(-1)^n/(sqrt(n)*{b}^n)", "{b}^n/n", "(-1)^n*{b}^n/(n+{d})", "{c}/(sqrt(n)*{b}^n)")
    exp_both = ("1/(n^2*{b}^n)", "{b}^n/n^2", "{c}/((n+{d})^2*{b}^n)", "(-1)^n*{b}^n/n^3")
    poly_none = ("n/(n+{d})", "n^2/(n^2+{d})", "(n+{d})/(n+{c})", "(-1)^n*n/(n+{d})")
    poly_one = ("(-1)^n/n", "(-1)^n/(n+{d})", "(-1)^n/sqrt(n+{d})", "1/sqrt(n+{d})", "{c}/(n+{d})")
    poly_both = ("1/n^2", "1/(n+{d})^2", "1/(n^2+{d})", "(-1)^n/n^2", "{c}/(n^2+{d}*n)")
    fact_radius = ("factorial(n)^2/(factorial(2*n)*{c}^n)", "{c}^n*factorial(n)^2/factorial(2*n)",
                   "factorial(2*n)/(factorial(n)^2*{c}^n)")
    fact_all = ("{c}^n/factorial(n)", "n^{k}/factorial(n)", "(-1)^n/factorial(2*n)", "{c}^n*n/factorial(n)",
                "(-1)^n*{c}^n/factorial(2*n+1)", "1/factorial(n)^2")
    kw = dict(a=a, k=k, b=b, d=d, c=c)

    def rows(terms, form):
        return _series(terms, form, **kw)

    return {
        "ri_radius_plain": rows(exp_none, "plain") + rows(poly_none, "plain"),
        "ri_radius_shifted": rows(exp_none, "moved"),
        "ri_interval_none": rows(exp_none + poly_none, "plain"),
        "ri_interval_all": rows(fact_all, "plain") + rows(fact_all[:3], "shifted"),
        "ri_radius_factorial": rows(fact_radius, "plain") + rows(fact_radius, "scaled"),
        "ri_interval_one": rows(exp_one + poly_one, "plain"),
        "ri_interval_both": rows(exp_both + poly_both, "plain"),
        "ri_interval_moved": rows(exp_one + exp_both + poly_one + poly_both + exp_none + poly_none, "moved"),
    }


def _ops_rows(functions, ks=(None,), x0s=(None,), **ranges):
    rows = []
    for f in functions:
        for row in grid({"f": f}, **{key: val for key, val in ranges.items() if "{" + key + "}" in f}):
            for k, x0 in itertools.product(ks, x0s):
                rows.append({**row, "k": None if k is None else str(k), "x0": x0})
    return rows


def _operations():
    rg = dict(a=R(1, 5), b=R(1, 5), c=R(2, 6), j=R(1, 4))
    geom = ("1/(1-{a}*x)", "1/(1+{a}*x)", "1/(1-{a}*x^2)", "1/({c}-x)", "{b}*x^{j}/(1-{a}*x)", "1/({c}+{a}*x^2)")
    expo = ("exp({a}*x)", "exp(-{a}*x)", "exp({a}*x^2)", "x^{j}*exp({a}*x)", "{b}*exp({a}*x)", "exp({a}*x^3)")
    trig = ("sin({a}*x)", "cos({a}*x)", "x^{j}*sin({a}*x)", "x^{j}*cos({a}*x)", "sin({a}*x^2)", "cos({a}*x^2)", "{b}*sin({a}*x)")
    logat = ("log(1+{a}*x)", "log(1-{a}*x)", "atan({a}*x)", "x^{j}*atan({a}*x)", "atan({a}*x^2)", "x^{j}*log(1+{a}*x)")
    simple = ("exp({a}*x)", "exp(-{a}*x)", "1/(1-{a}*x)", "1/(1+{a}*x)", "sin({a}*x)", "cos({a}*x)", "log(1+{a}*x)",
              "atan({a}*x)", "{b}*exp({a}*x)", "{b}/(1-{a}*x)")
    shifted = ("x^{j}*exp({a}*x)", "x^{j}*sin({a}*x)", "x^{j}*cos({a}*x)", "exp({a}*x^2)", "sin({a}*x^2)", "cos({a}*x^2)",
               "1/(1-{a}*x^2)", "x^{j}/(1-{a}*x)", "atan({a}*x^2)", "x^{j}*log(1+{a}*x)", "x^{j}*atan({a}*x)",
               "{b}*x^{j}*exp({a}*x)")
    product = ("exp(x)*sin(x)", "exp(x)*cos(x)", "exp({a}*x)*sin(x)", "exp(x)/(1-x)", "exp(-x)/(1-x)", "sin(x)/(1-x)",
               "cos(x)/(1-{a}*x)", "exp({a}*x)*cos({b}*x)", "atan(x)/(1-x)", "exp(x)*log(1+x)", "log(1+x)/(1-x)",
               "sin(x)*cos({a}*x)", "exp(x)*atan(x)", "exp({a}*x)/(1-{b}*x)", "sin({a}*x)*cos(x)")
    combo = ("{a}/(1-x)+exp({b}*x)", "sin(x)+cos({a}*x)", "exp(x)-{a}*cos(x)", "x*exp(x)+1/(1-{a}*x)",
             "log(1+x)+atan({a}*x)", "exp({a}*x)+{b}*sin(x)", "1/(1-x)-cos({a}*x)", "x*sin({a}*x)+exp(-x)",
             "atan({a}*x)-sin({b}*x)", "{a}*exp(x)+{b}*exp(-x)")
    ks = tuple(R(2, 9))
    x0s = ("1/2", "1/3", "1/4", "-1/2", "2/3", "1/5", "-1/3", "1/6", "3/4", "1", "-1", "1/10")
    return {
        "op_coeff": _ops_rows(simple, ks, **rg),
        "op_shifted": _ops_rows(shifted, ks, **rg),
        "op_deriv": _ops_rows(simple + shifted, ks, **rg),
        "op_integral": _ops_rows(geom + expo + trig + logat, ks, **rg),
        "op_sum": _ops_rows(geom[:4] + expo[:3] + trig[:3] + logat[:6], x0s=x0s, **rg),
        "op_combination": _ops_rows(combo, ks, **rg),
        "op_product": _ops_rows(product, ks, **rg),
        "op_hard": _ops_rows(product + combo, ks, **rg),
        "op_sum_scaled": _ops_rows(tuple(f"{{b}}*x^{{j}}*{g}" for g in ("exp({a}*x)", "sin({a}*x)", "cos({a}*x)", "atan({a}*x)")),
                                   x0s=x0s, **rg),
    }


def _taylor_rows(functions, centers, ks, ask_x1=(None,)):
    rows = []
    for f, a in itertools.product(functions, centers):
        for k, x1 in itertools.product(ks, ask_x1):
            rows.append({"f": f, "a": a, "k": str(k), "x1": x1})
    return rows


def _taylor():
    am = [f.format(a=a) for f in ("exp({a}*x)", "sin({a}*x)", "cos({a}*x)", "log(1+{a}*x)", "atan({a}*x)", "1/(1-{a}*x)",
                                 "sqrt(1+{a}*x)") for a in R(1, 4)]
    am += ["x*exp(x)", "exp(x)+sin(x)", "1/(1+x^2)", "exp(-x^2)", "x*cos(x)", "sin(x)^2", "exp(x)*cos(x)"]
    more = [f.format(a=a) for f in ("sin({a}*x^2)", "cos({a}*x^2)", "exp({a}*x^2)", "atan({a}*x^2)", "x*sin({a}*x)", "x^2*exp({a}*x)",
                                    "1/(1+{a}*x^2)", "x*atan({a}*x)", "log(1+{a}*x^2)") for a in R(1, 6)]
    rat = ["log(x)", "sqrt(x)", "1/x", "exp(x)", "x*log(x)", "1/(x+1)", "log(x+1)", "1/x^2", "sqrt(x+1)", "exp(2*x)", "exp(-x)"]
    rat_centers = ("1", "2", "3", "1/2", "4", "9")
    trig = ["sin(x)", "cos(x)", "sin(2*x)", "cos(2*x)", "sin(x)+cos(x)", "x*sin(x)"]
    pis = ("pi/6", "pi/4", "pi/3", "pi/2", "pi", "2*pi/3", "3*pi/4", "5*pi/6", "-pi/2", "-pi/4")
    x1s_mac = ("1/2", "1", "2", "-1", "1/3", "-1/2", "3", "1/4")
    x1s_rat = ("3/2", "5/4", "7/4", "5/2", "1/2", "3", "4")
    return {
        "tm_maclaurin_coeff": _taylor_rows(am, ("0",), R(2, 8)),
        "tm_maclaurin_terms": _taylor_rows(am + more, ("0",), (1,)),
        "tm_poly_value": _taylor_rows(am[:24], ("0",), R(2, 5), x1s_mac),
        "tm_rational_coeff": _taylor_rows(rat, rat_centers, R(2, 6)),
        "tm_rational_value": _poly_rows_rational(rat, rat_centers),
        "tm_pi_coeff": _taylor_rows(trig, pis, R(1, 5)),
        "tm_terms_shifted": _taylor_rows(rat + trig, rat_centers[:4] + pis[:6], (1,)),
    }


def _poly_rows_rational(functions, centers):
    rows = []
    for f, a in itertools.product(functions, centers):
        center = Fraction(a)
        for step, k in itertools.product((Fraction(1, 2), Fraction(1, 4), Fraction(-1, 4), Fraction(1)), R(2, 5)):
            x1 = center + step
            if x1 > 0:
                rows.append({"f": f, "a": a, "k": str(k), "x1": f"{x1.numerator}/{x1.denominator}"})
    return rows


def _binomial():
    halves, thirds = ("1/2", "-1/2", "3/2", "-3/2", "5/2"), ("1/3", "-1/3", "2/3", "-2/3", "4/3")
    others = ("1/4", "-1/4", "3/4", "-3/4", "1/5", "-1/5", "2/5", "-2/5", "3/5")
    plain = ("1+x", "1-x")
    scaled = ("1+{a}*x", "1-{a}*x", "1+x^2", "1-x^2", "1+{a}*x^2", "1-{a}*x^2", "1+x^3")
    shifted = ("{c}+x", "{c}-x", "{c}+{a}*x^2", "{c}-x^2", "{c}+x^3", "{c}+{a}*x")
    kw = dict(a=R(2, 5), c=(4, 8, 9, 16, 25, 27))

    def rows(bases, ps, ks=(None,), x0s=(None,)):
        out = []
        for base in bases:
            for row in grid({"base": base}, **{key: val for key, val in kw.items() if "{" + key + "}" in base}):
                for p, k, x0 in itertools.product(ps, ks, x0s):
                    out.append({**row, "p": p, "k": None if k is None else str(k), "x0": x0})
        return out

    small = ("1/10", "1/5", "1/4", "-1/10", "-1/5", "1/8", "1/3", "-1/4", "1/6", "-1/8")
    return {
        "bs_coeff_basic": rows(plain, ("1/2", "-1/2", "3/2", "-3/2", "1/3", "-1/3", "2/3", "-2/3"), R(2, 11)),
        "bs_coeff_scaled": rows(scaled, halves + thirds, R(2, 8)),
        "bs_approx": rows(plain, halves + thirds, (2, 3, 4), small) + rows(scaled[2:4], halves + thirds, (2, 3), ("1/2", "1/3", "-1/2", "1/4")),
        "bs_radius": rows(scaled + shifted, halves + thirds + others),
        "bs_coeff_other": rows(plain + scaled[:2], others + halves[2:], R(2, 7)),
        "bs_coeff_shifted": rows(shifted, halves + thirds + others[:4], R(2, 8)),
        "bs_approx_hard": rows(plain + scaled[2:4], others, (2, 3, 4), small),
    }


def _remainder_rows(functions, centers, x1s, ns=(None,), epss=(None,)):
    return [{"f": f, "a": a, "x1": x1, "n": None if n is None else str(n), "eps": eps}
            for f, a, x1, n, eps in itertools.product(functions, centers, x1s, ns, epss)]


def _remainder():
    exps = ("exp(x)", "exp(2*x)", "exp(x/2)", "exp(-x)", "exp(3*x)", "exp(-2*x)")
    trig = ("sin(x)", "cos(x)", "sin(2*x)", "cos(2*x)", "sin(x/2)", "cos(x/2)")
    pix = ("pi/6", "pi/4", "pi/3", "pi/2")
    logs = ("log(1+x)",)
    logx = ("log(x)",)
    alg = ("sqrt(1+x)", "1/(1-x)", "1/(1+x)", "(1+x)^(3/2)", "(1+x)^(1/3)", "1/(1-2*x)")
    small = ("1/8", "1/6", "1/5", "1/4", "1/3", "1/2", "2/3", "3/4")
    epss = ("1/10", "1/50", "1/100", "1/500", "1/1000", "1/5000", "1/10000", "1/100000")
    ns = tuple(R(1, 7))
    exp_x1 = ("1/2", "1", "3/2", "2", "1/3", "3")
    return {
        "tr_bound_exp": _remainder_rows(exps, ("0",), exp_x1, ns) + _remainder_rows(exps[:1], ("1",), ("3/2", "2", "5/2"), ns),
        "tr_bound_trig": _remainder_rows(trig, ("0",), pix, ns),
        "tr_bound_log": _remainder_rows(logs, ("0",), small, ns) + _remainder_rows(logx, ("1",), ("5/4", "3/2", "7/4", "2", "9/8"), ns),
        "tr_bound_alg": _remainder_rows(alg, ("0",), small[:7], ns),
        "tr_min_exp": _remainder_rows(exps, ("0",), exp_x1, (None,), epss),
        "tr_min_other": (_remainder_rows(trig, ("0",), pix, (None,), epss) + _remainder_rows(logs + alg, ("0",), small[:7], (None,), epss)
                         + _remainder_rows(logx, ("1",), ("5/4", "3/2", "7/4", "2"), (None,), epss)),
    }


def _ratio_string(r):
    return f"{r.numerator}*pi/{r.denominator}" if r.denominator != 1 else f"{r.numerator}*pi"


def _angles(dens, limit):
    out = set()
    for d in dens:
        for numer in R(-limit * d, limit * d + 1):
            r = Fraction(numer, d)
            if r != 0 and abs(r) <= limit:
                out.add(r)
    return sorted(out)


def _euler():
    axis = [{"z": f"I*({_ratio_string(r)})", "n": None} for r in _angles((1, 2), 16)]
    sixth = [{"z": f"I*({_ratio_string(r)})", "n": None} for r in _angles((3, 6), 6) if r.denominator in (3, 6)]
    eighth = [{"z": f"I*({_ratio_string(r)})", "n": None} for r in _angles((4,), 12) if r.denominator == 4]
    cx = [{"z": f"{re}+I*({_ratio_string(r)})", "n": None} for re in ("ln(2)", "ln(3)", "ln(4)", "ln(5)", "-ln(2)")
          for r in _angles((2, 3, 4, 6), 2) if abs(r) <= 2][:]
    cx += [{"z": f"{re}+I*({_ratio_string(r)})", "n": None} for re in ("1", "2", "-1", "1/2", "0") for r in _angles((2, 3, 4, 6), 2)]
    gauss = [{"z": z, "n": str(n)} for z in ("1+I", "1-I", "-1+I", "-1-I", "2+2*I", "2-2*I", "-2+2*I", "-2-2*I", "I", "-I", "2*I", "-2*I", "2", "-1-I")
             for n in R(2, 13)]
    radical = [{"z": z, "n": str(n)} for z in ("sqrt(3)+I", "sqrt(3)-I", "-sqrt(3)+I", "-sqrt(3)-I", "1+sqrt(3)*I", "1-sqrt(3)*I",
                                               "-1+sqrt(3)*I", "-1-sqrt(3)*I", "2*sqrt(3)+2*I", "2+2*sqrt(3)*I", "sqrt(2)+sqrt(2)*I", "sqrt(2)-sqrt(2)*I")
               for n in R(2, 13)]
    return {"eu_axis": axis, "eu_special": sixth + eighth, "eu_complex": cx, "eu_gaussian": gauss, "eu_radical": radical}


TABLES = {"radius_interval": _radius(), "operations": _operations(), "taylor_maclaurin": _taylor(),
          "binomial_series": _binomial(), "taylor_remainder": _remainder(), "euler_formula": _euler()}


def generate(recipe, axes, answers, calculator="none", seed=0, topic=None, limit=160):
    rows = list(TABLES[topic].get(recipe["id"], ()))
    random.Random(seed).shuffle(rows)
    full_axes = {"recipe": recipe["id"], **axes}
    for payload in rows[:limit]:
        result = power_series.verify(topic, axes=full_axes, calculator=calculator, **payload)
        if result["ok"] and result["answer"]["type"] in answers:
            return {"payload": payload, "result": result}
    return None
