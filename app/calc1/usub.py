"""Verify a u-substitution candidate and derive everything the student sees.

Runs inside the sandbox worker (see app/worker.py). The model supplies only g(x),
R(u) and optional bounds. The integrand R(g(x))*g'(x), the antiderivative, the
statement, the answer and the steps are all computed here, so what is shown is
what was checked.

A failed candidate is reported as cause "slip" (the model can fix it from the
reason) or "redraw" (a different recipe is needed).
"""
import mpmath as mp
import sympy as sp
from sympy.integrals.manualintegrate import integral_steps

from app.shared.clean_answer import canon, expression_reason, value_reason
from app.shared.integral_core import (  # noqa: F401  (re-exported: tests and the other verifiers use these names)
    L, MAX_EXPONENT, Reject, _CHECK_POINTS, _NON_ELEMENTARY, _NOT_PLAIN, _TOL, _antiderivative, _artifact,
    _bound, _crosscheck, _definite, _derivative_matches, _diff, _discontinuities, _diverges, _hash, _parse,
    _same_function, _shape, _tidy, _with_timeout, x)
from app.safe_parse import ParseError, safe_parse

u = sp.Symbol("u", real=True)


def verify(g: str, R: str, bounds: list[str] | None = None, trap: bool = False, axes: dict | None = None) -> dict:
    try:
        return _verify(g, R, bounds, trap, axes)
    except Reject as r:
        return {"ok": False, "cause": r.cause, "reason": r.reason, "cap": r.cap}


ENFORCE_SCOPE = True
_TRIG = (sp.sin, sp.cos, sp.tan, sp.cot, sp.sec, sp.csc)
w = sp.Symbol("w", real=True)


def _linear(e, v) -> bool:
    return e.is_polynomial(v) and sp.degree(e, v) == 1


def _divide(t, v):
    """(quotient, remainder over the denominator) when t is polynomial / polynomial and the numerator has at least
    the degree of the denominator, so polynomial long division applies; otherwise None."""
    n, d = sp.fraction(sp.cancel(sp.together(t)))
    if not (d.has(v) and n.is_polynomial(v) and d.is_polynomial(v)):
        return None
    if sp.degree(d, v) < 1 or sp.degree(n, v) < sp.degree(d, v):
        return None
    q, r = sp.div(n, d, v)
    return q, r / d


def _division_result(Ru):
    """R written as quotient plus remainder, when some term needs polynomial long division; else None."""
    if any(_divide(term.as_independent(u, as_Add=False)[1], u) is not None for term in sp.Add.make_args(sp.expand(Ru))):
        return sp.apart(Ru, u)
    return None


def _term_technique(t, v) -> str | None:
    """None if t (a term without its constant factor) is a standard form for one integration
    step in v, else the technique it would need."""
    if not t.has(v) or t == v:
        return None
    if isinstance(t, (sp.exp, *_TRIG)) and _linear(t.args[0], v):
        return None
    if t.is_Pow:
        base, e = t.as_base_exp()
        if _linear(base, v) and e.is_Number:
            return None
        if isinstance(base, (sp.cos, sp.sin)) and _linear(base.args[0], v) and e == -2:
            return None
        if isinstance(base, (sp.sec, sp.csc)) and _linear(base.args[0], v) and e == 2:
            return None
        if isinstance(base, (sp.sin, sp.cos)) and _linear(base.args[0], v) and e == 2:
            return None
        if isinstance(base, _TRIG):
            return "a trig identity"
        if base.is_polynomial(v) and sp.degree(base, v) == 2:
            a, b, c = (sp.Poly(base, v).coeff_monomial(m) for m in (v**2, v, 1))
            if b == 0 and e == -1 and a * c > 0:
                return None
            if b == 0 and e == -sp.Rational(1, 2) and a < 0 < c:
                return None
            return "trig substitution" if e.is_Rational and not e.is_Integer else "partial fractions"
        if base.is_polynomial(v) and e.is_Integer and e < 0:
            return "partial fractions"
    division = _divide(t, v)
    if division is not None:                    # polynomial long division, then the remainder must be a standard form
        rest = division[1].as_independent(v, as_Add=False)[1]
        return _term_technique(rest, v) if rest.has(v) else None
    parts = [p for p in sp.Mul.make_args(t) if p.has(v)]
    if len(parts) == 2:
        for arg in {p.args[0] for p in t.atoms(*_TRIG) if p.args and _linear(p.args[0], v)}:
            if any(sp.trigsimp(t - m) == 0 for m in (sp.sec(arg) * sp.tan(arg), sp.csc(arg) * sp.cot(arg))):
                return None
    if t.has(sp.log, sp.atan, sp.asin, sp.acos):
        return "integration by parts"
    if parts and all(isinstance(p.as_base_exp()[0], (sp.sin, sp.cos)) for p in parts):
        return "a trig identity"
    if any(isinstance(p, sp.Pow) and p.base.is_polynomial(v) and sp.degree(p.base, v) >= 2
           and p.exp.is_Rational and not p.exp.is_Integer for p in parts):
        return "trig substitution"
    if len(parts) > 1 and any(isinstance(p, (sp.exp, *_TRIG)) and _linear(p.args[0], v) for p in parts):
        return "integration by parts"
    if parts and all(p.is_polynomial(v) or (p.is_Pow and p.base.is_polynomial(v)) for p in parts):
        return "partial fractions"
    return "a non-standard form"


def _scope_reason(expr, v=u) -> str | None:
    for term in sp.Add.make_args(sp.expand(expr)):
        _, rest = term.as_independent(v, as_Add=False)
        if why := _term_technique(rest, v):
            return f"R needs {why}, which is outside this topic"
    return None


def _canon(Ru):
    """R with every additive term factored, so equivalent spellings of one term agree
    (1/(u^2+u), (1/u^2)/(1+1/u) and 1/(u(u+1)) all become 1/(u(u+1))) while the factors stay
    visible. A sum written as separate terms stays separate: 1/u + 1/(1+u^2) is two easy
    integrals and 1/u - 1/(u+1) is what the student sees, not 1/(u^2+u)."""
    terms = []
    for t in sp.Add.make_args(Ru):
        try:
            f = sp.factor(t)
        except (sp.PolynomialError, ValueError, NotImplementedError):
            f = t
        terms.append(t if f.has(sp.nan, sp.zoo, sp.oo) else f)
    return sp.Add(*terms)


def _in_w(q, h):
    """q with h(u) renamed to w, or None if a u is left over."""
    s = q.subs(h, w)
    if s.has(u):
        sols = sp.solve(h - w, u)
        if len(sols) == 1:
            s = s.subs(u, sols[0])
        elif h.is_polynomial(u) and len(sp.Poly(h, u).terms()) <= 2:
            P = sp.Poly(h, u)
            m = P.degree()
            s = s.subs(u**m, (w - P.coeff_monomial(1)) / P.coeff_monomial(u**m))
    s = sp.simplify(s)
    return None if s.has(u) else s


def _shows_derivative(Ru, dh) -> bool:
    """h'(u) is written out as a factor of every term of R (canonical, so factored), so the
    second substitution is visible: u*exp(u^2) shows 2u and 1/(u(1+ln(u)^2)) shows 1/u, but
    1/(u(u+1)) does not show the -1/u^2 that w = 1/u would need."""
    need = dh.as_independent(u, as_Add=False)[1].as_powers_dict()
    for term in sp.Add.make_args(Ru):
        have = term.as_independent(u, as_Add=False)[1].as_powers_dict()
        for b, e in need.items():
            have_e = have.get(b)
            if have_e is None or not (have_e.is_Number and e.is_Number) or have_e * e <= 0 or abs(have_e) < abs(e):
                return False
    return True


def _nested(Ru):
    """(h, S) when R(u) = S(h(u))*h'(u) for a non-linear h and S is a standard form in w."""
    cands = {u**2, sp.sqrt(u), 1 / u, sp.log(u)}
    cands |= set(Ru.atoms(sp.exp, sp.log, *_TRIG)) | {a.args[0] for a in Ru.atoms(sp.exp, sp.log, *_TRIG)}
    cands |= {p.base for p in Ru.atoms(sp.Pow)}
    cands |= {p for p in Ru.atoms(sp.Pow) if p.exp.is_Rational and not p.exp.is_Integer}
    for h in sorted(cands, key=sp.count_ops):
        if not h.has(u) or h == u or _linear(h, u):
            continue
        dh = sp.diff(h, u)
        if not _shows_derivative(Ru, dh):
            continue
        S = _in_w(sp.simplify(Ru / dh), h)
        if S is not None and S.has(w) and _scope_reason(S, w) is None:
            return h, S
    return None


def _convert(inner, src, G, var, a, b, value):
    """(inner(a), inner(b)) when G(var) evaluated between them gives the same value, else None."""
    lo, hi = sp.simplify(inner.subs(src, a)), sp.simplify(inner.subs(src, b))
    try:
        v = G.subs(var, hi) - G.subs(var, lo)
    except (ValueError, TypeError, ZeroDivisionError):
        return None
    if any(e.has(sp.zoo, sp.nan, sp.oo, -sp.oo) for e in (lo, hi, v)):
        return None
    return (lo, hi) if abs(complex(sp.N(v - value, 30))) <= _TOL else None


def _plain_power(e) -> bool:
    rest = e.as_independent(x, as_Add=False)[1]
    base = rest.base if rest.is_Pow else rest
    return base == x or base == sp.Abs(x)


def _collapse_reason(gx, Ru, nested) -> str | None:
    """A problem that is really one easy substitution dressed as two layers."""
    if nested:
        h, _ = nested
        if _linear(gx, x):
            return "a nested R over a linear g is really one substitution"
        if _plain_power(sp.simplify(h.subs(u, gx))):
            return "the second substitution just undoes the first: h(g(x)) is a plain power of x"
        return None
    c, rest = gx.as_independent(x, as_Add=False)
    if rest.is_Pow and rest.exp.is_Number and rest.exp != 1:
        k, phi = rest.base, lambda t: c * t**rest.exp
    elif isinstance(rest, sp.exp):
        k, phi = rest.args[0], lambda t: c * sp.exp(t)
    else:
        return None
    if not k.has(x) or _linear(k, x):
        return None
    S = sp.simplify(Ru.subs(u, phi(w)) * sp.diff(phi(w), w))
    if S.has(w) and _scope_reason(S, w) is None:
        return "g is a power or exponential of k(x) and R stays standard, so u = k(x) alone solves it"
    return None


def _second_substitution(h, S, Hs, ubounds=None, wbounds=None, value=None) -> list[dict]:
    """The worked steps for R(u) = S(h(u))*h'(u): name w, rewrite in w, integrate in w."""
    dh = sp.diff(h, u)
    steps = [
        {"text": "The new integrand needs a second substitution.", "latex": f"w = {L(h)}", "sympy": str(h)},
        {"text": "Differentiate again.", "latex": f"dw = {_diff(dh)}\\,du", "sympy": str(dh)},
    ]
    if wbounds:
        (lo, hi), (wlo, whi) = ubounds, wbounds
        steps += [
            {"text": "Convert the bounds again.", "sympy": None,
             "latex": f"u = {L(lo)} \\Rightarrow w = {L(wlo)},\\quad u = {L(hi)} \\Rightarrow w = {L(whi)}"},
            {"text": "Rewrite the integral in terms of w.", "sympy": str(S),
             "latex": f"\\int_{{{L(wlo)}}}^{{{L(whi)}}} {L(S)}\\,dw"},
            {"text": "Integrate and evaluate.", "sympy": str(value),
             "latex": f"\\left[{L(Hs)}\\right]_{{{L(wlo)}}}^{{{L(whi)}}} = {L(value)}"},
        ]
    else:
        steps += [
            {"text": "Rewrite the integral in terms of w.", "latex": f"\\int {L(S)}\\,dw", "sympy": str(S)},
            {"text": "Integrate.", "latex": f"{L(Hs)} + C", "sympy": str(Hs)},
        ]
    return steps


def _powers(Ru) -> dict | None:
    """{exponent of u: coefficient} when R is a sum of terms c*u^k, otherwise None."""
    out: dict = {}
    for t in sp.Add.make_args(sp.expand(Ru)):
        c, k = t.as_coeff_exponent(u)
        if c.has(u) or not k.is_Rational:
            return None
        out[k] = out.get(k, 0) + c
    return {k: c for k, c in out.items() if c != 0}


_HD_G = {"sin(x)/x": sp.sin(x) / x, "cos(x)/x": sp.cos(x) / x, "exp(x)/x": sp.exp(x) / x, "ln(x)/x": sp.log(x) / x,
         "x/(x^2+1)": x / (x ** 2 + 1), "x*exp(-x)": x * sp.exp(-x), "x^x": x ** x}
_HD_R = {"1": sp.Integer(1), "u": u, "u^2": u ** 2, "u^3": u ** 3, "cos(u)": sp.cos(u), "exp(u)": sp.exp(u)}
_HD_BOUNDS = {"sin(x)/x": (sp.pi / 2, sp.pi), "cos(x)/x": (sp.pi / 2, sp.pi), "exp(x)/x": (1, 2), "ln(x)/x": (1, sp.E),
              "x/(x^2+1)": (0, 1), "x*exp(-x)": (0, 1), "x^x": (1, 2)}
_HD_WHY = {"x^x": "logarithmic differentiation", "x*exp(-x)": "the product rule"}      # every other g: the quotient rule
_LD_G = {"sin(x)": sp.sin(x), "cos(x)": sp.cos(x), "exp(x)": sp.exp(x), "x^2": x ** 2}
_LD_BOUNDS = {"sin(x)": (0, sp.pi / 2), "cos(x)": (0, sp.pi / 2), "exp(x)": (0, sp.log(2)), "x^2": (0, 1)}
_FAMILY_G = {"cos": sp.cos(x), "sin": sp.sin(x), "tan": sp.tan(x), "sec": sp.sec(x)}
_PYTHAGOREAN_BOUNDS = {"cos": (0, sp.pi / 2), "sin": (0, sp.pi / 2), "tan": (0, sp.pi / 4), "sec": (0, sp.pi / 3)}


def _family_R(fam, k, n):
    """R(u) for a Pythagorean-identity problem: sin^(2k+1) cos^n with u = cos, cos^(2k+1) sin^n with u = sin,
    tan^n sec^(2k+2) with u = tan, and tan^(2k+1) sec^n with u = sec."""
    if fam in ("cos", "sin"):
        return (1 - u ** 2) ** k * u ** n
    if fam == "tan":
        return (1 + u ** 2) ** k * u ** n
    return (u ** 2 - 1) ** k * u ** (n - 1)


def _disguise(axes: dict, gx, Ru, plain):
    """The integrand a student is shown when the recipe wants an identity or completing the square first, and
    the worked step that gets back to R(g(x))*g'(x). None for every other recipe."""
    rid = axes["recipe"]
    if rid.startswith("pythagorean_trig"):
        fam, k, n = axes["family"], axes["k"], axes["n"]
        c = sp.simplify(Ru / _family_R(fam, k, n))
        shown = {"cos": -c * sp.sin(x) ** (2 * k + 1) * sp.cos(x) ** n,
                 "sin": c * sp.cos(x) ** (2 * k + 1) * sp.sin(x) ** n,
                 "tan": c * sp.tan(x) ** n * sp.sec(x) ** (2 * k + 2),
                 "sec": c * sp.tan(x) ** (2 * k + 1) * sp.sec(x) ** n}[fam]
        text = {"cos": "Split off one sin(x) and use sin^2(x) = 1 - cos^2(x).",
                "sin": "Split off one cos(x) and use cos^2(x) = 1 - sin^2(x).",
                "tan": "Split off sec^2(x) and use sec^2(x) = 1 + tan^2(x).",
                "sec": "Split off sec(x)tan(x) and use tan^2(x) = sec^2(x) - 1."}[fam]
        rewrite = {"text": text, "latex": f"{L(shown)} = {L(plain)}", "sympy": None}
    elif rid.startswith("hidden_derivative"):
        shown = sp.together(plain)
        how = _HD_WHY.get(axes["g"], "the quotient rule")
        rewrite = {"text": f"Spot the derivative hiding in the integrand ({how}).", "sympy": None,
                   "latex": f"\\frac{{d}}{{dx}}\\left[{L(gx)}\\right] = {L(sp.together(_tidy(sp.diff(gx, x))))}"}
    elif rid.startswith("complete_square"):
        kind, s = axes["kind"], axes["s"]
        if kind == "arctan":
            c, inner = sp.simplify(Ru * (u ** 2 + s ** 2)), gx ** 2 + s ** 2
            shown = c / sp.expand(inner)
        else:
            c, inner = sp.simplify(Ru * sp.sqrt(s ** 2 - u ** 2)), s ** 2 - gx ** 2
            shown = c / sp.sqrt(sp.expand(inner))
        rewrite = {"text": "Complete the square.", "latex": f"{L(sp.expand(inner))} = {L(inner)}", "sympy": None}
    else:
        return None
    if not _same_function(shown, plain):
        raise Reject("redraw", "the rewritten integrand does not match R(g(x)) * g'(x)")
    return shown, rewrite


def _axes_reason(axes: dict, gx, Ru, bounds=None) -> str | None:
    """The server assigned the structure (degree of g, the exponents, the family of g or the outer function).
    Compare it with what the model wrote, exactly, and name the first thing that differs."""
    v, rid = axes, axes["recipe"]
    rat = lambda s: sp.Rational(str(s))
    given = lambda s: safe_parse(s, {"x": x, "u": u})
    poly = lambda n: gx.is_polynomial(x) and sp.degree(gx, x) == n
    same = lambda a, b: sp.simplify(a - b) == 0
    pw = _powers(Ru)
    only = lambda k: pw is not None and set(pw) == {k}
    run = lambda p, j: pw is not None and set(pw) == {p + i for i in range(j + 1)}
    if rid in ("leftover_x_indef", "leftover_x_def"):
        p = rat(v["p"])
        ok = poly(v["n"]) and run(p, v["j"])
        want = f"g a polynomial of degree {v['n']} and R with powers of u from {p} to {p + v['j']}"
        if "a" in v:        # the server also fixed g and the bounds
            ok = ok and same(gx, v["a"] * x ** v["n"] + v["c"]) and bounds is not None and (
                [sp.sympify(b) for b in bounds] == [v["lo"], v["hi"]])
            want = f"g = {v['a']}*x^{v['n']} + ({v['c']}) on [{v['lo']}, {v['hi']}] with R having powers of u from {p} to {p + v['j']}"
    elif rid == "leftover_x_linear":
        p = rat(v["p"])
        ok = poly(1) and run(p, v["m"])
        want = f"g linear with a constant term and R with powers of u from {p} to {p + v['m']}"
    elif rid == "trap_endpoint":
        ok = same(gx, given(v["family"].split(",")[0])) and only(-rat(v["p"]))
        want = f"g = {v['family'].split(',')[0]} and R a single term c*u^({-rat(v['p'])})"
    elif rid == "linear_g":
        a = sp.Poly(gx, x).coeff_monomial(x) if gx.is_polynomial(x) and sp.degree(gx, x) == 1 else 0
        ok = a != 0 and same(Ru * a, given(v["outer"]))
        want = f"g linear and R = ({v['outer']})/a, with a the coefficient of x"
    elif rid in ("poly_power_indef", "poly_power_def"):
        ok = poly(v["deg"]) and only(rat(v["power"]))
        want = f"g a polynomial of degree {v['deg']} and R a single term c*u^({v['power']})"
    elif rid == "poly_trig_exp_indef":
        ratio = sp.simplify(Ru / given(v["outer"])) if Ru != 0 else 0
        ok = poly(v["deg"]) and ratio != 0 and not ratio.has(u)
        want = f"g a polynomial of degree {v['deg']} and R a constant times {v['outer']}"
    elif rid == "trig_inner_power_indef":
        ok = same(gx, given(v["inner"])) and only(rat(v["power"]))
        want = f"g = {v['inner']} and R a single term c*u^({v['power']})"
    elif rid in ("pythagorean_trig_indef", "pythagorean_trig_def"):
        fam, k, n = v["family"], v["k"], v["n"]
        ratio = sp.simplify(Ru / _family_R(fam, k, n))
        ok = same(gx, _FAMILY_G[fam]) and ratio != 0 and not ratio.has(u)
        want = f"g = {fam}(x) and R = c * {_family_R(fam, k, n)}"
        if rid.endswith("_def"):
            lo, hi = _PYTHAGOREAN_BOUNDS[fam]
            ok = ok and bounds is not None and [sp.sympify(b) for b in bounds] == [lo, hi]
            want += f", on [{lo}, {hi}]"
    elif rid in ("hidden_derivative_indef", "hidden_derivative_def"):
        expected = _HD_R[v["R"]]
        ratio = sp.simplify(Ru / expected)
        ok = same(gx, _HD_G[v["g"]]) and ratio != 0 and not ratio.has(u)
        want = f"g = {v['g']} and R = k * {v['R']}"
        if rid.endswith("_def"):
            lo, hi = _HD_BOUNDS[v["g"]]
            ok = ok and bounds is not None and [sp.sympify(b) for b in bounds] == [lo, hi]
            want += f", on [{lo}, {hi}]"
    elif rid in ("long_division_indef", "long_division_def"):
        m, c = v["m"], v["c"]
        numerator = sp.simplify(Ru * (u + c))
        ok = (same(gx, _LD_G[v["g"]]) and numerator.is_polynomial(u) and sp.degree(numerator, u) == m
              and numerator.subs(u, -c) != 0)
        want = f"g = {v['g']} and R = N(u)/(u + {c}) with N a polynomial of degree {m} and N({-c}) not 0"
        if rid.endswith("_def"):
            lo, hi = _LD_BOUNDS[v["g"]]
            ok = ok and bounds is not None and [sp.sympify(b) for b in bounds] == [lo, hi]
            want += f", on [{lo}, {hi}]"
    elif rid in ("complete_square_indef", "complete_square_def"):
        kind, k, s = v["kind"], v["k"], v["s"]
        core = (u ** 2 + s ** 2) if kind == "arctan" else sp.sqrt(s ** 2 - u ** 2)
        ratio = sp.simplify(Ru * core)
        ok = same(gx, x + k) and ratio != 0 and not ratio.has(u)
        want = f"g = x + ({k}) and R = c / ({core})"
        if rid.endswith("_def"):
            ok = ok and bounds is not None and [sp.sympify(b) for b in bounds] == [v["lo"], v["hi"]]
            want += f", on [{v['lo']}, {v['hi']}]"
    else:
        return None
    return None if ok else f"axes: the server assigned {want}"


def _verify(g, R, bounds, trap, axes=None):
    gx = _parse(g, x, "g")
    Ru = _parse(R, u, "R", depends=False)
    if axes and (why := _axes_reason(axes, gx, Ru, bounds)):
        raise Reject("redraw", why)
    gp = sp.diff(gx, x)
    if gp == 0:
        raise Reject("slip", "g must not be constant")
    hidden = bool(axes and str(axes.get("recipe", "")).startswith("hidden_derivative"))
    if any(not p.exp.is_Number and p.has(x) for p in gx.atoms(sp.Pow)) and not hidden:
        raise Reject("redraw", "a variable exponent in g is only used by the hidden-derivative recipes")
    if (not Ru.has(u) and not hidden) or (Ru.is_polynomial(u) and sp.degree(Ru, u) <= 1 and gx.is_polynomial(x)):
        raise Reject("redraw", "trivial: no substitution is needed")
    canonical = _canon(Ru)
    why = _scope_reason(canonical)
    nested = _nested(canonical) if why else None
    if why and not nested and ENFORCE_SCOPE:
        raise Reject("redraw", why)
    if reason := _collapse_reason(gx, Ru, nested):
        raise Reject("redraw", reason)
    definite = bounds is not None
    if trap and not definite:
        raise Reject("redraw", "trap recipes need bounds")
    if definite:
        a, b = _bound(bounds[0], "lower bound"), _bound(bounds[1], "upper bound")
        if not a < b:
            raise Reject("slip", "lower bound must be less than upper bound")

    f = sp.simplify(Ru.subs(u, gx) * gp)
    if not f.has(x) or f.has(sp.zoo, sp.nan, sp.oo):
        raise Reject("redraw", "trivial: the integrand does not depend on x")
    if nested:
        h, S = nested
        Hs = _antiderivative(S, w)
        G = Hs.subs(w, h)
    else:
        G = _antiderivative(Ru, u)
    F = G.subs(u, gx)
    if why := _artifact(f, F):
        raise Reject("redraw", why)
    if not _derivative_matches(F, f):
        raise Reject("redraw", "antiderivative failed the derivative check")

    shown = Ru.subs(u, gx) * _tidy(gp)    # unsimplified, so the student can still see u inside it
    steps = [
        {"text": "Choose the substitution.", "latex": f"u = {L(gx)}", "sympy": str(gx)},
        {"text": "Differentiate.", "latex": f"du = {_diff(_tidy(gp))}\\,dx", "sympy": str(gp)},
    ]
    if axes and (disguise := _disguise(axes, gx, Ru, shown)):
        shown, rewrite = disguise
        steps.insert(0, rewrite)
    divided = _division_result(Ru)
    if not definite:
        if r := expression_reason(F, x):
            raise Reject("redraw", f"answer is not a short exact form ({r})", cap=r)
        steps.append({"text": "Rewrite the integral in terms of u.", "latex": f"\\int {L(Ru)}\\,du", "sympy": str(Ru)})
        if nested:
            steps += _second_substitution(h, S, Hs)
            steps += [
                {"text": "Substitute back to u.", "latex": f"{L(G)} + C", "sympy": str(G)},
                {"text": "Substitute back to x.", "latex": f"{L(F)} + C", "sympy": str(F)},
            ]
        else:
            steps += [
                {"text": "Integrate.", "latex": f"{L(G)} + C", "sympy": str(G)},
                {"text": "Substitute back.", "latex": f"{L(F)} + C", "sympy": str(F)},
            ]
        statement = f"Find $\\displaystyle \\int {L(shown)}\\,dx$."
        answer = {"type": "expression", "latex": f"{L(F)} + C", "sympy": str(F), "numeric": None}
        method, pts, calc = "diff_antiderivative", [], "passed"
    else:
        value, pieces, pts, method = _definite(f, F, a, b, trap)
        statement = f"Evaluate $\\displaystyle \\int_{{{L(a)}}}^{{{L(b)}}} {L(shown)}\\,dx$. Give an exact answer, or state that it diverges."
        if value is not None:
            if r := value_reason(value):
                raise Reject("redraw", f"answer is not a short exact form ({r})", cap=r)
            value = canon(value)
        if nested and (pts or value is None):
            raise Reject("redraw", "a nested substitution needs a proper definite integral")
        if pts:
            steps += _improper_steps(F, pieces, pts, value)
        elif nested:
            ends = _convert(gx, x, G, u, a, b, value)
            wends = _convert(h, u, Hs, w, *ends, value) if ends else None
            if not wends:
                raise Reject("redraw", "the bounds could not be converted through both substitutions")
            (lo, hi), (wlo, whi) = ends, wends
            steps += [
                {"text": "Convert the bounds.", "sympy": None,
                 "latex": f"x = {L(a)} \\Rightarrow u = {L(lo)},\\quad x = {L(b)} \\Rightarrow u = {L(hi)}"},
                {"text": "Rewrite the integral in terms of u.", "sympy": str(Ru),
                 "latex": f"\\int_{{{L(lo)}}}^{{{L(hi)}}} {L(Ru)}\\,du"},
            ]
            steps += _second_substitution(h, S, Hs, (lo, hi), (wlo, whi), value)
        elif ends := _convert(gx, x, G, u, a, b, value):
            lo, hi = ends
            steps += [
                {"text": "Convert the bounds.", "sympy": None,
                 "latex": f"x = {L(a)} \\Rightarrow u = {L(lo)},\\quad x = {L(b)} \\Rightarrow u = {L(hi)}"},
                {"text": "Rewrite the integral in terms of u.", "sympy": str(Ru),
                 "latex": f"\\int_{{{L(lo)}}}^{{{L(hi)}}} {L(Ru)}\\,du"},
                {"text": "Integrate and evaluate.", "sympy": str(value),
                 "latex": f"\\left[{L(G)}\\right]_{{{L(lo)}}}^{{{L(hi)}}} = {L(value)}"},
            ]
        else:
            steps += [
                {"text": "Rewrite the integral in terms of u.", "latex": f"\\int {L(Ru)}\\,du", "sympy": str(Ru)},
                {"text": "Integrate and substitute back.", "latex": f"{L(F)} + C", "sympy": str(F)},
                {"text": "Evaluate between the bounds.",
                 "latex": f"\\left[{L(F)}\\right]_{{{L(a)}}}^{{{L(b)}}} = {L(value)}", "sympy": str(value)},
            ]
        if value is None:
            answer = {"type": "enum", "latex": "\\text{diverges}", "sympy": None, "numeric": None}
            calc = "n/a"
        else:
            answer = {"type": "numeric", "latex": L(value), "sympy": str(value),
                      "numeric": float(sp.N(value))}
            calc = "passed"

    if divided is not None:           # the integral in u needs polynomial long division before it can be integrated
        at = next(i for i, st in enumerate(steps) if st["text"] == "Rewrite the integral in terms of u.")
        steps.insert(at + 1, {"text": "Divide the numerator by the denominator.", "latex": f"{L(Ru)} = {L(divided)}",
                              "sympy": str(divided)})
    raw = _measures(Ru, gx, f, F, steps, definite, bool(pts), answer["type"])
    raw["nested"] = bool(nested)
    return {
        "ok": True, "statement": statement, "answer": answer, "steps": steps, "method": method,
        "calculator_check": calc, "hash": _hash(f, (a, b) if definite else None), "shape": _shape(f, definite),
        "has_discontinuity": bool(pts), "integrand": str(f), "raw": raw,
    }


def _improper_steps(F, pieces, pts, value) -> list[dict]:
    where = ",\\ ".join(f"x = {L(p)}" for p in pts)
    cuts = " + ".join(f"\\int_{{{L(p)}}}^{{{L(q)}}}" for p, q, _ in pieces)
    steps = [
        {"text": "The integrand is undefined inside or at the edge of the interval, so this is an "
                 "improper integral. Split it at each such point.", "latex": f"{where}", "sympy": None},
        {"text": "Write each piece as a limit.", "latex": f"{cuts}", "sympy": None},
        {"text": "Find an antiderivative with u = g(x).", "latex": f"{L(F)} + C", "sympy": str(F)},
    ]
    for p, q, piece in pieces:
        out = "\\text{diverges}" if piece is None else L(piece)
        steps.append({"text": "Evaluate the one-sided limits.", "sympy": None,
                      "latex": f"\\lim_{{x\\to {L(q)}^-}} F(x) - \\lim_{{x\\to {L(p)}^+}} F(x) = {out}"})
    steps.append({"text": "A divergent piece makes the whole integral diverge." if value is None
                  else "Every piece converges, so add them.",
                  "latex": "\\text{diverges}" if value is None else L(canon(value)),
                  "sympy": None if value is None else str(canon(value))})
    return steps


def _rule_names(Ru) -> list[str]:
    def walk(step, out):
        out.add(type(step).__name__)
        for attr in ("substep", "substeps", "alternatives", "v_step", "second_step"):
            sub = getattr(step, attr, None)
            for s in (sub if isinstance(sub, (list, tuple)) else [sub] if sub is not None else []):
                walk(s, out)
    out: set[str] = set()
    walk(integral_steps(Ru, u), out)
    return sorted(out)


def _measures(Ru, gx, f, F, steps, definite, has_disc, answer_type) -> dict:
    c, _ = Ru.as_coeff_Mul()
    poly = gx.is_polynomial(x)
    return {
        "ops_integrand": int(sp.count_ops(f)), "ops_R": int(sp.count_ops(Ru)), "ops_F": int(sp.count_ops(F)),
        "g_polynomial": bool(poly), "deg_g": int(sp.degree(gx, x)) if poly else None,
        "n_terms_R": len(sp.Add.make_args(sp.expand(Ru))), "const_factor": bool(c not in (1, -1)),
        "definite": definite, "has_discontinuity": has_disc, "steps": len(steps),
        "answer_type": answer_type, "rules": _with_timeout(5, lambda: _rule_names(Ru)),
    }
