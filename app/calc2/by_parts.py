"""Verify an integration-by-parts candidate and derive everything the student sees.

Runs inside the sandbox worker (see app/worker.py). The model supplies the pair (u, dv) for the first round, an
optional extra term `rest` (the integrand is u*dv + rest, which is how a hidden cancellation is written), an
optional substitution g(x) done before parts (u and dv are then written in the variable u), and optional
bounds. The server applies parts itself, round by round, with a fixed rule for later rounds (LIATE), detects the
cyclic case, checks the derivative, cross-checks definite values numerically and writes every step.

A failed candidate is reported as cause "slip" (the model can fix it from the reason) or "redraw" (a different
recipe is needed).
"""
import sympy as sp

from app.shared.integral_core import L, Reject, _parse, _antiderivative, _derivative_matches, _tidy, x
from app.shared.integral_finish import bound_ext, finish, table_ok

u = sp.Symbol("u", real=True)
MAX_ROUNDS = 4
_LAMBDAS = [sp.Rational(p, q) for q in (1, 2, 3, 4, 5, 9) for p in range(-9, 10) if p and sp.gcd(abs(p), q) == 1]


def verify(u_s: str, dv_s: str, rest: str | None = None, g: str | None = None, bounds: list[str] | None = None,
           axes: dict | None = None, calculator: str = "none") -> dict:
    try:
        return _verify(u_s, dv_s, rest, g, bounds, axes or {}, calculator)
    except Reject as r:
        return {"ok": False, "cause": r.cause, "reason": r.reason, "cap": r.cap}


# ---- families, used by the axes compliance check and by the LIATE choice of later rounds -------------------

def _lin(a, v) -> bool:
    return a.is_polynomial(v) and sp.degree(a, v) == 1


def family(e, v) -> str:
    """A short token for the kind of function e is in v, ignoring constant factors: poly2, exp, sin, cos, tan,
    sec2, csc2, sec, ln, ln2, atan, asin, acos, pow, one, or '*'-joined tokens for a product, else other."""
    _, rest = e.as_independent(v, as_Add=False)
    if rest == 1 or not rest.has(v):
        return "one"
    if rest.is_polynomial(v):
        return f"poly{sp.degree(rest, v)}"
    if isinstance(rest, sp.Mul):
        return "*".join(sorted(family(p, v) for p in rest.args if p.has(v)))
    if rest.is_Pow:
        b, k = rest.as_base_exp()
        if k.is_Rational and b.is_polynomial(v):
            return "pow"
        if isinstance(b, (sp.sec, sp.csc)) and k == 2 and _lin(b.args[0], v):
            return "sec2" if isinstance(b, sp.sec) else "csc2"
        if isinstance(b, sp.log) and k.is_Integer and k > 1 and _lin(b.args[0], v):
            return f"ln{k}"
        if isinstance(b, (sp.sin, sp.cos)) and k.is_Integer and k > 1 and _lin(b.args[0], v):
            return f"{type(b).__name__}{k}"
        if isinstance(b, (sp.atan, sp.asin, sp.acos)) and k.is_Integer and k > 1 and _lin(b.args[0], v):
            return f"{type(b).__name__}{k}"
        if isinstance(b, sp.log) and k == -1 and _lin(b.args[0], v):
            return "ln_recip"
        return "other"
    names = {sp.exp: "exp", sp.sin: "sin", sp.cos: "cos", sp.tan: "tan", sp.sec: "sec", sp.log: "ln",
             sp.atan: "atan", sp.asin: "asin", sp.acos: "acos"}
    for cls, name in names.items():
        if isinstance(rest, cls):
            return name if _lin(rest.args[0], v) else name + "_of_other"
    return "other"


_LIATE = ["L", "I", "A", "T", "E"]


def _liate_class(p, v) -> str:
    if isinstance(p, sp.exp) or (p.is_Pow and p.base == sp.E):
        return "E"
    base = p.as_base_exp()[0]
    if isinstance(base, sp.log):
        return "L"
    if isinstance(base, (sp.atan, sp.asin, sp.acos, sp.acot, sp.asinh, sp.acosh, sp.atanh)):
        return "I"
    if isinstance(base, (sp.sin, sp.cos, sp.tan, sp.sec, sp.csc, sp.cot)):
        return "T"
    return "A"


def _next_pair(w, v, prefer: str | None = None):
    """(U, DV) for the next round. U is the product of the factors in the class the previous round used for u
    (keeping the roles: swapping them undoes the last round), else by LIATE the highest class present."""
    factors = list(sp.Mul.make_args(w))
    consts = [p for p in factors if not p.has(v)]
    live = [p for p in factors if p.has(v)]
    classes = {p: _liate_class(p, v) for p in live}
    best = prefer if prefer in classes.values() else min(classes.values(), key=_LIATE.index)
    U = sp.Mul(*[p for p in live if classes[p] == best])
    DV = sp.Mul(*consts, *[p for p in live if classes[p] != best])
    return U, DV


def _class_of(U, v) -> str:
    live = [p for p in sp.Mul.make_args(U) if p.has(v)]
    return _liate_class(live[0], v) if live else "A"


# ---- the solver ---------------------------------------------------------------------------------------------

def _terms_equal_multiple(g, f, v):
    """(lam, r) with g = lam*f + r and r table-integrable, trying the Pythagorean rewrites a trig power needs;
    None when g is not a multiple of f plus an easy remainder."""
    a = sp.Wild("a")
    variants = [g, sp.expand(g)]
    for pat, rep in ((sp.tan(a) ** 2, sp.sec(a) ** 2 - 1), (sp.cot(a) ** 2, sp.csc(a) ** 2 - 1),
                     (sp.sin(a) ** 2, 1 - sp.cos(a) ** 2), (sp.cos(a) ** 2, 1 - sp.sin(a) ** 2)):
        variants.append(sp.expand(g.replace(pat, rep)))
    for h in variants:
        ratio = sp.simplify(h / f)
        if not ratio.has(v) and ratio != 0:
            return ratio, sp.Integer(0)
        for t in sp.Add.make_args(h):
            ratio = sp.simplify(t / f)
            if not ratio.has(v) and ratio != 0:
                r = sp.expand(h - ratio * f)
                if table_ok(r, v):
                    return ratio, r
    return None


def _solve(first_U, first_DV, rest, v):
    """Parts on f0 = U*DV + rest, round by round. Returns (F in v, rounds, cyclic) where cyclic is None or
    (j, lam, r): the integral of round j reappears with factor lam plus the easy remainder r.

    Round k has the integrand f_k, the pair (U_k, DV_k), P_k = U_k*V_k and the residual
    w_k = rest_k - V_k*dU_k. If w_k is table-only, it ends the chain; if it is lam*f_j + r with r table-only, it
    closes a cycle; otherwise its one hard term becomes f_{k+1} and its easy terms are integrated directly."""
    fs, rounds = [first_U * first_DV], []
    U, DV, extra = first_U, first_DV, rest
    tail = None
    for k in range(MAX_ROUNDS):
        if not table_ok(DV, v):
            raise Reject("redraw", "dv is not a standard integral: it needs a technique outside this topic")
        V = _antiderivative(DV, v)
        dU = sp.diff(U, v)
        P = sp.simplify(U * V)
        w = sp.expand(sp.simplify(extra - V * dU))
        rd = {"U": U, "DV": DV, "V": V, "dU": dU, "P": P, "w": w, "easy": sp.Integer(0)}
        rounds.append(rd)
        if w == 0 or table_ok(w, v):
            tail = ("table", w)
            break
        for j, fj in enumerate(fs):
            hit = _terms_equal_multiple(w, fj, v)
            if hit:
                tail = ("cyclic", j, hit[0], hit[1])
                break
        if tail:
            break
        terms = sp.Add.make_args(w)
        hard = [t for t in terms if not table_ok(t, v)]
        if len(hard) != 1:
            raise Reject("redraw", "the remaining integral needs more than one round of parts on separate terms")
        rd["easy"] = sp.Add(*[t for t in terms if t != hard[0]])
        fs.append(hard[0])
        U, DV = _next_pair(hard[0], v, _class_of(U, v))
        extra = sp.Integer(0)
    else:
        raise Reject("redraw", f"more than {MAX_ROUNDS} rounds of parts are needed")

    def integ(e):
        return _antiderivative(e, v) if e != 0 else sp.Integer(0)

    step = [rd["P"] + integ(rd["easy"]) for rd in rounds]       # P_k plus the easy terms split off at round k
    if tail[0] == "table":
        return sp.Add(*step) + integ(tail[1]), rounds, None
    _, j, lam, r = tail
    if lam == 1:
        raise Reject("redraw", "the cyclic step cancels the integral instead of solving for it")
    Ij = (sp.Add(*step[j:]) + integ(r)) / (1 - lam)
    return sp.Add(*step[:j]) + Ij, rounds, (j, lam, r)


def _steps(rounds, v, cyc, F, back, gx, a, b):
    steps = []
    for n, rd in enumerate(rounds, 1):
        tag = "" if len(rounds) == 1 else f" (round {n})"
        steps += [
            {"text": f"Choose u and dv{tag}.", "latex": f"u = {L(rd['U'])},\\quad dv = {L(rd['DV'])}\\,d{v.name}",
             "sympy": str(rd["U"])},
            {"text": f"Differentiate u and integrate dv{tag}.",
             "latex": f"du = {L(_tidy(rd['dU']))}\\,d{v.name},\\quad v = {L(rd['V'])}", "sympy": str(rd["V"])},
            {"text": f"Apply uv minus the integral of v du{tag}.",
             "latex": f"{L(rd['P'])} - \\int {L(sp.simplify(rd['V'] * rd['dU']))}\\,d{v.name}", "sympy": None},
        ]
    if cyc:
        j, lam, _ = cyc
        steps.append({"text": "The original integral appears again on the right. Solve for it.",
                      "latex": f"(1 - ({L(lam)}))\\,I = \\ldots", "sympy": None})
    steps.append({"text": "Integrate the last term and collect." if not cyc else "Collect the terms.",
                  "latex": f"{L(F)} + C", "sympy": str(F)})
    return steps


# ---- axes ---------------------------------------------------------------------------------------------------

def _axes_reason(axes: dict, u_e, dv_e, rest, v, g, bounds, n_rounds, cyclic) -> str | None:
    """The server assigned the families of u and dv, the number of rounds and the kind of bounds; compare."""
    want = []
    if "u" in axes and family(u_e, v) != axes["u"]:
        want.append(f"u of kind {axes['u']} (not {family(u_e, v)})")
    if "dv" in axes and family(dv_e, v) != axes["dv"]:
        want.append(f"dv of kind {axes['dv']} (not {family(dv_e, v)})")
    if "rounds" in axes and int(axes["rounds"]) != n_rounds:
        want.append(f"{axes['rounds']} rounds of parts (this takes {n_rounds})")
    if "cyclic" in axes and bool(axes["cyclic"]) != cyclic:
        want.append("a cyclic problem" if axes["cyclic"] else "a non-cyclic problem")
    if "sub" in axes and bool(axes["sub"]) != (g is not None):
        want.append("a substitution before parts" if axes["sub"] else "no substitution")
    if "rest" in axes and bool(axes["rest"]) != (rest != 0):
        want.append("an extra term `rest`" if axes["rest"] else "no `rest` term")
    if "bounds" in axes:
        kind = "indef" if bounds is None else "inf" if any(b in (sp.oo, -sp.oo) for b in bounds) else "def"
        if kind != axes["bounds"]:
            want.append(f"bounds of kind {axes['bounds']}")
    return ("axes: the server assigned " + "; ".join(want)) if want else None


# ---- main ---------------------------------------------------------------------------------------------------

def _verify(u_s, dv_s, rest_s, g_s, bounds, axes, calculator):
    sub = g_s is not None and g_s.strip() not in ("", "x")
    v = u if sub else x
    U = _parse(u_s, v, "u")
    DV = _parse(dv_s, v, "dv", depends=False)
    rest = _parse(rest_s, v, "rest", depends=False) if rest_s and rest_s.strip() not in ("", "0") else sp.Integer(0)
    gx = _parse(g_s, x, "g") if sub else None
    if sub and sp.diff(gx, x) == 0:
        raise Reject("slip", "g must not be constant")
    a_b = None
    if bounds is not None:
        a_b = (bound_ext(bounds[0], "lower bound"), bound_ext(bounds[1], "upper bound"))
    if U.is_Number or (U.is_polynomial(v) and sp.degree(U, v) == 0):
        raise Reject("slip", "u must depend on the variable")
    if family(U, v) in ("asin", "acos", "asin2", "acos2") and family(DV, v) != "one":
        raise Reject("redraw", "asin or acos with a power of x leaves a residual integral that needs "
                               "trigonometric substitution; use dv = dx")
    f_var = U * DV + rest
    if sub:
        gp = sp.diff(gx, x)
        f = sp.simplify(f_var.subs(u, gx) * gp)
        shown = f_var.subs(u, gx) * _tidy(gp)
    else:
        f = sp.simplify(f_var)
        shown = f_var
    if not f.has(x) or f.has(sp.zoo, sp.nan, sp.oo):
        raise Reject("redraw", "trivial: the integrand does not depend on x")
    if table_ok(f, x) or (sub and table_ok(f_var, v)):
        raise Reject("redraw", "this integral does not need integration by parts")
    F_v, rounds, cyc = _solve(U, DV, rest, v)
    F = F_v.subs(u, gx) if sub else F_v
    if axes and (why := _axes_reason(axes, U, DV, rest, v, gx, a_b, len(rounds), cyc is not None)):
        raise Reject("redraw", why)
    if sp.count_ops(F) < 40:
        simp = sp.simplify(F)
        if sp.count_ops(simp) <= sp.count_ops(F):
            F = simp
    steps = []
    if sub:
        steps += [
            {"text": "Choose the substitution.", "latex": f"u = {L(gx)}", "sympy": str(gx)},
            {"text": "Differentiate.", "latex": f"du = {L(_tidy(sp.diff(gx, x)))}\\,dx", "sympy": str(sp.diff(gx, x))},
            {"text": "Rewrite the integral in terms of u.", "latex": f"\\int {L(f_var)}\\,du", "sympy": str(f_var)},
        ]
    if rest != 0:
        steps.insert(0, {"text": "Split the integrand and apply parts to one piece; the leftover pieces cancel or are easy.",
                         "latex": f"{L(U * DV)} + \\left({L(rest)}\\right)", "sympy": None})
    steps += _steps(rounds, v, cyc, F_v, sub, gx, None, None)
    if sub:
        steps.append({"text": "Substitute back.", "latex": f"{L(F)} + C", "sympy": str(F)})
    recipe = str(axes.get("recipe", "")) if axes else ""
    if recipe.startswith("hidden"):
        shown = sp.together(f)
    rules = ["PartsRule"] + (["CyclicPartsRule"] if cyc is not None else []) + (["URule"] if sub else [])
    extra = {"rounds": len(rounds), "cyclic": cyc is not None, "substitution": sub, "split": rest != 0, "rules": rules,
             "u_family": family(U, v), "dv_family": family(DV, v)}
    return finish(f, F, shown, steps, a_b, calculator=calculator, allow_improper=True,
                  how="Find an antiderivative by parts.", extra_raw=extra)
