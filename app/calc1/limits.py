"""Verifiers for the limits and continuity chapter (calc.limits.*, calc.continuity.*).

One entry point, `verify(stem, ...)`, runs in the sandbox (app/worker.py). The model supplies a function (and the
point, side, parameters or interval the topic needs); the server builds the statement, takes the exact limit with
SymPy, cross-checks it numerically with mpmath at points approaching the limit point, and writes the steps.

Stems: algebraic, one_sided, infinite, at_infinity, squeeze, epsilon_delta, classify_discontinuity,
make_continuous, ivt.

A failed candidate is cause "slip" (the model can fix it from the reason) or "redraw" (draw another recipe).
"""
import hashlib

import mpmath as mp
import sympy as sp

from app.shared.clean_answer import canon, value_reason
from app.shared.integral_core import L, Reject, _shape, _with_timeout, x
from app.safe_parse import ParseError, safe_parse

STEMS = ("algebraic", "one_sided", "infinite", "at_infinity", "squeeze", "epsilon_delta",
         "classify_discontinuity", "make_continuous", "ivt")
_BAD = (sp.Integral, sp.Derivative, sp.Limit, sp.Sum, sp.Product, sp.oo, sp.zoo, sp.nan, sp.I)
_TRANSCENDENTAL = (sp.sin, sp.cos, sp.tan, sp.cot, sp.sec, sp.csc, sp.exp, sp.log, sp.asin, sp.acos, sp.atan,
                   sp.sinh, sp.cosh, sp.tanh)
MAX_EXP = 12
TOL = 1e-5


def verify(stem: str, bounds=None, axes: dict | None = None, calculator: str = "none", **fields) -> dict:
    try:
        if stem not in STEMS:
            raise Reject("slip", f"unknown limits topic {stem}")
        if calculator != "none":
            raise Reject("redraw", "limits topics have only the exact tier")
        return _VERIFY[stem](axes or {}, **fields)
    except Reject as r:
        return {"ok": False, "cause": r.cause, "reason": r.reason, "cap": r.cap}


# -- parsing ------------------------------------------------------------------------------------------------

def _expr(s, label: str, symbols: dict | None = None, piecewise: bool = False) -> sp.Expr:
    if not isinstance(s, str):
        raise Reject("slip", f"{label} must be a string")
    try:
        e = safe_parse(s, {"x": x, **(symbols or {})})
    except ParseError as err:
        raise Reject("slip", f"{label}: {err}") from None
    if not isinstance(e, sp.Expr) or e.has(*_BAD):
        raise Reject("slip", f"{label} must be a plain real expression")
    if e.has(sp.Piecewise) and not piecewise:
        raise Reject("slip", f"{label} may not be piecewise in this topic")
    extra = e.free_symbols - {x} - set((symbols or {}).values())
    if extra:
        raise Reject("slip", f"{label} may contain only x; found {', '.join(sorted(map(str, extra)))}")
    if any(p.exp.is_Number and abs(p.exp) > MAX_EXP for p in e.atoms(sp.Pow)):
        raise Reject("slip", f"{label}: exponents must be at most {MAX_EXP} in size")
    return e


def _point(s, label: str, infinite: bool = False) -> sp.Expr:
    try:
        v = safe_parse(str(s))
    except ParseError as err:
        raise Reject("slip", f"{label}: {err}") from None
    ok = v.is_number and (v.is_real is True or (infinite and v in (sp.oo, -sp.oo)))
    if not ok or v.has(sp.zoo, sp.nan):
        raise Reject("slip", f"{label} must be a real number" + (" or oo / -oo" if infinite else ""))
    if v.is_Rational is False and v not in (sp.oo, -sp.oo) and not v.is_Integer:
        v = sp.nsimplify(v)
    return v


def _scope(f, allowed: tuple, label: str = "f") -> None:
    """Reject functions outside the topic's families (transcendental functions are not 'algebraic')."""
    bad = [a for a in f.atoms(sp.Function) if not isinstance(a, allowed) and not isinstance(a, sp.Piecewise)]
    if bad:
        raise Reject("redraw", f"{label} uses {bad[0].func.__name__}, which is outside this topic")


# -- limits -------------------------------------------------------------------------------------------------

def _active(pw: sp.Piecewise, a, d: int):
    p = a + d * sp.Rational(1, 10 ** 6)
    for e, cond in pw.args:
        try:
            if bool(cond.subs(x, p)):
                return e
        except TypeError:
            continue
    return sp.nan


def side_limit(f, a, d: int | None):
    """Exact limit as x -> a from the right (d = 1), left (d = -1) or at infinity (d None, a = +-oo). Piecewise
    pieces are resolved to the one active on that side first. None if SymPy cannot decide."""
    g = f
    if g.has(sp.Piecewise) and d is not None:
        g = g.replace(lambda e: isinstance(e, sp.Piecewise), lambda e: _active(e, a, d))
        if g.has(sp.nan):
            return None
    try:
        v = _with_timeout(6, lambda: sp.limit(g, x, a, "+" if d == 1 else "-") if d is not None
                          else sp.limit(g, x, a))
    except Exception:
        return None
    if v is None or v.has(sp.Limit, sp.AccumBounds, sp.nan) or v == sp.zoo:
        return None
    return v


def _lam(f):
    return sp.lambdify(x, f, "mpmath")


def _near(f, a, d: int, ks=(6, 9, 12)):
    """f at a + d*10^-k for the k in ks, high precision; None if the values are complex or undefined."""
    fl, out = _lam(f), []
    mp.mp.dps = 70
    base = mp.mpf(str(sp.N(a, 70)))
    for k in ks:
        try:
            v = fl(base + d * mp.mpf(10) ** -k)
        except (ValueError, ZeroDivisionError, TypeError, ArithmeticError):
            return None
        if isinstance(v, mp.mpc) and abs(v.imag) > mp.mpf(10) ** -30:
            return None
        out.append(mp.re(v) if isinstance(v, mp.mpc) else v)
    return out


def _far(f, sign: int, ks=(6, 9, 12)):
    fl, out = _lam(f), []
    mp.mp.dps = 70
    for k in ks:
        try:
            v = fl(sign * mp.mpf(10) ** k)
        except (ValueError, ZeroDivisionError, TypeError, ArithmeticError):
            return None
        if isinstance(v, mp.mpc):
            return None
        out.append(v)
    return out


def _agrees(vals, v) -> bool:
    """Do the sampled values approach the exact limit v (a number, oo or -oo)?"""
    if vals is None:
        return False
    if v == sp.oo:
        return vals[-1] > 1e5 and vals[-1] > vals[0]
    if v == -sp.oo:
        return vals[-1] < -1e5 and vals[-1] < vals[0]
    want = mp.mpf(str(sp.N(v, 40)))
    return abs(vals[-1] - want) <= TOL * max(1, abs(want)) and abs(vals[-2] - want) <= 1e3 * TOL * max(1, abs(want))


def _checked_side(f, a, d: int, label: str):
    v = side_limit(f, a, d)
    if v is None:
        raise Reject("redraw", f"could not evaluate the {label} limit")
    if not _agrees(_near(f, a, d), v):
        raise Reject("redraw", f"the {label} limit failed the numeric cross-check")
    return v


def _checked_far(f, sign: int):
    v = side_limit(f, sp.oo if sign > 0 else -sp.oo, None)
    if v is None:
        raise Reject("redraw", "could not evaluate the limit at infinity")
    if not _agrees(_far(f, sign), v):
        raise Reject("redraw", "the limit at infinity failed the numeric cross-check")
    return v


# -- answers and printing ----------------------------------------------------------------------------------

def _inf_answer(v) -> dict:
    return {"type": "enum", "latex": "\\infty" if v == sp.oo else "-\\infty", "sympy": "oo" if v == sp.oo else "-oo",
            "numeric": None}


def _value_answer(v) -> dict:
    v = canon(v)
    if v in (sp.oo, -sp.oo):
        return _inf_answer(v)
    if why := value_reason(v, True):
        raise Reject("redraw", f"answer is not a short exact form ({why})", cap=why)
    return {"type": "numeric", "latex": L(v), "sympy": str(v), "numeric": float(sp.N(v, 15))}


def _dne() -> dict:
    return {"type": "enum", "latex": "\\text{does not exist}", "sympy": None, "numeric": None}


def _sub(v) -> str:
    """'- v' for a nonnegative v and '+ |v|' for a negative one, so x - (-1) is written x + 1."""
    return f"- {L(v)}" if v >= 0 else f"+ {L(-v)}"


def _under(f) -> str:
    return f"\\left({L(f)}\\right)" if isinstance(f, sp.Add) else L(f)


def _bps(pw: sp.Piecewise) -> list:
    out = set()
    for _, cond in pw.args:
        for rel in cond.atoms(sp.Rel):
            out |= {side for side in (rel.lhs, rel.rhs) if side.is_number}
    return sorted(out, key=float)


def _active_expr(pw: sp.Piecewise, t):
    for e, cond in pw.args:
        try:
            if bool(cond.subs(x, t)):
                return e
        except TypeError:
            continue
    return None


def _show(f) -> str:
    """f as typeset in a statement. A piecewise function is written with explicit intervals (1 <= x < 3), not
    SymPy's ordered conditions, so no piece can be misread."""
    pws = list(f.atoms(sp.Piecewise))
    pts = _bps(pws[0]) if len(pws) == 1 and f == pws[0] else []
    if not pts:
        return L(f)
    pw, n = pws[0], len(pts)
    toks = []                                   # open interval 0, point 0, open interval 1, point 1, ...
    for k in range(n + 1):
        t = pts[0] - 1 if k == 0 else pts[-1] + 1 if k == n else (pts[k - 1] + pts[k]) / 2
        toks.append(("i", k, _active_expr(pw, t)))
        if k < n:
            toks.append(("p", k, _active_expr(pw, pts[k])))
    runs = []
    for tok in toks:
        if runs and runs[-1][1][2] == tok[2]:
            runs[-1][1] = tok
        else:
            runs.append([tok, tok])
    rows = []
    for first, last in runs:
        expr = first[2]
        if expr is None:
            continue
        lo = (pts[first[1]], True) if first[0] == "p" else None if first[1] == 0 else (pts[first[1] - 1], False)
        hi = (pts[last[1]], True) if last[0] == "p" else None if last[1] == n else (pts[last[1]], False)
        if lo and hi and lo[0] == hi[0]:
            cond = f"x = {L(lo[0])}"
        elif lo and hi:
            cond = f"{L(lo[0])} {'\\le' if lo[1] else '<'} x {'\\le' if hi[1] else '<'} {L(hi[0])}"
        elif lo:
            cond = f"x {'\\ge' if lo[1] else '>'} {L(lo[0])}"
        else:
            cond = f"x {'\\le' if hi[1] else '<'} {L(hi[0])}"
        rows.append(f"{L(expr)} & \\text{{if }} {cond}")
    return "\\begin{cases} " + " \\\\ ".join(rows) + " \\end{cases}"


def _lim(f, a, d: int | None = None) -> str:
    sup = "" if d is None else "^{+}" if d == 1 else "^{-}"
    shown = "f(x)" if f.has(sp.Piecewise) else _under(f)
    return f"\\lim_{{x \\to {L(a)}{sup}}} {shown}"


def _step(text: str, latex: str = "", sympy_: str | None = None) -> dict:
    return {"text": text, "latex": latex, "sympy": sympy_}


def _terms(f) -> int:
    return len(sp.Add.make_args(sp.expand(f))) if not f.has(sp.Piecewise) else 2


# Topics where each function is its own problem: the shape keeps its constants. The others mask the constants of f
# but keep the point and the question (key), so (x^2-9)/(x-3) and (x^2-16)/(x-4) are different problems.
_EXACT_SHAPE = ("ivt", "epsilon_delta", "make_continuous")


def _finish(stem: str, f, key: str, statement: str, answer: dict, steps: list, technique: str,
            has_disc: bool, axes: dict, extra_shape: str = "") -> dict:
    if "technique" in axes and axes["technique"] != technique:
        raise Reject("redraw", f"axes: the server assigned {axes['technique']} (this is {technique})")
    value = sp.sympify(answer["sympy"]) if answer.get("sympy") else sp.Integer(0)
    raw = {"ops_integrand": int(sp.count_ops(f)), "ops_R": int(sp.count_ops(f)), "ops_F": int(sp.count_ops(value)),
           "g_polynomial": True, "deg_g": None, "n_terms_R": _terms(f), "const_factor": False, "definite": False,
           "has_discontinuity": has_disc, "steps": len(steps), "answer_type": answer["type"], "rules": [],
           "stem": stem, "technique": technique}
    h = hashlib.sha256((stem + "|" + sp.srepr(f) + "|" + key).encode()).hexdigest()[:16]
    return {"ok": True, "statement": statement, "answer": answer, "steps": steps, "method": f"limit_{stem}",
            "calculator_check": "passed", "hash": h, "shape": f"{str(f) if stem in _EXACT_SHAPE else _shape(f, False)}|{stem}|{extra_shape}|{key}|{answer.get('sympy')}",
            "has_discontinuity": has_disc, "integrand": str(f), "raw": raw, "technique": technique}


def _check_axes(axes: dict, **found) -> None:
    for k, v in found.items():
        if k in axes and str(axes[k]) != str(v):
            raise Reject("redraw", f"axes: the server assigned {k} = {axes[k]} (this is {v})")


# -- 1. algebraic -------------------------------------------------------------------------------------------

def _algebraic_technique(f) -> str:
    if any(p.exp.is_Rational and not p.exp.is_Integer for p in f.atoms(sp.Pow)):
        return "conjugate"
    n, d = sp.fraction(f)
    nested = any(isinstance(t, sp.Pow) and t.exp.is_negative and t.base.has(x)
                 for part in (n, d) for t in sp.preorder_traversal(part) if t is not part)
    return "complex_fraction" if nested else "factor"


def _verify_algebraic(axes, f, a, **_):
    fe = _expr(f, "f")
    _scope(fe, (), "f")
    pt = _point(a, "a")
    direct = fe.subs(x, pt)
    if direct.has(sp.zoo, sp.oo, -sp.oo):
        raise Reject("redraw", "substitution gives a nonzero number over 0, not the indeterminate form 0/0")
    if not direct.has(sp.nan):
        raise Reject("redraw", "direct substitution works; the limit needs an indeterminate form 0/0")
    v = side_limit(fe, pt, 1)
    w = side_limit(fe, pt, -1)
    if v is None or w is None or v != w or v in (sp.oo, -sp.oo):
        raise Reject("redraw", "the two-sided limit is not a finite number")
    if not (_agrees(_near(fe, pt, 1), v) and _agrees(_near(fe, pt, -1), v)):
        raise Reject("redraw", "the limit failed the numeric cross-check")
    tech = _algebraic_technique(fe)
    ans = _value_answer(v)
    simp = sp.factor(sp.cancel(sp.together(fe))) if tech == "factor" else sp.simplify(fe)
    steps = [_step("Substitute x = a: the result is 0/0, so the limit needs algebra first.",
                   "\\frac{0}{0}"),
             _step({"factor": "Factor and cancel the common factor.", "conjugate": "Multiply by the conjugate and simplify.",
                    "complex_fraction": "Combine the fractions, simplify, and cancel."}[tech], L(simp), str(simp)),
             _step("Substitute x = a into the simplified expression.", f"{_lim(simp, pt)} = {ans['latex']}")]
    st = f"Evaluate $\\displaystyle {_lim(fe, pt)}$. Give an exact answer."
    return _finish("algebraic", fe, f"{pt}", st, ans, steps, tech, True, axes, f"{tech}")


# -- 2. one-sided -------------------------------------------------------------------------------------------

def _form(f) -> str:
    if f.has(sp.Piecewise):
        return "piecewise"
    if f.has(sp.Abs):
        return "abs"
    if any(p.exp.is_Rational and not p.exp.is_Integer for p in f.atoms(sp.Pow)):
        return "root"
    return "rational"


def _verify_one_sided(axes, f, a, ask, **_):
    fe = _expr(f, "f", piecewise=True)
    _scope(fe, (sp.Abs, sp.sign))
    pt = _point(a, "a")
    if ask not in ("left", "right", "two_sided", "pair"):
        raise Reject("slip", "ask must be left, right, two_sided or pair")
    left = _checked_side(fe, pt, -1, "left") if ask != "right" else side_limit(fe, pt, -1)
    right = _checked_side(fe, pt, 1, "right") if ask != "left" else side_limit(fe, pt, 1)
    both_real = _near(fe, pt, -1) is not None and _near(fe, pt, 1) is not None
    if both_real and left == right and not fe.has(sp.Piecewise, sp.Abs):
        raise Reject("redraw", "the function is continuous at a; a one-sided limit is plain substitution")
    form = _form(fe)
    _check_axes(axes, form=form, ask=ask)
    if ask == "left":
        ans, what = _value_answer(left), (-1,)
    elif ask == "right":
        ans, what = _value_answer(right), (1,)
    elif ask == "two_sided":
        ans = _value_answer(left) if left == right else _dne()
        what = (-1, 1)
    else:
        l_, r_ = _value_answer(left), _value_answer(right)
        ans = {"type": "multi_part", "latex": f"{l_['latex']},\\ {r_['latex']}",
               "sympy": f"({l_['sympy']}, {r_['sympy']})", "numeric": None}
        what = (-1, 1)
    steps = []
    for d in what:
        v = left if d == -1 else right
        steps.append(_step(f"Take x to {L(pt)} from the {'left' if d == -1 else 'right'}.",
                           f"{_lim(fe, pt, d)} = {_value_answer(v)['latex']}", str(v)))
    if ask == "two_sided":
        steps.append(_step("The two-sided limit exists only if both one-sided limits are equal.",
                           ans["latex"], ans["sympy"]))
    st = {"left": f"Evaluate $\\displaystyle {_lim(fe, pt, -1)}$. Give an exact answer, or $\\infty$ or $-\\infty$.",
          "right": f"Evaluate $\\displaystyle {_lim(fe, pt, 1)}$. Give an exact answer, or $\\infty$ or $-\\infty$.",
          "two_sided": f"Evaluate $\\displaystyle {_lim(fe, pt)}$. Give an exact answer, $\\infty$, $-\\infty$, or "
                       "state that the limit does not exist.",
          "pair": f"Find the left-hand and right-hand limits of $f(x) = {_show(fe)}$ as $x \\to {L(pt)}$. "
                  "Give them in that order."}[ask]
    return _finish("one_sided", fe, f"{pt}|{ask}", st, ans, steps, form, True, axes, f"{form}|{ask}")


# -- 3. infinite --------------------------------------------------------------------------------------------

def _pole_form(f) -> str:
    n, d = sp.fraction(sp.cancel(sp.together(f)))
    n0, d0 = sp.fraction(sp.together(f))
    if sp.degree(sp.Poly(d0, x)) > sp.degree(sp.Poly(d, x)):
        return "hole"
    roots = sp.roots(sp.Poly(d, x))
    real = {r: m for r, m in roots.items() if r.is_real}
    if len(real) >= 2:
        return "two"
    if any(m % 2 == 0 for m in real.values()):
        return "squared"
    return "simple"


def _verify_infinite(axes, f, a, ask, **_):
    fe = _expr(f, "f")
    if not fe.is_rational_function(x):
        raise Reject("redraw", "f must be a rational function in this topic")
    if ask not in ("left", "right", "two_sided", "asymptotes"):
        raise Reject("slip", "ask must be left, right, two_sided or asymptotes")
    form = _pole_form(fe)
    _check_axes(axes, form=form, ask=ask)
    n, d = sp.fraction(sp.cancel(sp.together(fe)))
    poles = sorted((r for r in sp.roots(sp.Poly(d, x)) if r.is_real), key=float)
    if not poles:
        raise Reject("redraw", "f has no vertical asymptote")
    if ask == "asymptotes":
        ans = {"type": "set", "latex": "\\left\\{" + ",\\ ".join(L(p) for p in poles) + "\\right\\}",
               "sympy": "{" + ", ".join(str(p) for p in poles) + "}", "numeric": None}
        for p in poles:
            if not (_checked_side(fe, p, 1, "right") in (sp.oo, -sp.oo) or
                    _checked_side(fe, p, -1, "left") in (sp.oo, -sp.oo)):
                raise Reject("redraw", "a pole without an infinite limit")
        steps = [_step("Factor and cancel any common factor of the numerator and denominator.", L(sp.factor(sp.cancel(fe)))),
                 _step("Vertical asymptotes are at the zeros of the denominator that remain.",
                       ans["latex"], ans["sympy"])]
        st = f"Find all vertical asymptotes of $f(x) = {L(fe)}$. Give the values of $x$."
        return _finish("infinite", fe, f"asy|{fe}", st, ans, steps, form, True, axes, f"{form}|{ask}")
    pt = _point(a, "a")
    if pt not in poles:
        raise Reject("redraw", "a must be a vertical asymptote of f")
    left, right = _checked_side(fe, pt, -1, "left"), _checked_side(fe, pt, 1, "right")
    if left not in (sp.oo, -sp.oo) and right not in (sp.oo, -sp.oo):
        raise Reject("redraw", "no infinite limit at a")
    if (ask == "left" and left not in (sp.oo, -sp.oo)) or (ask == "right" and right not in (sp.oo, -sp.oo)):
        raise Reject("redraw", "the limit from that side is finite; this topic asks for infinite limits")
    if ask == "left":
        ans, d_ = _value_answer(left), (-1,)
    elif ask == "right":
        ans, d_ = _value_answer(right), (1,)
    else:
        ans, d_ = (_value_answer(left) if left == right else _dne()), (-1, 1)
    steps = [_step(f"Evaluate the {'left' if d == -1 else 'right'}-hand limit by the sign of the numerator and denominator.",
                   f"{_lim(fe, pt, d)} = {_value_answer(left if d == -1 else right)['latex']}") for d in d_]
    if ask == "two_sided":
        steps.append(_step("The two-sided limit is infinite only if both sides give the same infinity.",
                           ans["latex"], ans["sympy"]))
    side = {"left": -1, "right": 1, "two_sided": None}[ask]
    st = (f"Evaluate $\\displaystyle {_lim(fe, pt, side)}$. Give $\\infty$ or $-\\infty$"
          + (", or state that the limit does not exist." if ask == "two_sided" else "."))
    return _finish("infinite", fe, f"{pt}|{ask}", st, ans, steps, form, True, axes, f"{form}|{ask}")


# -- 4. at infinity -----------------------------------------------------------------------------------------

def _inf_form(f) -> str:
    if f.has(sp.exp):
        return "exp"
    if f.has(sp.atan):
        return "atan"
    if any(p.exp.is_Rational and not p.exp.is_Integer for p in f.atoms(sp.Pow)):
        return "radical"
    n, d = sp.fraction(sp.cancel(sp.together(f)))
    if d.has(x) and n.is_polynomial(x) and d.is_polynomial(x):
        dn, dd = sp.degree(n, x), sp.degree(d, x)
        return "same_degree" if dn == dd else "lower_degree" if dn < dd else "higher_degree"
    return "other"


def _verify_at_infinity(axes, f, direction, ask, **_):
    fe = _expr(f, "f")
    _scope(fe, (sp.exp, sp.atan))
    if direction not in ("oo", "-oo", "+oo"):
        raise Reject("slip", "direction must be oo or -oo")
    if ask not in ("limit", "horizontal"):
        raise Reject("slip", "ask must be limit or horizontal")
    sign = -1 if direction == "-oo" else 1
    form = _inf_form(fe)
    if form == "other":
        raise Reject("redraw", "f must be a rational function, a radical, or built from exp or atan")
    _check_axes(axes, form=form, ask=ask)
    pt = sp.oo if sign > 0 else -sp.oo
    if ask == "limit":
        v = _checked_far(fe, sign)
        ans = _value_answer(v)
        how = ("Multiply and divide by the conjugate, then simplify." if isinstance(fe, sp.Add) and form == "radical"
               else "Divide the numerator and denominator by the highest power of x in the denominator "
                    "(or compare the growth rates).")
        steps = [_step(how, L(fe)),
                 _step("Let x grow without bound and use that 1/x^k -> 0.", f"{_lim(fe, pt)} = {ans['latex']}", ans["sympy"])]
        st = f"Evaluate $\\displaystyle {_lim(fe, pt)}$. Give an exact answer, $\\infty$ or $-\\infty$."
        return _finish("at_infinity", fe, f"{direction}|limit", st, ans, steps, form, False, axes, f"{form}|limit")
    vals = []
    for s in (1, -1):
        v = _checked_far(fe, s)
        if v not in (sp.oo, -sp.oo) and v not in vals:
            vals.append(canon(v))
    if not vals:
        raise Reject("redraw", "f has no horizontal asymptote")
    vals.sort(key=float)
    for v in vals:
        if r := value_reason(v, True):
            raise Reject("redraw", f"answer is not a short exact form ({r})", cap=r)
    ans = {"type": "set", "latex": "\\left\\{" + ",\\ ".join(L(v) for v in vals) + "\\right\\}",
           "sympy": "{" + ", ".join(str(v) for v in vals) + "}", "numeric": None}
    steps = [_step(f"Find the limit as x -> {s}.", f"{_lim(fe, pt2)} = "
                   f"{_value_answer(_checked_far(fe, sg))['latex']}") for s, sg, pt2 in
             (("\\infty", 1, sp.oo), ("-\\infty", -1, -sp.oo))]
    steps.append(_step("Each finite limit L gives a horizontal asymptote y = L.", ans["latex"], ans["sympy"]))
    st = f"Find all horizontal asymptotes of $f(x) = {L(fe)}$. Give the values of $y$."
    return _finish("at_infinity", fe, "horizontal", st, ans, steps, form, False, axes, f"{form}|horizontal")


# -- 5. squeeze ---------------------------------------------------------------------------------------------

_OSC = {"sin": sp.sin, "cos": sp.cos}


def _osc_kind(o) -> tuple[str, sp.Expr] | None:
    base, e = o.as_base_exp()
    if isinstance(base, (sp.sin, sp.cos)) and e in (1, 2):
        return (type(base).__name__ + ("2" if e == 2 else ""), base.args[0])
    return None


def _verify_squeeze(axes, p, osc, a, c, ask, **_):
    pe, oe = _expr(p, "p"), _expr(osc, "osc")
    ce = _expr(c, "c")
    if not ce.is_number or ce.is_real is not True:
        raise Reject("slip", "c must be a number")
    k = _osc_kind(oe)
    if k is None:
        raise Reject("slip", "osc must be sin(q), cos(q), sin(q)^2 or cos(q)^2 for an expression q in x")
    kind, q = k
    pt = _point(a, "a", infinite=True)
    if ask not in ("given", "find"):
        raise Reject("slip", "ask must be given or find")
    at = "zero" if pt == 0 else "infinity" if pt in (sp.oo, -sp.oo) else "point"
    _check_axes(axes, osc=kind, at=at, ask=ask)
    f = ce + pe * oe
    d_dirs = (None,) if pt in (sp.oo, -sp.oo) else (1, -1)
    # the middle function must be undefined or oscillating at the point, so that substitution does not decide it
    if pt not in (sp.oo, -sp.oo) and not (f.subs(x, pt).has(sp.nan, sp.zoo, sp.oo, -sp.oo)):
        raise Reject("redraw", "f is defined at a; no squeeze is needed")
    for d in d_dirs:
        v = side_limit(pe, pt, d)
        if v != 0:
            raise Reject("redraw", "p must tend to 0, so that the bounds squeeze")
    # inequality on a punctured neighborhood, sampled densely at several scales
    sgn = {sp.oo: "positive", -sp.oo: "negative"}.get(pt)
    absp = sp.Abs(pe)
    if sgn:                      # x is large, so |p(x)| has no bars: 3/|x| becomes 3/x
        xs = sp.Symbol("x", real=True, **{sgn: True})
        absp = sp.Abs(pe.subs(x, xs)).subs(xs, x)
    lo_f = ce - absp if kind in ("sin", "cos") else ce
    hi_f = ce + absp
    ff, lo_l, hi_l = _lam(f), _lam(lo_f), _lam(hi_f)
    mp.mp.dps = 40
    for scale in (1, 2, 3, 4, 6):
        for i in range(1, 61):
            t = mp.mpf(i) / 7 * mp.mpf(10) ** -scale
            for s in (1, -1):
                xv = (mp.mpf(str(sp.N(pt, 30))) + s * t) if pt not in (sp.oo, -sp.oo) else (
                    (1 if pt == sp.oo else -1) * (mp.mpf(10) ** scale) * (1 + mp.mpf(i) / 7))
                try:
                    fv, lv, hv = ff(xv), lo_l(xv), hi_l(xv)
                except (ValueError, ZeroDivisionError, ArithmeticError):
                    continue
                if any(isinstance(z, mp.mpc) for z in (fv, lv, hv)):
                    raise Reject("redraw", "f is not real near a")
                if not lv - mp.mpf(10) ** -25 <= fv <= hv + mp.mpf(10) ** -25:
                    raise Reject("redraw", "the bounds do not hold near a")
    ans = _value_answer(ce)
    low, high = L(lo_f), L(hi_f)
    steps = [_step("Bound the oscillating factor: " + ("-1 <= sin or cos <= 1." if kind in ("sin", "cos")
                                                         else "0 <= sin^2 or cos^2 <= 1."), ""),
             _step("Multiply by |p(x)| to bound f.", f"{low} \\le {L(f)} \\le {high}"),
             _step("Both bounds have the same limit.", f"{_lim(lo_f, pt)} = {_lim(hi_f, pt)} = {ans['latex']}", ans["sympy"]),
             _step("By the squeeze theorem the limit of f is that value.", f"{_lim(f, pt)} = {ans['latex']}", ans["sympy"])]
    if ask == "given":
        near = "for large $x$" if pt == sp.oo else "for $x$ large and negative" if pt == -sp.oo else f"for $x$ near ${L(pt)}$"
        st = (f"Given that ${low} \\le f(x) \\le {high}$ {near}, where "
              f"$f(x) = {L(f)}$, use the squeeze theorem to evaluate $\\displaystyle {_lim(f, pt)}$.")
    else:
        st = f"Use the squeeze theorem to evaluate $\\displaystyle {_lim(f, pt)}$."
    return _finish("squeeze", f, f"{pt}|{ask}", st, ans, steps, kind, False, axes, f"{kind}|{at}|{ask}")


# -- 6. epsilon-delta ---------------------------------------------------------------------------------------

def _delta_form(f) -> str:
    if f.is_polynomial(x):
        return "linear" if sp.degree(f, x) == 1 else "quadratic"
    if any(p.exp.is_Rational and not p.exp.is_Integer for p in f.atoms(sp.Pow)):
        return "root"
    return "rational"


def _verify_epsilon_delta(axes, f, a, eps, **_):
    fe = _expr(f, "f")
    _scope(fe, ())
    pt = _point(a, "a")
    try:
        ev = sp.Rational(str(eps))
    except (TypeError, ValueError):
        raise Reject("slip", "eps must be a positive rational number") from None
    if ev <= 0 or ev > 1:
        raise Reject("slip", "eps must be between 0 and 1")
    form = _delta_form(fe)
    if fe.is_polynomial(x) and sp.degree(fe, x) > 2:
        raise Reject("redraw", "f must have degree at most 2 (or be a root or a reciprocal of a linear function)")
    _check_axes(axes, form=form)
    Lv = fe.subs(x, pt)
    if Lv.has(sp.nan, sp.zoo, sp.oo, -sp.oo) or Lv.is_real is not True:
        raise Reject("redraw", "f must be defined and real at a")
    Lv = sp.nsimplify(Lv) if not Lv.is_Rational else Lv
    cands = []
    for target in (Lv + ev, Lv - ev):
        for r in sp.solve(sp.Eq(fe, target), x):
            if r.is_real is True and r != pt and not fe.subs(x, r).has(sp.nan, sp.zoo):
                cands.append(r)
    # points where f stops being defined bound the neighborhood too
    n, d = sp.fraction(sp.together(fe))
    for g in [d] + [t.base for t in fe.atoms(sp.Pow) if t.exp.is_Rational and not t.exp.is_Integer]:
        if g.has(x):
            cands += [r for r in sp.solve(sp.Eq(g, 0), x) if r.is_real is True]
    if pt in cands:
        raise Reject("redraw", "a is at the edge of the domain of f")
    if not cands:
        raise Reject("redraw", "no finite delta")
    delta = canon(min((sp.Abs(r - pt) for r in cands), key=lambda t: float(sp.N(t))))
    if delta == 0 or delta.is_real is not True:
        raise Reject("redraw", "no positive delta")
    if r := value_reason(delta, True):
        raise Reject("redraw", f"answer is not a short exact form ({r})", cap=r)
    # numeric check: inside delta |f - L| < eps everywhere sampled, and just outside it fails on some side
    ff = _lam(fe)
    mp.mp.dps = 40
    base, dl, Ln, en = (mp.mpf(str(sp.N(v, 40))) for v in (pt, delta, Lv, ev))
    for i in range(1, 400):
        for s in (1, -1):
            t = dl * mp.mpf(i) / 400
            if abs(ff(base + s * t) - Ln) >= en:
                raise Reject("redraw", "|f - L| reaches epsilon inside delta")
    if not any(abs(ff(base + s * dl * mp.mpf("1.0000001")) - Ln) >= en for s in (1, -1)):
        raise Reject("redraw", "delta is not the largest")
    ans = {"type": "numeric", "latex": L(delta), "sympy": str(delta), "numeric": float(sp.N(delta, 15))}
    steps = [_step("The limit is L = f(a).", f"L = {L(Lv)}", str(Lv)),
             _step("Solve |f(x) - L| = epsilon on each side of a.", ",\\ ".join(f"x = {L(r)}" for r in sorted(set(cands), key=float)[:4])),
             _step("The largest delta is the distance from a to the nearest such point.", f"\\delta = {L(delta)}", str(delta))]
    st = (f"For $\\displaystyle \\lim_{{x \\to {L(pt)}}} {_under(fe)} = {L(Lv)}$ and $\\varepsilon = {L(ev)}$, find the "
          f"largest $\\delta > 0$ such that $0 < \\left|x {_sub(pt)}\\right| < \\delta$ implies "
          f"$\\left|f(x) {_sub(Lv)}\\right| < \\varepsilon$, "
          f"where $f(x) = {L(fe)}$.")
    return _finish("epsilon_delta", fe, f"{pt}|{ev}", st, ans, steps, form, False, axes, f"{form}")


# -- 7. classify discontinuity ------------------------------------------------------------------------------

def _verify_classify(axes, f, a, **_):
    fe = _expr(f, "f", piecewise=True)
    _scope(fe, (sp.Abs, sp.sign))
    pt = _point(a, "a")
    left, right = _checked_side(fe, pt, -1, "left"), _checked_side(fe, pt, 1, "right")
    val = fe.subs(x, pt)
    defined = not val.has(sp.nan, sp.zoo, sp.oo, -sp.oo) and val.is_real is True
    inf = lambda v: v in (sp.oo, -sp.oo)
    if inf(left) or inf(right):
        kind = "infinite"
    elif left != right:
        kind = "jump"
    elif not defined or sp.simplify(val - left) != 0:
        kind = "removable"
    else:
        raise Reject("redraw", "f is continuous at a")
    _check_axes(axes, kind=kind, form=_form(fe))
    word = {"removable": "removable", "jump": "jump", "infinite": "infinite"}[kind]
    ans = {"type": "enum", "latex": f"\\text{{{word}}}", "sympy": word, "numeric": None}
    why = {"removable": "The two one-sided limits are equal and finite, but f(a) is missing or different.",
           "jump": "Both one-sided limits are finite but different.",
           "infinite": "At least one one-sided limit is infinite."}[kind]
    fa = L(val) if defined else "\\text{undefined}"
    steps = [_step("Find the one-sided limits and the value at a.",
                   f"{_lim(fe, pt, -1)} = {_value_answer(left)['latex']},\\ {_lim(fe, pt, 1)} = "
                   f"{_value_answer(right)['latex']},\\ f({L(pt)}) = {fa}"),
             _step(why, ans["latex"], ans["sympy"])]
    st = (f"The function $f(x) = {_show(fe)}$ is discontinuous at $x = {L(pt)}$. Classify the discontinuity as "
          "removable, jump or infinite.")
    return _finish("classify_discontinuity", fe, f"{pt}", st, ans, steps, kind, True, axes, f"{_form(fe)}|{kind}")


# -- 8. make continuous -------------------------------------------------------------------------------------

def _breakpoints(pw: sp.Piecewise) -> list:
    out = set()
    for _, cond in pw.args:
        for rel in cond.atoms(sp.Rel):
            if isinstance(rel, (sp.core.relational.Equality, sp.core.relational.Unequality)):
                raise Reject("redraw", "equality conditions are not used here")
            if rel.lhs == x and rel.rhs.is_number:
                out.add(rel.rhs)
            elif rel.rhs == x and rel.lhs.is_number:
                out.add(rel.lhs)
            else:
                raise Reject("slip", "each condition must compare x with a number")
    return sorted(out, key=float)


def _verify_make_continuous(axes, f, params, **_):
    names = [s.strip() for s in str(params).split(",") if s.strip()]
    if not 1 <= len(names) <= 2 or len(set(names)) != len(names) or any(n == "x" or len(n) != 1 for n in names):
        raise Reject("slip", "params must be one or two distinct single letters other than x, such as k or k,m")
    syms = {n: sp.Symbol(n, real=True) for n in names}
    fe = _expr(f, "f", syms, piecewise=True)
    pws = list(fe.atoms(sp.Piecewise))
    if len(pws) != 1 or fe != pws[0]:
        raise Reject("slip", "f must be a single Piecewise((expr, condition), ...)")
    pw = pws[0]
    P = [syms[n] for n in names]
    if not all(fe.has(p) for p in P):
        raise Reject("slip", "every parameter must appear in f")
    bps = _breakpoints(pw)
    if len(bps) != len(P):
        raise Reject("redraw", f"{len(P)} parameter(s) need {len(P)} breakpoint(s), f has {len(bps)}")
    # each piece must be continuous inside its own interval
    for e, cond in pw.args:
        for r in sp.solve(sp.denom(sp.together(e)), x):
            if r.is_real is True and bool(cond.subs(x, r)):
                raise Reject("redraw", "a piece has a vertical asymptote inside its own interval")
    eqs = []
    for b in bps:
        lft, rgt = side_limit(fe, b, -1), side_limit(fe, b, 1)
        if lft is None or rgt is None or any(v in (sp.oo, -sp.oo) for v in (lft, rgt)):
            raise Reject("redraw", "a one-sided limit at a breakpoint is not finite")
        eqs.append(sp.Eq(lft, rgt))
    sol = sp.solve(eqs, P, dict=True)
    if len(sol) != 1 or set(sol[0]) != set(P):
        raise Reject("redraw", "the parameters are not determined uniquely")
    sol = {k: canon(v) for k, v in sol[0].items()}
    if any(v == 0 for v in sol.values()):
        raise Reject("redraw", "a parameter comes out as 0, so it vanishes from the function")
    for v in sol.values():
        if v.is_real is not True or (r := value_reason(v, True)):
            raise Reject("redraw", f"parameter value is not a short exact form ({r if v.is_real else 'not_real'})")
    # numeric: the continuous function really has equal one-sided limits at every breakpoint
    g = fe.subs(sol)
    for b in bps:
        if not (_agrees(_near(g, b, 1), side_limit(g, b, 1)) and
                sp.simplify(side_limit(g, b, 1) - side_limit(g, b, -1)) == 0):
            raise Reject("redraw", "the solved function is not continuous at a breakpoint")
    pieces = [e for e, _ in pw.args]
    form = ("trig" if any(e.has(sp.sin, sp.cos) for e in pieces) else "exp" if any(e.has(sp.exp) for e in pieces)
            else "hole" if any(not e.is_polynomial(x) for e in pieces) else "poly")
    _check_axes(axes, n_params=len(P), form=form)
    if len(P) == 1:
        v = sol[P[0]]
        ans = {"type": "numeric", "latex": f"{names[0]} = {L(v)}", "sympy": str(v), "numeric": float(sp.N(v, 15))}
    else:
        ans = {"type": "multi_part", "latex": ",\\ ".join(f"{n} = {L(sol[syms[n]])}" for n in names),
               "sympy": "{" + ", ".join(f"{n}: {sol[syms[n]]}" for n in names) + "}", "numeric": None}
    steps = [_step("A piecewise function is continuous where the pieces meet when the one-sided limits agree.",
                   ",\\ ".join(f"{_lim(fe, b, -1)} = {_lim(fe, b, 1)}" for b in bps)),
             _step("Write each side's limit and set them equal.", ",\\ ".join(L(e) for e in eqs)),
             _step("Solve for the parameter" + ("s." if len(P) > 1 else "."), ans["latex"], ans["sympy"])]
    plist = ", ".join(f"${n}$" for n in names)
    st = (f"Find the value{'s' if len(P) > 1 else ''} of {plist} that make{'' if len(P) > 1 else 's'} "
          f"$f(x) = {_show(fe)}$ continuous for all real $x$.")
    return _finish("make_continuous", fe.subs({p: 0 for p in P}) + sum(P), ",".join(names), st, ans, steps, form,
                   False, axes, f"{form}|{len(P)}")


# -- 9. IVT -------------------------------------------------------------------------------------------------

def _verify_ivt(axes, f, lo, hi, **_):
    fe = _expr(f, "f")
    for node in sp.preorder_traversal(fe):
        if isinstance(node, sp.Pow) and not (node.exp.is_Integer and node.exp >= 0):
            raise Reject("redraw", "f must be continuous everywhere: polynomials with exp, sin, cos only")
        if isinstance(node, sp.Function) and not isinstance(node, (sp.exp, sp.sin, sp.cos)):
            raise Reject("redraw", "f must be continuous everywhere: polynomials with exp, sin, cos only")
    a, b = _point(lo, "lo"), _point(hi, "hi")
    if not (a.is_Integer and b.is_Integer and 1 <= b - a <= 6):
        raise Reject("slip", "lo and hi must be integers with 1 <= hi - lo <= 6")
    fa, fb = sp.N(fe.subs(x, a), 40), sp.N(fe.subs(x, b), 40)
    if fa == 0 or fb == 0 or fa * fb > 0:
        raise Reject("redraw", "f must change sign strictly between lo and hi")
    if fe.is_polynomial(x):
        if sp.Poly(fe, x).count_roots(a, b) != 1:
            raise Reject("redraw", "f must have exactly one root in [lo, hi]")
    else:
        d = sp.lambdify(x, sp.diff(fe, x), "math")
        vals = [d(float(a) + float(b - a) * i / 2000) for i in range(2001)]
        pos, neg = sum(v > 1e-9 for v in vals), sum(v < -1e-9 for v in vals)
        if (pos and neg) or pos + neg < 1990:
            raise Reject("redraw", "f must be monotonic on [lo, hi] so the root is unique")
    ff = _lam(fe)
    lo_m, hi_m = mp.mpf(str(a)), mp.mpf(str(b))
    sg = mp.sign(ff(lo_m))
    for _ in range(200):
        mid = (lo_m + hi_m) / 2
        if mp.sign(ff(mid)) == sg:
            lo_m = mid
        else:
            hi_m = mid
    root = (lo_m + hi_m) / 2
    n = int(mp.floor(root))
    if abs(root - round(root)) < mp.mpf(10) ** -6:
        raise Reject("redraw", "the root is an integer; choose f so the root lies strictly between integers")
    vn, vn1 = sp.N(fe.subs(x, n), 40), sp.N(fe.subs(x, n + 1), 40)
    if vn * vn1 >= 0:
        raise Reject("redraw", "the integer interval around the root has no sign change")
    if isinstance(fe, sp.Basic) and fe.is_polynomial(x):
        form = "cubic" if sp.degree(fe, x) == 3 else "quartic" if sp.degree(fe, x) == 4 else "poly"
    else:
        form = "trig" if fe.has(sp.sin, sp.cos) else "exp"
    _check_axes(axes, form=form, width=int(b - a))
    ans = {"type": "interval", "latex": f"({n},\\ {n + 1})", "sympy": f"Interval.open({n}, {n + 1})", "numeric": None}
    fmt = lambda v: L(sp.nsimplify(sp.N(v, 6), rational=True)) if False else f"{float(v):.4g}"
    steps = [_step("f is continuous on every interval, so the Intermediate Value Theorem applies.", ""),
             _step("Evaluate f at the integers.", f"f({n}) \\approx {fmt(vn)},\\ f({n + 1}) \\approx {fmt(vn1)}"),
             _step("f changes sign on this interval, so it has a root in it.", ans["latex"], ans["sympy"])]
    st = (f"Let $f(x) = {L(fe)}$. Use the Intermediate Value Theorem to find the integer $n$ such that $f$ has a root "
          f"in the interval $(n, n + 1)$, given that $f$ has exactly one root between ${L(a)}$ and ${L(b)}$. "
          "Give the interval.")
    return _finish("ivt", fe, f"{a}|{b}", st, ans, steps, form, False, axes, f"{form}|{int(b - a)}")


_VERIFY = {"algebraic": _verify_algebraic, "one_sided": _verify_one_sided, "infinite": _verify_infinite,
           "at_infinity": _verify_at_infinity, "squeeze": _verify_squeeze, "epsilon_delta": _verify_epsilon_delta,
           "classify_discontinuity": _verify_classify, "make_continuous": _verify_make_continuous, "ivt": _verify_ivt}
