"""Trigonometric and hyperbolic integrals: one engine, two function sets.

The model supplies the integrand f(x) as a product of powers of sin, cos, tan, sec (or sinh, cosh, tanh, sech),
or a product sin(ax)cos(bx), or an inverse-hyperbolic form such as 1/sqrt(x^2 + 4). The server classifies it
into a fair family, builds the antiderivative by the family's textbook method, writes the steps, and checks
the derivative. A form outside the families is rejected with the technique it would need.

Families
  sc   sin^m cos^n:      m odd -> u = cos; n odd -> u = sin; both even -> power reduction.
  ts   tan^m sec^n:      n even -> u = tan; m odd -> u = sec; otherwise tan^2 = sec^2 - 1 and the sec reduction.
  prod sin(ax)cos(bx), sin(ax)sin(bx), cos(ax)cos(bx), a != b: product to sum.
  inv  (hyperbolic only) 1/sqrt(x^2 + a^2), 1/sqrt(x^2 - a^2), 1/(a^2 - x^2): the logarithmic form.
Hyperbolic mirrors trig: sinh/cosh with cosh^2 - sinh^2 = 1, tanh/sech with tanh^2 + sech^2 = 1.
"""
import sympy as sp
from sympy.simplify.fu import TR8

from app.shared.integral_core import L, Reject, _parse, x
from app.shared.integral_finish import bound_ext, finish

u = sp.Symbol("u", real=True)
MAX_DEGREE = 8

TRIG = {"s": sp.sin, "c": sp.cos, "t": sp.tan, "e": sp.sec}
HYP = {"s": sp.sinh, "c": sp.cosh, "t": sp.tanh, "e": sp.sech}


def _funcs(hyp: bool) -> dict:
    return HYP if hyp else TRIG


def classify(f, hyp: bool) -> dict | None:
    """{family, k, m, n, c, tech} or None. m is the exponent of sin (tan), n of cos (sec)."""
    F = _funcs(hyp)
    c, rest = f.as_independent(x, as_Add=False)
    if not (c.is_Rational and c != 0):
        return None
    if rest == 1:
        return None
    # inverse-hyperbolic forms (hyperbolic topic only)
    if hyp:
        inv = _classify_inv(c, rest)
        if inv:
            return inv
    parts: dict = {}
    args = set()
    for p in sp.Mul.make_args(rest):
        base, e = p.as_base_exp()
        if not (e.is_Integer and e > 0):
            return None
        for key, fn in F.items():
            if isinstance(base, fn):
                a = base.args[0]
                k = sp.Poly(a, x).coeff_monomial(x) if a.is_polynomial(x) and sp.degree(a, x) == 1 and a.subs(x, 0) == 0 else None
                if k is None or not (k.is_Integer and 0 < k <= 5):
                    return None
                parts[key] = (parts.get(key, (0, k))[0] + int(e), k)
                args.add(int(k))
                break
        else:
            return None
    keys = set(parts)
    if len(args) != 1:
        # two different arguments: product of two plain sin/cos factors, each to the first power
        if keys <= {"s", "c"} and sum(e for e, _ in parts.values()) == 2 and len(rest.args) == 2:
            fs = [p for p in sp.Mul.make_args(rest)]
            a = sorted(int(p.args[0].coeff(x)) for p in fs)
            if a[0] != a[1] and not hyp:
                return {"family": "prod", "k": 1, "m": a[0], "n": a[1], "c": c, "tech": "prod_sum"}
        return None
    k = args.pop()
    deg = sum(e for e, _ in parts.values())
    if deg > MAX_DEGREE:
        return None
    if keys <= {"s", "c"}:
        m, n = parts.get("s", (0, k))[0], parts.get("c", (0, k))[0]
        tech = "u_cos" if m % 2 == 1 else "u_sin" if n % 2 == 1 else "reduce"
        return {"family": "sc", "k": k, "m": m, "n": n, "c": c, "tech": tech}
    if keys <= {"t", "e"}:
        m, n = parts.get("t", (0, k))[0], parts.get("e", (0, k))[0]
        if n % 2 == 0 and n >= 2:
            tech = "u_tan"
        elif m % 2 == 1 and n >= 1:
            tech = "u_sec"
        else:
            tech = "tan_reduce" if n == 0 else "sec_reduce"
        if hyp and tech in ("sec_reduce",):
            return None                 # needs the integral of sech, the Gudermannian: out of scope
        return {"family": "ts", "k": k, "m": m, "n": n, "c": c, "tech": tech}
    return None


def _classify_inv(c, rest):
    """c/sqrt(x^2 + a^2), c/sqrt(x^2 - a^2), c/(a^2 - x^2) with integer a."""
    q = sp.simplify(c / rest)
    num, den = sp.fraction(sp.together(1 / q))
    del num
    if den == 1:
        return None
    # rest = 1/D with D = sqrt(x^2 + s a^2) or (a^2 - x^2)
    D = sp.simplify(1 / rest)
    if D.is_Pow and D.exp == sp.Rational(1, 2) and D.base.is_polynomial(x) and sp.degree(D.base, x) == 2:
        P = sp.Poly(D.base, x)
        if P.coeff_monomial(x) == 0 and P.coeff_monomial(x ** 2) == 1:
            a2 = P.coeff_monomial(1)
            if a2.is_Integer and a2 != 0 and sp.sqrt(a2).is_Integer or (a2.is_Integer and a2 < 0 and sp.sqrt(-a2).is_Integer):
                return {"family": "inv", "k": 1, "m": 0, "n": 0, "c": c, "a2": a2,
                        "tech": "inv_sinh" if a2 > 0 else "inv_cosh"}
    if D.is_polynomial(x) and sp.degree(D, x) == 2:
        P = sp.Poly(D, x)
        if P.coeff_monomial(x) == 0 and P.coeff_monomial(x ** 2) == -1 and P.coeff_monomial(1).is_Integer \
                and P.coeff_monomial(1) > 0 and sp.sqrt(P.coeff_monomial(1)).is_Integer:
            return {"family": "inv", "k": 1, "m": 0, "n": 0, "c": c, "a2": P.coeff_monomial(1), "tech": "inv_tanh"}
    return None


# ---- antiderivatives -----------------------------------------------------------------------------------------

def _poly_int(expr):
    return sp.integrate(sp.expand(expr), u)


def _sec_int(j: int, v):
    """Integral of sec(v)^j dv by the reduction formula (v is the argument)."""
    if j == 0:
        return v
    if j == 1:
        return sp.log(sp.Abs(sp.sec(v) + sp.tan(v)))
    return sp.sec(v) ** (j - 2) * sp.tan(v) / (j - 1) + sp.Rational(j - 2, j - 1) * _sec_int(j - 2, v)


def _tan_int(m: int, v, hyp: bool):
    if m == 0:
        return v
    if m == 1:
        return sp.log(sp.cosh(v)) if hyp else -sp.log(sp.Abs(sp.cos(v)))
    if hyp:
        return -sp.tanh(v) ** (m - 1) / (m - 1) + _tan_int(m - 2, v, hyp)
    return sp.tan(v) ** (m - 1) / (m - 1) - _tan_int(m - 2, v, hyp)


def _reduce_trig(f):
    """Repeated power reduction / product to sum until no trig power above 1 remains."""
    g = sp.expand(TR8(f))
    for _ in range(6):
        h = sp.expand(TR8(g))
        if h == g:
            break
        g = h
    return g


def _reduce_hyp(f):
    """sinh/cosh powers to a sum of cosh(kx), sinh(kx) through exponentials."""
    g = sp.expand(f.rewrite(sp.exp))
    out = sp.Integer(0)
    coeffs: dict = {}
    for t in sp.Add.make_args(g):
        c, rest = t.as_independent(x, as_Add=False)
        if rest == 1:
            coeffs[0] = coeffs.get(0, 0) + c
            continue
        if isinstance(rest, sp.exp):
            k = sp.simplify(rest.args[0] / x)
        else:
            return None
        coeffs[k] = coeffs.get(k, 0) + c
    for k in sorted([k for k in coeffs if k != 0 and k > 0]):
        a, b = coeffs.get(k, 0), coeffs.get(-k, 0)
        out += (a + b) * sp.cosh(k * x) + (a - b) * sp.sinh(k * x)
    for k in coeffs:
        if k < 0 and -k not in coeffs:
            return None
    return sp.expand(out + coeffs.get(0, 0))


def antiderivative(fam: dict, hyp: bool):
    """(F, f_rewritten_or_None, explanation steps) for a classified integrand (constant c included)."""
    F_, c, k, m, n, tech = _funcs(hyp), fam["c"], fam["k"], fam["m"], fam["n"], fam["tech"]
    S, C, T, E = F_["s"], F_["c"], F_["t"], F_["e"]
    v = k * x
    steps: list[dict] = []

    def sub_steps(text_split, ufunc, du_text, inner, back):
        steps.extend([
            {"text": text_split, "latex": None, "sympy": None},
            {"text": "Substitute.", "latex": f"u = {L(ufunc)},\\quad {du_text}", "sympy": str(ufunc)},
            {"text": "Rewrite the integral in terms of u.", "latex": f"\\int {L(sp.expand(inner))}\\,du", "sympy": str(inner)},
        ])

    if fam["family"] == "inv":
        a2 = fam["a2"]
        if tech == "inv_sinh":
            F = c * sp.log(x + sp.sqrt(x ** 2 + a2))
            steps.append({"text": "Use the standard form for 1/sqrt(x^2 + a^2).", "latex": f"{L(F)} + C", "sympy": str(F)})
        elif tech == "inv_cosh":
            F = c * sp.log(sp.Abs(x + sp.sqrt(x ** 2 + a2)))
            steps.append({"text": "Use the standard form for 1/sqrt(x^2 - a^2).", "latex": f"{L(F)} + C", "sympy": str(F)})
        else:
            a = sp.sqrt(a2)
            F = c / (2 * a) * sp.log(sp.Abs((a + x) / (a - x)))
            steps.append({"text": "Use the standard form for 1/(a^2 - x^2).", "latex": f"{L(F)} + C", "sympy": str(F)})
        return F, None, steps
    if fam["family"] == "sc":
        if tech == "u_cos":
            inner = ((1 - u ** 2) if not hyp else (u ** 2 - 1)) ** ((m - 1) // 2) * u ** n
            sign = -1 if not hyp else 1
            ufun = C(v)
            ident = "sin^2 = 1 - cos^2" if not hyp else "sinh^2 = cosh^2 - 1"
            F = sign * _poly_int(inner).subs(u, ufun) / k
            du = (f"du = -{k if k != 1 else ''}\\sin({L(v)})\\,dx" if not hyp else
                  f"du = {k if k != 1 else ''}\\sinh({L(v)})\\,dx")
            sub_steps(f"Split off one {S.__name__}({k if k != 1 else ''}x) and use {ident}.", ufun, du, sign * inner, None)
        elif tech == "u_sin":
            inner = u ** m * ((1 - u ** 2) if not hyp else (1 + u ** 2)) ** ((n - 1) // 2)
            ufun = S(v)
            ident = "cos^2 = 1 - sin^2" if not hyp else "cosh^2 = 1 + sinh^2"
            F = _poly_int(inner).subs(u, ufun) / k
            du = f"du = {k if k != 1 else ''}\\{C.__name__}({L(v)})\\,dx"
            sub_steps(f"Split off one {C.__name__}({k if k != 1 else ''}x) and use {ident}.", ufun, du, inner, None)
        else:  # reduce
            g = _reduce_hyp(S(v) ** m * C(v) ** n) if hyp else _reduce_trig(S(v) ** m * C(v) ** n)
            if g is None:
                raise Reject("redraw", "could not reduce the powers of sinh and cosh")
            F = sp.integrate(g, x)
            steps.append({"text": "Both powers are even: use the power-reduction identities.",
                          "latex": f"{L(S(v) ** m * C(v) ** n)} = {L(g)}", "sympy": str(g)})
        F = sp.expand(c * F)
        steps.append({"text": "Integrate and substitute back.", "latex": f"{L(F)} + C", "sympy": str(F)})
        return F, None, steps
    # ts
    if tech == "u_tan":
        inner = u ** m * ((1 + u ** 2) if not hyp else (1 - u ** 2)) ** ((n - 2) // 2)
        ufun = T(v)
        ident = "sec^2 = 1 + tan^2" if not hyp else "sech^2 = 1 - tanh^2"
        F = _poly_int(inner).subs(u, ufun) / k
        sub_steps(f"Split off {E.__name__}^2 and use {ident}.", ufun,
                  f"du = {k if k != 1 else ''}\\operatorname{{{E.__name__}}}^2({L(v)})\\,dx", inner, None)
    elif tech == "u_sec":
        ufun = E(v)
        if not hyp:
            inner = (u ** 2 - 1) ** ((m - 1) // 2) * u ** (n - 1)
            F = _poly_int(inner).subs(u, ufun) / k
            ident = "tan^2 = sec^2 - 1"
            du = f"du = {k if k != 1 else ''}\\sec({L(v)})\\tan({L(v)})\\,dx"
        else:
            inner = (1 - u ** 2) ** ((m - 1) // 2) * u ** (n - 1)
            F = -_poly_int(inner).subs(u, ufun) / k
            ident = "tanh^2 = 1 - sech^2"
            du = f"du = -{k if k != 1 else ''}\\operatorname{{sech}}({L(v)})\\tanh({L(v)})\\,dx"
        sub_steps(f"Split off {E.__name__}*{T.__name__} and use {ident}.", ufun, du, inner if not hyp else -inner, None)
    elif n == 0:                              # tan^m or tanh^m alone
        F = _tan_int(m, v, hyp) / k
        steps.append({"text": "Use tan^2 = sec^2 - 1 repeatedly (a reduction formula)." if not hyp else
                      "Use tanh^2 = 1 - sech^2 repeatedly (a reduction formula).",
                      "latex": f"{L(F)} + C", "sympy": str(F)})
    else:                                     # tan^even * sec^odd
        j = m // 2
        total = sum(sp.binomial(j, i) * (-1) ** (j - i) * _sec_int(n + 2 * i, v) for i in range(j + 1)) / k
        F = total
        steps.append({"text": "Write tan^2 = sec^2 - 1, expand, and use the reduction formula for each power of sec.",
                      "latex": f"{L(F)} + C", "sympy": str(F)})
    F = c * F
    steps.append({"text": "Integrate and substitute back.", "latex": f"{L(F)} + C", "sympy": str(F)})
    return F, None, steps


def verify(f_s: str, bounds=None, axes: dict | None = None, calculator: str = "none", hyp: bool = False) -> dict:
    try:
        return _verify(f_s, bounds, axes or {}, calculator, hyp)
    except Reject as r:
        return {"ok": False, "cause": r.cause, "reason": r.reason, "cap": r.cap}


def _axes_reason(axes, fam, bounds) -> str | None:
    want = []
    for key in ("family", "m", "n", "tech", "k"):
        if key in axes and str(fam.get(key if key != "tech" else "tech")) != str(axes[key]):
            want.append(f"{key} = {axes[key]} (not {fam.get(key)})")
    if "bounds" in axes:
        kind = "indef" if bounds is None else "def"
        if kind != axes["bounds"]:
            want.append(f"bounds of kind {axes['bounds']}")
    return ("axes: the server assigned " + "; ".join(want)) if want else None


def _verify(f_s, bounds, axes, calculator, hyp):
    f = _parse(f_s, x, "f")
    if hyp and f.has(sp.sin, sp.cos, sp.tan, sp.sec):
        raise Reject("slip", "use sinh, cosh, tanh and sech in this topic")
    if not hyp and f.has(sp.sinh, sp.cosh, sp.tanh, sp.sech):
        raise Reject("slip", "use sin, cos, tan and sec in this topic")
    fam = classify(f, hyp)
    if fam is None:
        raise Reject("redraw", "the integrand is not one of the trigonometric families of this topic "
                     "(powers of sin and cos, powers of tan and sec, or a product of sin and cos of different "
                     "multiples)" if not hyp else
                     "the integrand is not one of the hyperbolic families of this topic")
    if axes and (why := _axes_reason(axes, fam, bounds)):
        raise Reject("redraw", why)
    if fam["family"] == "prod":
        g = sp.expand(TR8(f))
        F = sp.integrate(g, x)
        steps = [{"text": "Rewrite the product as a sum (product-to-sum identity).",
                  "latex": f"{L(f)} = {L(g)}", "sympy": str(g)},
                 {"text": "Integrate term by term.", "latex": f"{L(F)} + C", "sympy": str(F)}]
    else:
        F, _, steps = antiderivative(fam, hyp)
    a_b = None
    if bounds is not None:
        a_b = (bound_ext(bounds[0], "lower bound"), bound_ext(bounds[1], "upper bound"))
    steps = [s if s.get("latex") is not None else {**s, "latex": ""} for s in steps]
    rules = {"u_cos": ["URule"], "u_sin": ["URule"], "u_tan": ["URule"], "u_sec": ["URule"],
             "reduce": ["RewriteRule"], "prod_sum": ["RewriteRule"], "tan_reduce": ["RewriteRule"],
             "sec_reduce": ["RewriteRule", "PartsRule"]}.get(fam["tech"], [])
    extra = {"family": fam["family"], "tech": fam["tech"], "m": fam["m"], "n": fam["n"], "k": fam["k"],
             "rules": rules}
    return finish(f, F, f, steps, a_b, calculator=calculator, allow_improper=False,
                  how="Find an antiderivative.", extra_raw=extra, hyperbolic=hyp, forbid_zero=True)
