"""Helpers shared by every integration verifier: parsing, the derivative check, definite and improper
evaluation, hashing and printing. Moved out of app/calc1/usub.py unchanged; usub.py imports them back, so its
behavior is the same."""
import hashlib
import signal

import mpmath as mp
import sympy as sp
from sympy.printing.latex import LatexPrinter
from sympy.calculus.util import continuous_domain

from app.safe_parse import ParseError, safe_parse

x = sp.Symbol("x", real=True)

_NON_ELEMENTARY = (sp.Integral, sp.Piecewise, sp.erf, sp.erfi, sp.erfc, sp.Ei, sp.li, sp.Si, sp.Ci,
                   sp.Shi, sp.Chi, sp.fresnels, sp.fresnelc, sp.polylog, sp.gamma,
                   sp.uppergamma, sp.lowergamma, sp.hyper, sp.meijerg)
_NOT_PLAIN = (sp.Integral, sp.Derivative, sp.Limit, sp.Sum, sp.Product, sp.Piecewise,
              sp.oo, sp.zoo, sp.nan, sp.I)
_CHECK_POINTS = [sp.Rational(n, 100) for n in (37, 113, 191, -61, 243, -157, 71, 337, 521, 907, -233)]
_TOL = 1e-9
MAX_EXPONENT = 50


class _Latex(LatexPrinter):
    def _print_Pow(self, expr):
        """A power of a logarithm reads ln^3(x), like sin^3(x). SymPy's ln(x)^3 can be read as ln of a cube."""
        base, e = expr.as_base_exp()
        if isinstance(base, sp.log) and len(base.args) == 1 and e.is_Number and e > 0 and e != sp.Rational(1, 2):
            return rf"\ln^{{{self._print(e)}}}{{\left({self._print(base.args[0])} \right)}}"
        return super()._print_Pow(expr)


def L(e) -> str:
    return _Latex({"ln_notation": True, "inv_trig_style": "full"}).doprint(e)


def _tidy(gp):
    """d/dx tan shown as sec^2 and d/dx cot as -csc^2, as a textbook writes them."""
    a = sp.Wild("a")
    return gp.replace(sp.tan(a) ** 2 + 1, sp.sec(a) ** 2).replace(-sp.cot(a) ** 2 - 1, -sp.csc(a) ** 2)


def _diff(gp) -> str:
    return f"\\left({L(gp)}\\right)" if isinstance(gp, sp.Add) else L(gp)


def _artifact(f, F) -> str | None:
    """Simplification artifacts that no student should see: |.| from sqrt(1-sin^2) and the like,
    or an inverse trig function straight over its own trig function."""
    if f.has(sp.Abs, sp.sign):
        return "the integrand contains an absolute value after simplifying"
    if any(a.args[0].func in (sp.sin, sp.cos, sp.tan) for a in F.atoms(sp.asin, sp.acos)):
        return "the answer contains an inverse trig function of its own trig function"
    return None


class Reject(Exception):
    def __init__(self, cause: str, reason: str, cap: str | None = None):
        super().__init__(reason)
        self.cause, self.reason, self.cap = cause, reason, cap


def _parse(s: str, sym: sp.Symbol, label: str, depends: bool = True) -> sp.Expr:
    try:
        e = safe_parse(s, {sym.name: sym})
    except ParseError as err:
        raise Reject("slip", f"{label}: {err}") from None
    if not isinstance(e, sp.Expr) or e.has(*_NOT_PLAIN):
        raise Reject("slip", f"{label} must be a plain real expression")
    if any(p.exp.is_Number and abs(p.exp) > MAX_EXPONENT for p in e.atoms(sp.Pow)):
        raise Reject("slip", f"{label}: exponents must be at most {MAX_EXPONENT} in size")
    extra = e.free_symbols - {sym}
    if extra:
        raise Reject("slip", f"{label} must contain only {sym}; found {', '.join(sorted(map(str, extra)))}")
    if depends and sym not in e.free_symbols:
        raise Reject("slip", f"{label} must depend on {sym}")
    return e


def _bound(s: str, label: str) -> sp.Expr:
    try:
        e = safe_parse(s)
    except ParseError as err:
        raise Reject("slip", f"{label}: {err}") from None
    if e.free_symbols or e.is_real is not True or e.has(sp.oo, sp.zoo, sp.nan):
        raise Reject("slip", f"{label} must be a finite real number")
    return e


def _derivative_matches(F, f) -> bool:
    """d/dx F equals f: simplify to zero, or agree numerically at points where both sides are
    real and finite (outside the domain of e.g. ln(x) one side is complex, and says nothing)."""
    dF = sp.diff(F, x)
    if sp.simplify(dF - f) == 0:
        return True
    ok = 0
    for p in _CHECK_POINTS:
        try:
            a, b = complex(dF.subs(x, p).evalf(30)), complex(f.subs(x, p).evalf(30))
        except (TypeError, ValueError):
            continue
        if any(v != v or abs(v) == float("inf") or abs(v.imag) > 1e-12 for v in (a, b)):
            continue
        if abs(a - b) > _TOL * max(1.0, abs(b)):
            return False
        ok += 1
    return ok >= 3


def _discontinuities(f, a, b) -> list:
    span = sp.Interval(a, b)
    try:
        bad = span - continuous_domain(f, x, span)
    except NotImplementedError:
        raise Reject("redraw", "could not locate the discontinuities") from None
    if bad.is_empty:
        return []
    if not isinstance(bad, sp.FiniteSet):
        raise Reject("redraw", "integrand is discontinuous on an interval")
    return sorted(bad.args, key=float)


def _diverges(L) -> bool:
    if L.has(sp.Limit, sp.AccumBounds):
        raise Reject("redraw", "could not evaluate a one-sided limit")
    return L.has(sp.oo, -sp.oo, sp.zoo, sp.nan)


def _crosscheck(f, p, q, expected) -> bool:
    mp.mp.dps = 25
    try:
        num = mp.quad(sp.lambdify(x, f, modules="mpmath"),
                      [mp.mpf(str(sp.N(p, 30))), mp.mpf(str(sp.N(q, 30)))])
        want = complex(sp.N(expected, 30))
        return abs(complex(num) - want) <= _TOL * max(1.0, abs(want))
    except (ValueError, TypeError, ZeroDivisionError, ArithmeticError):
        raise Reject("redraw", "numeric cross-check could not run") from None



def _definite(f, F, a, b, trap):
    """Return (value or None if divergent, pieces, discontinuity points, method)."""
    pts = _discontinuities(f, a, b)
    if trap and not pts:
        raise Reject("redraw", "trap recipe produced a continuous integrand")
    if pts and not trap:
        raise Reject("redraw", "integrand is discontinuous on the interval")
    if not pts:
        value = sp.simplify(F.subs(x, b) - F.subs(x, a))
        if value.has(sp.zoo, sp.nan, sp.oo, -sp.oo):
            raise Reject("redraw", "antiderivative is undefined at a bound")
        if not _crosscheck(f, a, b, value):
            raise Reject("redraw", "numeric cross-check disagrees with the closed form")
        return value, [(a, b, value)], pts, "diff_antiderivative+mpmath"
    cuts = sorted({a, b, *pts}, key=float)
    pieces, total = [], sp.Integer(0)
    for p, q in zip(cuts, cuts[1:]):
        hi, lo = sp.limit(F, x, q, "-"), sp.limit(F, x, p, "+")
        if _diverges(hi) or _diverges(lo):
            pieces.append((p, q, None))
            continue
        piece = sp.simplify(hi - lo)
        if not _crosscheck(f, p, q, piece):
            raise Reject("redraw", "numeric cross-check disagrees with the closed form")
        pieces.append((p, q, piece))
        total += piece
    value = None if any(v is None for *_, v in pieces) else sp.simplify(total)
    return value, pieces, pts, "diff_antiderivative+limits+mpmath"


def _antiderivative(expr, v):
    G = sp.integrate(expr, v, manual=True)
    if G.has(*_NON_ELEMENTARY):
        raise Reject("redraw", "no elementary antiderivative")
    return G.replace(lambda e: isinstance(e, sp.log) and not e.args[0].has(sp.Abs),
                     lambda e: sp.log(sp.Abs(e.args[0])))


def _same_function(a, b) -> bool:
    """a and b agree numerically at the check points where both are finite (at least five of them)."""
    agreed = 0
    for p in _CHECK_POINTS:
        try:
            va, vb = complex(sp.N(a.subs(x, p))), complex(sp.N(b.subs(x, p)))
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        if any(z != z or abs(z) == float("inf") for z in (va, vb)):
            continue
        if abs(va - vb) > 1e-9 * (1 + abs(vb)):
            return False
        agreed += 1
    return agreed >= 5


def _hash(f, bounds) -> str:
    key = sp.srepr(f) + "|" + (sp.srepr(bounds) if bounds else "")
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _shape(f, definite: bool) -> str:
    """The integrand with its constants masked, so 3x^2 cos(x^3) and 5x^2 cos(x^3) agree. Exponents stay:
    (x^2+1)^3 and (x^3+1)^-2 are different problems, not the same functions with other constants."""
    c = sp.Symbol("c")
    f = f.replace(lambda e: e.is_Pow and e.exp.is_Number, lambda e: sp.Pow(e.base, sp.Symbol(f"e{e.exp}")))
    masked = f.xreplace({n: c for n in f.atoms(sp.Number)})
    return sp.srepr(masked) + ("|definite" if definite else "|indefinite")


def _with_timeout(seconds: float, fn, default=None):
    """Bound an optional measurement. SIGALRM exists on Linux (Vercel) but not on Windows
    dev machines, where the sandbox's own timeout is the only guard."""
    if not hasattr(signal, "setitimer"):
        try:
            return fn()
        except Exception:
            return default

    def _raise(*_):
        raise TimeoutError

    old = signal.signal(signal.SIGALRM, _raise)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        return fn()
    except Exception:
        return default
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def basic_primitive(f):
    """Integrate only sums of table forms with affine arguments, after algebraic expansion."""
    expanded = sp.expand(f)
    terms = sp.Add.make_args(expanded)
    if len(terms) > 8 or f == 0 or f.has(sp.Float):
        raise Reject("redraw", "basic scope requires one to eight nonzero exact table terms")

    def affine(e):
        return e.is_polynomial(x) and sp.degree(e, x) == 1

    for term in terms:
        c, rest = term.as_independent(x, as_Add=False)
        if not c.is_Rational or abs(c) > 30:
            raise Reject("redraw", "basic scope requires small rational coefficients")
        allowed = rest == 1 or rest == x
        base, power = rest.as_base_exp()
        if power.is_Rational and abs(power) <= 8 and power.q <= 3 and affine(base):
            allowed = True
        if rest.func in (sp.sin, sp.cos, sp.exp) and affine(rest.args[0]):
            allowed = True
        if base.func in (sp.sec, sp.csc) and power == 2 and affine(base.args[0]):
            allowed = True
        if power in (-1, -sp.Rational(1, 2)) and base.is_polynomial(x) and sp.degree(base, x) == 2:
            poly = sp.Poly(base, x)
            a, b, d = poly.all_coeffs()
            allowed = b == 0 and ((power == -1 and a > 0 and d > 0) or
                                  (power == -sp.Rational(1, 2) and a < 0 and d > 0))
        if not allowed:
            raise Reject("redraw", "outside basic scope: use table forms, not substitution, parts or partial fractions")
    F = _antiderivative(expanded, x)
    if not _derivative_matches(F, f):
        raise Reject("redraw", "basic antiderivative failed the derivative check")
    return F
