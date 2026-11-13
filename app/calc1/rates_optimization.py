"""Calculus methods for the word-problem pipeline (app/shared/wordproblem.py): related rates and optimization.

Both are registered with `register_method` and named by the topic's verifier (`method_module="app.calc1.rates_optimization"`).
The model supplies the structure and the statement; these methods do the calculus, so the answer never depends on the
model's arithmetic.

related_rates   relations: the base relation(s) among the quantities, and their time derivatives written with rate
                symbols. params: one pair per rate symbol, {key: the rate symbol, value: the quantity it is the rate of}.
                A value written "-y" means the symbol is the SPEED OF DECREASE of y (givens cannot be negative). The
                server checks every rate relation is the time derivative of a base relation (up to a constant factor),
                finds each quantity at the instant, and solves for the unknown rate.
optimize        relations: the constraint(s) and the definition of the objective. params: objective (a symbol), goal
                (max or min), choose (the decision variable), and optionally domain ("lo, hi" in the givens). The server
                writes the objective in the decision variable, finds the one critical point in the domain, checks it is
                the global maximum or minimum against the ends of the domain and a grid, and returns the unknown there.
"""
import mpmath as mp
import sympy as sp

from app.shared.clean_answer import canon
from app.shared.integral_core import L
from app.safe_parse import ParseError, safe_parse
from app.shared.wordproblem import Ctx, Derived, fail, register_method

S = sp.S


def _step(text: str, latex: str, sympy_: str | None = None) -> dict:
    return {"text": text, "latex": latex, "sympy": sympy_}


def _eq(expr) -> str:
    return L(sp.Eq(expr, 0))


def _positive_real(v) -> bool:
    return v.is_real is True and v.is_positive is True


# -- related rates -------------------------------------------------------------------------------------------------

def _rates(c: Ctx) -> dict:
    """{rate symbol: (quantity, sign)}: the symbol equals sign * d(quantity)/dt."""
    out = {}
    for key, val in c.params.items():
        sign, name = (-1, val[1:]) if val.startswith("-") else (1, val)
        if key not in c.symbols or name not in c.symbols or key == name:
            raise fail("method", f"params must pair a rate symbol with the quantity it is the rate of ({key}: {val})")
        out[c.symbols[key]] = (c.symbols[name], sign)
    if not out:
        raise fail("method", "related rates needs params: one pair per rate symbol (rate symbol, quantity)")
    return out


def _proportional(rr, d) -> bool:
    """rr is a nonzero constant multiple of d. Symbolic first; when simplification cannot decide (a trigonometric
    identity such as 1/cos^2 = 1 + tan^2), the ratio is compared at several numeric points."""
    ratio = sp.simplify(rr / d)
    if ratio.is_number:
        return ratio != 0
    syms = sorted(rr.free_symbols | d.free_symbols, key=str)
    seen = []
    for k in range(5):
        env = {s: sp.Rational(3 + 2 * i + 5 * k + (i * k) % 7, 13) for i, s in enumerate(syms)}
        try:
            den, num = complex(sp.N(d.subs(env), 30)), complex(sp.N(rr.subs(env), 30))
        except (TypeError, ValueError, ZeroDivisionError):
            return False
        if abs(den) > 1e-9:
            seen.append(num / den)
    return len(seen) >= 3 and abs(seen[0]) > 1e-9 and all(abs(v - seen[0]) < 1e-9 * max(1, abs(seen[0])) for v in seen)


@register_method("related_rates")
def related_rates(c: Ctx) -> Derived:
    rates = _rates(c)
    if c.unknown not in rates:
        raise fail("method", "the unknown of a related rates problem is a rate: name it in params")
    rate_syms = set(rates)
    base = [r for r in c.relations if not (r.free_symbols & rate_syms)]
    rel = [r for r in c.relations if r.free_symbols & rate_syms]
    if not base or not rel:
        raise fail("method", "write the relation among the quantities and its derivative with respect to time")
    deriv = [sum(sp.diff(b, q) * sign * r for r, (q, sign) in rates.items()) for b in base]     # d/dt of each base relation
    for rr in rel:
        if not any(d != 0 and _proportional(rr, d) for d in deriv):
            raise fail("method", "a rate relation must be the derivative with respect to time of a relation among the "
                                 "quantities (check the signs and that every moving quantity has a rate symbol)")
    for q in {q for q, _ in rates.values()}:
        if not any(q in b.free_symbols for b in base):
            raise fail("method", f"{q} has a rate but appears in no relation among the quantities")
    state_free = sorted({q for q, _ in rates.values()} - set(c.givens), key=str)
    given_eqs = [b.subs(c.givens) for b in base]
    state = {}
    if state_free:
        sols = sp.solve(given_eqs, state_free, dict=True)
        sols = [s for s in sols if all(_positive_real(v) for v in s.values() if not v.free_symbols)]
        if len(sols) != 1 or any(k not in sols[0] or sols[0][k].free_symbols for k in state_free):
            raise fail("underdetermined" if not sols or any(k not in s for s in sols for k in state_free)
                       else "not_unique", "the quantities at that instant are not fixed to one positive value by the "
                                          "relations and givens; add a given")
        state = sols[0]
    env = {**c.givens, **state}
    rate_free = sorted(rate_syms - set(c.givens), key=str)
    eqs = [r.subs(env) for r in rel]
    sol = sp.solve(eqs, rate_free, dict=True)
    if len(sol) != 1 or c.unknown not in sol[0] or sol[0][c.unknown].free_symbols:
        raise fail("underdetermined", "the givens do not determine the unknown rate; add a given or a relation")
    solved = sol[0]
    value = canon(solved[c.unknown])
    full = {**state, **{k: canon(v) for k, v in solved.items() if not v.free_symbols}}
    if any(k not in full for k in rate_free):
        raise fail("underdetermined", "every rate must be given or solved")
    steps = [
        _step("Write the relation among the quantities.", ",\\ ".join(_eq(b) for b in base)),
        _step("Differentiate both sides with respect to time t (every moving quantity has a rate).",
              ",\\ ".join(_eq(r) for r in rel)),
    ]
    if state:
        steps.append(_step("Find the other quantities at that instant from the relation.",
                           ",\\ ".join(f"{L(k)} = {L(canon(v))}" for k, v in sorted(state.items(), key=lambda kv: str(kv[0]))),
                           str({str(k): str(v) for k, v in state.items()})))
    steps.append(_step("Substitute the values and solve for the unknown rate.",
                       ",\\ ".join(_eq(e) for e in eqs) + f";\\ {L(c.unknown)} = {L(value)}", str(value)))
    return Derived(value, steps, full, {"n_rates": len(rate_syms), "n_rate_relations": len(rel), "method": "related_rates"})


# -- optimization --------------------------------------------------------------------------------------------------

def _domain(c: Ctx, d: sp.Symbol, exprs: list) -> tuple:
    if "domain" in c.params:
        try:
            lo, hi = (safe_parse(s.strip(), c.symbols).subs(c.givens) for s in c.params["domain"].split(","))
        except (ParseError, ValueError):
            raise fail("parse", "params domain must be 'lo, hi' written with numbers and givens") from None
        if not (lo.is_real and hi.is_real and lo < hi):
            raise fail("method", "the domain must be an interval with lo < hi")
        return lo, hi
    dom = sp.Interval.open(0, sp.oo)
    for e in [d] + exprs:
        try:
            dom = sp.Intersection(dom, sp.solveset(e > 0, d, sp.Reals))
        except (NotImplementedError, ValueError):
            raise fail("method", "the domain could not be found; give params domain") from None
    if not isinstance(dom, sp.Interval):
        raise fail("method", "the quantities are positive on more than one interval; give params domain")
    return dom.start, dom.end


@register_method("optimize")
def optimize(c: Ctx) -> Derived:
    p = c.params
    for k in ("objective", "goal", "choose"):
        if k not in p:
            raise fail("method", f"optimization needs params {k}")
    if p["goal"] not in ("max", "min"):
        raise fail("method", "params goal must be max or min")
    if p["objective"] not in c.symbols or p["choose"] not in c.symbols:
        raise fail("method", "params objective and choose must name variables in the relations")
    obj, d, mx = c.symbols[p["objective"]], c.symbols[p["choose"]], p["goal"] == "max"
    if obj == d or d in c.givens or obj in c.givens:
        raise fail("method", "the objective and the decision variable must be different, and not givens")
    rels = [r.subs(c.givens) for r in c.relations]
    others = sorted({s for r in rels for s in r.free_symbols} - {d}, key=str)
    sols = sp.solve(rels, others, dict=True)
    sols = [s for s in sols if all(v.is_real is not False for v in s.values())]
    if not sols or obj not in sols[0] or any(k not in sols[0] for k in others):
        raise fail("underdetermined", "the relations do not express every quantity in terms of the decision variable")
    if len(sols) > 1:                                          # several branches (a square root): keep the positive ones
        pos = [s for s in sols if all((v.subs(d, 1)).is_positive for v in s.values())]
        sols = pos if len(pos) == 1 else sols
    if len(sols) != 1:
        raise fail("not_unique", "the quantities are not fixed by the decision variable; make the situation fix one")
    sol = sols[0]
    J = sp.simplify(sol[obj])
    lo, hi = _domain(c, d, [sol[k] for k in others if k != obj])
    dJ = sp.diff(J, d)
    try:
        crit = sp.solveset(sp.numer(sp.together(dJ)), d, sp.Interval.open(lo, hi))
    except (NotImplementedError, ValueError):
        raise fail("method", "the critical point could not be found exactly") from None
    if not isinstance(crit, sp.FiniteSet) or len(crit) != 1:
        raise fail("not_unique", "the objective must have exactly one critical point inside the domain")
    d0 = canon(next(iter(crit)))
    j0 = canon(J.subs(d, d0))
    curv = sp.diff(J, d, 2).subs(d, d0)
    if curv == 0 or (curv < 0) != mx:
        raise fail("method", f"the critical point is not a {'maximum' if mx else 'minimum'}")
    for end, side in ((lo, "+"), (hi, "-")):
        lim = sp.limit(J, d, end, side) if end not in (sp.oo, -sp.oo) else sp.limit(J, d, end)
        if not (lim < j0 if mx else lim > j0):
            raise fail("method", "the objective is not extreme at the critical point compared with the ends of the domain")
    a_num, b_num = float(lo), float(hi if hi != sp.oo else max(10 * abs(d0), 10 * float(d0) + 10))
    fl = sp.lambdify(d, J, "mpmath")
    mp.mp.dps = 30
    for i in range(1, 600):
        v = fl(mp.mpf(a_num) + (mp.mpf(b_num) - a_num) * i / 600)
        if isinstance(v, mp.mpc) or v is None:
            continue
        if (v > mp.mpf(str(sp.N(j0, 30))) + mp.mpf(10) ** -12 * max(1, abs(v))) if mx else \
                (v < mp.mpf(str(sp.N(j0, 30))) - mp.mpf(10) ** -12 * max(1, abs(v))):
            raise fail("residual", "a grid of the objective found a better value than the critical point", "redraw")
    full = {d: d0, **{k: canon(sol[k].subs(d, d0)) for k in others}}
    if c.unknown == d:
        value = d0
    elif c.unknown in full:
        value = full[c.unknown]
    else:
        raise fail("method", "the unknown must be the decision variable, the objective or another quantity in the relations")
    value = canon(value)
    steps = [
        _step("Write the quantity to optimize and the constraint(s).", ",\\ ".join(_eq(r) for r in c.relations)),
        _step(f"Express {L(obj)} in terms of {L(d)}.", f"{L(obj)} = {L(J)}", str(J)),
        _step("Set the derivative equal to zero (the critical point inside the domain).", f"{L(dJ)} = 0,\\ {L(d)} = {L(d0)}", str(d0)),
        _step(f"The second derivative is {'negative' if mx else 'positive'} there and the ends of the domain give "
              f"{'smaller' if mx else 'larger'} values, so it is the {'maximum' if mx else 'minimum'}.",
              f"{L(obj)} = {L(j0)}", str(j0)),
        _step(f"Find the quantity asked for, {L(c.unknown)}.", f"{L(c.unknown)} = {L(value)}", str(value)),
    ]
    return Derived(value, steps, full, {"goal": p["goal"], "n_relations": len(c.relations), "method": "optimize"})
