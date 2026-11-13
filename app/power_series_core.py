"""Exact power-series arithmetic for C9: known series as Fraction lists, and the matcher that reads a function of x
as constant * x^m * (up to two known series evaluated at a x^p). The coefficient lists are an independent derivation
from SymPy's own series; `power_series_checks` compares them with a direct mpmath evaluation of the function."""
import math
from fractions import Fraction

import sympy as sp

from app.integral_core import Reject, x

DEG = 44                      # degree of the lists used by the independent evaluation
MAX_SHIFT = 6                 # highest power of x multiplied in front
MAX_INNER = 3                 # highest p in u = a x^p
BASE_NAMES = {"geom": "geometric", "exp": "exponential", "sin": "trigonometric", "cos": "trigonometric",
              "log1p": "log_atan", "atan": "log_atan"}


def base_series(kind, deg=DEG):
    out = [Fraction(0)] * (deg + 1)
    for k in range(deg + 1):
        if kind == "geom":
            out[k] = Fraction(1)
        elif kind == "exp":
            out[k] = Fraction(1, math.factorial(k))
        elif kind == "sin" and k % 2:
            out[k] = Fraction((-1) ** ((k - 1) // 2), math.factorial(k))
        elif kind == "cos" and k % 2 == 0:
            out[k] = Fraction((-1) ** (k // 2), math.factorial(k))
        elif kind == "log1p" and k:
            out[k] = Fraction((-1) ** (k + 1), k)
        elif kind == "atan" and k % 2:
            out[k] = Fraction((-1) ** ((k - 1) // 2), k)
    return out


def substitute(coeffs, a, p, deg=DEG):
    out = [Fraction(0)] * (deg + 1)
    for k, c in enumerate(coeffs):
        if p * k > deg:
            break
        out[p * k] = c * a ** k
    return out


def multiply(left, right, deg=DEG):
    out = [Fraction(0)] * (deg + 1)
    for i, c in enumerate(left):
        if c:
            for j in range(deg + 1 - i):
                out[i + j] += c * right[j]
    return out


def shift(coeffs, m, deg=DEG):
    return ([Fraction(0)] * m + coeffs)[:deg + 1]


def derivative(coeffs):
    return [(k + 1) * c for k, c in enumerate(coeffs[1:])] + [Fraction(0)]


def antiderivative(coeffs):
    return [Fraction(0)] + [c / (k + 1) for k, c in enumerate(coeffs[:-1])]


def _monomial(u):
    """(a, p) with u = a x^p, a a nonzero rational and 1 <= p <= MAX_INNER, else None."""
    c, e = u.as_coeff_exponent(x)
    if c.is_Rational is True and c != 0 and e.is_Integer is True and 1 <= e <= MAX_INNER:
        return Fraction(int(c.p), int(c.q)), int(e)
    return None


def _factor(g):
    """(kind, a, p, scale) when g is a known series of a x^p, or None."""
    kinds = {sp.exp: "exp", sp.sin: "sin", sp.cos: "cos", sp.atan: "atan"}
    if isinstance(g, tuple(kinds)):
        mono = _monomial(g.args[0])
        return (kinds[type(g)], *mono, Fraction(1)) if mono else None
    if isinstance(g, sp.log):
        arg = g.args[0]
        mono = _monomial(arg - 1) if arg.subs(x, 0) == 1 else None
        return ("log1p", *mono, Fraction(1)) if mono else None
    if g.is_Pow and g.exp == -1 and g.base.is_polynomial(x):
        c0 = g.base.subs(x, 0)
        mono = _monomial(g.base - c0) if c0.is_Rational is True and c0 != 0 else None
        if mono:
            return ("geom", -mono[0] / Fraction(int(c0.p), int(c0.q)), mono[1], 1 / Fraction(int(c0.p), int(c0.q)))
    return None


def parse_function(f):
    """List of terms {c, m, factors:[(kind, a, p)]} for f = sum of c x^m * known series, else a Reject."""
    terms = []
    for t in sp.Add.make_args(f):
        c, rest = t.as_independent(x, as_Add=False)
        if c.is_Rational is not True or c == 0:
            raise Reject("redraw", "each term needs a rational coefficient")
        coeff, m, factors = Fraction(int(c.p), int(c.q)), 0, []
        for g in sp.Mul.make_args(rest):
            if g == x:
                m += 1
            elif g.is_Pow and g.base == x and g.exp.is_Integer is True and g.exp > 0:
                m += int(g.exp)
            elif rest != 1:
                got = _factor(g)
                if got is None:
                    raise Reject("redraw", "function is outside the power-series scope whitelist")
                factors.append(got[:3])
                coeff *= got[3]
        if m > MAX_SHIFT or len(factors) > 2:
            raise Reject("redraw", "function is outside the power-series scope whitelist")
        terms.append({"c": coeff, "m": m, "factors": factors})
    if len(terms) > 2:
        raise Reject("redraw", "function is outside the power-series scope whitelist")
    if not any(t["factors"] for t in terms):
        raise Reject("redraw", "the function needs at least one known series (geometric, exp, sin, cos, ln or arctan)")
    return terms


def term_series(term, deg=DEG):
    out = [term["c"]] + [Fraction(0)] * deg
    for kind, a, p in term["factors"]:
        out = multiply(out, substitute(base_series(kind, deg), a, p, deg), deg)
    return shift(out, term["m"], deg)


def function_series(terms, deg=DEG):
    out = [Fraction(0)] * (deg + 1)
    for t in terms:
        out = [u + v for u, v in zip(out, term_series(t, deg))]
    return out


def family_of(terms):
    if len(terms) > 1:
        return "combination"
    factors = terms[0]["factors"]
    return "product" if len(factors) == 2 else BASE_NAMES[factors[0][0]]


def safe_radius(terms):
    """A point x0 in (0, 1/2] where every factor's inner argument has magnitude at most 1/4."""
    x0 = Fraction(1, 2)
    for t in terms:
        for kind, a, p in t["factors"]:
            if kind in ("geom", "log1p", "atan"):
                while abs(a) * x0 ** p > Fraction(1, 4):
                    x0 /= 2
    return x0


def sympy_coefficient(f, k):
    """Coefficient of x^k from SymPy's own series (the derivation the Fraction lists are compared with)."""
    return sp.series(f, x, 0, k + 1).removeO().coeff(x, k)


def to_rational(frac):
    return sp.Rational(frac.numerator, frac.denominator)
