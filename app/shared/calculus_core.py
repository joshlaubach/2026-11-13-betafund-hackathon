"""Helpers shared by the derivative and application verifiers (C2, C3): the result dict, an independent
finite-difference check, and the answer rule for expressions and numbers.

The result has the same shape as every other verifier (statement, answer, steps, hash, shape, raw), so
app/api/pipeline.py and app/shared/difficulty.py treat it identically.
"""
import hashlib

import mpmath as mp
import sympy as sp

from app.shared import function_pool
from app.shared.clean_answer import canon, value_reason
from app.shared.integral_core import L, Reject, _shape, x

CHECK_POINTS = [sp.Rational(n, 10) for n in (3, 7, 13, 19, 24, -6, -14, -22, 31, 45)] + [
    sp.Rational(n, 100) for n in (5, 11, 17, -9, -15)]      # small points keep asin(kx) and acos(kx) in range


def step(text: str, latex: str = "", sympy_: str | None = None) -> dict:
    return {"text": text, "latex": latex, "sympy": sympy_}


def numeric_answer(v, exp_form: bool = False) -> dict:
    """A short exact number. exp_form keeps (e - 1/e)/2 as written: SymPy's canon would turn it back into sinh(1),
    which the answer rule does not know, so the rule is applied to each term instead."""
    if exp_form:
        terms = sp.Add.make_args(sp.expand(v))
        if v.has(sp.zoo, sp.nan, sp.oo, -sp.oo) or len(terms) > 3 or any(value_reason(t, True) for t in terms):
            raise Reject("redraw", "answer is not a short exact form (hyperbolic value)", cap="factor_not_allowed")
        v = sp.expand(v)
        return {"type": "numeric", "latex": L(v), "sympy": str(v), "numeric": float(sp.N(v, 15))}
    v = canon(v)
    if v.is_real is not True or v.has(sp.zoo, sp.nan, sp.oo, -sp.oo):
        raise Reject("redraw", "the value is not a finite real number")
    if why := value_reason(v, True):
        raise Reject("redraw", f"answer is not a short exact form ({why})", cap=why)
    return {"type": "numeric", "latex": L(v), "sympy": str(v), "numeric": float(sp.N(v, 15))}


def expression_answer(e) -> dict:
    return {"type": "expression", "latex": L(e), "sympy": str(e), "numeric": None}


def coefficient_reason(e) -> str | None:
    """The answer rule applied to the numeric coefficient of each additive term of an expression in x."""
    for t in sp.Add.make_args(e):                   # the shown form, not its expansion: 15(3x+1)^4 is fine
        c = t.as_independent(x, as_Add=False)[0]
        c = c.replace(lambda e: isinstance(e, sp.log) and e.args[0].is_Integer, lambda e: e.args[0])   # 1/ln b: b
        if c != 1 and (r := value_reason(c, True)):
            return r
    return None


def fd_agrees(f, d, points=CHECK_POINTS, need: int = 2) -> bool:
    """Is d the derivative of f? Central differences at mpmath precision against d, at points where f is real.
    This is the check that does not use SymPy's differentiation."""
    mp.mp.dps = 40
    fl, dl = sp.lambdify(x, f, "mpmath"), sp.lambdify(x, d, "mpmath")
    good = 0
    for p in points:
        pt = mp.mpf(str(sp.N(p, 30)))
        try:
            vals = [fl(pt + s * mp.mpf(10) ** -8) for s in (-1, 1)] + [fl(pt)]
            if any(isinstance(v, mp.mpc) and abs(v.imag) > 1e-25 for v in vals):
                continue
            ref = mp.diff(lambda t: mp.re(fl(t)), pt)
            got = dl(pt)
            if isinstance(got, mp.mpc):
                if abs(got.imag) > 1e-25:
                    continue
                got = got.real
        except (ValueError, ZeroDivisionError, ArithmeticError, TypeError):
            continue
        if abs(ref - got) > mp.mpf(10) ** -10 * max(1, abs(ref)):
            return False
        good += 1
    return good >= need


def finish(stem: str, f, key: str, statement: str, answer: dict, steps: list, technique: str, axes: dict,
           extra_shape: str = "", exact: bool = True, has_disc: bool = False, raw_extra: dict | None = None) -> dict:
    for k, v in {"technique": technique, **(raw_extra or {})}.items():
        if k in axes and str(axes[k]) != str(v):
            raise Reject("redraw", f"axes: the server assigned {k} = {axes[k]} (this is {v})")
    try:
        value = sp.sympify(answer["sympy"]) if answer.get("sympy") else sp.Integer(0)
    except (sp.SympifyError, SyntaxError, ValueError, TypeError):       # an enum answer such as 'vertical tangent'
        value = sp.Integer(0)
    if not isinstance(value, sp.Expr):
        value = sp.Integer(0)
    raw = {"ops_integrand": int(sp.count_ops(f)), "ops_R": int(sp.count_ops(f)), "ops_F": int(sp.count_ops(value)),
           "g_polynomial": True, "deg_g": None, "n_terms_R": len(sp.Add.make_args(sp.expand(f))), "const_factor": False,
           "definite": False, "has_discontinuity": has_disc, "steps": len(steps), "answer_type": answer["type"],
           "rules": [], "stem": stem, "technique": technique, "complexity": round(function_pool.complexity(f), 2),
           **(raw_extra or {})}
    h = hashlib.sha256((stem + "|" + sp.srepr(f) + "|" + key).encode()).hexdigest()[:16]
    base = str(f) if exact else _shape(f, False)
    return {"ok": True, "statement": statement, "answer": answer, "steps": steps, "method": f"derivative_{stem}",
            "calculator_check": "passed", "hash": h, "shape": f"{base}|{stem}|{extra_shape}|{key}|{answer.get('sympy')}",
            "has_discontinuity": has_disc, "integrand": str(f), "raw": raw, "technique": technique}
