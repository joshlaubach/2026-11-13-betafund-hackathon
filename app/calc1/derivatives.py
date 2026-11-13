"""Verifiers for the derivatives chapter (calc.derivatives.*), one entry point `verify(stem, ...)` run in the sandbox.

Milestone (a): difference_quotient, rate_of_change, limit_definition, differentiability, power_rule, trig,
exponential_log, inverse_trig, hyperbolic. The model supplies a function (and a point or parameters); the server
differentiates with SymPy, checks the result with finite differences at mpmath precision (app/shared/calculus_core.fd_agrees),
and writes the statement and the steps. Scope functions say which rule a topic may need; a function that needs the
product, quotient or chain rule is rejected here (those are milestone (b)).
"""
import mpmath as mp
import sympy as sp

from app.shared import function_pool as pool
from app.shared.calculus_core import (coefficient_reason, expression_answer, fd_agrees, finish, numeric_answer, step)
from app.shared.clean_answer import canon, value_reason
from app.shared.integral_core import L, Reject, _tidy, x
from app.calc1.limits import (_active_expr, _bps, _expr, _lam, _point, _show, _sub, _under, side_limit)

STEMS = ("difference_quotient", "rate_of_change", "limit_definition", "differentiability", "power_rule", "trig",
         "exponential_log", "inverse_trig", "dhyperbolic")
h = sp.Symbol("h", real=True)
MAX_TERMS = 4


def verify(stem: str, bounds=None, axes: dict | None = None, calculator: str = "none", **fields) -> dict:
    try:
        if stem not in STEMS:
            raise Reject("slip", f"unknown derivatives topic {stem}")
        if calculator != "none":
            raise Reject("redraw", "derivative topics have only the exact tier")
        return _VERIFY[stem](stem, axes or {}, **fields)
    except Reject as r:
        return {"ok": False, "cause": r.cause, "reason": r.reason, "cap": r.cap}


def _check(axes: dict, **found) -> None:
    for k, v in found.items():
        if k in axes and str(axes[k]) != str(v):
            raise Reject("redraw", f"axes: the server assigned {k} = {axes[k]} (this is {v})")


def _tidy2(d):
    """d/dx tanh as sech^2 and d/dx coth as -csch^2, with the trig tidy of the integral code."""
    a = sp.Wild("a")
    return _tidy(d).replace(1 - sp.tanh(a) ** 2, sp.sech(a) ** 2).replace(1 - sp.coth(a) ** 2, -sp.csch(a) ** 2)


def _linear(e) -> bool:
    return e.is_polynomial(x) and sp.degree(e, x) == 1


# -- rule topics: power_rule, trig, exponential_log, inverse_trig, hyperbolic -------------------------------------

_CLASSES = {
    "power_rule": (),
    "trig": (sp.sin, sp.cos, sp.tan, sp.cot, sp.sec, sp.csc),
    "exponential_log": (sp.exp, sp.log),
    "inverse_trig": (sp.asin, sp.acos, sp.atan, sp.acot, sp.exp),
    "dhyperbolic": (sp.sinh, sp.cosh, sp.tanh, sp.coth, sp.sech, sp.csch),
}
_OWN = {"power_rule": {"power", "root", "reciprocal"}, "trig": {"sincos", "tansec", "cotcsc"},
        "exponential_log": {"exp", "log"}, "inverse_trig": {"asin", "atan"},
        "dhyperbolic": {"sinhcosh", "tanhcoth", "sechcsch"}}


def _term_reason(t, classes) -> str | None:
    """None if t is c * (one standard form of this topic), else the rule it would need."""
    _, rest = t.as_independent(x, as_Add=False)
    if rest == 1 or rest == x:
        return None
    if rest.is_Pow and rest.base == x and rest.exp.is_Rational:
        return None
    if isinstance(rest, classes) and _linear(rest.args[0]):
        return None
    if rest.is_Pow and rest.base.is_number and rest.base != sp.E and _linear(rest.exp) and sp.exp in classes:
        return None                                        # a^x, a^(kx)
    if rest.is_Pow and isinstance(rest.base, classes):
        return "the chain rule (a power of a function)"
    if any(isinstance(n, classes) and not _linear(n.args[0]) for n in sp.preorder_traversal(rest) if n.args and classes
           and isinstance(n, classes)):
        return "the chain rule (a non-linear argument)"
    return "the product, quotient or chain rule"


def _fam_label(stem: str, f) -> str:
    own = pool.families_in(f) & _OWN[stem]
    if stem == "power_rule":
        if own == {"power"}:
            return "poly"
        if own <= {"power", "root"}:
            return "root"
        if own <= {"power", "reciprocal"}:
            return "reciprocal"
        return "mixed"
    if stem == "exponential_log":
        if own == {"exp"}:
            return "base_a" if any(p.base.is_number and p.base != sp.E for p in f.atoms(sp.Pow)) else "exp"
        if own == {"log"}:
            return "log_b" if any(a.is_number and a.has(sp.log) for t in sp.preorder_traversal(f)
                                  if isinstance(t, sp.Mul) for a in t.args) else "ln"
        return "mixed"
    names = {"trig": {"sincos": "sincos", "tansec": "tansec", "cotcsc": "cotcsc"},
             "inverse_trig": {"asin": "asin_acos", "atan": "atan_acot"},
             "dhyperbolic": {"sinhcosh": "sinh_cosh", "tanhcoth": "tanh_coth", "sechcsch": "sech_csch"}}[stem]
    return names[next(iter(own))] if len(own) == 1 else "mixed"


def _arg_label(f) -> str:
    for n in sp.preorder_traversal(f):
        if isinstance(n, sp.Function) and n.args and n.args[0].has(x) and n.args[0] != x:
            return "kx"
        if isinstance(n, sp.Pow) and n.base.is_number and n.exp != x and n.exp.has(x):
            return "kx"
    return "x"


def _verify_rule(stem, axes, f, at, **_):
    fe = _expr(f, "f")
    classes = _CLASSES[stem]
    terms = sp.Add.make_args(fe)
    if len(terms) > MAX_TERMS:
        raise Reject("redraw", f"at most {MAX_TERMS} terms")
    for t in terms:
        if why := _term_reason(t, classes):
            raise Reject("redraw", f"f needs {why}, which is outside this topic")
    own = pool.families_in(fe) & _OWN[stem]
    if not own:
        raise Reject("redraw", f"f has no {stem.replace('_', ' ')} term")
    if stem == "power_rule" and pool.families_in(fe) - _OWN[stem]:
        raise Reject("redraw", "only powers of x are allowed here")
    point = None if at.strip() in ("", "x") else _point(at, "at")
    fam, arg = _fam_label(stem, fe), _arg_label(fe)
    _check(axes, fam=fam, arg=arg, at="point" if point is not None else "expr", terms=len(terms))
    d = _tidy2(sp.diff(fe, x))
    if not fd_agrees(fe, d):
        raise Reject("redraw", "the derivative failed the finite-difference check")
    if point is None:
        if why := coefficient_reason(d):
            raise Reject("redraw", f"derivative has an unwieldy coefficient ({why})", cap=why)
        ans = expression_answer(d)
        st = f"Find $f'(x)$ for $f(x) = {L(fe)}$."
    else:
        fa = fe.subs(x, point)
        if fa.has(sp.nan, sp.zoo, sp.oo, -sp.oo) or fa.is_real is not True:
            raise Reject("redraw", "f is not defined and real at the point")
        val = d.subs(x, point)
        hyper = val.has(sp.sinh, sp.cosh, sp.tanh, sp.coth, sp.sech, sp.csch)
        if hyper:                                  # no calculator: cosh(1) is written (e + 1/e)/2
            val = sp.expand(val.rewrite(sp.exp))
        if val.has(sp.nan, sp.zoo, sp.oo, -sp.oo):
            raise Reject("redraw", "the derivative is not defined at the point")
        ans = numeric_answer(val if hyper else canon(val), exp_form=hyper)
        st = f"Find $f'({L(point)})$ for $f(x) = {L(fe)}$. Give an exact answer."
    steps = []
    for t in terms:
        if t.has(x):
            steps.append(step(f"Differentiate the term: {pool.rule_text(t) or 'constants differentiate to 0'}",
                              f"\\frac{{d}}{{dx}}\\left[{L(t)}\\right] = {L(_tidy2(sp.diff(t, x)))}", str(sp.diff(t, x))))
    steps.append(step("Add the derivatives of the terms." if len(terms) > 1 else "That is the derivative.",
                      f"f'(x) = {L(d)}", str(d)))
    if point is not None:
        steps.append(step("Substitute the point.", f"f'({L(point)}) = {ans['latex']}", ans["sympy"]))
    return finish(stem, fe, "x" if point is None else str(point), st, ans, steps, fam, axes, exact=True,
                  raw_extra={"fam": fam, "arg": arg, "terms": len(terms)})


# -- difference quotient, rate of change, limit definition ---------------------------------------------------------

def _dq_scope(f) -> str:
    """The kind of function (poly, recip, root, rational), or a rejection: the quotient must be simplifiable by hand."""
    if f.has(sp.Piecewise, sp.Abs) or pool.families_in(f) - {"power", "root", "reciprocal"}:
        raise Reject("redraw", "f must be a polynomial, a reciprocal, a square root or a simple fraction")
    if f.is_polynomial(x):
        if sp.degree(f, x) > 3:
            raise Reject("redraw", "polynomials of degree at most 3")
        return "poly"
    if f.is_rational_function(x):
        n, dd = sp.fraction(sp.together(f))
        recip = not n.has(x)
        if sp.degree(dd, x) > (3 if recip else 2) or sp.degree(n, x) > 2:
            raise Reject("redraw", "fractions with numerator and denominator of degree at most 2 (c/x^n up to n = 3)")
        return "recip" if recip else "rational"
    half = (sp.Rational(1, 2), -sp.Rational(1, 2))
    if any(p.exp in half and _linear(p.base) for p in f.atoms(sp.Pow)) and not any(
            p.exp.is_Rational and p.exp not in half and not p.exp.is_Integer for p in f.atoms(sp.Pow)):
        return "root"
    raise Reject("redraw", "f must be a polynomial, a reciprocal, a square root or a simple fraction")


def _dq(f, point):
    """(Q, simplified) for the quotient over h: f(x+h) or f(a+h), simplified so h no longer divides by zero.
    A square-root term is rationalized with its conjugate, so the answer is 1/(sqrt(..) + sqrt(..))."""
    base = x if point is None else point
    Q = (f.subs(x, base + h) - f.subs(x, base)) / h
    if not any(p.exp in (sp.Rational(1, 2), -sp.Rational(1, 2)) for p in f.atoms(sp.Pow)):
        s = sp.factor(sp.cancel(sp.together(Q)))
    else:
        s = 0
        for t in sp.Add.make_args(f):
            c, rest = t.as_independent(x, as_Add=False)
            if rest.is_Pow and rest.exp == sp.Rational(1, 2):
                u = rest.base
                s += c * sp.diff(u, x) / (sp.sqrt(u.subs(x, base + h)) + sp.sqrt(u.subs(x, base)))
            elif rest.is_Pow and rest.exp == -sp.Rational(1, 2):
                u = rest.base
                u0, uh = sp.sqrt(u.subs(x, base)), sp.sqrt(u.subs(x, base + h))
                s += -c * sp.diff(u, x) / (u0 * uh * (u0 + uh))
            else:
                s += sp.expand(sp.cancel((t.subs(x, base + h) - t.subs(x, base)) / h))
    z = s.subs(h, 0)
    if z.has(sp.nan, sp.zoo, sp.oo, -sp.oo):
        raise Reject("redraw", "the quotient does not simplify to a form defined at h = 0")
    return Q, s


def _dq_checked(f, point):
    Q, s = _dq(f, point)
    want = sp.diff(f, x) if point is None else sp.diff(f, x).subs(x, point)
    if sp.simplify(s.subs(h, 0) - want) != 0:
        raise Reject("redraw", "the simplified quotient does not tend to the derivative")
    return Q, s


def _verify_difference_quotient(stem, axes, f, at, **_):
    fe = _expr(f, "f")
    kind = _dq_scope(fe)
    mode = "h" if at.strip() == "h" else "a"
    pt = None if mode == "h" else _point(at, "at")
    _check(axes, kind=kind, form=mode)
    Q, s = _dq_checked(fe, pt)
    if mode == "h":
        ans = expression_answer(s)
        st = (f"For $f(x) = {L(fe)}$, simplify the difference quotient $\\displaystyle \\frac{{f(x + h) - f(x)}}{{h}}$ "
              "until $h$ is no longer a factor of the denominator.")
        steps = [step("Write f(x + h) and f(x).", f"f(x+h) = {L(fe.subs(x, x + h))}", str(fe.subs(x, x + h))),
                 step("Form the quotient and simplify (expand, combine, cancel or rationalize).", f"{L(s)}", str(s))]
    else:
        e = sp.factor(sp.simplify(s.subs(h, x - pt))) if not s.has(sp.sqrt) else s.subs(h, x - pt)
        ans = expression_answer(e)
        st = (f"For $f(x) = {L(fe)}$, simplify $\\displaystyle \\frac{{f(x) - f({L(pt)})}}{{x {_sub(pt)}}}$ "
              f"until $x {_sub(pt)}$ is no longer a factor of the denominator.")
        steps = [step("Write f(x) - f(a) over x - a.", f"\\frac{{{L(fe)} - {L(fe.subs(x, pt))}}}{{x {_sub(pt)}}}", None),
                 step("Simplify (factor, combine, cancel or rationalize).", L(e), str(e))]
    return finish(stem, fe, f"{at}", st, ans, steps, kind, axes, raw_extra={"kind": kind, "form": mode})


def _verify_rate_of_change(stem, axes, f, a, b, ask, **_):
    fe = _expr(f, "f")
    kind = _dq_scope(fe)
    pa = _point(a, "a")
    if ask not in ("average", "instantaneous"):
        raise Reject("slip", "ask must be average or instantaneous")
    _check(axes, kind=kind, ask=ask)
    if ask == "average":
        pb = _point(b, "b")
        if not pa < pb:
            raise Reject("slip", "a must be less than b")
        fa, fb = fe.subs(x, pa), fe.subs(x, pb)
        if any(v.has(sp.nan, sp.zoo, sp.oo, -sp.oo) for v in (fa, fb)):
            raise Reject("redraw", "f is not defined at an endpoint")
        val = (fb - fa) / (pb - pa)
        ans = numeric_answer(val)
        steps = [step("Evaluate f at both ends.", f"f({L(pa)}) = {L(canon(fa))},\\ f({L(pb)}) = {L(canon(fb))}"),
                 step("Divide the change in f by the change in x.",
                      f"\\frac{{f({L(pb)}) - f({L(pa)})}}{{{L(pb)} - {L(pa)}}} = {ans['latex']}", ans["sympy"])]
        st = f"Find the average rate of change of $f(x) = {L(fe)}$ on the interval $[{L(pa)}, {L(pb)}]$."
        key = f"{pa}|{pb}|avg"
    else:
        Q, s = _dq_checked(fe, pa)
        val = s.subs(h, 0)
        if not fd_agrees(fe, sp.diff(fe, x)):
            raise Reject("redraw", "the derivative failed the finite-difference check")
        ans = numeric_answer(val)
        steps = [step("The average rate of change over [a, a + h], simplified.", L(s), str(s)),
                 step("Let h tend to 0.", f"\\lim_{{h \\to 0}} {_under(s)} = {ans['latex']}", ans["sympy"])]
        st = f"Find the instantaneous rate of change of $f(x) = {L(fe)}$ at $x = {L(pa)}$."
        key = f"{pa}|inst"
    return finish(stem, fe, key, st, ans, steps, kind, axes, raw_extra={"kind": kind, "ask": ask})


def _verify_limit_definition(stem, axes, f, at, **_):
    fe = _expr(f, "f")
    kind = _dq_scope(fe)
    pt = None if at.strip() in ("", "x") else _point(at, "at")
    _check(axes, kind=kind, ask="expression" if pt is None else "point")
    Q, s = _dq_checked(fe, pt)
    lim = s.subs(h, 0)
    if pt is None:
        ans = expression_answer(_tidy2(sp.simplify(lim)))
        st = f"Use the limit definition of the derivative to find $f'(x)$ for $f(x) = {L(fe)}$."
        set_up = f"\\lim_{{h \\to 0}} \\frac{{f(x + h) - f(x)}}{{h}}"
    else:
        ans = numeric_answer(lim)
        st = (f"Use the limit definition of the derivative to find $f'({L(pt)})$ for $f(x) = {L(fe)}$. "
              "Give an exact answer.")
        set_up = f"\\lim_{{h \\to 0}} \\frac{{f({L(pt)} + h) - f({L(pt)})}}{{h}}"
    steps = [step("Set up the limit of the difference quotient.", set_up),
             step("Simplify the quotient so that h cancels.", L(s), str(s)),
             step("Let h tend to 0.", f"f' = {ans['latex']}", ans["sympy"])]
    return finish(stem, fe, f"{at}", st, ans, steps, kind, axes, raw_extra={"kind": kind})


# -- differentiability --------------------------------------------------------------------------------------------

_WORDS = {"differentiable": "differentiable", "corner": "corner", "cusp": "cusp", "vertical": "vertical tangent",
          "discontinuous": "discontinuous"}


def _classify(fe, pt):
    fa = fe.subs(x, pt)
    if fa.has(sp.nan, sp.zoo, sp.oo, -sp.oo) or fa.is_real is not True:
        raise Reject("redraw", "f must be defined at the point")
    lo, hi = side_limit(fe, pt, -1), side_limit(fe, pt, 1)
    if lo is None or hi is None:
        raise Reject("redraw", "could not evaluate a one-sided limit of f")
    if sp.simplify(lo - fa) != 0 or sp.simplify(hi - fa) != 0:
        return "discontinuous"
    Q = (fe - fa) / (x - pt)
    dl, dr = side_limit(Q, pt, -1), side_limit(Q, pt, 1)
    if dl is None or dr is None:
        raise Reject("redraw", "could not evaluate a one-sided derivative")
    inf = (sp.oo, -sp.oo)
    if dl in inf or dr in inf:
        if dl in inf and dr in inf:
            return "vertical" if dl == dr else "cusp"
        raise Reject("redraw", "one one-sided derivative is infinite and the other finite")
    return "differentiable" if sp.simplify(dl - dr) == 0 else "corner"


def _verify_differentiability(stem, axes, f, params, a, ask, **_):
    if ask not in ("classify", "params"):
        raise Reject("slip", "ask must be classify or params")
    names = [s.strip() for s in str(params).split(",") if s.strip()]
    syms = {n: sp.Symbol(n, real=True) for n in names}
    fe = _expr(f, "f", syms, piecewise=True)
    if ask == "classify":
        if names:
            raise Reject("slip", "classify questions have no parameters")
        pt = _point(a, "a")
        kind = ("piece" if fe.has(sp.Piecewise) else "abs" if fe.has(sp.Abs) else "power")
        _check(axes, ask=ask, kind=kind)
        word = _classify(fe, pt)
        # independent: one-sided slopes from difference quotients very near the point
        mp.mp.dps = 80
        fl = _lam(fe)
        p0, e = mp.mpf(str(sp.N(pt, 60))), mp.mpf(10) ** -30
        sl = [(fl(p0 + s * e) - fl(p0)) / (s * e) for s in (-1, 1)]
        agree = {"differentiable": abs(sl[0] - sl[1]) < 1e-6 and abs(sl[0]) < 1e6,
                 "corner": abs(sl[0] - sl[1]) > 1e-6 and max(map(abs, sl)) < 1e6,
                 "vertical": sl[0] > 1e6 and sl[1] > 1e6 or sl[0] < -1e6 and sl[1] < -1e6,
                 "cusp": sl[0] * sl[1] < -1e12, "discontinuous": max(map(abs, sl)) > 1e12}[word]
        if not agree:
            raise Reject("redraw", "the classification failed the numeric slope check")
        ans = {"type": "enum", "latex": f"\\text{{{_WORDS[word]}}}", "sympy": _WORDS[word], "numeric": None}
        reason = {"differentiable": "The one-sided derivatives exist and are equal.",
                  "corner": "f is continuous but the one-sided derivatives are different finite numbers.",
                  "vertical": "The difference quotients tend to the same infinity from both sides.",
                  "cusp": "The difference quotients tend to infinity of opposite signs.",
                  "discontinuous": "f is not continuous at the point, so it is not differentiable."}[word]
        steps = [step("Check continuity, then take the one-sided limits of the difference quotient.",
                      f"\\frac{{f(x) - f({L(pt)})}}{{x {_sub(pt)}}}"), step(reason, ans["latex"], ans["sympy"])]
        st = (f"Is $f(x) = {_show(fe)}$ differentiable at $x = {L(pt)}$? Answer differentiable, corner, cusp, "
              "vertical tangent or discontinuous.")
        return finish(stem, fe, f"{pt}|classify", st, ans, steps, kind, axes, exact=True,
                      raw_extra={"ask": ask, "kind": kind})
    # parameters
    if not 1 <= len(names) <= 2 or len(set(names)) != len(names) or any(n == "x" or len(n) != 1 for n in names):
        raise Reject("slip", "params must be one or two distinct single letters other than x, such as k or a,b")
    if not isinstance(fe, sp.Piecewise) or not all(fe.has(syms[n]) for n in names):
        raise Reject("slip", "f must be one Piecewise using every parameter")
    pts = _bps(fe)
    if not pts or len(pts) > 2:
        raise Reject("redraw", "one or two breakpoints")
    eqs = []
    for b in pts:
        left, right = _active_expr(fe, b - sp.Rational(1, 10 ** 6)), _active_expr(fe, b + sp.Rational(1, 10 ** 6))
        if left is None or right is None:
            raise Reject("slip", "every point must lie in some piece")
        eqs += [sp.Eq(left.subs(x, b), right.subs(x, b)), sp.Eq(sp.diff(left, x).subs(x, b),
                                                              sp.diff(right, x).subs(x, b))]
    P = [syms[n] for n in names]
    sol = sp.solve([e for e in eqs if e is not sp.true], P, dict=True)
    if len(sol) != 1 or set(sol[0]) != set(P):
        raise Reject("redraw", "the parameters are not determined uniquely by value and slope matching")
    sol = {k: canon(v) for k, v in sol[0].items()}
    for v in sol.values():
        if v == 0:
            raise Reject("redraw", "a parameter comes out as 0, so it vanishes from the function")
        if v.is_real is not True or (r := value_reason(v, True)):
            raise Reject("redraw", f"parameter value is not a short exact form ({r})")
    g = fe.subs(sol)
    mp.mp.dps = 60
    gl = _lam(g)
    for b in pts:
        bb, e = mp.mpf(str(sp.N(b, 40))), mp.mpf(10) ** -25
        v_l, v_r = gl(bb - e), gl(bb + e)
        s_l, s_r = (gl(bb - e) - gl(bb - 2 * e)) / e, (gl(bb + 2 * e) - gl(bb + e)) / e
        if abs(v_l - v_r) > 1e-20 or abs(s_l - s_r) > 1e-15:
            raise Reject("redraw", "the solved function is not differentiable at a breakpoint (numeric check)")
    pieces = [e for e, _ in fe.args]
    kind = ("one" if len(P) == 1 else "trig" if any(p.has(sp.sin, sp.cos, sp.exp, sp.log) for p in pieces) else "two")
    _check(axes, ask=ask, kind=kind)
    if len(P) == 1:
        v = sol[P[0]]
        ans = {"type": "numeric", "latex": f"{names[0]} = {L(v)}", "sympy": str(v), "numeric": float(sp.N(v, 15))}
    else:
        ans = {"type": "multi_part", "latex": ",\\ ".join(f"{n} = {L(sol[syms[n]])}" for n in names),
               "sympy": "{" + ", ".join(f"{n}: {sol[syms[n]]}" for n in names) + "}", "numeric": None}
    steps = [step("Differentiable means continuous and equal one-sided slopes at each breakpoint.", ""),
             step("Equate the values and the derivatives of the two pieces at each breakpoint.",
                  ",\\ ".join(L(e) for e in eqs)),
             step("Solve for the parameter" + ("s." if len(P) > 1 else "."), ans["latex"], ans["sympy"])]
    plist = ", ".join(f"${n}$" for n in names)
    st = (f"Find the value{'s' if len(P) > 1 else ''} of {plist} that make{'' if len(P) > 1 else 's'} "
          f"$f(x) = {_show(fe)}$ differentiable for all real $x$.")
    return finish(stem, fe.subs({p: 0 for p in P}) + sum(P), ",".join(names), st, ans, steps, kind, axes,
                  raw_extra={"ask": ask, "kind": kind})


_VERIFY = {"difference_quotient": _verify_difference_quotient, "rate_of_change": _verify_rate_of_change,
           "limit_definition": _verify_limit_definition, "differentiability": _verify_differentiability,
           "power_rule": _verify_rule, "trig": _verify_rule, "exponential_log": _verify_rule,
           "inverse_trig": _verify_rule, "dhyperbolic": _verify_rule}
