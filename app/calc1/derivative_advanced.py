"""Verifiers for the last derivative topics (C2 milestone c): implicit, logarithmic, inverse_functions, higher_order.
Same contract as app/calc1/derivative_rules.py (verify(stem, ...) in the sandbox).

implicit: the server differentiates both sides and checks the slope against a numerical solve of the curve (mpmath
findroot), not against SymPy. inverse_functions: the model gives f and the point a; the server prints b = f(a), so
the student must find a. Second derivatives (implicit d2y/dx2 and (f^-1)'') are the provisional level-5 families.
"""
import mpmath as mp
import sympy as sp

from app.shared import function_pool as pool
from app.shared.calculus_core import coefficient_reason, expression_answer, fd_agrees, finish, numeric_answer, step
from app.shared.clean_answer import canon, value_reason
from app.calc1.derivative_rules import _TRANSCENDENTAL, _basic, _factors, _nice
from app.calc1.derivatives import _check, _linear, _tidy2
from app.shared.integral_core import L, Reject, x
from app.calc1.limits import _expr, _point

STEMS = ("implicit", "logarithmic", "inverse_functions", "higher_order")
y = sp.Symbol("y", real=True)


def verify(stem: str, bounds=None, axes: dict | None = None, calculator: str = "none", **fields) -> dict:
    try:
        if stem not in STEMS:
            raise Reject("slip", f"unknown derivative topic {stem}")
        if calculator != "none":
            raise Reject("redraw", "derivative topics have only the exact tier")
        return _VERIFY[stem](stem, axes or {}, **fields)
    except Reject as r:
        return {"ok": False, "cause": r.cause, "reason": r.reason, "cap": r.cap}


def _pt_value(v, what: str):
    if v.has(sp.nan, sp.zoo, sp.oo, -sp.oo) or v.is_real is not True:
        raise Reject("redraw", f"{what} is not a defined real number")
    return canon(v)


# -- implicit differentiation --------------------------------------------------------------------------------------

def _walk(Hf, x0, y0, xs):
    """y(x) on the curve at each x in xs (sorted away from x0 on both sides) by continuation from (x0, y0)."""
    out = {}
    for sign in (1, -1):
        guess, prev = y0, x0
        for t in sorted((v for v in xs if (v - x0) * sign > 0), key=lambda v: abs(v - x0)):
            try:
                guess = mp.findroot(lambda yy: Hf(t, yy), guess + 0 * (t - prev), tol=1e-30, maxsteps=60)
            except (ValueError, ZeroDivisionError, ArithmeticError):
                raise Reject("redraw", "the curve could not be followed numerically near the point") from None
            out[t], prev = guess, t
    return out


def _verify_implicit(stem, axes, lhs, rhs, point, ask, **_):
    if ask not in ("expression", "point", "tangent", "second"):
        raise Reject("slip", "ask must be expression, point, tangent or second")
    sym = {"y": y}
    le, re_ = _expr(lhs, "lhs", sym), _expr(rhs, "rhs", sym)
    H = le - re_
    if not (H.has(x) and H.has(y)):
        raise Reject("redraw", "the equation must involve both x and y")
    if len(sp.Add.make_args(le)) + len(sp.Add.make_args(re_)) > 5 or pool.complexity(H.subs(y, x)) > 12:
        raise Reject("redraw", "the equation is too complicated for this topic")
    try:
        xs_, ys_ = (s.strip() for s in str(point).strip("() ").split(","))
    except ValueError:
        raise Reject("slip", "point must be 'x0, y0'") from None
    x0, y0 = _point(xs_, "x0"), _point(ys_, "y0")
    if sp.simplify(H.subs({x: x0, y: y0})) != 0:
        raise Reject("redraw", "the point is not on the curve")
    Hx, Hy = sp.diff(H, x), sp.diff(H, y)
    if sp.simplify(Hy.subs({x: x0, y: y0})) == 0:
        raise Reject("redraw", "the tangent is vertical at the point (dy/dx is not defined)")
    dydx = _nice(_tidy2(-Hx / Hy))
    if not (dydx.has(y) or ask == "second"):
        raise Reject("redraw", "dy/dx must depend on y: use an equation that cannot be solved easily for y")
    trans = bool(H.atoms(*_TRANSCENDENTAL) | {a for a in H.atoms(sp.Function) if isinstance(a, _TRANSCENDENTAL)})
    mixed = any(t.has(x) and t.has(y) for t in sp.Add.make_args(sp.expand(H)))
    kind = ("mixed" if trans and mixed else "trans" if trans else "product" if mixed else "poly")
    _check(axes, mix="second" if ask == "second" else kind, ask=ask)
    mp.mp.dps = 40
    Hl = sp.lambdify((x, y), H, "mpmath")
    xm, ym = mp.mpf(str(sp.N(x0, 30))), mp.mpf(str(sp.N(y0, 30)))
    slope_l = sp.lambdify((x, y), dydx, "mpmath")
    h = mp.mpf(10) ** -6
    near = _walk(Hl, xm, ym, [xm - h, xm + h, xm - 2 * h, xm + 2 * h] + [xm + mp.mpf(k) / 20 for k in (-3, -1, 1, 3)])
    num = (near[xm + h] - near[xm - h]) / (2 * h)
    if abs(num - slope_l(xm, ym)) > 1e-8 * max(1, abs(num)):
        raise Reject("redraw", "dy/dx failed the numerical check on the curve")
    for t in (xm - mp.mpf(3) / 20, xm + mp.mpf(1) / 20):
        hh = mp.mpf(10) ** -6
        pts = _walk(Hl, t, near[t], [t - hh, t + hh])
        ref = (pts[t + hh] - pts[t - hh]) / (2 * hh)
        if abs(ref - slope_l(t, near[t])) > 1e-7 * max(1, abs(ref)):
            raise Reject("redraw", "dy/dx failed the numerical check at a second point")
    stmt_eq = f"{L(le)} = {L(re_)}"
    d_step = step("Differentiate both sides with respect to x, treating y as a function of x.",
                  f"{L(Hx)} + \\left({L(Hy)}\\right)\\frac{{dy}}{{dx}} = 0")
    solve = step("Solve for dy/dx.", f"\\frac{{dy}}{{dx}} = {L(dydx)}", str(dydx))
    pt_tex = f"\\left({L(x0)}, {L(y0)}\\right)"
    sub = {x: x0, y: y0}
    if ask == "expression":
        for t in sp.Add.make_args(dydx):
            c = t.as_independent(x, y, as_Add=False)[0]
            if c != 1 and (why := value_reason(c, True)):
                raise Reject("redraw", f"dy/dx has an unwieldy coefficient ({why})", cap=why)
        st = f"Find $\\dfrac{{dy}}{{dx}}$ if ${stmt_eq}$."
        return finish(stem, H, "expr", st, expression_answer(dydx), [d_step, solve], kind, axes, exact=True,
                      raw_extra={"mix": kind, "ask": ask})
    val = _pt_value(dydx.subs(sub), "dy/dx")
    if ask == "point":
        ans = numeric_answer(val)
        st = f"Find $\\dfrac{{dy}}{{dx}}$ at the point ${pt_tex}$ on the curve ${stmt_eq}$."
        steps = [d_step, solve, step("Substitute the point.", f"\\left.\\frac{{dy}}{{dx}}\\right|_{{{pt_tex}}} = {ans['latex']}",
                                     ans["sympy"])]
        return finish(stem, H, f"point|{x0},{y0}", st, ans, steps, kind, axes, exact=True,
                      raw_extra={"mix": kind, "ask": ask})
    if ask == "tangent":
        if r := value_reason(val, True):
            raise Reject("redraw", f"the slope is not a short exact form ({r})", cap=r)
        line = sp.expand(val * (x - x0) + y0)
        if line == 0:
            raise Reject("redraw", "the tangent line is y = 0; choose another point")
        ans = {"type": "expression", "latex": f"y = {L(line)}", "sympy": str(line), "numeric": None}
        st = f"Find an equation of the tangent line to the curve ${stmt_eq}$ at the point ${pt_tex}$."
        steps = [d_step, solve, step("Slope at the point.", f"m = {L(val)}", str(val)),
                 step("Point-slope form, simplified.", ans["latex"], ans["sympy"])]
        return finish(stem, H, f"tangent|{x0},{y0}", st, ans, steps, kind, axes, exact=True,
                      raw_extra={"mix": kind, "ask": ask})
    second = sp.diff(dydx, x) + sp.diff(dydx, y) * dydx
    v2 = _pt_value(second.subs(sub), "d2y/dx2")
    ans = numeric_answer(v2)
    h2 = mp.mpf(10) ** -5
    pts = _walk(Hl, xm, ym, [xm - h2, xm + h2])
    ref = (pts[xm + h2] - 2 * ym + pts[xm - h2]) / h2 ** 2
    if abs(ref - mp.mpf(str(ans["numeric"]))) > 1e-5 * max(1, abs(ref)):
        raise Reject("redraw", "the second derivative failed the numerical check")
    st = f"Find $\\dfrac{{d^2y}}{{dx^2}}$ at the point ${pt_tex}$ on the curve ${stmt_eq}$."
    steps = [d_step, solve,
             step("Differentiate dy/dx again, replacing dy/dx by the expression above.",
                  f"\\frac{{d^2y}}{{dx^2}} = {L(sp.simplify(second))}"),
             step("Substitute the point.", f"\\left.\\frac{{d^2y}}{{dx^2}}\\right|_{{{pt_tex}}} = {ans['latex']}", ans["sympy"])]
    return finish(stem, H, f"second|{x0},{y0}", st, ans, steps, "second", axes, exact=True,
                  raw_extra={"mix": "second", "ask": ask})


# -- logarithmic differentiation -----------------------------------------------------------------------------------

def _log_factor_ok(b) -> bool:
    _, r = b.as_independent(x, as_Add=False)
    if r.is_polynomial(x):
        return len(sp.Add.make_args(r)) <= 3 and sp.degree(r, x) <= 2
    return _basic(r)


def _verify_logarithmic(stem, axes, f, at, **_):
    fe = _expr(f, "f")
    c, rest = fe.as_independent(x, as_Add=False)
    powers = [p for p in sp.preorder_traversal(rest) if p.is_Pow and p.exp.has(x) and p.base.has(x)]
    if powers:
        if len(powers) != 1 or rest != powers[0]:
            raise Reject("redraw", "f must be one variable power g(x)^h(x), times a constant")
        b, e = rest.base, rest.exp
        if not (_log_factor_ok(b) and _log_factor_ok(e)):
            raise Reject("redraw", "the base and the exponent must be simple (a polynomial of degree 2 or less or one elementary function)")
        kind = "variable"
        logs = [(e, b)]
    else:
        fs = list(sp.Mul.make_args(rest))
        logs = []
        for t in fs:
            b, e = (t.base, t.exp) if t.is_Pow else (t, sp.Integer(1))
            if not (e.is_Rational and b.has(x) and _log_factor_ok(b)):
                raise Reject("redraw", "each factor must be a power (a number exponent) of a simple function of x")
            logs.append((e, b))
        if len(logs) < 3:
            raise Reject("redraw", "use at least three factors (numerator and denominator together) so that logarithmic differentiation is worth it")
        den = any(e < 0 for e, _ in logs)
        trans = any(not b.is_polynomial(x) for _, b in logs)
        kind = "mixed" if trans else "quotient" if den else "product"
    _check(axes, mix=kind)
    d = _tidy2(sp.diff(fe, x))
    if not fd_agrees(fe, d):
        raise Reject("redraw", "the derivative failed the finite-difference check")
    if sp.count_ops(d) > 90:
        raise Reject("redraw", "the derivative is too long to be a fair answer")
    exp_log = " + ".join(f"{L(e)}\\ln\\left({L(b)}\\right)" if e != 1 else f"\\ln\\left({L(b)}\\right)" for e, b in logs)
    dsum = sum(sp.diff(e, x) * sp.log(b) + e * sp.diff(b, x) / b for e, b in logs)
    steps = [step("Take the natural log of both sides and expand.", f"\\ln y = {L(sp.log(abs(c)) if c != 1 else 0)} + {exp_log}"
                  if c != 1 else f"\\ln y = {exp_log}"),
             step("Differentiate both sides with respect to x.", f"\\frac{{y'}}{{y}} = {L(dsum)}"),
             step("Multiply by y = f(x).", f"f'(x) = {L(fe)}\\left({L(dsum)}\\right)"),
             step("Simplify.", f"f'(x) = {L(d)}", str(d))]
    from app.calc1.derivative_rules import _finish_expr
    return _finish_expr(stem, fe, d, at, f"Find $f'(x)$ for $f(x) = {L(fe)}$. Use logarithmic differentiation.",
                        f"Find $f'(@)$ for $f(x) = {L(fe)}$. Use logarithmic differentiation. Give an exact answer.",
                        steps, kind, axes, {})


# -- derivatives of inverse functions ------------------------------------------------------------------------------

def _verify_inverse(stem, axes, f, a, ask="first", dom="all", **_):
    if ask not in ("first", "second") or dom not in ("all", "positive"):
        raise Reject("slip", "ask must be first or second and dom all or positive")
    fe = _expr(f, "f")
    a0 = _point(a, "a")
    if dom == "positive" and a0 <= 0:
        raise Reject("redraw", "a must be positive on the domain x > 0")
    d, dd = sp.diff(fe, x), sp.diff(fe, x, 2)
    if pool.complexity(fe) > 8:
        raise Reject("redraw", "f is too complicated for this topic")
    grid = [sp.Rational(n, 4) for n in range(-40, 41)] if dom == "all" else [sp.Rational(n, 8) for n in range(1, 60)]
    signs = set()
    for t in grid:
        v = d.subs(x, t)
        if v.is_real is not True or v == 0 or v.has(sp.zoo, sp.nan):
            raise Reject("redraw", "f must be strictly monotone with a nonzero derivative on its domain")
        signs.add(v > 0)
    if len(signs) != 1:
        raise Reject("redraw", "f is not one-to-one: f' changes sign")
    if fe.is_polynomial(x) and sp.Poly(d, x).count_roots() != 0:
        raise Reject("redraw", "f' has a real zero, so f is not one-to-one on R")
    if not fd_agrees(fe, d, need=2):
        raise Reject("redraw", "the derivative failed the finite-difference check")
    b0 = _pt_value(fe.subs(x, a0), "f(a)")
    if r := value_reason(b0, True):
        raise Reject("redraw", f"b = f(a) is not a short exact number ({r})", cap=r)
    if b0.is_Rational is not True:
        raise Reject("redraw", "b = f(a) must be a rational number")
    fp, fpp = canon(d.subs(x, a0)), canon(dd.subs(x, a0))
    mp.mp.dps = 40
    fl = sp.lambdify(x, fe, "mpmath")
    bm, am = mp.mpf(str(sp.N(b0, 30))), mp.mpf(str(sp.N(a0, 30)))
    h = mp.mpf(10) ** -6
    try:
        ap, an = (mp.findroot(lambda t: fl(t) - (bm + s * h), am, tol=1e-30, maxsteps=80) for s in (1, -1))
    except (ValueError, ZeroDivisionError, ArithmeticError):
        raise Reject("redraw", "the inverse could not be evaluated numerically") from None
    if ask == "first":
        v = canon(1 / fp)
        ref = (ap - an) / (2 * h)
        label, latex_q = "first", f"\\left(f^{{-1}}\\right)'({L(b0)})"
        steps = [step("Find a with f(a) = b.", f"f({L(a0)}) = {L(b0)}"),
                 step("Differentiate f.", f"f'(x) = {L(_tidy2(d))},\\ f'({L(a0)}) = {L(fp)}"),
                 step("Use the inverse function rule.", f"{latex_q} = \\frac{{1}}{{f'({L(a0)})}} = {L(v)}", str(v))]
        st = f"Let $f(x) = {L(fe)}$" + (" for $x > 0$" if dom == "positive" else "") + f". Find $\\left(f^{{-1}}\\right)'({L(b0)})$."
    else:
        v = canon(-fpp / fp ** 3)
        ref = (ap - 2 * am + an) / h ** 2
        label = "second"
        steps = [step("Find a with f(a) = b.", f"f({L(a0)}) = {L(b0)}"),
                 step("Values of f' and f'' at a.", f"f'({L(a0)}) = {L(fp)},\\ f''({L(a0)}) = {L(fpp)}"),
                 step("Differentiate the inverse function rule again.",
                      f"\\left(f^{{-1}}\\right)''(b) = -\\frac{{f''(a)}}{{f'(a)^3}} = {L(v)}", str(v))]
        st = (f"Let $f(x) = {L(fe)}$" + (" for $x > 0$" if dom == "positive" else "")
              + f". Find $\\left(f^{{-1}}\\right)''({L(b0)})$.")
    if v == 0 or abs(ref - mp.mpf(str(sp.N(v, 30)))) > 1e-5 * max(1, abs(ref)):
        raise Reject("redraw", "the inverse derivative is 0 or failed the numerical check")
    ans = numeric_answer(v)
    kind = "poly" if fe.is_polynomial(x) else "trans"
    _check(axes, mix=kind, ask=ask)
    return finish(stem, fe, f"{label}|{b0}", st, ans, steps, kind if ask == "first" else "second", axes, exact=True,
                  raw_extra={"mix": kind, "ask": ask})


# -- higher-order derivatives --------------------------------------------------------------------------------------

def _term_ok(t) -> bool:
    fs = _factors(t)
    return not t.has(x) or (1 <= len(fs) <= 2 and all(_hbasic(q) for q in fs))


def _hbasic(q) -> bool:
    _, r = q.as_independent(x, as_Add=False)
    return _basic(q) or _lin_pow(q) or (r.is_polynomial(x) and len(sp.Add.make_args(r)) <= 2)


def _lin_pow(q) -> bool:
    _, r = q.as_independent(x, as_Add=False)
    return r.is_Pow and r.exp.is_Integer and r.exp < 0 and _linear(r.base)


def _pattern_ok(terms) -> bool:
    if len(terms) != 1 or len(_factors(terms[0])) != 1:
        return False
    _, r = terms[0].as_independent(x, as_Add=False)
    fn = [t for t in sp.preorder_traversal(r) if isinstance(t, sp.Function)]
    return _lin_pow(r) or (bool(fn) and all(_linear(q.args[0]) for q in fn))


def _verify_higher(stem, axes, f, n, at, **_):
    try:
        order = int(str(n).strip())
    except ValueError:
        raise Reject("slip", "n must be an integer") from None
    if not 2 <= order <= 12:
        raise Reject("redraw", "n must be between 2 and 12")
    fe = _expr(f, "f")
    terms = sp.Add.make_args(fe)
    if len(terms) > 3 or not all(_term_ok(t) for t in terms):
        raise Reject("redraw", "f must be at most three terms, each a product of at most two basic factors")
    if order >= 6 and not _pattern_ok(terms):
        raise Reject("redraw", "for n >= 6, f must be a single function of x or kx whose derivatives follow a pattern")
    dn = sp.diff(fe, x, order)
    if dn == 0:
        raise Reject("redraw", f"the derivative of order {order} is identically 0")
    if sp.count_ops(dn) > 60:
        raise Reject("redraw", "the derivative is too long to be a fair answer")
    mp.mp.dps = 60
    fl = sp.lambdify(x, fe, "mpmath")
    dl = sp.lambdify(x, dn, "mpmath")
    good = 0
    for p in ("0.7", "1.3", "2.1", "0.45"):
        pt = mp.mpf(p)
        try:
            ref = mp.diff(lambda t: mp.re(fl(t)), pt, order)
            got = dl(pt)
        except (ValueError, ZeroDivisionError, ArithmeticError, TypeError):
            continue
        if isinstance(got, mp.mpc) and abs(got.imag) > 1e-25:
            continue
        if abs(ref - mp.re(got)) > mp.mpf(10) ** -8 * max(1, abs(ref)):
            raise Reject("redraw", "the derivative failed the numerical check")
        good += 1
    if good < 2:
        raise Reject("redraw", "the derivative could not be checked at enough points")
    if fe.is_polynomial(x):
        kind = "poly"
    elif order >= 6:
        kind = "pattern"
    elif any(len(_factors(t)) == 2 for t in terms):
        kind = "product"
    else:
        kind = "trans"
    _check(axes, mix=kind)
    steps = []
    cur = fe
    for k in range(1, min(order, 4) + 1):
        cur = sp.diff(cur, x)
        steps.append(step(f"Differentiate ({k}).", f"f^{{({k})}}(x) = {L(_tidy2(cur))}", str(cur)))
    if order > 4:
        steps.append(step("The derivatives repeat in a pattern; continue to the requested order.",
                          f"f^{{({order})}}(x) = {L(_tidy2(dn))}", str(dn)))
    if at.strip() in ("", "x"):
        if why := coefficient_reason(dn):
            raise Reject("redraw", f"the derivative has an unwieldy coefficient ({why})", cap=why)
        st = f"Find $f^{{({order})}}(x)$ for $f(x) = {L(fe)}$."
        return finish(stem, fe, f"n{order}|x", st, expression_answer(_tidy2(dn)), steps, kind, axes, exact=True,
                      raw_extra={"mix": kind, "n": order, "at": "expr"})
    pt = _point(at, "at")
    val = _pt_value(dn.subs(x, pt), "f^(n)(a)")
    ans = numeric_answer(val)
    steps.append(step("Substitute the point.", f"f^{{({order})}}({L(pt)}) = {ans['latex']}", ans["sympy"]))
    st = f"Find $f^{{({order})}}({L(pt)})$ for $f(x) = {L(fe)}$."
    return finish(stem, fe, f"n{order}|{pt}", st, ans, steps, kind, axes, exact=True,
                  raw_extra={"mix": kind, "n": order, "at": "point"})


_VERIFY = {"implicit": _verify_implicit, "logarithmic": _verify_logarithmic, "inverse_functions": _verify_inverse,
           "higher_order": _verify_higher}
