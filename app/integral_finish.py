"""Shared tail for the integration topics after u-substitution.

Bounds that may be infinite, improper pieces, the answer rule for each calculator level, a table-only test
built on SymPy's manual-integration rule tree, and `finish`, the one function that turns an integrand f, an
antiderivative F and the method's worked steps into the verified result every topic returns.

Used by app/by_parts.py and the other topic verifiers. app/usub.py keeps its own tail (its steps and nested
substitutions are specific to that topic) and imports only app/integral_core.py.
"""
import mpmath as mp
import sympy as sp
from sympy.integrals.manualintegrate import integral_steps

from app.clean_answer import canon, expression_reason, value_reason
from app.integral_core import (L, Reject, _CHECK_POINTS, _NON_ELEMENTARY, _TOL, _artifact, _crosscheck,
                               _derivative_matches, _discontinuities, _diverges, _hash, _same_function, _shape,
                               _with_timeout, x)
from app.safe_parse import ParseError, safe_parse

SCIENTIFIC_MAX = 10 ** 4      # a scientific-calculator answer must stay this small
_BAD_RULES = {"PartsRule", "CyclicPartsRule", "DontKnowRule", "TrigSubstitutionRule", "PartialFractionsRule",
              "SqrtQuadraticRule", "SqrtQuadraticDenomRule",
              "EiRule", "LiRule", "ErfRule", "FresnelCRule", "FresnelSRule", "UpperGammaRule", "SiRule", "CiRule"}
_INF = (sp.oo, -sp.oo)


def bound_ext(s: str, label: str):
    """A bound that may be -oo or oo as well as a finite real number."""
    try:
        e = safe_parse(s)
    except ParseError as err:
        raise Reject("slip", f"{label}: {err}") from None
    if e in _INF:
        return e
    if e.free_symbols or e.is_real is not True or e.has(sp.oo, sp.zoo, sp.nan):
        raise Reject("slip", f"{label} must be a real number, or oo")
    return e


def rule_tree(expr, var=x) -> set[str]:
    """Every SymPy manual-integration rule name used for expr, expanding all alternatives."""
    out: set[str] = set()

    def walk(step):
        out.add(type(step).__name__)
        for attr in ("substep", "substeps", "alternatives", "v_step", "second_step"):
            sub = getattr(step, attr, None)
            for s in (sub if isinstance(sub, (list, tuple)) else [sub] if sub is not None else []):
                walk(s)
    walk(integral_steps(expr, var))
    return out


def table_ok(expr, var=x) -> bool:
    """True when SymPy integrates expr with table forms, rewrites and substitution only: no parts, trig
    substitution, partial fractions or special function. SymPy answers DontKnowRule for some solvable forms,
    so False means 'not shown to be table-only', which is the conservative answer."""
    if expr == 0 or not expr.has(var):
        return True

    def ok(step) -> bool:
        if type(step).__name__ in _BAD_RULES:
            return False
        if type(step).__name__ == "AlternativeRule":
            return any(ok(a) for a in step.alternatives)
        subs = [s for s in (getattr(step, a, None) for a in ("substep", "v_step", "second_step")) if s is not None]
        subs += list(getattr(step, "substeps", None) or [])
        return all(ok(s) for s in subs)
    try:
        return ok(integral_steps(expr, var))
    except Exception:
        return False


_PLAIN = (sp.Add, sp.Mul, sp.Pow, sp.sin, sp.cos, sp.sinh, sp.cosh, sp.tanh, sp.sech, sp.exp, sp.atan,
          sp.Symbol, sp.Number, sp.NumberSymbol)
_SINGULAR = {sp.tan: sp.cos, sp.sec: sp.cos, sp.cot: sp.sin, sp.csc: sp.sin}


def fast_discontinuities(f, a, b):
    """The points of [a, b] where f is undefined, without calling continuous_domain (which can take minutes on
    trigonometric powers). Handles polynomials and exp, sin, cos and the hyperbolic functions (no singularities)
    and tan, sec, cot, csc of a linear argument. Returns None when f is outside what this can decide."""
    for node in sp.preorder_traversal(f):
        if isinstance(node, sp.Pow) and not (node.exp.is_Integer and node.exp >= 0):
            return None
        if isinstance(node, tuple(_SINGULAR)):
            continue
        if not isinstance(node, _PLAIN) and not isinstance(node, tuple(_SINGULAR)):
            return None
    pts = []
    for node in f.atoms(*_SINGULAR):
        arg = node.args[0]
        if not (arg.is_polynomial(x) and sp.degree(arg, x) == 1):
            return None
        k, c = sp.Poly(arg, x).coeff_monomial(x), sp.Poly(arg, x).coeff_monomial(1)
        base = sp.pi / 2 if isinstance(node, (sp.tan, sp.sec)) else 0
        lo, hi = float(sp.N(a)) if a not in _INF else -1e9, float(sp.N(b)) if b not in _INF else 1e9
        n_lo = int(sp.floor((min(lo, hi) * k - c - base) / sp.pi)) - 1 if k > 0 else None
        if k <= 0 or n_lo is None:
            return None
        n = n_lo
        while True:
            point = (base + n * sp.pi - c) / k
            if float(sp.N(point)) > hi + 1e-9:
                break
            if float(sp.N(point)) >= lo - 1e-9:
                pts.append(sp.nsimplify(point) if point.is_Rational else sp.simplify(point))
            n += 1
            if n - n_lo > 400:
                return None
    return sorted(set(pts), key=float)


def derivative_matches_fast(F, f) -> bool:
    """d/dx F equals f: numeric agreement at five or more check points first (the exact simplify of a trigonometric
    difference can take minutes), the exact test only when that is inconclusive."""
    dF = sp.diff(F, x)
    agree = 0
    for p in _CHECK_POINTS:
        try:
            a, b = complex(dF.subs(x, p).evalf(30)), complex(f.subs(x, p).evalf(30))
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        if any(v != v or abs(v) == float("inf") or abs(v.imag) > 1e-12 for v in (a, b)):
            continue
        if abs(a - b) > _TOL * max(1.0, abs(b)):
            return False
        agree += 1
    return agree >= 5 or _derivative_matches(F, f)


def _pt(v):
    return mp.inf if v == sp.oo else -mp.inf if v == -sp.oo else mp.mpf(str(sp.N(v, 30)))


def _finite_range_agrees(f, F, p) -> bool:
    """Slow tails (1/(x ln^2 x)) defeat quadrature to infinity, so check F against the integral of f over
    [p, 1e8] instead; the limit of F at infinity is taken symbolically by the caller."""
    mp.mp.dps = 25
    try:
        fn, Fn = sp.lambdify(x, f, modules="mpmath"), sp.lambdify(x, F, modules="mpmath")
        lo = mp.mpf(str(sp.N(p, 30)))
        cuts = [lo]
        while cuts[-1] < 1e8:
            cuts.append(max(cuts[-1], mp.mpf(1)) * 10)
        num, want = mp.quad(fn, cuts), complex(Fn(cuts[-1]) - Fn(lo))
        return abs(complex(num) - want) <= 1e-7 * max(1.0, abs(want))
    except (ValueError, TypeError, ZeroDivisionError, ArithmeticError):
        return False


def _crosscheck_ext(f, p, q, expected, F=None) -> bool:
    mp.mp.dps = 25
    failed = False
    try:
        num = mp.quad(sp.lambdify(x, f, modules="mpmath"), [_pt(p), _pt(q)])
        want = complex(sp.N(expected, 30))
        if abs(complex(num) - want) <= 1e-7 * max(1.0, abs(want)):
            return True
    except (ValueError, TypeError, ZeroDivisionError, ArithmeticError):
        failed = True
    if F is not None and q == sp.oo and p not in _INF and _finite_range_agrees(f, F, p):
        return True
    if failed:
        raise Reject("redraw", "numeric cross-check could not run")
    return False


def _end_limit(F, p, side):
    return sp.limit(F, x, p) if p in _INF else sp.limit(F, x, p, side)


def _key(v) -> float:
    return 1e300 if v == sp.oo else -1e300 if v == -sp.oo else float(sp.N(v))


def definite_ext(f, F, a, b, allow_improper: bool):
    """(value or None when divergent, pieces, points, method). Handles infinite bounds and, when
    allow_improper, points where the integrand is undefined."""
    finite = [p for p in (a, b) if p not in _INF]
    infinite = len(finite) < 2
    if len(finite) == 2:
        pts = fast_discontinuities(f, a, b)
        if pts is None:
            pts = _discontinuities(f, a, b)
    elif finite:
        lo, hi = (finite[0], finite[0] + 50) if b == sp.oo else (finite[0] - 50, finite[0])
        pts = [p for p in _discontinuities(f, lo, hi) if a <= p <= b]
    else:
        pts = []
    if pts and not allow_improper:
        raise Reject("redraw", "integrand is discontinuous on the interval")
    if infinite and not allow_improper:
        raise Reject("redraw", "an infinite bound is used only where improper integrals are in scope")
    if not pts and not infinite:
        value = sp.simplify(F.subs(x, b) - F.subs(x, a))
        if value.has(sp.zoo, sp.nan, sp.oo, -sp.oo):
            raise Reject("redraw", "antiderivative is undefined at a bound")
        if not _crosscheck(f, a, b, value):
            raise Reject("redraw", "numeric cross-check disagrees with the closed form")
        return value, [(a, b, value)], pts, "diff_antiderivative+mpmath"
    cuts = sorted({a, b, *pts}, key=_key)
    pieces, total = [], sp.Integer(0)
    for p, q in zip(cuts, cuts[1:]):
        hi, lo = _end_limit(F, q, "-"), _end_limit(F, p, "+")
        if _diverges(hi) or _diverges(lo):
            pieces.append((p, q, None))
            continue
        piece = sp.simplify(hi - lo)
        if not _crosscheck_ext(f, p, q, piece, F):
            raise Reject("redraw", "numeric cross-check disagrees with the closed form")
        pieces.append((p, q, piece))
        total += piece
    value = None if any(v is None for *_, v in pieces) else sp.simplify(total)
    return value, pieces, pts, "diff_antiderivative+limits+mpmath"


def improper_steps(F, pieces, pts, value, how: str = "Find an antiderivative.") -> list[dict]:
    cuts = " + ".join(f"\\int_{{{L(p)}}}^{{{L(q)}}}" for p, q, _ in pieces)
    steps = []
    if pts:
        where = ",\\ ".join(f"x = {L(p)}" for p in pts)
        steps.append({"text": "The integrand is undefined at a point of the interval, so this is an improper "
                              "integral. Split it at each such point.", "latex": where, "sympy": None})
    steps += [
        {"text": "Write each improper piece as a limit.", "latex": cuts, "sympy": None},
        {"text": how, "latex": f"{L(F)} + C", "sympy": str(F)},
    ]
    for p, q, piece in pieces:
        out = "\\text{diverges}" if piece is None else L(piece)
        steps.append({"text": "Evaluate the limits at the ends.", "sympy": None,
                      "latex": f"\\lim_{{x\\to {L(q)}}} F(x) - \\lim_{{x\\to {L(p)}}} F(x) = {out}"})
    steps.append({"text": "A divergent piece makes the whole integral diverge." if value is None
                  else "Every piece converges, so add them.",
                  "latex": "\\text{diverges}" if value is None else L(canon(value)),
                  "sympy": None if value is None else str(canon(value))})
    return steps


def scientific_reason(value) -> str | None:
    """The scientific-calculator tier: any real number of modest size, shown to three decimals."""
    v = sp.N(value, 30)
    if v.is_real is not True or v.has(sp.nan, sp.zoo, sp.oo, -sp.oo):
        return "not_real"
    if abs(v) > SCIENTIFIC_MAX or (v != 0 and abs(v) < 1e-3):
        return "decimal_size"
    return None


def generic_raw(f, F, steps, definite: bool, has_disc: bool, answer_type: str, extra: dict | None = None) -> dict:
    """The measures app/difficulty.py v0 reads (the same keys as app/usub.py), computed from the integrand."""
    raw = {
        "ops_integrand": int(sp.count_ops(f)), "ops_R": int(sp.count_ops(f)), "ops_F": int(sp.count_ops(F)),
        "g_polynomial": True, "deg_g": None, "n_terms_R": len(sp.Add.make_args(sp.expand(f))),
        "const_factor": False, "definite": definite, "has_discontinuity": has_disc, "steps": len(steps),
        "answer_type": answer_type,
    }
    raw.update(extra or {})
    if "rules" not in raw:      # a topic that knows its own method passes `rules`; SymPy's tree can hang on trig powers
        raw["rules"] = _with_timeout(5, lambda: sorted(rule_tree(f)))
    return raw


def _under(expr) -> str:
    """The integrand as typeset under the integral sign: a sum is wrapped, so dx applies to all of it."""
    return f"\\left({L(expr)}\\right)" if isinstance(expr, sp.Add) else L(expr)


def _non_real_where_integrand_real(f, F) -> bool:
    """True if F has an imaginary part at a sample point where f is real. SymPy sometimes returns a form such as
    ln(-1 + sqrt(x^2 - 1)/x) that differs from a real antiderivative only by a constant i*pi/2; that is correct
    to differentiate but is not an answer a student can be shown."""
    for v in ("3/10", "7/10", "7/5", "11/5", "18/5"):
        pt = sp.Rational(v)
        try:
            fv = complex(sp.N(f.subs(x, pt), 15))
            if abs(fv.imag) > 1e-12 or fv != fv:
                continue
            Fv = complex(sp.N(F.subs(x, pt), 15))
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        if Fv == Fv and abs(Fv.imag) > 1e-9:
            return True
    return False


def finish(f, F, shown, steps, bounds, *, calculator: str = "none", allow_improper: bool = False,
           how: str = "Find an antiderivative.", extra_raw: dict | None = None, hyperbolic: bool = False,
           forbid_zero: bool = False) -> dict:
    """Turn an integrand f, a candidate antiderivative F and the method's steps into the verified result.

    `shown` is the integrand the student sees (equal to f; the topic's disguise). The derivative check and, for
    definite integrals, a numeric cross-check run here, so every topic gets them the same way."""
    if why := _artifact(f, F):
        raise Reject("redraw", why)
    if F.has(*_NON_ELEMENTARY):
        raise Reject("redraw", "no elementary antiderivative")
    if _non_real_where_integrand_real(f, F):
        # ln(arg) and ln|arg| differ by a constant, so writing |arg| keeps F an antiderivative and makes it real
        F = F.replace(sp.log, lambda arg: sp.log(sp.Abs(arg)))
        if _non_real_where_integrand_real(f, F):
            raise Reject("redraw", "the antiderivative is not real where the integrand is")
    if not derivative_matches_fast(F, f):
        raise Reject("redraw", "antiderivative failed the derivative check")
    if shown is not f and not _same_function(shown, f):
        raise Reject("redraw", "the displayed integrand does not match the integrand")
    steps = list(steps)
    definite = bounds is not None
    pts: list = []
    if not definite:
        if calculator == "none" and (r := expression_reason(F, x, True)):
            raise Reject("redraw", f"answer is not a short exact form ({r})", cap=r)
        statement = f"Find $\\displaystyle \\int {_under(shown)}\\,dx$."
        answer = {"type": "expression", "latex": f"{L(F)} + C", "sympy": str(F), "numeric": None}
        method, calc = "diff_antiderivative", "passed"
    else:
        a, b = bounds
        if not _key(a) < _key(b):
            raise Reject("slip", "lower bound must be less than upper bound")
        value, pieces, pts, method = definite_ext(f, F, a, b, allow_improper)
        if hyperbolic and value is not None:       # sinh(1) is shown as (e - 1/e)/2, which the answer rule knows
            value = sp.simplify(value.rewrite(sp.exp))
        if forbid_zero and value == 0:
            raise Reject("redraw", "the value is exactly 0, which a student can guess")
        end = ("Give the answer to three decimal places, or state that it diverges." if calculator == "scientific"
               else "Give an exact answer, or state that it diverges.")
        statement = f"Evaluate $\\displaystyle \\int_{{{L(a)}}}^{{{L(b)}}} {_under(shown)}\\,dx$. {end}"
        if value is not None:
            if calculator == "scientific":
                if r := scientific_reason(value):
                    raise Reject("redraw", f"answer is not a usable decimal ({r})", cap=r)
            elif r := value_reason(value, True):
                raise Reject("redraw", f"answer is not a short exact form ({r})", cap=r)
            value = canon(value)
        if pts or any(p in _INF for p in (a, b)):
            steps += improper_steps(F, pieces, pts, value, how)
        else:
            steps.append({"text": "Evaluate between the bounds.", "sympy": str(value),
                          "latex": f"\\left[{L(F)}\\right]_{{{L(a)}}}^{{{L(b)}}} = {L(value)}"})
        if value is None:
            answer = {"type": "enum", "latex": "\\text{diverges}", "sympy": None, "numeric": None}
            calc = "n/a"
        else:
            num = float(sp.N(value))
            latex = f"{num:.3f}" if calculator == "scientific" else L(value)
            answer = {"type": "numeric", "latex": latex, "sympy": str(value), "numeric": num}
            calc = "passed"
    raw = generic_raw(f, F, steps, definite, bool(pts), answer["type"], extra_raw)
    return {"ok": True, "statement": statement, "answer": answer, "steps": steps, "method": method,
            "calculator_check": calc, "hash": _hash(f, (bounds[0], bounds[1]) if definite else None),
            "shape": _shape(f, definite), "has_discontinuity": bool(pts), "integrand": str(f), "raw": raw}
