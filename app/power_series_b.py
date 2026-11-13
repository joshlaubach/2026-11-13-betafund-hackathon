"""C9 topics taylor_maclaurin, binomial_series, taylor_remainder and euler_formula (dispatched by app/power_series.py)."""
import mpmath as mp
import sympy as sp

from app import power_series_checks as checks
from app.clean_answer import value_reason
from app.integral_core import L, Reject, _bound, _parse, x
from app.sequences_series import _answer, _check_axes, _exact, _finish, _step

DPS = checks.DPS
MAX_ORDER = 8
MAX_SEARCH = 30
_FUNCS = (sp.exp, sp.sin, sp.cos, sp.log, sp.atan)


def _small_int(s, label, lo, hi):
    v = _exact(s, label) if isinstance(s, str) else None
    if v is None or v.is_Integer is not True or not lo <= v <= hi:
        raise Reject("slip", f"{label} must be an integer from {lo} to {hi}")
    return int(v)


def _function(s, label="f"):
    f = _parse(s, x, label)
    if sp.count_ops(f) > 18 or any(not isinstance(g, _FUNCS) for g in f.atoms(sp.Function)):
        raise Reject("redraw", f"{label} is outside the power-series scope whitelist")
    if any(pw.exp.has(x) or (pw.exp.is_Rational is not True and not pw.exp.has(sp.Function)) for pw in f.atoms(sp.Pow)
           if pw.base != sp.E):
        raise Reject("redraw", f"{label} is outside the power-series scope whitelist")
    return f


def _clean(v, what):
    why = value_reason(v, True)
    if why:
        raise Reject("redraw", f"{what} is not a usable short exact value ({why})", why)
    return v


def _center_kind(a):
    if a == 0:
        return "maclaurin"
    if a.is_Rational is True:
        return "rational_center"
    ratio = sp.simplify(a / sp.pi)
    if ratio.is_Rational is True and ratio.q in (2, 3, 4, 6, 1):
        return "pi_center"
    raise Reject("slip", "the center must be a rational number or a rational multiple of pi (denominator 1, 2, 3, 4 or 6)")


# ---- Taylor and Maclaurin series ----------------------------------------------------------------------------------

def _taylor_coefficient(f, a, j):
    v = sp.simplify(sp.diff(f, x, j).subs(x, a) / sp.factorial(j))
    if v.has(sp.zoo, sp.nan, sp.oo, sp.I) or v.is_real is not True:
        raise Reject("redraw", "f is not analytic with real derivatives at the center")
    return v


def _taylor(p, axes, calculator):
    f = _function(p["f"])
    a = _bound(p["a"], "center")
    family = _center_kind(a)
    _taylor_coefficient(f, a, 0)
    ask = str(axes.get("ask", "coeff"))
    if ask not in ("coeff", "poly_value", "terms"):
        raise Reject("slip", "ask must be coeff, poly_value or terms")
    _check_axes(axes, family=family, ask=ask)
    k = _small_int(p["k"], "k", 1, MAX_ORDER)
    shown = L(f)
    where = "Maclaurin series" if family == "maclaurin" else rf"Taylor series about $x={L(a)}$"
    if ask == "coeff":
        value = _taylor_coefficient(f, a, k)
        if value == 0:
            raise Reject("redraw", "the coefficient is zero")
        _clean(value, "the coefficient")
        ok, detail = checks.coefficient_matches(f, a, k, value)
        power = "x" if family == "maclaurin" else rf"(x-{L(a)})"
        statement = rf"Find the coefficient of ${power}^{{{k}}}$ in the {where} of $f(x)={shown}$."
        steps = [_step("The coefficient is the k-th derivative at the center divided by k!.",
                       rf"c_{{{k}}}=\frac{{f^{{({k})}}({L(a)})}}{{{k}!}}"),
                 _step("Differentiate and evaluate.", rf"c_{{{k}}}={L(value)}", value)]
        answer, meta = _answer(value, "converges", calculator), {"kind": "coeff", "k": k, "value": str(value)}
    elif ask == "poly_value":
        x1 = _bound(p.get("x1") or "", "x1") if p.get("x1") else None
        if x1 is None or a.is_Rational is not True or x1.is_Rational is not True or x1 == a:
            raise Reject("slip", "a polynomial-value question needs a rational center and a different rational x1")
        coeffs = [_taylor_coefficient(f, a, j) for j in range(k + 1)]
        value = sp.simplify(sum(c * (x1 - a) ** j for j, c in enumerate(coeffs)))
        _clean(value, "the polynomial value")
        mp.mp.dps = DPS
        numeric = mp.mpf(0)
        for j, c in enumerate(mp.taylor(sp.lambdify(x, f, "mpmath"), mp.mpf(str(sp.N(a, DPS))), k)):
            numeric += c * mp.mpf(str(sp.N(x1 - a, DPS))) ** j
        want = mp.mpf(str(sp.N(value, DPS)))
        ok, detail = bool(abs(numeric - want) <= mp.mpf("1e-12") * max(1, abs(want))), f"numerical Taylor sum {mp.nstr(numeric, 12)} vs {mp.nstr(want, 12)}"
        statement = rf"Let $P_{{{k}}}(x)$ be the degree-{k} Taylor polynomial of $f(x)={shown}$ about $x={L(a)}$. Find $P_{{{k}}}({L(x1)})$."
        steps = [_step("Write the Taylor polynomial.", rf"P_{{{k}}}(x)={L(sum(c * (x - a) ** j for j, c in enumerate(coeffs)))}"),
                 _step("Evaluate at the point.", rf"P_{{{k}}}({L(x1)})={L(value)}", value)]
        answer, meta = _answer(value, "converges", calculator), {"kind": "poly", "k": k, "x1": str(x1), "value": str(value)}
    else:
        found, j = [], 0
        while len(found) < 3 and j <= 14:
            c = _taylor_coefficient(f, a, j)
            if c != 0:
                found.append((j, _clean(c, "a coefficient")))
            j += 1
        if len(found) < 3:
            raise Reject("redraw", "fewer than three nonzero terms up to degree 14")
        expr = sum(c * (x - a) ** j for j, c in found)
        results = [checks.coefficient_matches(f, a, j, c) for j, c in found]
        ok, detail = all(r[0] for r in results), "; ".join(r[1] for r in results)
        statement = rf"Find the first three nonzero terms of the {where} of $f(x)={shown}$."
        steps = [_step("Find the first three nonzero coefficients $f^{(j)}(c)/j!$.", ",\\ ".join(rf"c_{{{j}}}={L(c)}" for j, c in found)),
                 _step("Write the terms.", L(expr))]
        value = None
        answer = {"type": "expression", "latex": L(expr), "sympy": str(expr), "numeric": None}
        meta = {"kind": "terms", "terms": [[j, str(c)] for j, c in found]}
    if not ok:
        raise Reject("redraw", f"independent numerical Taylor check disagrees: {detail}")
    meta |= {"f": str(f), "a": str(a), "ask": ask}
    return _finish("taylor_maclaurin", f, f"{ask}|{a}|{k}|{p.get('x1')}", 0, family, "converges", value, statement,
                   steps, "sympy_derivatives+mpmath_numerical_taylor", detail, {"ask": ask, "check": meta}, calculator, answer)


# ---- binomial series --------------------------------------------------------------------------------------------

def _binomial_parts(base_s):
    base = _parse(base_s, x, "base")
    if not base.is_polynomial(x):
        raise Reject("slip", "base must be a polynomial c + w*x^q")
    c0 = base.subs(x, 0)
    c, e = (base - c0).as_coeff_exponent(x)
    if c0.is_Rational is not True or c0 <= 0 or c.is_Rational is not True or c == 0 or e.is_Integer is not True or not 1 <= e <= 3:
        raise Reject("redraw", "base must be c + w*x^q with c positive rational, w nonzero rational and q from 1 to 3")
    return base, c0, c, int(e)


def _binomial(p, axes, calculator):
    base, c0, w, q = _binomial_parts(p["base"])
    pw = _exact(p["p"], "p")
    if pw.is_Rational is not True or pw.is_Integer or pw.q > 5 or abs(pw) > 5:
        raise Reject("redraw", "p must be a non-integer rational with denominator at most 5 and |p| at most 5")
    family = {2: "half", 3: "third"}.get(int(pw.q), "other")
    ask = str(axes.get("ask", "coeff"))
    if ask not in ("coeff", "radius", "approx"):
        raise Reject("slip", "ask must be coeff, radius or approx")
    _check_axes(axes, family=family, ask=ask)
    f = base ** pw
    shown = L(f)
    u = w / c0 * x ** q
    if ask == "radius":
        value = sp.simplify((c0 / abs(w)) ** sp.Rational(1, q))
        _clean(value, "the radius")
        ok, detail = checks.binomial_radius(pw, w, c0, q, value)
        statement = rf"Find the radius of convergence of the Maclaurin series of $f(x)={shown}$."
        steps = [_step("Factor out the constant to reach the form $(1+u)^p$.", rf"f(x)={L(c0 ** pw)}\left(1+{L(u)}\right)^{{{L(pw)}}}"),
                 _step("The binomial series converges for |u|<1.", rf"R={L(value)}", value)]
        meta = {"kind": "binomial_radius", "value": str(value)}
        k = 0
    elif ask == "coeff":
        k = _small_int(p["k"], "k", 1, 12)
        value = sp.simplify(sp.series(f, x, 0, k + 1).removeO().coeff(x, k))
        if value == 0:
            raise Reject("redraw", "the coefficient is zero")
        if k % q == 0:
            formula = sp.simplify(c0 ** pw * sp.binomial(pw, k // q) * (w / c0) ** (k // q))
            if sp.simplify(formula - value) != 0:
                raise Reject("redraw", "the binomial coefficient formula and SymPy's series disagree")
        _clean(value, "the coefficient")
        ok, detail = checks.coefficient_matches(f, 0, k, value)
        statement = rf"Find the coefficient of $x^{{{k}}}$ in the Maclaurin series of $f(x)={shown}$."
        steps = [_step("Factor out the constant to reach the form $(1+u)^p$.", rf"f(x)={L(c0 ** pw)}\left(1+{L(u)}\right)^{{{L(pw)}}}"),
                 _step("Use $\\binom{p}{j}u^j$ with $x^{k}$ coming from $j=k/q$.", rf"[x^{{{k}}}]={L(value)}", value)]
        meta = {"kind": "coeff", "k": k, "value": str(value)}
    else:
        if c0 != 1:
            raise Reject("redraw", "an approximation question needs a base of the form 1 + w*x^q")
        k = _small_int(p["k"], "k", 2, 5)
        x0 = _exact(p.get("x0"), "x0") if isinstance(p.get("x0"), str) else None
        if x0 is None or x0.is_Rational is not True or x0 == 0 or abs(w * x0 ** q) > sp.Rational(1, 2):
            raise Reject("redraw", "x0 must be a nonzero rational with |w*x0^q| at most 1/2")
        uval = w * x0 ** q
        value = sp.simplify(sum(sp.binomial(pw, j) * uval ** j for j in range(k)))
        _clean(value, "the approximation")
        mp.mp.dps = DPS
        pm, um = mp.mpf(str(sp.N(pw, DPS))), mp.mpf(str(sp.N(uval, DPS)))
        partial = sum(mp.binomial(pm, j) * um ** j for j in range(k))
        full = sum(mp.binomial(pm, j) * um ** j for j in range(120))
        true = (1 + um) ** pm
        want = mp.mpf(str(sp.N(value, DPS)))
        ok = bool(abs(partial - want) <= mp.mpf("1e-25") and abs(full - true) <= mp.mpf("1e-25"))
        detail = f"partial sum {mp.nstr(partial, 12)}, true value {mp.nstr(true, 12)}"
        statement = (rf"Use the first {k} terms of the binomial series of $f(x)={shown}$ to approximate $f\left({L(x0)}\right)$.")
        steps = [_step("Write the first terms of the binomial series.",
                       L(sum(sp.binomial(pw, j) * (w * x ** q) ** j for j in range(k)))),
                 _step("Substitute the point.", L(value), value)]
        meta = {"kind": "approx", "k": k, "x0": str(x0), "value": str(value)}
    if not ok:
        raise Reject("redraw", f"independent binomial check disagrees: {detail}")
    meta |= {"base": str(base), "p": str(pw), "ask": ask}
    return _finish("binomial_series", f, f"{ask}|{pw}|{k}|{p.get('x0')}", 0, family, "converges", value, statement, steps,
                   "binomial_formula+sympy_series+mpmath", detail, {"ask": ask, "check": meta}, calculator,
                   _answer(value, "converges", calculator))


# ---- Taylor remainder (Lagrange error bound) -----------------------------------------------------------------------

def _max_derivative(f, a, x1, order):
    """(M, detail): the exact largest |f^(order)(t)| on [a, x1], required to sit at an endpoint of a monotone |f^(order)|."""
    g = sp.diff(f, x, order)
    ends = [sp.simplify(abs(g.subs(x, e))) for e in (a, x1)]
    if any(v.has(sp.zoo, sp.nan, sp.oo, sp.I) for v in ends):
        raise Reject("redraw", "the derivative is not finite and real on the interval")
    M = ends[0] if sp.simplify(ends[0] - ends[1]) >= 0 else ends[1]
    ok, detail = checks.max_at_endpoint(g, a, x1, M)
    if not ok:
        raise Reject("redraw", f"|f^({order})| is not monotone on the interval, so M is not at an endpoint: {detail}")
    return sp.simplify(M)


def _bound_value(f, a, x1, n):
    M = _max_derivative(f, a, x1, n + 1)
    return sp.simplify(M * abs(x1 - a) ** (n + 1) / sp.factorial(n + 1)), M


def _remainder(p, axes, calculator):
    f = _function(p["f"])
    a, x1 = _bound(p["a"], "a"), _bound(p["x1"], "x1")
    if a == x1:
        raise Reject("slip", "x1 must differ from the center")
    ask = str(axes.get("ask", "bound"))
    if ask not in ("bound", "min_n"):
        raise Reject("slip", "ask must be bound or min_n")
    family = _remainder_family(f)
    _check_axes(axes, family=family, ask=ask)
    shown = L(f)
    theorem = (r"Taylor's inequality gives $|f(x_1)-P_n(x_1)|\le\dfrac{M}{(n+1)!}|x_1-a|^{n+1}$, where $M$ is the largest "
               r"value of $|f^{(n+1)}(t)|$ for $t$ between $a$ and $x_1$.")
    setup = rf"Let $P_n$ be the degree-$n$ Taylor polynomial of $f(x)={shown}$ about $x={L(a)}$. {theorem}"
    if ask == "bound":
        n = _small_int(p["n"], "n", 1, MAX_ORDER)
        value, M = _bound_value(f, a, x1, n)
        _clean(value, "the bound")
        ok, detail = checks.remainder_holds(f, a, x1, n, value)
        statement = rf"{setup} Find this bound for $n={n}$ and $x_1={L(x1)}$."
        steps = [_step("Find the largest value of the next derivative on the interval.", rf"M=\max|f^{{({n + 1})}}(t)|={L(M)}", M),
                 _step("Substitute into the bound.", rf"\frac{{M}}{{{n + 1}!}}|x_1-a|^{{{n + 1}}}={L(value)}", value)]
        meta = {"kind": "bound", "n": n, "value": str(value)}
    else:
        eps = _exact(p.get("eps"), "eps") if isinstance(p.get("eps"), str) else None
        if eps is None or eps.is_Rational is not True or not 0 < eps < 1:
            raise Reject("slip", "eps must be a rational number between 0 and 1")
        values = [_bound_value(f, a, x1, j)[0] for j in range(1, MAX_SEARCH + 1)]
        hits = [j for j, v in enumerate(values, 1) if v <= eps]
        if not hits:
            raise Reject("redraw", "the smallest n is too large to find by hand")
        n = hits[0]
        if n == 1:
            raise Reject("redraw", "the smallest n would be 1")
        if any(values[j] > eps or values[j] > values[j - 1] for j in range(n - 1, len(values))):
            raise Reject("redraw", "the bound is not decreasing from the smallest n")
        value = sp.Integer(n)
        ok, detail = checks.threshold_holds(f, a, x1, n, eps)
        statement = rf"{setup} Find the smallest $n$ for which this bound at $x_1={L(x1)}$ is at most ${L(eps)}$."
        steps = [_step("Compute the bound for successive n.", rf"B({n - 1})={L(values[n - 2])}>{L(eps)}\ge B({n})={L(values[n - 1])}"),
                 _step("The smallest such n is", rf"n={n}", value)]
        meta = {"kind": "min_n", "n": n, "eps": str(eps)}
    if not ok:
        raise Reject("redraw", f"independent remainder check disagrees: {detail}")
    meta |= {"f": str(f), "a": str(a), "x1": str(x1), "ask": ask}
    return _finish("taylor_remainder", f, f"{ask}|{a}|{x1}|{n}|{p.get('eps')}", 0, family, "converges", value, statement,
                   steps, "taylor_inequality+mpmath_grid", detail, {"ask": ask, "check": meta}, calculator,
                   _answer(value, "converges", calculator))


def _remainder_family(f):
    if f.has(sp.exp):
        return "exponential"
    if f.has(sp.sin, sp.cos):
        return "trigonometric"
    return "logarithmic" if f.has(sp.log) else "algebraic"


# ---- Euler's formula --------------------------------------------------------------------------------------------

def _theta(t):
    """The angle t as a rational multiple of pi with denominator 1, 2, 3, 4 or 6."""
    ratio = sp.simplify(t / sp.pi)
    if ratio.is_Rational is not True or ratio.q not in (1, 2, 3, 4, 6) or abs(ratio) > 12 or ratio == 0:
        raise Reject("redraw", "the angle must be a nonzero rational multiple of pi (denominator 1, 2, 3, 4 or 6) with |angle| at most 12*pi")
    return ratio


def _complex_answer(value, calculator):
    re, im = sp.re(value), sp.im(value)
    for part, name in ((re, "real part"), (im, "imaginary part")):
        _clean(part, name)
    value = sp.expand(re + sp.I * im)
    return {"type": "expression", "latex": L(value), "sympy": str(value), "numeric": None}, value


def _euler(p, axes, calculator):
    z = _parse(p["z"].replace("i", "I") if "I" not in p["z"] and p["z"].strip().endswith("i") else p["z"], x, "z", depends=False) \
        if False else _complex_input(p["z"])
    ask = str(axes.get("ask", "exp_value"))
    if ask not in ("exp_value", "complex_exp", "power"):
        raise Reject("slip", "ask must be exp_value, complex_exp or power")
    re, im = sp.re(z), sp.im(z)
    if ask == "power":
        n = _small_int(p.get("n"), "n", 2, 12)
        r = sp.simplify(sp.Abs(z))
        theta = _theta(sp.arg(z))
        value = sp.expand_complex(sp.expand(z ** n))
        family = "gaussian" if re.is_Integer and im.is_Integer else "radical"
        statement = rf"Find $\left({L(z)}\right)^{{{n}}}$ in the form $a+bi$."
        steps = [_step("Write the number in polar form.", rf"{L(z)}={L(r)}e^{{{L(theta)}\pi i}}"),
                 _step("Raise to the power and convert back.", rf"{L(r ** n)}e^{{{L(theta * n)}\pi i}}={L(value)}", value)]
        meta = {"kind": "power", "n": n}
        method = "polar_form+sympy_expand+mpmath_mpc"
    elif ask == "exp_value":
        n = 0
        if re != 0:
            raise Reject("redraw", "an e^(i theta) question needs a purely imaginary exponent")
        theta = _theta(im)
        value = sp.cos(im) + sp.I * sp.sin(im)
        family = {1: "axis", 2: "axis", 3: "sixth", 6: "sixth", 4: "eighth"}[int(theta.q)]
        statement = rf"Find $e^{{{L(z)}}}$ in the form $a+bi$."
        steps = [_step("Apply Euler's formula.", rf"e^{{i\theta}}=\cos\theta+i\sin\theta,\ \theta={L(im)}"),
                 _step("Evaluate the cosine and sine.", L(value), value)]
        meta = {"kind": "exp_value"}
        method = "euler_formula+mpmath_mpc"
    else:
        n = 0
        theta = _theta(im)
        if not (re.is_Rational is True or (isinstance(re, sp.log) and re.args[0].is_Integer and 2 <= re.args[0] <= 9)):
            raise Reject("redraw", "the real part must be a rational number or ln m for an integer m from 2 to 9")
        value = sp.exp(re) * (sp.cos(im) + sp.I * sp.sin(im))
        family = "log_exponent" if isinstance(re, sp.log) else "rational_exponent"
        statement = rf"Find $e^{{{L(z)}}}$ in the form $a+bi$."
        steps = [_step("Split the exponent: $e^{a+bi}=e^a\\left(\\cos b+i\\sin b\\right)$.", rf"e^{{{L(re)}}}\left(\cos {L(im)}+i\sin {L(im)}\right)"),
                 _step("Evaluate.", L(value), value)]
        meta = {"kind": "complex_exp"}
        method = "euler_formula+mpmath_mpc"
    _check_axes(axes, family=family, ask=ask)
    answer, value = _complex_answer(sp.simplify(value) if ask != "power" else value, calculator)
    ok, detail = checks.complex_matches(z, ask, n, value)
    if not ok:
        raise Reject("redraw", f"independent complex evaluation disagrees: {detail}")
    meta |= {"z": str(z), "n": n, "ask": ask, "value": str(value)}
    return _finish("euler_formula", z, f"{ask}|{n}", 0, family, "converges", None, statement, steps, method, detail,
                   {"ask": ask, "check": meta}, calculator, answer)


def _complex_input(s):
    if not isinstance(s, str):
        raise Reject("slip", "z must be a string")
    from app.safe_parse import ParseError, safe_parse
    try:
        z = safe_parse(s)
    except ParseError as err:
        raise Reject("slip", f"z: {err}") from None
    if z.free_symbols or z.has(sp.Float) or not isinstance(z, sp.Expr) or sp.count_ops(z) > 20:
        raise Reject("slip", "z must be an exact constant complex number")
    if z.has(sp.oo, sp.zoo, sp.nan, sp.Sum, sp.Integral, sp.Derivative, sp.Limit):
        raise Reject("slip", "z must be a plain complex number")
    return z


VERIFIERS = {"taylor_maclaurin": _taylor, "binomial_series": _binomial, "taylor_remainder": _remainder,
             "euler_formula": _euler}
