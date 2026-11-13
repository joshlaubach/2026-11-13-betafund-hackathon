"""No-calculator answer rule: the final answer must be a short exact form.

Tier A constants: pi^k (integer k up to MAX_POW), e^a (any integer or fraction a), square and cube roots of integers.
Tier B values: ln m, sin/cos/tan/asin/acos/atan of a small rational or of a reciprocal constant (1/pi, 2/e,
1/(pi*e)), and e raised to a reciprocal constant (e^(1/e)).
Every cap below is a starting guess; the returned reason is logged so the
pass-rate script can show which cap rejects the most candidates.
"""
import sympy as sp

MAX_INT = 999      # numerators, denominators, radicands, log arguments
MAX_TERMS = 3
MAX_POW = 4        # exponent on pi or e
ROOT_INDEX = {2, 3}
MAX_ARG = 9        # numerator and denominator of a trig argument
MAX_FACTORS = 2    # irrational factors per term
MAX_CONSTANTS = 3  # distinct irrational constants in the whole answer

_TRIG = (sp.sin, sp.cos, sp.tan, sp.asin, sp.acos, sp.atan)


def _reciprocal_constant(a) -> bool:
    """A small rational times 1/pi, 1/pi^2, 1/e or 1/e^2 (or their product): 1/pi, 2/e, 3/(pi*e)."""
    c, rest = a.as_coeff_Mul()
    if rest == 1 or not (c.is_Rational and c != 0 and abs(c.p) <= MAX_ARG and c.q <= MAX_ARG):
        return False
    for f in sp.Mul.make_args(rest):
        base, ex = f.as_base_exp()
        if base not in (sp.pi, sp.E) or not (ex.is_Integer and ex in (-1, -2)):
            return False
    return True


def canon(v):
    return sp.expand(sp.sqrtdenest(sp.radsimp(sp.simplify(v))))


def _extended_log(a) -> bool:
    """ln of a + b*sqrt(m): ln(1 + sqrt 2), ln(2 + sqrt 3). Only for the extended tier."""
    a = sp.expand(a)
    c, rest = a.as_independent(sp.sqrt(2), sp.sqrt(3), sp.sqrt(5), as_Add=True)
    if not (c.is_Integer and abs(c) <= 3 and rest != 0):
        return False
    k, r = rest.as_coeff_Mul()
    return k.is_Integer and abs(k) <= 3 and isinstance(r, sp.Pow) and r.exp == sp.Rational(1, 2) and r.base in (2, 3, 5)


def _kind(f, extended: bool = False):
    """'A' basic constant, 'B' unevaluated value, None if not allowed. `extended` (the integration topics after
    u-substitution) also allows e^(c*pi) for a small rational c and ln(a + b*sqrt(m))."""
    base, ex = f.as_base_exp()
    if base in (sp.pi, sp.E):
        if base == sp.E:
            if ex.is_Rational:
                return "A"                                              # e^a for any integer or fraction a
            if extended and ex.is_Mul and ex.args[-1] == sp.pi and ex.as_coeff_Mul()[0].is_Rational and                     abs(ex.as_coeff_Mul()[0].p) <= 3 and ex.as_coeff_Mul()[0].q <= 3 or (extended and ex == sp.pi):
                return "B"                                              # e^pi, e^(2 pi), e^(pi/2)
            return "B" if _reciprocal_constant(ex) else None            # e^(1/e), e^(2/pi)
        return "A" if ex.is_Integer and abs(ex) <= MAX_POW else None
    if base.is_Integer and 1 < base <= MAX_INT and ex.is_Rational and not ex.is_Integer:
        return "A" if ex.q in ROOT_INDEX and abs(ex.p) < ex.q else None
    if ex == 1 and isinstance(f, sp.log):
        a = f.args[0]
        if extended and _extended_log(a):
            return "B"
        return "B" if a.is_Integer and 1 < a <= MAX_INT else None
    if ex == 1 and isinstance(f, _TRIG):
        a = f.args[0]
        small = a.is_Rational and a != 0 and abs(a.p) <= MAX_ARG and a.q <= MAX_ARG
        return "B" if small or _reciprocal_constant(a) else None
    return None


def value_reason(v, extended: bool = False) -> str | None:
    """None if the value is a clean exact answer, else the name of the cap it broke."""
    v = canon(v)
    if v.has(sp.Float):
        return "float"
    if v.is_real is not True:
        return "not_real"
    terms = sp.Add.make_args(v)
    if len(terms) > MAX_TERMS:
        return "too_many_terms"
    constants = set()
    for t in terms:
        c, rest = t.as_coeff_Mul()
        if not (c.is_Rational and abs(c.p) <= MAX_INT and c.q <= MAX_INT):
            return "coefficient_size"
        factors = [] if rest == 1 else list(sp.Mul.make_args(rest))
        kinds = [_kind(f, extended) for f in factors]
        if None in kinds:
            return "factor_not_allowed"
        if len(factors) > MAX_FACTORS or kinds.count("B") > 1:
            return "too_many_factors"
        constants.update(f.as_base_exp()[0] for f in factors)
    return "too_many_constants" if len(constants) > MAX_CONSTANTS else None


def expression_reason(F, x, extended: bool = False) -> str | None:
    """Indefinite answers: the rule applies to the numeric coefficient of each term."""
    for t in sp.Add.make_args(F):
        c = t.as_independent(x, as_Add=False)[0]
        if c != 1 and (r := value_reason(c, extended)):
            return r
    return None
