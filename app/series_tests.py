"""Verified series convergence-test problems (C8); called only by the sandbox worker.

The model proposes a term in n and a starting index (plus an index or tolerance for the remainder topics). The server
parses it with safe_parse, decides the verdict or value with SymPy (app/series_tests_core.py) and re-checks it with
mpmath (app/series_tests_checks.py).
"""
import mpmath as mp
import sympy as sp

from app import series_tests_checks as checks
from app.clean_answer import canon, value_reason
from app.integral_core import L, Reject
from app.sequences_series import _answer, _check_axes, _exact, _finish, _start, _step
from app.series_tests_core import (TEST_NAMES, _lim, _power_form, abs_term, antiderivative, conclusive_tests,
                                   decreasing_from, exponential_in_n, has_factorial, has_log, integral_form, n, sign_atoms,
                                   parse_term, positive_from, tail_value, x)

TOPICS = ("convergence_tests", "integral_test_remainder", "alternating_error", "absolute_conditional")
PRIORITY = ("nth_term", "ratio", "root", "limit_comparison", "comparison", "integral")
MAX_K = 50
MAX_ANSWER_N = 999
CLASSES = {"absolute": "absolutely convergent", "conditional": "conditionally convergent", "divergent": "divergent"}


def verify(topic, term, start="1", k=None, eps=None, axes=None, calculator="none", bounds=None):
    try:
        if bounds is not None:
            raise Reject("slip", "series-test payloads do not use bounds")
        if topic not in TOPICS:
            raise Reject("slip", "unknown series-test topic")
        if calculator not in ("none", "scientific"):
            raise Reject("slip", "unsupported calculator tier")
        return _VERIFIERS[topic](term, _start(start), k, eps, axes or {}, calculator)
    except Reject as r:
        return {"ok": False, "cause": r.cause, "reason": r.reason, "cap": r.cap}


def _sum(term, start):
    return rf"\displaystyle\sum_{{n={start}}}^\infty {L(term)}"


def _enum(word):
    return {"type": "enum", "latex": rf"\text{{{word}}}", "sympy": None, "numeric": None}


def _alternating_parts(t, start):
    """b_n = |a_n| for a term equal to +-(-1)^n b_n with b_n > 0 from the starting index."""
    if len(sign_atoms(t)) != 1:
        raise Reject("redraw", "the term must contain exactly one (-1)^n sign factor")
    b = abs_term(t)
    if sign_atoms(b) or not positive_from(b, start):
        raise Reject("redraw", "the term must equal (-1)^n times a positive b_n from the starting index")
    ft, fb = sp.lambdify(n, t, "mpmath"), sp.lambdify(n, b, "mpmath")
    signs = {(-1) ** i * (1 if ft(mp.mpf(i)) > 0 else -1) for i in range(start, start + 8)}
    if len(signs) != 1 or any(abs(abs(ft(mp.mpf(i))) - fb(mp.mpf(i))) > mp.mpf("1e-20") for i in range(start, start + 8)):
        raise Reject("redraw", "the term does not alternate in sign")
    return b


def _b_family(b):
    if has_factorial(b):
        return "factorial"
    if has_log(b):
        return "log"
    if exponential_in_n(b):
        return "exponential"
    return "power" if _power_form(b) else ("rational" if b.is_rational_function(n) else "radical")


def _decide(b, start, axes):
    """The conclusive tests for b and the one the problem uses, from the test axis (or the first by priority)."""
    if sign_atoms(b):
        raise Reject("redraw", "this topic's series have positive terms")
    if not positive_from(b, start):
        raise Reject("redraw", "the terms must be positive from the starting index")
    test = str(axes.get("test", "any"))
    if test != "any" and test not in TEST_NAMES:
        raise Reject("slip", "unknown test axis")
    tests = conclusive_tests(b, start)
    if not tests:
        raise Reject("redraw", "no supported convergence test decides this series")
    if len({t["verdict"] for t in tests.values()}) > 1:
        raise Reject("redraw", "conclusive tests disagree, so a limit was not trusted")
    if test != "any" and test not in tests:
        raise Reject("redraw", f"the {TEST_NAMES[test]} is inconclusive for this term")
    chosen = test if test != "any" else next(name for name in PRIORITY if name in tests)
    return test, chosen, tests


def _positive_check(b, start, chosen, info):
    verdict = info["verdict"]
    ok, detail = checks.positive(b, start, chosen, verdict, info.get("value"), info.get("p"), info.get("F"))
    if not ok:
        raise Reject("redraw", f"independent numeric check of the {TEST_NAMES[chosen]} disagrees: {detail}")
    meta = {"kind": "positive", "b": str(b), "test": chosen, "verdict": verdict,
            "value": None if info.get("value") is None else str(info["value"]),
            "p": None if info.get("p") is None else str(info["p"]),
            "F": None if info.get("F") is None else str(info["F"])}
    return detail, meta


def _test_steps(b, chosen, info, start=1):
    v, verdict = info.get("value"), info["verdict"]
    shown = L(v) if v is not None else r"\infty"
    if chosen == "nth_term":
        return [_step("Take the limit of the terms.", rf"\lim_{{n\to\infty}} a_n={shown}\ne 0"),
                _step("The terms do not approach 0, so the series diverges.", r"\text{diverges}")]
    if chosen in ("ratio", "root"):
        form = (r"\lim_{n\to\infty}\left|\frac{a_{n+1}}{a_n}\right|" if chosen == "ratio"
                else r"\lim_{n\to\infty}\sqrt[n]{|a_n|}")
        side = "L<1" if verdict == "converges" else "L>1"
        return [_step("Compute the limit used by the test.", rf"L={form}={shown}", v),
                _step(f"Since ${side}$, the {TEST_NAMES[chosen]} gives {verdict}.", rf"\text{{{verdict}}}")]
    if chosen == "limit_comparison":
        p = info["p"]
        return [_step("Compare with the p-series 1/n^p.", rf"\lim_{{n\to\infty}}\frac{{a_n}}{{1/n^{{{L(p)}}}}}={shown}", v),
                _step(f"The limit is finite and positive and p={L(p)}, so the series behaves like the p-series and {verdict}.",
                      rf"\text{{{verdict}}}")]
    if chosen == "comparison":
        return [_step("Compare with the harmonic series: ln n < n, so a_n exceeds c/n.", rf"a_n\ge \frac{{{L(v)}}}{{n}}"),
                _step("The harmonic series diverges, so the series diverges.", r"\text{diverges}")]
    integral = rf"\int_{{{start}}}^\infty {L(b.subs(n, x))}\,dx"
    return [_step("The terms are positive, continuous and decreasing, so integrate.", integral),
            _step("The improper integral " + ("converges" if verdict == "converges" else "diverges") + ".",
                  rf"\text{{{verdict}}}")]


def _limit_statement(b, start, chosen, info):
    head = rf"For the series $\displaystyle\sum_{{n={start}}}^\infty a_n$ with $a_n={L(b)}$"
    if chosen == "ratio":
        return head + r", find $L=\lim_{n\to\infty}\left|\dfrac{a_{n+1}}{a_n}\right|$, the limit used in the Ratio Test."
    if chosen == "root":
        return head + r", find $L=\lim_{n\to\infty}\sqrt[n]{|a_n|}$, the limit used in the Root Test."
    return (head + rf" and $b_n=\dfrac{{1}}{{n^{{{L(info['p'])}}}}}$, find $\lim_{{n\to\infty}} a_n/b_n$, "
            "the limit used in the Limit Comparison Test.")


def _convergence(term_s, start, k, eps, axes, calculator):
    b = parse_term(term_s)
    test, chosen, tests = _decide(b, start, axes)
    info = tests[chosen]
    ask = str(axes.get("ask", "verdict"))
    if ask not in ("verdict", "limit"):
        raise Reject("slip", "ask must be verdict or limit")
    _check_axes(axes, family=chosen, test=test, verdict=info["verdict"], ask=ask)
    detail, meta = _positive_check(b, start, chosen, info)
    steps = _test_steps(b, chosen, info, start)
    if ask == "limit":
        value = info.get("value")
        if chosen not in ("ratio", "root", "limit_comparison") or value is None or value.is_finite is not True:
            raise Reject("redraw", "a limit question needs a finite ratio, root or limit-comparison value")
        answer = _answer(value, "converges", calculator)
        statement = _limit_statement(b, start, chosen, info)
    else:
        value, answer = None, _enum(info["verdict"])
        lead = f"Use the {TEST_NAMES[test]} to determine" if test != "any" else "Determine"
        statement = rf"{lead} whether ${_sum(b, start)}$ converges or diverges."
    return _finish("convergence_tests", b, f"{ask}|{test}", start, chosen, info["verdict"], value, statement, steps,
                   "sympy_test_limit+mpmath_probe", detail,
                   {"test": chosen, "ask": ask, "tests": sorted(tests), "check": meta}, calculator, answer)


def _class_of(b, start):
    tests = conclusive_tests(b, start)
    if not tests:
        raise Reject("redraw", "no supported convergence test decides |a_n|")
    if len({t["verdict"] for t in tests.values()}) > 1:
        raise Reject("redraw", "conclusive tests disagree, so a limit was not trusted")
    chosen = next(name for name in PRIORITY if name in tests)
    return chosen, tests[chosen]


def _classification(term_s, start, k, eps, axes, calculator):
    t = parse_term(term_s)
    b = _alternating_parts(t, start)
    chosen, info = _class_of(b, start)
    if info["verdict"] == "converges":
        verdict, why = "absolute", f"The series of absolute values converges by the {TEST_NAMES[chosen]}."
    elif chosen == "nth_term":
        verdict, why = "divergent", "The terms do not approach 0, so the series diverges."
    elif decreasing_from(b, start)[0]:
        verdict, why = "conditional", "The absolute series diverges, but b_n decreases to 0, so the Alternating Series Test applies."
    else:
        raise Reject("redraw", "the alternating series test cannot be applied to this b_n")
    _check_axes(axes, family=chosen, verdict=verdict)
    detail, meta = _positive_check(b, start, chosen, info)
    if verdict == "conditional":
        ok, extra = checks.alternating_converges(t, b, start)
        if not ok:
            raise Reject("redraw", f"independent alternating-series check disagrees: {extra}")
        detail += "; " + extra
    steps = [_step("Test absolute convergence with $|a_n|$.", rf"|a_n|={L(b)}", b), *_test_steps(b, chosen, info, start)[-1:],
             _step(why, rf"\text{{{CLASSES[verdict]}}}")]
    statement = (rf"Classify ${_sum(t, start)}$ as absolutely convergent, conditionally convergent or divergent.")
    return _finish("absolute_conditional", t, "classify", start, chosen, verdict, None, statement, steps,
                   "sympy_test_limit+mpmath_probe+alternating_test", detail,
                   {"test": chosen, "check": meta}, calculator, _enum(CLASSES[verdict]))


def _alternating(term_s, start, k_s, eps_s, axes, calculator):
    t = parse_term(term_s)
    b = _alternating_parts(t, start)
    ask = str(axes.get("ask", "verdict"))
    if ask not in ("verdict", "bound", "min_n"):
        raise Reject("slip", "ask must be verdict, bound or min_n")
    zero = _lim(b)
    family = _b_family(b)
    if zero is None or zero.is_finite is not True:
        raise Reject("redraw", "b_n must have a finite limit")
    diverges = zero != 0
    if diverges and ask != "verdict":
        raise Reject("redraw", "an error bound needs b_n to decrease to 0")
    if not diverges and not decreasing_from(b, start)[0]:
        raise Reject("redraw", "b_n must be decreasing from the starting index")
    verdict = "diverges" if diverges else "converges"
    _check_axes(axes, family=family, verdict=verdict, ask=ask)
    meta = {"kind": "alternating", "b": str(b), "ask": ask, "verdict": verdict}
    if ask == "verdict":
        ok, detail = checks.alternating_diverges(t) if diverges else checks.alternating_converges(t, b, start)
        if not ok:
            raise Reject("redraw", f"independent alternating-series check disagrees: {detail}")
        word = "diverges" if diverges else "converges"
        steps = ([_step("The terms do not approach 0, so the series diverges.", rf"\lim_{{n\to\infty}}|a_n|={L(zero)}\ne 0")]
                 if diverges else
                 [_step("b_n is positive and decreasing.", rf"b_n={L(b)}", b),
                  _step("b_n tends to 0, so the Alternating Series Test shows convergence.", rf"\lim_{{n\to\infty}} b_n=0")])
        statement = rf"Determine whether ${_sum(t, start)}$ converges or diverges."
        return _finish("alternating_error", t, "verdict", start, family, verdict, None, statement, steps,
                       "alternating_test+mpmath_probe", detail, {"ask": ask, "check": meta}, calculator, _enum(word))
    return _alternating_estimate(t, b, start, k_s, eps_s, ask, family, meta, calculator)


def _alternating_estimate(t, b, start, k_s, eps_s, ask, family, meta, calculator):
    fb = lambda i: sp.simplify(b.subs(n, i))
    if ask == "bound":
        k = _index(k_s, start)
        value = canon(fb(k + 1))
        ok, detail = checks.alternating_bound(t, b, start, k, value)
        meta |= {"k": k, "bound": str(value)}
        statement = (rf"The alternating series ${_sum(t, start)}$ converges. Let $s_k$ be the partial sum through $n=k$ "
                     rf"and $S$ the sum. By the Alternating Series Estimation Theorem, $|S-s_k|\le |a_{{k+1}}|$. "
                     rf"Find this bound for $k={k}$.")
        steps = [_step("The error is at most the first omitted term.", rf"|S-s_k|\le b_{{k+1}}=b_{{{k + 1}}}", fb(k + 1)),
                 _step("Evaluate it.", L(value), value)]
        answer = _answer(value, "converges", calculator)
    else:
        eps = _exact(eps_s, "tolerance")
        if eps.is_Rational is not True or not 0 < eps < 1:
            raise Reject("redraw", "the tolerance must be a rational number between 0 and 1")
        k = _first_index(lambda i: sp.lambdify(n, b, "mpmath")(mp.mpf(i + 1)), eps, start)
        ok, detail = checks.alternating_threshold(b, k, eps)
        meta |= {"k": k, "eps": str(eps)}
        value = sp.Integer(k)
        statement = (rf"The alternating series ${_sum(t, start)}$ converges. Let $s_k$ be the partial sum through $n=k$ "
                     rf"and $S$ the sum. Using $|S-s_k|\le |a_{{k+1}}|$, find the smallest integer $k$ that guarantees "
                     rf"$|S-s_k|\le {L(eps)}$.")
        steps = [_step("Require the first omitted term to be small enough.", rf"b_{{k+1}}={L(b.subs(n, n + 1))}\le {L(eps)}"),
                 _step("The smallest such integer is", rf"k={k}", value)]
        answer = _answer(value, "converges", calculator)
    if not ok:
        raise Reject("redraw", f"independent alternating-series check disagrees: {detail}")
    return _finish("alternating_error", t, f"{ask}|{k}|{meta.get('eps')}", start, family, "converges", value, statement,
                   steps, "alternating_estimation+mpmath_partial_sums", detail, {"ask": ask, "check": meta, "k": k},
                   calculator, answer)


def _index(k_s, start):
    if not isinstance(k_s, str):
        raise Reject("slip", "k must be an integer string")
    k = _exact(k_s, "k")
    if k.is_Integer is not True or not start <= k <= MAX_K:
        raise Reject("slip", f"k must be an integer from the starting index to {MAX_K}")
    return int(k)


def _first_index(quantity, eps, start):
    """Smallest k > start with quantity(k) <= eps, for a decreasing quantity."""
    mp.mp.dps = 50
    e = mp.mpf(str(sp.N(eps, 50)))
    for k in range(start, MAX_ANSWER_N + 1):
        value = quantity(k)
        if value <= e + checks.TIE:
            if k == start:
                raise Reject("redraw", "the smallest k would be the starting index")
            return k
    raise Reject("redraw", "the smallest k is too large to find by hand")


def _remainder(term_s, start, k_s, eps_s, axes, calculator):
    b = parse_term(term_s)
    form = integral_form(b)
    if form not in ("power", "gaussian", "atan"):
        raise Reject("redraw", "term is outside the integral-test remainder scope whitelist")
    if form == "power" and not -b.as_independent(n, as_Add=False)[1].as_base_exp()[1] > 1:
        raise Reject("redraw", "a power term needs exponent below -1 so the series converges")
    if not positive_from(b, start) or not decreasing_from(b, start)[0]:
        raise Reject("redraw", "f must be positive and decreasing from the starting index")
    F = antiderivative(b)
    ask = str(axes.get("ask", "upper"))
    if F is None or ask not in ("upper", "lower", "min_n"):
        raise Reject("redraw" if F is None else "slip", "no antiderivative" if F is None else "ask must be upper, lower or min_n")
    _check_axes(axes, family=form, verdict="converges", ask=ask)
    fx = b.subs(n, x)
    meta = {"kind": "remainder", "b": str(b), "ask": ask}
    if ask == "min_n":
        k, value, statement, steps = _remainder_threshold(b, F, fx, start, eps_s, meta)
        upper = lower = None
        ok, detail = checks.smallest_n(b, start, k, sp.sympify(meta["eps"]))
    else:
        k = _index(k_s, start)
        upper, lower = (_clean_tail(F, k), _clean_tail(F, k + 1))
        value = upper if ask == "upper" else lower
        lo = k if ask == "upper" else k + 1
        meta |= {"k": k, "upper": str(upper), "lower": str(lower)}
        word = "upper" if ask == "upper" else "lower"
        statement = (rf"The series ${_sum(b, start)}$ converges by the Integral Test with $f(x)={L(fx)}$. Let $s_k$ be the "
                     rf"partial sum through $n=k$ and $R_k=S-s_k$. Find the {word} bound $\displaystyle\int_{{{lo}}}^\infty f(x)\,dx$ "
                     rf"on $R_k$ for $k={k}$.")
        steps = [_step("The terms are positive, continuous and decreasing, so the remainder is bounded by integrals.",
                       rf"\int_{{k+1}}^\infty f(x)\,dx\le R_k\le\int_k^\infty f(x)\,dx"),
                 _step("Evaluate the integral.", rf"\int_{{{lo}}}^\infty {L(fx)}\,dx={L(value)}", value)]
        ok, detail = checks.remainder(b, start, k, upper, lower)
    if not ok:
        raise Reject("redraw", f"independent remainder check disagrees: {detail}")
    answer = _answer(value, "converges", calculator)
    return _finish("integral_test_remainder", b, f"{ask}|{k}|{meta.get('eps')}", start, form, "converges", value,
                   statement, steps, "sympy_antiderivative+mpmath_quad_nsum", detail,
                   {"ask": ask, "k": k, "check": meta}, calculator, answer)


def _clean_tail(F, lower):
    tail = tail_value(F, lower)
    if tail is None:
        raise Reject("redraw", "the improper integral diverges")
    value = canon(tail)
    why = value_reason(value, True)
    if why:
        raise Reject("redraw", f"answer is not a usable short exact value ({why})", why)
    return value


def _remainder_threshold(b, F, fx, start, eps_s, meta):
    eps = _exact(eps_s, "tolerance")
    if eps.is_Rational is not True or not 0 < eps < 1:
        raise Reject("redraw", "the tolerance must be a rational number between 0 and 1")
    top = _lim(F, x)
    if top is None or top.is_finite is not True:
        raise Reject("redraw", "the improper integral diverges")
    tail = sp.lambdify(x, top - F, "mpmath")
    mp.mp.dps = 50
    k = _first_index(lambda i: tail(mp.mpf(i)), eps, start)
    meta |= {"k": k, "eps": str(eps)}
    value = sp.Integer(k)
    statement = (rf"The series ${_sum(b, start)}$ converges by the Integral Test with $f(x)={L(fx)}$. Let $s_N$ be the partial "
                 rf"sum through $n=N$ and $R_N=S-s_N$. Find the smallest integer $N$ for which the Integral Test bound "
                 rf"$\displaystyle\int_N^\infty f(x)\,dx$ on $R_N$ is at most ${L(eps)}$.")
    steps = [_step("Require the upper bound to be small enough.", rf"\int_N^\infty {L(fx)}\,dx\le {L(eps)}"),
             _step("The smallest such integer is", rf"N={k}", value)]
    return k, value, statement, steps


_VERIFIERS = {"convergence_tests": _convergence, "integral_test_remainder": _remainder,
              "alternating_error": _alternating, "absolute_conditional": _classification}
