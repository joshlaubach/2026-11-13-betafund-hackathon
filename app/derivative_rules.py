"""Verifiers for the combining rules of the derivatives chapter (C2 milestone b): product_rule, quotient_rule,
chain_rule, tangent_normal_lines. Same contract as app/derivatives.py (verify(stem, ...) in the sandbox).

Factors and inner/outer functions come from the elementary pool (app/function_pool.py). Level comes from the number
of factors, the families that appear and the composition depth (`mix`, `layers`), not from polynomial degree.
Chain-rule table problems (`ask = "table"`) are the provisional level-5 family of D33: the student is given a table
of values of f, f', g and g' and must see which entries the chain rule needs.
"""
import mpmath as mp
import sympy as sp

from app import function_pool as pool
from app.calculus_core import coefficient_reason, expression_answer, fd_agrees, finish, numeric_answer, step
from app.clean_answer import canon, value_reason
from app.derivatives import _check, _linear, _tidy2
from app.integral_core import L, Reject, _with_timeout, x
from app.limits import _expr, _point

STEMS = ("product_rule", "quotient_rule", "chain_rule", "tangent_normal_lines")
_TRANSCENDENTAL = (sp.sin, sp.cos, sp.tan, sp.cot, sp.sec, sp.csc, sp.exp, sp.log, sp.asin, sp.acos, sp.atan, sp.acot,
                   sp.sinh, sp.cosh, sp.tanh, sp.coth, sp.sech, sp.csch)
u = sp.Symbol("u", real=True)
MAX_TABLE_DENOM = 12


def verify(stem: str, bounds=None, axes: dict | None = None, calculator: str = "none", **fields) -> dict:
    try:
        if stem not in STEMS:
            raise Reject("slip", f"unknown derivative-rule topic {stem}")
        if calculator != "none":
            raise Reject("redraw", "derivative topics have only the exact tier")
        return _VERIFY[stem](stem, axes or {}, **fields)
    except Reject as r:
        return {"ok": False, "cause": r.cause, "reason": r.reason, "cap": r.cap}


# -- factors -------------------------------------------------------------------------------------------------------

def _basic(t) -> bool:
    """A factor the earlier topics differentiate in one step: a polynomial of at most three terms, a power of x, or
    one elementary function of x or of a linear argument (times a constant)."""
    _, rest = t.as_independent(x, as_Add=False)
    if rest.is_polynomial(x):
        return len(sp.Add.make_args(rest)) <= 3 and sp.degree(rest, x) <= 3
    if rest.is_Pow and rest.base == x and rest.exp.is_Rational:
        return True
    if isinstance(rest, _TRANSCENDENTAL) and _linear(rest.args[0]):
        return True
    return rest.is_Pow and rest.base.is_number and _linear(rest.exp)


def _nice(d):
    """The derivative in a readable form: for a rational function, simplified and factored when that is shorter.
    Anything with a transcendental function is left as SymPy wrote it (simplify can be slow on those)."""
    if not d.is_rational_function(x):
        return d
    s = sp.factor(sp.cancel(sp.together(d)))
    return s if sp.count_ops(s) <= sp.count_ops(d) else d


def _factors(e) -> list:
    return [t for t in sp.Mul.make_args(e) if t.has(x)]


def _mix(parts) -> str:
    fams = set()
    for p in parts:
        fams |= pool.families_in(p) - {"power"}
    trans = {f for f in fams if f not in ("root", "reciprocal")}
    return "poly" if not fams else "poly_trans" if len(trans) <= 1 and len(fams) <= 1 else "trans2"


def _arg(f) -> str:
    return "kx" if any(isinstance(n, sp.Function) and n.args and n.args[0].has(x) and n.args[0] != x
                       for n in sp.preorder_traversal(f)) else "x"


def _point_value(fe, d, at):
    """(answer dict, statement tail, point) for a derivative asked as a function or at a number."""
    if at.strip() in ("", "x"):
        if why := coefficient_reason(d):
            raise Reject("redraw", f"derivative has an unwieldy coefficient ({why})", cap=why)
        return expression_answer(d), None
    pt = _point(at, "at")
    fa = fe.subs(x, pt)
    if fa.has(sp.nan, sp.zoo, sp.oo, -sp.oo) or fa.is_real is not True:
        raise Reject("redraw", "f is not defined and real at the point")
    val = d.subs(x, pt)
    if val.has(sp.nan, sp.zoo, sp.oo, -sp.oo):
        raise Reject("redraw", "the derivative is not defined at the point")
    return numeric_answer(canon(val)), pt


def _finish_expr(stem, fe, d, at, st_expr, st_point, steps, mix, axes, extra):
    ans, pt = _point_value(fe, d, at)
    if pt is not None:
        steps = steps + [step("Substitute the point.", f"f'({L(pt)}) = {ans['latex']}", ans["sympy"])]
    _check(axes, mix=mix, at="expr" if pt is None else "point", **extra)
    st = st_expr if pt is None else st_point.replace("@", L(pt))
    return finish(stem, fe, "x" if pt is None else str(pt), st, ans, steps, mix, axes, exact=True,
                  raw_extra={"mix": mix, "at": "expr" if pt is None else "point", **extra})


# -- product rule --------------------------------------------------------------------------------------------------

def _verify_product(stem, axes, f, at, **_):
    fe = _expr(f, "f")
    fs = _factors(fe)
    if not 2 <= len(fs) <= 3:
        raise Reject("redraw", "f must be a product of two or three non-constant factors")
    if any(isinstance(t, sp.Add) is False and t.is_Pow and t.exp.is_negative and not t.base.is_number for t in fs):
        raise Reject("redraw", "a quotient needs the quotient rule; write the product with positive powers")
    if not all(_basic(t) for t in fs):
        raise Reject("redraw", "each factor must be a polynomial, a power of x, or one elementary function of x or kx")
    if len({sp.srepr(t) for t in fs}) < len(fs):
        raise Reject("redraw", "the factors must be different")
    d = _tidy2(sp.diff(fe, x))
    if not fd_agrees(fe, d):
        raise Reject("redraw", "the derivative failed the finite-difference check")
    d = _nice(d)
    mix = "three" if len(fs) == 3 else _mix(fs)
    terms = [sp.Mul(*[sp.diff(t, x) if j == i else t for j, t in enumerate(fs)]) for i in range(len(fs))]
    c = sp.Mul(*[t for t in sp.Mul.make_args(fe) if not t.has(x)])
    steps = [step("Name the factors.", ",\\ ".join(f"u_{i + 1} = {L(t)}" for i, t in enumerate(fs))),
             step("Differentiate each factor.", ",\\ ".join(f"u_{i + 1}' = {L(_tidy2(sp.diff(t, x)))}"
                                                           for i, t in enumerate(fs))),
             step("Apply the product rule: differentiate one factor at a time and add.",
                  "f' = " + (L(c) + "\\left(" if c != 1 else "") + " + ".join(L(_tidy2(t)) for t in terms)
                  + ("\\right)" if c != 1 else ""), None),
             step("Simplify.", f"f'(x) = {L(d)}", str(d))]
    ans_tail = f"Find $f'(x)$ for $f(x) = {L(fe)}$."
    return _finish_expr(stem, fe, d, at, ans_tail, f"Find $f'(@)$ for $f(x) = {L(fe)}$. Give an exact answer.", steps, mix,
                        axes, {"arg": _arg(fe)})


# -- quotient rule -------------------------------------------------------------------------------------------------

def _part_ok(p) -> bool:
    fs = _factors(p)
    return len(fs) <= 2 and all(_basic(t) for t in fs)


def _verify_quotient(stem, axes, f, at, **_):
    fe = _expr(f, "f")
    n, dd = sp.fraction(fe)
    if not dd.has(x):
        raise Reject("redraw", "the denominator must contain x")
    if not (_part_ok(n) and _part_ok(dd)):
        raise Reject("redraw", "numerator and denominator must each be one basic factor or a product of two")
    if (not n.has(x)) and len(_factors(dd)) > 1:
        raise Reject("redraw", "a constant over a product is a product-rule problem; use the quotient of two functions")
    prod = len(_factors(n)) > 1 or len(_factors(dd)) > 1
    d = _tidy2(sp.diff(fe, x))
    if not fd_agrees(fe, d):
        raise Reject("redraw", "the derivative failed the finite-difference check")
    d = _nice(d)
    mix = "prod" if prod else _mix([n, dd])
    nu, nv = sp.diff(n, x), sp.diff(dd, x)
    steps = [step("Name the numerator and the denominator.", f"u = {L(n)},\\ v = {L(dd)}"),
             step("Differentiate both.", f"u' = {L(_tidy2(nu))},\\ v' = {L(_tidy2(nv))}"),
             step("Apply the quotient rule (u'v - uv') / v^2.",
                  f"\\frac{{\\left({L(_tidy2(nu))}\\right)\\left({L(dd)}\\right) - \\left({L(n)}\\right)"
                  f"\\left({L(_tidy2(nv))}\\right)}}{{\\left({L(dd)}\\right)^{{2}}}}", None),
             step("Simplify.", f"f'(x) = {L(d)}", str(d))]
    return _finish_expr(stem, fe, d, at, f"Find $f'(x)$ for $f(x) = {L(fe)}$.",
                        f"Find $f'(@)$ for $f(x) = {L(fe)}$. Give an exact answer.", steps, mix, axes,
                        {"arg": _arg(fe)})


# -- chain rule ----------------------------------------------------------------------------------------------------

def _depth(e) -> int:
    """Composition depth: how many functions are applied one inside another. A linear inner function counts 0,
    a non-linear polynomial inner function 1: sin(3x) is 1, (3x + 1)^4 is 1, sin(x^2) is 2, (3x^2 + 1)^4 is 2,
    e^(sin(x^2)) is 3."""
    if e == x or not e.has(x) or _linear(e):
        return 0
    if e.is_Pow and e.base != x and not e.exp.has(x) and not _linear(e.base):
        return 1 + _depth(e.base)            # (3x^2 + 1)^4: the power wraps a polynomial that is itself a layer
    if e.is_polynomial(x):
        return 1
    if isinstance(e, (sp.Add, sp.Mul)):
        return max((_depth(a) for a in e.args if a.has(x)), default=0)
    if e.is_Pow:
        base, ex = e.as_base_exp()
        if ex.has(x):
            return 1 + max(_depth(ex), 0 if base.is_number else _depth(base))
        return 1 + _depth(base)
    if isinstance(e, sp.Function):
        return 1 + _depth(e.args[0])
    return 0


def _inner_ok(e) -> bool:
    """No product of two x-dependent factors anywhere (that would need the product rule inside)."""
    for n in sp.preorder_traversal(e):
        if isinstance(n, sp.Mul) and len(_factors(n)) > 1:
            return False
        if isinstance(n, sp.Pow) and n.exp.is_negative and n.base.has(x) and n.base != x and not n.exp.has(x):
            return False                                  # a quotient needs the quotient rule
    return True


def _layers(e):
    """[(outer expression in u, inner expression)] from the outside in, peeling a constant multiple."""
    out = []
    while e.has(x) and e != x:
        c, rest = e.as_independent(x, as_Add=False)
        e = rest
        if isinstance(e, sp.Add):
            break
        if e.is_Pow and not e.exp.has(x):
            outer, inner = sp.Pow(u, e.exp), e.base
        elif e.is_Pow:
            outer, inner = sp.Pow(e.base, u), e.exp
        elif isinstance(e, sp.Function):
            outer, inner = e.func(u), e.args[0]
        else:
            break
        out.append((outer, inner))
        e = inner
    return out


def _table_rows(F, G, a):
    """Rows of the table: x, F(x), F'(x), G(x), G'(x) for x in a, G(a) and one distractor; None if a value is not
    a small rational."""
    ga = G.subs(x, a)
    xs = []
    for v in (a, ga, a + 1 if a + 1 not in (a, ga) else a - 1):
        if v not in xs:
            xs.append(v)
    rows = []
    for v in sorted(xs):
        vals = [F.subs(x, v), sp.diff(F, x).subs(x, v), G.subs(x, v), sp.diff(G, x).subs(x, v)]
        if any(not (t.is_Rational and t.q <= MAX_TABLE_DENOM and abs(t.p) <= 99) for t in vals):
            return None
        rows.append((v, *vals))
    return rows


def _verify_chain_table(stem, axes, f, g, at):
    F, G = _expr(f, "f"), _expr(g, "g")
    a = _point(at, "at")
    if not a.is_Rational:
        raise Reject("slip", "at must be a rational number")
    for e, name in ((F, "f"), (G, "g")):
        if not e.is_polynomial(x) or sp.degree(e, x) > 3:
            raise Reject("redraw", f"{name} must be a polynomial of degree at most 3 for a table problem")
    rows = _table_rows(F, G, a)
    if rows is None:
        raise Reject("redraw", "a table entry is not a small rational number")
    ga = G.subs(x, a)
    d = sp.diff(F, x).subs(x, ga) * sp.diff(G, x).subs(x, a)
    h = F.subs(x, G)
    if not fd_agrees(h, sp.diff(h, x), points=[a + sp.Rational(k, 100) for k in (-3, 1, 4)], need=2) or \
            sp.diff(h, x).subs(x, a) != d:
        raise Reject("redraw", "the chain rule value failed the check")
    _check(axes, mix="table", at="point")
    if d == 0:
        raise Reject("redraw", "the answer is 0; choose values so that the product is not guessable")
    naive = sp.diff(F, x).subs(x, a) * sp.diff(G, x).subs(x, a)        # the usual slip: f' read at a, not at g(a)
    if naive == d:
        raise Reject("redraw", "reading f' at x = a gives the same answer, so the table does not test the chain rule")
    ans = numeric_answer(d)
    body = " \\\\ ".join(" & ".join(L(v) for v in r) for r in rows)
    table = ("\\begin{array}{c|cccc} x & f(x) & f'(x) & g(x) & g'(x) \\\\ \\hline " + body + " \\end{array}")
    st = (f"Let $h(x) = f(g(x))$. The table gives values of $f$, $f'$, $g$ and $g'$: ${table}$ "
          f"Find $h'({L(a)})$.")
    steps = [step("Chain rule: h'(a) = f'(g(a)) * g'(a).", f"h'({L(a)}) = f'(g({L(a)}))\\,g'({L(a)})"),
             step("Read g(a) and g'(a) from the row x = a.", f"g({L(a)}) = {L(ga)},\\ g'({L(a)}) = "
                  f"{L(sp.diff(G, x).subs(x, a))}"),
             step("Read f' at g(a) from the row x = g(a), then multiply.",
                  f"h'({L(a)}) = f'({L(ga)})\\,g'({L(a)}) = {ans['latex']}", ans["sympy"])]
    return finish(stem, F.subs(x, G), f"table|{a}", st, ans, steps, "table", axes, exact=True,
                  raw_extra={"mix": "table", "at": "point", "layers": 2})


def _verify_chain(stem, axes, f, at, g="", ask="expression", **_):
    if ask == "table":
        return _verify_chain_table(stem, axes, f, g, at)
    fe = _expr(f, "f")
    c, rest = fe.as_independent(x, as_Add=False)
    if isinstance(rest, sp.Add) or len(_factors(rest)) > 1:
        raise Reject("redraw", "f must be a constant times one composite function (not a sum or a product)")
    depth = _depth(rest)
    if not 1 <= depth <= 3 or (_basic(rest) and not (rest.is_Pow and isinstance(rest.base, sp.Add))):
        raise Reject("redraw", "f must be a composite function of one to three layers (not a basic form)")
    if depth == 1 and _basic(rest):
        raise Reject("redraw", "a function of x alone is not a composition")
    if not _inner_ok(rest):
        raise Reject("redraw", "an inner function needs the product or quotient rule")
    d = _tidy2(sp.diff(fe, x))
    if not fd_agrees(fe, d):
        raise Reject("redraw", "the derivative failed the finite-difference check")
    d = _nice(d)
    outer = _layers(fe)
    fam = sorted(pool.families_in(fe), key=list(pool.FAMILIES).index)
    steps = []
    for k, (o, inner) in enumerate(outer, 1):
        steps.append(step(f"Layer {k}: the outer function of u = {L(inner)}.",
                          f"\\frac{{d}}{{du}}\\left[{L(o)}\\right] = {L(_tidy2(sp.diff(o, u)))}", str(sp.diff(o, u))))
    steps.append(step("Multiply the derivatives of the layers, working from the outside in.",
                      f"f'(x) = {L(d)}", str(d)))
    st_expr = f"Find $f'(x)$ for $f(x) = {L(fe)}$."
    return _finish_expr(stem, fe, d, at, st_expr, f"Find $f'(@)$ for $f(x) = {L(fe)}$. Give an exact answer.", steps,
                        f"d{depth}", axes, {"layers": depth, "arg": _arg(fe)})


# -- tangent and normal lines --------------------------------------------------------------------------------------

def _tn_scope(f) -> str:
    if f.has(sp.Abs, sp.Piecewise, sp.sign):
        raise Reject("redraw", "f must be a smooth expression")
    if pool.complexity(f) > 9:
        raise Reject("redraw", "f is too complicated for this topic")
    if f.is_polynomial(x):
        return "poly"
    if f.is_rational_function(x):
        return "rational"
    return "composite" if _depth(f) >= 2 else "trans"


def _verify_tangent(stem, axes, f, a, ask, **_):
    if ask not in ("tangent", "normal", "horizontal"):
        raise Reject("slip", "ask must be tangent, normal or horizontal")
    fe = _expr(f, "f")
    fam = _tn_scope(fe)
    _check(axes, ask=ask, fam=fam)
    d = _tidy2(sp.diff(fe, x))
    if not fd_agrees(fe, d):
        raise Reject("redraw", "the derivative failed the finite-difference check")
    if ask == "horizontal":
        if fam not in ("poly", "rational"):
            raise Reject("redraw", "horizontal tangents are asked only for polynomials and rational functions")
        num = sp.numer(sp.together(d))
        roots = sorted((r for r in sp.solve(sp.Eq(num, 0), x) if r.is_real is True
                        and not sp.denom(sp.together(fe)).subs(x, r) == 0), key=float)
        if not 1 <= len(roots) <= 3:
            raise Reject("redraw", "the function must have one to three horizontal tangents")
        for r in roots:
            if value_reason(canon(r), True):
                raise Reject("redraw", "a root is not a short exact form")
            fl = sp.lambdify(x, d, "mpmath")
            mp.mp.dps = 30
            if abs(fl(mp.mpf(str(sp.N(r, 30))))) > 1e-15:
                raise Reject("redraw", "f' does not vanish at a computed root (numeric check)")
        ans = {"type": "set", "latex": "\\left\\{" + ",\\ ".join(L(r) for r in roots) + "\\right\\}",
               "sympy": "{" + ", ".join(str(r) for r in roots) + "}", "numeric": None}
        steps = [step("A horizontal tangent has slope 0, so solve f'(x) = 0.", f"f'(x) = {L(d)}"),
                 step("Keep the real solutions in the domain of f.", ans["latex"], ans["sympy"])]
        st = f"Find all values of $x$ at which the graph of $f(x) = {L(fe)}$ has a horizontal tangent line."
        return finish(stem, fe, "horizontal", st, ans, steps, fam, axes, exact=True,
                      raw_extra={"ask": ask, "fam": fam})
    pt = _point(a, "a")
    fa = fe.subs(x, pt)
    m = d.subs(x, pt)
    if any(v.has(sp.nan, sp.zoo, sp.oo, -sp.oo) or v.is_real is not True for v in (fa, m)):
        raise Reject("redraw", "f and f' must be defined and real at a")
    fa, m = canon(fa), canon(m)
    for v in (fa, m):
        if r := value_reason(v, True):
            raise Reject("redraw", f"a value is not a short exact form ({r})", cap=r)
    if ask == "normal":
        if m == 0:
            raise Reject("redraw", "the tangent is horizontal, so the normal is vertical; choose another point")
        m = canon(-1 / m)
        if r := value_reason(m, True):
            raise Reject("redraw", f"the normal slope is not a short exact form ({r})", cap=r)
    line = sp.expand(m * (x - pt) + fa)
    if abs(complex(sp.N(line.subs(x, pt) - fa))) > 1e-12:
        raise Reject("redraw", "the line misses the point")
    ans = {"type": "expression", "latex": f"y = {L(line)}", "sympy": str(line), "numeric": None}
    word = "tangent" if ask == "tangent" else "normal"
    steps = [step("Find the point and the slope of the tangent.", f"f({L(pt)}) = {L(fa)},\\ f'({L(pt)}) = {L(canon(d.subs(x, pt)))}"),
             step("The normal slope is the negative reciprocal." if ask == "normal" else "The slope is f'(a).",
                  f"m = {L(m)}"),
             step("Write the line through the point with that slope.",
                  f"y - {L(fa)} = {L(m)}\\left(x - {L(pt)}\\right)".replace("- -", "+ "), None),
             step("Simplify.", ans["latex"], ans["sympy"])]
    st = f"Find an equation of the {word} line to the graph of $f(x) = {L(fe)}$ at $x = {L(pt)}$."
    return finish(stem, fe, f"{ask}|{pt}", st, ans, steps, fam, axes, exact=True, raw_extra={"ask": ask, "fam": fam})


_VERIFY = {"product_rule": _verify_product, "quotient_rule": _verify_quotient, "chain_rule": _verify_chain,
           "tangent_normal_lines": _verify_tangent}
