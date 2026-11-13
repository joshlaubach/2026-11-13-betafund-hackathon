"""Seeded offline pools for the C8 series-test topics (the same payloads a good model would write)."""
import itertools
import random

from app import series_tests

R = range
NO_ZERO = ("1/10", "1/20", "1/50", "1/100", "1/200", "1/500", "1/1000")


def _grid(term, start=1, idx=(None,), tol=(None,), **ranges):
    """Every payload from a term template: each keyword is formatted over its values, start, idx (k) and tol (eps) are crossed."""
    names = list(ranges)
    rows = []
    for combo in itertools.product(*(ranges[name] for name in names)):
        text = term.format(**dict(zip(names, combo)))
        for s, kk, e in itertools.product([start] if isinstance(start, int) else start, idx, tol):
            rows.append({"term": text, "start": str(s), "k": None if kk is None else str(kk),
                         "eps": e})
    return rows


def _convergence():
    ratio_conv = (_grid("{c}^n/factorial(n)", c=R(2, 10)) + _grid("{a}*n^{k}/{c}^n", a=R(1, 5), k=R(1, 5), c=R(2, 7))
                  + _grid("n^{k}*({p}/{q})^n", k=R(1, 5), p=R(1, 6), q=R(2, 8))
                  + _grid("factorial(n)/n^n") + _grid("factorial(n)^2/factorial(2*n)")
                  + _grid("{a}*factorial(n)/(n+{b})^n", a=R(1, 4), b=R(0, 3)))
    ratio_div = (_grid("factorial(n)/{c}^n", c=R(2, 10)) + _grid("{a}*{c}^n/n^{k}", a=R(1, 4), c=R(2, 7), k=R(1, 5))
                 + _grid("n^{k}*({p}/{q})^n", k=R(1, 5), p=R(3, 9), q=R(2, 3)) + _grid("n^n/factorial(n)")
                 + _grid("{a}*n^{k}*factorial(n)/{c}^n", a=R(1, 3), k=R(0, 3), c=R(2, 7))
                 + _grid("factorial(2*n)/(factorial(n)^2*{c}^n)", c=R(1, 4)))
    lc_conv = (_grid("({a}*n+{b})/({c}*n^3+{d})", a=R(1, 8), b=R(1, 6), c=R(1, 6), d=R(1, 5))
               + _grid("({a}*n+{b})/(n^2+{c}*n+{d})", a=R(1, 6), b=R(1, 5), c=R(1, 5), d=R(1, 5))
               + _grid("sqrt(n)/({a}*n^2+{b})", a=R(1, 6), b=R(1, 9)) + _grid("({a}*n+{b})/sqrt(n^5+{c})", a=R(1, 6), b=R(1, 5), c=R(1, 6)))
    lc_div = (_grid("({a}*n+{b})/({c}*n^2+{d})", a=R(1, 8), b=R(1, 6), c=R(1, 6), d=R(1, 5))
              + _grid("({a}*n^2+{b})/({c}*n^3+{d}*n+1)", a=R(1, 6), b=R(1, 5), c=R(1, 5), d=R(1, 4))
              + _grid("{a}/sqrt(n+{b})", a=R(1, 8), b=R(1, 9)) + _grid("sqrt({a}*n+{b})/(n+{c})", a=R(1, 6), b=R(1, 5), c=R(1, 6)))
    root_conv = (_grid("(({a}*n+{b})/({c}*n+{d}))^n", a=R(1, 5), b=R(1, 5), c=R(2, 9), d=R(1, 4))
                 + _grid("(n/(n+{a}))^(n^2)", a=R(1, 5)) + _grid("{c}*(n/(2*n+{b}))^n", c=R(1, 5), b=R(1, 6)))
    root_div = (_grid("(({a}*n+{b})/({c}*n+{d}))^n", a=R(2, 9), b=R(1, 5), c=R(1, 5), d=R(1, 4))
                + _grid("(1+{a}/n)^(n^2)", a=R(1, 6)) + _grid("{c}*((n+{b})/n)^(n^2)", c=R(1, 4), b=R(1, 4)))
    comparison = _grid("{a}/ln(n)^({q})", start=R(2, 7), a=R(1, 10), q=("1", "2", "3", "1/2", "3/2"))
    integral_conv = (_grid("{a}/(n*ln(n)^({q}))", start=R(2, 6), a=R(1, 8), q=("2", "3", "3/2", "5/2"))
                     + _grid("{a}*ln(n)/n^({p})", start=R(2, 5), a=R(1, 6), p=("2", "3", "5/2", "3/2"))
                     + _grid("{a}*n*exp(-n^2)", a=R(1, 8)) + _grid("{a}*n*exp(-{k}*n)", start=R(1, 4), a=R(1, 5), k=R(1, 4)))
    integral_div = _grid("{a}/(n*ln(n)^({q}))", start=R(2, 7), a=R(1, 10), q=("1", "1/2", "2/3", "3/4"))
    choose_conv = ratio_conv[::2] + lc_conv[::6] + root_conv[::3] + integral_conv[::2]
    choose_div = lc_div[::6] + integral_div
    ratio = ratio_conv + ratio_div
    return {
        "ct_nth": (_grid("({a}*n+{b})/({c}*n+{d})", a=R(1, 8), b=R(1, 6), c=R(1, 7), d=R(1, 4))
                   + _grid("{a}*n^2/({c}*n^2+{d})", a=R(1, 6), c=R(1, 5), d=R(1, 6))),
        "ct_ratio": ratio, "ct_ratio_value": ratio,
        "ct_lc": lc_conv + lc_div, "ct_lc_value": lc_conv + lc_div,
        "ct_root": root_conv + root_div, "ct_root_value": root_conv + root_div,
        "ct_comparison": comparison, "ct_integral": integral_conv + integral_div,
        "ct_choose_conv": choose_conv, "ct_choose_div": choose_div,
    }


def _remainder():
    basic = _grid("{c}/n^({p})", idx=R(1, 21), c=R(1, 6), p=(2, 3, 4))
    power = _grid("{c}/({m}*n+{s})^({p})", idx=R(1, 13), c=R(1, 7), m=R(1, 4), s=R(1, 6), p=(2, 3))
    gauss = (_grid("{c}*exp(-{m}*n)", idx=R(1, 10), c=R(1, 7), m=R(1, 4))
             + _grid("{c}*n*exp(-n^2)", idx=R(1, 9), c=R(1, 7)))
    atan = _grid("{c}/(n^2+{d})", idx=R(1, 10), c=R(1, 7), d=(1, 4, 9))
    min_power = (_grid("{c}/({m}*n+{s})^({p})", tol=NO_ZERO, c=R(1, 6), m=R(1, 4), s=R(0, 4), p=(2, 3))
                 + _grid("{c}/n^({p})", tol=NO_ZERO, c=R(1, 9), p=(2, 3, 4)))
    min_other = (_grid("{c}*exp(-{m}*n)", tol=NO_ZERO, c=R(1, 7), m=R(1, 4))
                 + _grid("{c}*n*exp(-n^2)", tol=NO_ZERO, c=R(1, 7)) + _grid("{c}/(n^2+{d})", tol=NO_ZERO, c=R(1, 7), d=(1, 4, 9)))
    return {"itr_basic": basic, "itr_power": power, "itr_gauss": gauss, "itr_atan": atan,
            "itr_min_power": min_power, "itr_min_other": min_other}


def _alternating():
    sign = ("(-1)^n*", "(-1)^(n+1)*")
    def alt(fmt, **kw):
        return [row for s in sign for row in _grid(s + fmt, **kw)]
    power = alt("{c}/(n+{s})^({p})", c=R(1, 5), s=R(0, 6), p=("1", "2", "3", "1/2", "3/2"))
    expo = alt("{c}/{r}^n", c=R(1, 6), r=("2", "3", "4", "5", "3/2"))
    fact = alt("{c}/factorial(n)", c=R(1, 8)) + alt("{c}/(factorial(n)+{d})", c=R(1, 5), d=R(0, 4))
    rational = alt("n/(n^2+{d})", start=R(2, 7), d=R(1, 10)) + alt("(n+{a})/(n^2+{d})", start=R(3, 8), a=R(1, 3), d=R(1, 10))
    radical = alt("{c}/sqrt(n^2+{d})", c=R(1, 5), d=R(1, 12))
    logs = alt("{c}/ln(n+{s})", start=R(2, 5), c=R(1, 4), s=R(0, 5))
    diverge = alt("({a}*n+{b})/({c}*n+{d})", a=R(1, 6), b=R(1, 5), c=R(1, 6), d=R(1, 4)) + alt("n^2/({c}*n^2+{d})", c=R(1, 4), d=R(1, 8))
    def ask(rows, k=None, eps=None):
        out = []
        for row in rows:
            for kk in (k or (None,)):
                for e in (eps or (None,)):
                    out.append({**row, "k": None if kk is None else str(kk), "eps": e})
        return out
    easy = power + expo + fact
    hard = rational + radical
    return {"ae_verdict_conv": ask(power), "ae_verdict_div": ask(diverge),
            "ae_bound": ask(easy, k=R(2, 12, 2)), "ae_bound_hard": ask(hard, k=R(2, 12, 2)),
            "ae_min": ask(easy, eps=NO_ZERO[:5]),
            "ae_min_hard": ask(hard, eps=NO_ZERO[:5]) + ask(logs, eps=("1/2", "1/3", "1/4", "1/5", "3/10"))}


def _classification():
    sign = ("(-1)^n*", "(-1)^(n+1)*")
    def alt(fmt, **kw):
        return [row for s in sign for row in _grid(s + fmt, **kw)]
    ac_p = alt("{c}/(n+{s})^({p})", c=R(1, 5), s=R(0, 6), p=("1/2", "2/3", "1", "3/2", "2", "3"))
    divergent = (alt("({a}*n+{b})/({c}*n+{d})", a=R(1, 6), b=R(1, 5), c=R(1, 6), d=R(1, 4))
                 + alt("factorial(n)/{c}^n", c=R(2, 9)) + alt("{c}^n/n^{k}", c=R(2, 6), k=R(1, 4))
                 + alt("n^2/({c}*n^2+{d})", c=R(1, 4), d=R(1, 8)))
    ratio = (alt("{a}*n^{k}/{c}^n", a=R(1, 4), k=R(1, 5), c=R(2, 7)) + alt("{c}^n/factorial(n)", c=R(2, 9))
             + alt("factorial(n)/n^n") + alt("n^{k}*({p}/{q})^n", k=R(1, 4), p=R(1, 5), q=R(2, 7)))
    root = alt("(({a}*n+{b})/({c}*n+{d}))^n", a=R(1, 5), b=R(1, 5), c=R(2, 9), d=R(1, 4))
    rational = (alt("(n+{a})/(n^2+{d})", start=R(2, 7), a=R(1, 4), d=R(1, 9)) + alt("(n+{a})/(n^3+{d})", a=R(1, 4), d=R(1, 9))
                + alt("sqrt(n)/(n+{c})", start=R(2, 6), c=R(1, 9)) + alt("sqrt(n)/(n^2+{c})", c=R(1, 9))
                + alt("n/(n^2+{d})", start=R(2, 7), d=R(1, 12)) + alt("{a}/sqrt(n^3+{d})", a=R(1, 5), d=R(1, 9)))
    comparison = alt("{a}/ln(n)^({q})", start=R(2, 6), a=R(1, 6), q=("1", "2", "1/2"))
    integral = (alt("{a}/(n*ln(n))", start=R(2, 6), a=R(1, 8)) + alt("{a}/(n*ln(n)^2)", start=R(2, 6), a=R(1, 8))
                + alt("{a}*ln(n)/n^2", start=R(2, 6), a=R(1, 8)) + alt("{a}/(n*ln(n)^({q}))", start=R(2, 6), a=R(1, 4), q=("3/2", "3", "1/2")))
    return {"ac_p": ac_p, "ac_divergent": divergent, "ac_ratio": ratio, "ac_root": root, "ac_rational": rational,
            "ac_comparison": comparison, "ac_integral": integral}


TABLES = {"convergence_tests": _convergence(), "integral_test_remainder": _remainder(),
          "alternating_error": _alternating(), "absolute_conditional": _classification()}


def generate(recipe, axes, answers, calculator="none", seed=0, topic=None, limit=240):
    rows = list(TABLES[topic].get(recipe["id"], ()))
    random.Random(seed).shuffle(rows)
    full_axes = {"recipe": recipe["id"], **axes}
    for payload in rows[:limit]:
        result = series_tests.verify(topic, axes=full_axes, calculator=calculator, **payload)
        if result["ok"] and result["answer"]["type"] in answers:
            return {"payload": payload, "result": result}
    return None
