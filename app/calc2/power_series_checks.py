"""Independent numeric checks for the C9 power-series verifiers (mpmath only; no SymPy limits or series)."""
import mpmath as mp
import sympy as sp

from app.calc2 import power_series_core as core
from app.shared.integral_core import x
from app.calc2.series_tests_core import n

DPS = 50
TOL = mp.mpf("1e-15")
_RATIO_N, _ROOT_N = 1500, 3000


def _close(got, want, tol=TOL):
    return abs(got - want) <= tol * max(1, abs(want))


def _frac(c):
    return mp.mpf(c.numerator) / c.denominator


def same_function(left, right):
    """Two expressions in n agree at several integers (used to confirm a power simplification)."""
    mp.mp.dps = DPS
    fl, fr = sp.lambdify(n, left, "mpmath"), sp.lambdify(n, right, "mpmath")
    return all(_close(fl(mp.mpf(i)), fr(mp.mpf(i)), mp.mpf("1e-30")) for i in (3, 4, 5, 8, 11))


def radius_probe(c, R):
    """Late ratio |a(N+1)/a(N)| and root |a(N)|^(1/N) both sit near 1/R (below 0.01 when R is infinite)."""
    mp.mp.dps = DPS
    fn = sp.lambdify(n, c, "mpmath")
    N, M = mp.mpf(_RATIO_N), mp.mpf(_ROOT_N)
    ratio, root = abs(fn(N + 1) / fn(N)), abs(fn(M)) ** (1 / M)
    if R == sp.oo:
        return bool(ratio < mp.mpf("0.01") and root < mp.mpf("0.01")), f"ratio {mp.nstr(ratio, 6)}, root {mp.nstr(root, 6)}"
    want = 1 / mp.mpf(str(sp.N(R, DPS)))
    ok = _close(ratio, want, mp.mpf("0.02")) and _close(root, want, mp.mpf("0.03"))
    return bool(ok), f"ratio {mp.nstr(ratio, 6)}, root {mp.nstr(root, 6)}, 1/R {mp.nstr(want, 6)}"


def series_sum(term, start, value):
    """mpmath's nsum of the displayed series equals the claimed sum."""
    mp.mp.dps = DPS
    fn = sp.lambdify(n, term, "mpmath")
    got = mp.nsum(fn, [start, mp.inf])
    want = mp.mpf(str(sp.N(value, DPS)))
    return bool(_close(got, want, mp.mpf("1e-12"))), f"nsum {mp.nstr(got, 12)} vs {mp.nstr(want, 12)}"


def operation(f, terms, ask, target):
    """The exact series of f (or of f', or of the integral of f) agrees with a direct mpmath evaluation."""
    mp.mp.dps = DPS
    pt = _frac(core.safe_radius(terms))
    fx = sp.lambdify(x, f, "mpmath")
    direct = {"coeff": lambda: fx(pt), "deriv": lambda: mp.diff(fx, pt), "integral": lambda: mp.quad(fx, [0, pt])}[ask]()
    summed = sum(_frac(c) * pt ** j for j, c in enumerate(target))
    return bool(_close(summed, direct)), f"series {mp.nstr(summed, 15)} vs direct {mp.nstr(direct, 15)} at {mp.nstr(pt, 4)}"


def taylor_coefficient(f, a, k):
    """f^(k)(a)/k! from mpmath's numerical Taylor expansion."""
    mp.mp.dps = DPS
    fx = sp.lambdify(x, f, "mpmath")
    return mp.taylor(fx, mp.mpf(str(sp.N(a, DPS))), k)[k]


def coefficient_matches(f, a, k, value):
    got = taylor_coefficient(f, a, k)
    want = mp.mpf(str(sp.N(value, DPS)))
    return bool(_close(got, want, mp.mpf("1e-12"))), f"numerical Taylor coefficient {mp.nstr(got, 12)} vs {mp.nstr(want, 12)}"


def _num(v):
    return mp.mpf(str(sp.N(v, DPS)))


def max_at_endpoint(g, a, x1, M):
    """|g| is monotone on a 200-point grid of [a, x1] and its largest value is M, at an endpoint."""
    mp.mp.dps = DPS
    fn = sp.lambdify(x, g, "mpmath")
    lo, hi = _num(a), _num(x1)
    try:
        vals = [abs(fn(lo + (hi - lo) * i / 200)) for i in range(201)]
    except (ValueError, ZeroDivisionError, ArithmeticError, TypeError):
        return False, "g is undefined on the interval"
    slack = mp.mpf("1e-30")
    mono = all(u <= v + slack for u, v in zip(vals, vals[1:])) or all(u + slack >= v for u, v in zip(vals, vals[1:]))
    return bool(mono and _close(max(vals), _num(M), mp.mpf("1e-12"))), f"max on grid {mp.nstr(max(vals), 10)} vs M {mp.nstr(_num(M), 10)}"


def _numeric_bound(f, a, x1, n):
    fx = sp.lambdify(x, f, "mpmath")
    lo, hi = _num(a), _num(x1)
    M = max(abs(mp.diff(fx, lo, n + 1)), abs(mp.diff(fx, hi, n + 1)))
    return M * abs(hi - lo) ** (n + 1) / mp.factorial(n + 1)


def remainder_holds(f, a, x1, n, bound):
    """The bound equals one built from numerical derivatives, and the true error |f(x1) - P_n(x1)| is below it."""
    mp.mp.dps = DPS
    fx = sp.lambdify(x, f, "mpmath")
    lo, hi = _num(a), _num(x1)
    poly = sum(c * (hi - lo) ** j for j, c in enumerate(mp.taylor(fx, lo, n)))
    error, want = abs(fx(hi) - poly), _num(bound)
    ok = _close(_numeric_bound(f, a, x1, n), want, mp.mpf("1e-10")) and error <= want * (1 + mp.mpf("1e-12"))
    return bool(ok), f"true error {mp.nstr(error, 8)} <= bound {mp.nstr(want, 8)}"


def threshold_holds(f, a, x1, n, eps):
    """B(n) <= eps < B(n-1) with B built from numerical derivatives."""
    mp.mp.dps = DPS
    here, before, e = _numeric_bound(f, a, x1, n), _numeric_bound(f, a, x1, n - 1), _num(eps)
    return bool(here <= e * (1 + mp.mpf("1e-12")) and before > e), f"B({n}) = {mp.nstr(here, 8)}, B({n - 1}) = {mp.nstr(before, 8)}, eps = {mp.nstr(e, 8)}"


def binomial_radius(p, w, c0, q, R):
    """|w/c0| R^q = 1, and the binomial coefficient ratios tend to 1 (so the radius in u is 1)."""
    mp.mp.dps = DPS
    pm = _num(p)
    ratio = abs(mp.binomial(pm, 1001) / mp.binomial(pm, 1000))
    edge = abs(_num(w) / _num(c0)) * _num(R) ** q
    return bool(_close(edge, mp.mpf(1), mp.mpf("1e-12")) and abs(ratio - 1) < mp.mpf("0.01")), f"|u| at R = {mp.nstr(edge, 8)}, coefficient ratio {mp.nstr(ratio, 6)}"


def complex_matches(z, ask, n, value):
    """e^z or z^n evaluated with mpmath complex arithmetic equals the claimed a + bi."""
    mp.mp.dps = DPS
    zc = mp.mpc(_num(sp.re(z)), _num(sp.im(z)))
    got = zc ** n if ask == "power" else mp.exp(zc)
    want = mp.mpc(_num(sp.re(value)), _num(sp.im(value)))
    return bool(abs(got - want) <= mp.mpf("1e-25") * max(1, abs(want))), f"mpmath {mp.nstr(got, 12)} vs {mp.nstr(want, 12)}"


def _late_terms(c, R, sign, start):
    mp.mp.dps = DPS
    fn = sp.lambdify(n, c, "mpmath")
    return [abs(fn(mp.mpf(i)) * (sign * _num(R)) ** i) for i in (10 ** 5, 10 ** 6)]


def audit(topic, payload, answer, raw):
    """Packet audit entry point. Parsing still happens in the sandbox worker."""
    from app.safe_parse import safe_parse
    from app.calc2.series_tests_core import parse_term

    mp.mp.dps = DPS
    chk = raw["check"]
    kind = chk["kind"]
    if kind == "radius":
        c, R = parse_term(chk["c"]), safe_parse(chk["R_u"])
        ok, detail = radius_probe(c, R)
        out = [["P8 late ratio and root probes put the radius at R", ok, detail]]
        if answer["type"] == "numeric":
            out.append(["P8 the radius answer is R divided by m", abs(answer["numeric"] * chk["m"] - float(sp.N(R))) < 1e-9,
                        f"{answer['numeric']} * {chk['m']} vs {R}"])
        for label, sign in (("left", -1), ("right", 1)):
            if chk.get(label) is not None:
                late = _late_terms(c, R, sign, int(raw["start"]))
                small = max(late) < mp.mpf("0.01")
                end = chk[label]
                agrees = small if end["closed"] else (not small if end["kind"] == "terms" else True)
                out.append([f"P8 {label} endpoint: late terms are consistent with its verdict", agrees,
                            f"late terms {[mp.nstr(v, 6) for v in late]}, closed {end['closed']}"])
        return out
    if kind == "sum":
        return [["P8 nsum of the displayed series equals the answer", *series_sum(safe_parse(chk["term"], {"n": n}), int(chk["start"]), safe_parse(chk["value"]))]]
    f = safe_parse(chk["f"], {"x": x}) if "f" in chk else None
    if kind == "operation":
        terms = core.parse_function(f)
        series = core.function_series(terms)
        k = int(chk["k"])
        target = {"coeff": series, "deriv": core.derivative(series), "integral": core.antiderivative(series)}[chk["ask"]]
        ok, detail = operation(f, terms, chk["ask"], target)
        return [["P8 exact series agrees with a direct evaluation", ok, detail],
                ["P8 the answer is the series coefficient", core.to_rational(target[k]) == safe_parse(chk["value"]), chk["value"]]]
    if kind in ("coeff", "poly", "terms") and topic == "taylor_maclaurin":
        a = safe_parse(chk["a"])
        if kind == "coeff":
            return [["P8 numerical Taylor coefficient", *coefficient_matches(f, a, chk["k"], safe_parse(chk["value"]))]]
        if kind == "terms":
            return [[f"P8 numerical Taylor coefficient c_{j}", *coefficient_matches(f, a, j, safe_parse(c))] for j, c in chk["terms"]]
        coeffs = mp.taylor(sp.lambdify(x, f, "mpmath"), _num(a), chk["k"])
        h = _num(safe_parse(chk["x1"]) - a)
        total, want = sum(c * h ** j for j, c in enumerate(coeffs)), _num(safe_parse(chk["value"]))
        return [["P8 numerical Taylor polynomial value", _close(total, want, mp.mpf("1e-12")), f"{mp.nstr(total, 12)} vs {mp.nstr(want, 12)}"]]
    if topic == "binomial_series":
        base, pw = safe_parse(chk["base"], {"x": x}), safe_parse(chk["p"])
        if kind == "coeff":
            return [["P8 numerical Taylor coefficient", *coefficient_matches(base ** pw, 0, chk["k"], safe_parse(chk["value"]))]]
        c0 = base.subs(x, 0)
        w, q = (base - c0).as_coeff_exponent(x)
        if kind == "binomial_radius":
            return [["P8 coefficient ratios and the edge |u| = 1", *binomial_radius(pw, w, c0, int(q), safe_parse(chk["value"]))]]
        u = w * safe_parse(chk["x0"]) ** q
        total = sum(mp.binomial(_num(pw), j) * _num(u) ** j for j in range(chk["k"]))
        return [["P8 partial sum of the binomial series", _close(total, _num(safe_parse(chk["value"])), mp.mpf("1e-20")), mp.nstr(total, 12)]]
    if topic == "taylor_remainder":
        a, x1 = safe_parse(chk["a"]), safe_parse(chk["x1"])
        if kind == "bound":
            return [["P8 numerical-derivative bound and the true error", *remainder_holds(f, a, x1, chk["n"], safe_parse(chk["value"]))]]
        return [["P8 B(n) <= eps < B(n-1) from numerical derivatives", *threshold_holds(f, a, x1, chk["n"], safe_parse(chk["eps"]))]]
    if topic == "euler_formula":
        z = safe_parse(chk["z"])
        return [["P8 mpmath complex evaluation", *complex_matches(z, chk["ask"], chk["n"], safe_parse(chk["value"]))]]
    return [["P8 unknown check kind", False, kind]]
