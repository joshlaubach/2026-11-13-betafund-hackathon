"""Independent numeric checks for the C8 series-test verifiers (mpmath only; no SymPy limits)."""
import mpmath as mp
import sympy as sp

from app.calc2.series_tests_core import n, x

DPS = 50
_LOG_PROBES = (9, 12)        # X = exp(10**k): ln X = 10**k
_POW_PROBES = (3, 6)         # X = 10**k
TIE = mp.mpf("1e-30")        # a threshold equal to the tolerance counts as meeting it


def _num(v):
    if v is None:
        return None
    return mp.inf if v == sp.oo else mp.mpf(str(sp.N(v, DPS)))


def _near(got, want, tol):
    return abs(got - want) <= tol * max(1, abs(want))


def _integral_probe(f, F, start, verdict, value, has_log):
    """The antiderivative differentiates to f numerically, and F at huge X shows the claimed tail or growth."""
    for x0 in (start + mp.mpf("0.37"), start + mp.mpf("5.1"), start + mp.mpf("50.7")):
        if not _near(mp.diff(F, x0), f(x0), mp.mpf("1e-12")):
            return False, f"F' differs from f at {mp.nstr(x0, 5)}"
    if has_log:
        X1, X2 = (mp.exp(mp.mpf(10) ** k) for k in _LOG_PROBES)
    else:
        X1, X2 = (mp.mpf(10) ** k for k in _POW_PROBES)
    if verdict == "diverges":
        grow = F(X2) - F(X1)
        return bool(grow > 1), f"F grows by {mp.nstr(grow, 6)} between the far probes"
    tail = F(X2) - F(mp.mpf(start))
    return bool(_near(tail, _num(value), mp.mpf("1e-3"))), f"tail {mp.nstr(tail, 8)} vs {mp.nstr(_num(value), 8)}"


def positive(b, start, test, verdict, value=None, p=None, F=None):
    """Check a verdict for the positive series sum b(n) with the test that decided it."""
    mp.mp.dps = DPS
    fn = sp.lambdify(n, b, "mpmath")
    want = _num(value)
    if test == "nth_term":
        late = [abs(fn(mp.mpf(10) ** k)) for k in (6, 7)]
        floor = mp.mpf(1) if want == mp.inf else abs(want) / 2
        return bool(verdict == "diverges" and min(late) >= floor), f"late terms {[mp.nstr(v, 6) for v in late]}"
    if test in ("ratio", "root"):
        N = 1500 if test == "ratio" else 3000
        N = mp.mpf(N)
        got = fn(N + 1) / fn(N) if test == "ratio" else fn(N) ** (1 / N)
        side = got < mp.mpf("0.99") if verdict == "converges" else got > mp.mpf("1.01")
        agrees = want == mp.inf or _near(got, want, mp.mpf("0.02"))
        return bool(side and agrees), f"{test} quotient at {N}: {mp.nstr(got, 8)} vs {mp.nstr(want, 8)}"
    if test == "limit_comparison":
        N, pw = mp.mpf(10) ** 6, mp.mpf(str(sp.N(p, DPS)))
        local = -mp.log(fn(2 * N) / fn(N)) / mp.log(2)
        scale = fn(N) * mp.mpf(N) ** pw
        ok = abs(local - pw) < mp.mpf("1e-3") and _near(scale, want, mp.mpf("1e-3")) and (pw > 1) == (verdict == "converges")
        return bool(ok), f"local exponent {mp.nstr(local, 8)}, scaled term {mp.nstr(scale, 8)} vs {mp.nstr(want, 8)}"
    if test == "comparison":
        late = [fn(mp.mpf(10) ** k) * mp.mpf(10) ** k for k in (6, 8)]
        return bool(verdict == "diverges" and min(late) >= want), f"n*a_n at late n {[mp.nstr(v, 6) for v in late]}"
    if test == "integral":
        Ff = sp.lambdify(x, F, "mpmath")
        ff = sp.lambdify(x, b.subs(n, x), "mpmath")
        return _integral_probe(ff, Ff, start, verdict, value, b.has(sp.log))
    return False, "unknown test"


def alternating_sum(term, start, terms=70):
    """Sum of an alternating series with decreasing terms: repeated averaging of late partial sums (Euler)."""
    mp.mp.dps = DPS
    fn = sp.lambdify(n, term, "mpmath")
    partial, acc = [], mp.mpf(0)
    for i in range(start, start + terms + 40):
        acc += fn(mp.mpf(i))
        partial.append(acc)
    tail = partial[terms:]
    while len(tail) > 1:
        tail = [(tail[i] + tail[i + 1]) / 2 for i in range(len(tail) - 1)]
    return tail[0], partial


def alternating_bound(term, b, start, k, bound):
    """|S - s_k| is below the claimed bound b_(k+1) and has the sign of a_(k+1)."""
    mp.mp.dps = DPS
    S, partial = alternating_sum(term, start)
    sk = partial[k - start]
    err = S - sk
    nxt = sp.lambdify(n, term, "mpmath")(mp.mpf(k + 1))
    want = _num(bound)
    ok = abs(err) <= want * (1 + mp.mpf("1e-9")) and err * nxt > 0 and _near(sp.lambdify(n, b, "mpmath")(mp.mpf(k + 1)), want, mp.mpf("1e-12"))
    return bool(ok), f"|S-s_k| = {mp.nstr(abs(err), 8)} <= {mp.nstr(want, 8)}"


def alternating_threshold(b, k, eps):
    """b_(k+1) <= eps < b_k, evaluated numerically."""
    mp.mp.dps = DPS
    fn = sp.lambdify(n, b, "mpmath")
    lo, hi = fn(mp.mpf(k + 1)), fn(mp.mpf(k))
    e = _num(eps)
    return bool(lo <= e + TIE < hi), f"b_(k+1) = {mp.nstr(lo, 8)}, b_k = {mp.nstr(hi, 8)}, eps = {mp.nstr(e, 8)}"


def alternating_diverges(term):
    mp.mp.dps = DPS
    fn = sp.lambdify(n, term, "mpmath")
    late = [abs(fn(mp.mpf(10) ** k)) for k in (6, 7)]
    return bool(min(late) > mp.mpf("0.01")), f"late terms {[mp.nstr(v, 6) for v in late]}"


def alternating_converges(term, b, start):
    """Terms shrink and the Euler-averaged sum agrees with the raw late partial sums."""
    mp.mp.dps = DPS
    S, partial = alternating_sum(term, start)
    fnb = sp.lambdify(n, b, "mpmath")
    gap = abs(partial[-1] - S)
    far = mp.exp(10 ** 6) if b.has(sp.log) else mp.mpf(10) ** 30
    return bool(gap <= fnb(mp.mpf(start + 110)) * (1 + mp.mpf("1e-9")) and fnb(far) < mp.mpf("0.05")), f"late partial sums within {mp.nstr(gap, 6)} of {mp.nstr(S, 8)}"


def remainder(f, start, k, upper, lower):
    """For a positive decreasing f: quad(k+1..oo) <= nsum remainder <= quad(k..oo), matching the claimed values."""
    mp.mp.dps = DPS
    fn = sp.lambdify(n, f, "mpmath")
    fx = sp.lambdify(x, f.subs(n, x), "mpmath")
    up = mp.quad(fx, [k, mp.inf])
    lo = mp.quad(fx, [k + 1, mp.inf])
    rem = mp.nsum(fn, [k + 1, mp.inf])
    eps = mp.mpf("1e-12")
    ok = lo - eps * max(1, lo) <= rem <= up + eps * max(1, up)
    ok = ok and _near(up, _num(upper), mp.mpf("1e-9")) and _near(lo, _num(lower), mp.mpf("1e-9"))
    return bool(ok), f"{mp.nstr(lo, 8)} <= remainder {mp.nstr(rem, 8)} <= {mp.nstr(up, 8)}"


def smallest_n(f, start, k, eps):
    """quad(k..oo) <= eps < quad(k-1..oo) for the claimed smallest k."""
    mp.mp.dps = DPS
    fx = sp.lambdify(x, f.subs(n, x), "mpmath")
    here, before = mp.quad(fx, [k, mp.inf]), mp.quad(fx, [k - 1, mp.inf])
    e = _num(eps)
    return bool(here <= e + TIE < before and k - 1 >= start), f"tail {mp.nstr(here, 8)} <= eps {mp.nstr(e, 8)} < {mp.nstr(before, 8)}"


def audit(topic, payload, answer, raw):
    """Packet audit entry point. Parsing still happens in the sandbox worker."""
    from app.safe_parse import safe_parse
    from app.calc2.series_tests_core import parse_term

    term = parse_term(payload["term"])
    start = int(safe_parse(payload["start"]))
    chk = raw["check"]
    if chk["kind"] == "positive":
        b = parse_term(chk["b"])
        F = safe_parse(chk["F"], {"x": x}) if chk.get("F") else None
        value = safe_parse(chk["value"]) if chk.get("value") is not None else None
        p = safe_parse(chk["p"]) if chk.get("p") is not None else None
        ok, detail = positive(b, start, chk["test"], chk["verdict"], value, p, F)
        out = [["P8 independent numeric check of the " + chk["test"] + " verdict", ok, detail]]
        if raw.get("verdict") == "conditional":
            alt_ok, alt_detail = alternating_converges(term, b, start)
            out.append(["P8 the alternating series converges (Euler-averaged partial sums)", alt_ok, alt_detail])
        return out
    b = parse_term(chk["b"])
    if chk["kind"] == "remainder":
        k = int(chk["k"])
        if chk["ask"] == "min_n":
            ok, detail = smallest_n(b, start, k, safe_parse(chk["eps"]))
            return [["P8 quad(k..oo) <= eps < quad(k-1..oo)", ok, detail]]
        ok, detail = remainder(b, start, k, safe_parse(chk["upper"]), safe_parse(chk["lower"]))
        return [["P8 integral bounds enclose the nsum remainder", ok, detail]]
    if chk["kind"] == "alternating":
        if chk["ask"] == "bound":
            ok, detail = alternating_bound(term, b, start, int(chk["k"]), safe_parse(chk["bound"]))
        elif chk["ask"] == "min_n":
            ok, detail = alternating_threshold(b, int(chk["k"]), safe_parse(chk["eps"]))
        elif chk["verdict"] == "diverges":
            ok, detail = alternating_diverges(term)
        else:
            ok, detail = alternating_converges(term, b, start)
        return [["P8 independent numeric check of the alternating-series estimate", ok, detail]]
    return [["P8 unknown check kind", False, chk["kind"]]]
