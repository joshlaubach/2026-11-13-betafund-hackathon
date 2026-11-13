"""Convergence-test derivations shared by the C8 series-test verifiers (and by C9's radius of convergence).

All limits come from SymPy and are cross-checked by `series_tests_checks`; nothing here reads model output except
through `app.safe_parse`. Public helpers for other chapters: `ratio_limit`, `root_limit`, `abs_term`.
"""
import sympy as sp

from app.integral_core import Reject, _parse

n = sp.Symbol("n", integer=True, positive=True)
x = sp.Symbol("x", positive=True)

TEST_NAMES = {"nth_term": "nth-term test", "ratio": "Ratio Test", "root": "Root Test",
              "limit_comparison": "Limit Comparison Test", "comparison": "Direct Comparison Test",
              "integral": "Integral Test"}
_ALLOWED_FUNCS = (sp.factorial, sp.log, sp.exp)
_GRID = tuple(range(0, 400, 7))


def parse_term(s, label="term"):
    if not isinstance(s, str):
        raise Reject("slip", f"{label} must be a string")
    t = _parse(s, n, label)
    if t.has(sp.Float, sp.Abs) or sp.count_ops(t) > 30:
        raise Reject("redraw", f"{label} must use exact numbers, no absolute value and at most 30 operations")
    if any(not isinstance(f, _ALLOWED_FUNCS) for f in t.atoms(sp.Function)):
        raise Reject("redraw", f"{label} is outside the series scope whitelist (factorial, ln, exp, powers, roots)")
    if any(p.exp.has(n) and p.base.has(n) and p.base != n and not p.base.is_rational_function(n)
           for p in t.atoms(sp.Pow)):
        raise Reject("redraw", f"{label}: a power with n in the exponent needs a rational base")
    return t


def _clean(v):
    if v is None or v.has(sp.Limit, sp.nan, sp.zoo) or v.is_extended_real is False:
        return None
    return v


def _lim(expr, var=n):
    try:
        return _clean(sp.limit(expr, var, sp.oo))
    except (RecursionError, NotImplementedError, ValueError, TypeError, ZeroDivisionError, AttributeError):
        return None


def sign_atoms(t, var=n):
    """Powers with a negative rational base and var in the exponent: (-1)^n, (-2)^n, (-1/3)^n."""
    return [p for p in t.atoms(sp.Pow) if p.base.is_Rational and p.base < 0 and p.exp.has(var)]


def abs_term(t, var=n):
    """The term with any alternating sign factor and constant sign removed (for |a_n|)."""
    s = t
    for p in sign_atoms(t, var):
        s = s.subs(p, (-p.base) ** p.exp)
    import mpmath as mp
    return -s if sp.lambdify(var, s, "mpmath")(mp.mpf(1000)) < 0 else s


def ratio_limit(b, var=n):
    """lim |b(n+1)/b(n)| as an exact value (oo allowed), or None if SymPy cannot decide."""
    b = abs_term(b, var)
    r = _lim(sp.gammasimp(b.subs(var, var + 1) / b), var)
    return None if r is None or (r.is_finite and r < 0) else r


def root_limit(b, var=n):
    """lim |b(n)|^(1/n) as an exact value (oo allowed), or None."""
    b = abs_term(b, var)
    return _lim(sp.powdenest(sp.powsimp(b ** (1 / var), force=True), force=True), var)


def lc_exponent(b):
    """(p, L) with b(n) ~ L / n^p, p rational and L finite and positive, or None."""
    q = _lim(sp.log(b) / sp.log(n))
    if q is None or q.is_Rational is not True:
        return None
    L = _lim(b * n ** (-q))
    return None if L is None or L.is_finite is not True or not L > 0 else (-q, L)


def has_factorial(b):
    return b.has(sp.factorial)


def has_log(b):
    return b.has(sp.log)


def exponential_in_n(b):
    return any(p.exp.has(n) for p in b.atoms(sp.Pow)) or b.has(sp.exp)


def ratio_ok(b):
    """The Ratio Test is offered on factorials, constant^n, n^n and n^k terms, not on (rational in n)^n."""
    return has_factorial(b) or (exponential_in_n(b) and all(
        not p.base.has(n) or p.base == n for p in b.atoms(sp.Pow) if p.exp.has(n)))


def algebraic(b):
    return not (has_factorial(b) or has_log(b) or exponential_in_n(b))


def _verdict_from(r):
    if r is None or r == 1:
        return None
    return "converges" if r < 1 else "diverges"


def _power_form(b):
    c, rest = b.as_independent(n, as_Add=False)
    if c.is_Rational is not True or not c > 0 or not rest.is_Pow:
        return False
    base, e = rest.as_base_exp()
    if e.is_Rational is not True or not e < 0 or not base.is_polynomial(n) or sp.degree(base, n) != 1:
        return False
    poly = sp.Poly(base, n)
    return poly.LC().is_Rational is True and poly.LC() > 0 and poly.coeff_monomial(1).is_Integer is True


def integral_form(b):
    """Name of the closed-form family the Integral Test is offered for, or None."""
    if _power_form(b):
        return "power"
    c, q, p, d, k, j, m = (sp.Wild(w, exclude=[n]) for w in "cqpdkjm")
    for name, pat in (("log_power", c / (n * sp.log(n) ** q)), ("ln_over_power", c * sp.log(n) / n ** p),
                      ("atan", c / (n ** 2 + d)), ("gaussian", c * n ** j * sp.exp(-k * n ** m))):
        got = b.match(pat)
        if not got or not all(v.is_Rational is True for v in got.values()) or not got[c] > 0:
            continue
        if name == "log_power" and got[q] > 0 or name == "ln_over_power" and got[p] > 1 or                 name == "atan" and got[d] > 0 or name == "gaussian" and got[k] > 0 and got[m] in (1, 2)                 and got[j] in (0, 1, 2):
            return name
    return None


def antiderivative(b):
    """F(x) with F' = b(x) for a term the Integral Test is offered for; verified by differentiation."""
    f = b.subs(n, x)
    F = sp.integrate(f, x)
    if F.has(sp.Integral) or sp.simplify(sp.diff(F, x) - f) != 0:
        return None
    return F


def tail_value(F, lower):
    """lim_{X->oo} F(X) - F(lower), or None when it is infinite."""
    top = _lim(F, x)
    if top is None or top.is_finite is not True:
        return None
    return sp.simplify(top - F.subs(x, lower))


def decreasing_from(b, start):
    """(True, method) when b(n+1) < b(n) for every n >= start; rational terms are decided exactly by the real roots
    of the difference's numerator, the others by a dense numeric grid plus very large n."""
    d = sp.cancel(sp.together(b.subs(n, n + 1) - b))
    if b.is_rational_function(n):
        num, den = sp.fraction(d)
        if any(r >= start for r in sp.Poly(den, n).real_roots()):
            return False, "exact"
        pn = sp.Poly(num, n)
        roots = pn.real_roots() if pn.degree() > 0 else []
        lead = pn.LC()
        ok = all(r < start for r in roots) and (lead < 0) == (sp.Poly(den, n).LC() > 0) and num != 0
        return bool(ok), "exact"
    import mpmath as mp
    mp.mp.dps = 40
    fn = sp.lambdify(n, b, "mpmath")
    pts = [start + i for i in _GRID] + [10 ** 3, 10 ** 5, 10 ** 7]
    try:
        return all(fn(mp.mpf(i) + 1) < fn(mp.mpf(i)) for i in pts), "grid"
    except (ValueError, ZeroDivisionError, ArithmeticError):
        return False, "grid"


def positive_from(b, start):
    import mpmath as mp
    mp.mp.dps = 40
    fn = sp.lambdify(n, b, "mpmath")
    try:
        return all(fn(mp.mpf(i)) > 0 for i in [start + j for j in range(60)] + [10 ** 3, 10 ** 6])
    except (ValueError, ZeroDivisionError, ArithmeticError, TypeError):
        return False


def conclusive_tests(b, start, wanted=None):
    """Every convergence test that decides the positive series sum b(n): name -> {"verdict", "value", ...}."""
    out = {}
    names = wanted or tuple(TEST_NAMES)
    if "nth_term" in names:
        v = _lim(b)
        if v is not None and v != 0:
            out["nth_term"] = {"verdict": "diverges", "value": v}
    if "ratio" in names and ratio_ok(b):
        r = ratio_limit(b)
        if _verdict_from(r):
            out["ratio"] = {"verdict": _verdict_from(r), "value": r}
    if "root" in names and not (has_factorial(b) or has_log(b)) and exponential_in_n(b):
        r = root_limit(b)
        if _verdict_from(r):
            out["root"] = {"verdict": _verdict_from(r), "value": r}
    if "limit_comparison" in names and algebraic(b):
        got = lc_exponent(b)
        if got and got[0] > 0:
            out["limit_comparison"] = {"verdict": "converges" if got[0] > 1 else "diverges", "value": got[1],
                                       "p": got[0]}
    if "comparison" in names and has_log(b) and not has_factorial(b):
        c, rest = b.as_independent(n, as_Add=False)
        base, e = rest.as_base_exp()
        if c.is_Rational is True and c > 0 and base == sp.log(n) and e.is_Rational is True and e < 0:
            out["comparison"] = {"verdict": "diverges", "value": c}
    if "integral" in names:
        form = integral_form(b)
        if form and decreasing_from(b, start)[0]:
            F = antiderivative(b)
            if F is not None:
                tail = tail_value(F, start)
                out["integral"] = {"verdict": "diverges" if tail is None else "converges", "value": tail,
                                   "form": form, "F": F}
    return out
