"""An offline source of by-parts problems: for a recipe and its assigned axes, the payloads a good model reply
would contain, tried in a seeded order until the verifier accepts one.

This is what lets the engine produce a verified problem at any level and calculator tier with no model call (the
calibration lists, the constraint tests and a fallback when no API key is set). The verifier is the same one the
model's replies go through, so nothing here is trusted: an invalid sample is simply skipped.
"""
import itertools
import random
import re

from app import by_parts

_U = {
    "poly1": ["x", "2*x", "3*x", "x+1", "2*x+1", "3*x-1", "-x"],
    "poly2": ["x^2", "x^2+1", "2*x^2", "x^2-x", "x^2+x"],
    "poly3": ["x^3", "x^3+1", "2*x^3"],
    "poly4": ["x^4"],
    "ln": ["ln(x)", "ln(2*x)", "ln(x+1)", "ln(3*x)"],
    "ln2": ["ln(x)^2"],
    "atan": ["atan(x)", "atan(2*x)"],
    "asin": ["asin(x)", "asin(x/2)"],
    "asin2": ["asin(x)^2"],
    "acos2": ["acos(x)^2"],
    "sin": ["sin(x)", "sin(2*x)", "sin(3*x)"],
    "cos": ["cos(x)", "cos(2*x)", "cos(3*x)"],
    "sec": ["sec(x)", "sec(2*x)"],
    "sin2": ["sin(x)^2"],
    "ln_recip": ["1/ln(x)"],
    "sin_of_other": ["sin(ln(x))"],
    "cos_of_other": ["cos(ln(x))"],
    "ln_of_other": ["ln(x+sqrt(1+x^2))", "ln(2*x+sqrt(1+4*x^2))"],
    "exp*poly1": ["x*exp(x)"],
}
_DV = {
    "exp": ["exp(x)", "exp(2*x)", "exp(-x)", "exp(3*x)", "exp(-2*x)"],
    "sin": ["sin(x)", "sin(2*x)", "sin(3*x)"],
    "cos": ["cos(x)", "cos(2*x)", "cos(3*x)"],
    "sec2": ["sec(x)^2", "sec(2*x)^2"],
    "csc2": ["csc(x)^2", "csc(2*x)^2"],
    "pow": ["x^(-2)", "sqrt(x)", "x^(-3)", "x^(-1/2)", "x^(-3/2)"],
    "poly1": ["x", "2*x", "3*x"],
    "poly2": ["x^2", "3*x^2"],
    "poly3": ["x^3", "4*x^3"],
    "one": ["1"],
}
_BOUNDS = {
    "exp": [("0", "1"), ("0", "2"), ("1", "2"), ("0", "oo")],
    "trig": [("0", "pi"), ("0", "pi/2"), ("0", "pi/4"), ("0", "2*pi"), ("pi/4", "pi/2")],
    "ln": [("1", "e"), ("1", "2"), ("1", "4"), ("1", "3"), ("1", "oo"), ("0", "1")],
    "atan": [("0", "1"), ("0", "2")],
    "any": [("0", "1"), ("1", "2"), ("0", "2")],
}


def _bounds_for(u_tok: str, dv_tok: str, kind: str | None) -> list:
    if kind == "inf":
        return [("0", "oo"), ("1", "oo")]
    pool = []
    for tok in (u_tok, dv_tok):
        if tok in ("sin", "cos", "sec", "sec2", "csc2", "sin2", "sin_of_other", "cos_of_other"):
            pool += _BOUNDS["trig"]
        elif tok in ("ln", "ln2", "ln_recip"):
            pool += _BOUNDS["ln"]
        elif tok in ("atan", "asin", "asin2", "acos2", "ln_of_other"):
            pool += _BOUNDS["atan"]
        elif tok == "exp":
            pool += _BOUNDS["exp"]
    pool += _BOUNDS["any"]
    return list(dict.fromkeys(pool))


def _payloads(recipe_id: str, axes: dict, answers: set[str]):
    """Yield (payload, comment) in a fixed order; the caller shuffles."""
    u_tok, dv_tok = axes.get("u"), axes.get("dv")
    kind = axes.get("bounds")
    want_indef = "expression" in answers and kind in (None, "indef")
    want_def = bool(answers & {"numeric", "enum"}) and kind in (None, "def", "inf")

    def with_bounds(base: dict, u_t: str, dv_t: str):
        if want_indef:
            yield {**base, "bounds": None}
        if want_def:
            for lo, hi in _bounds_for(u_t, dv_t, kind):
                yield {**base, "bounds": {"lower": lo, "upper": hi}}

    if recipe_id == "hidden_quotient":
        for k, c in itertools.product((1, 2), (1, 2, 3)):
            a = f"{k}*x+{k * c - 1}" if k * c - 1 else f"{k}*x"
            yield from with_bounds({"u": f"({a})*exp({k}*x)", "dv": f"1/(x+{c})^2", "rest": None, "g": None}, "any", "pow")
        return
    if recipe_id == "exp_f_plus_fprime":
        table = {"ln": ("ln(x)", "exp(x)/x"), "poly2": ("x^2", "2*x*exp(x)")}
        f, extra = table[u_tok]
        yield from with_bounds({"u": f, "dv": "exp(x)", "rest": extra, "g": None}, u_tok, "exp")
        return
    if recipe_id == "log_hidden":
        for n in (1, 2):
            yield from with_bounds({"u": "1/ln(x)", "dv": f"{n}*x^{n - 1}" if n > 1 else "1",
                                    "rest": f"-x^{n - 1}/ln(x)^2" if n > 1 else "-1/ln(x)^2", "g": None}, "ln", "any")
        return
    if recipe_id == "sub_then_parts":
        for gx, gp in (("x^2", 2), ("x^3", 3)):
            for u_e, d in itertools.product(_U[u_tok][:2], _DV[dv_tok][:1]):
                u_u = re.sub(r"\bx\b", "u", u_e)
                dv_u = re.sub(r"\bx\b", "u", d)
                base = {"u": u_u, "dv": f"({dv_u})/{gp}", "rest": None, "g": gx}
                yield from with_bounds(base, "any", dv_tok)
        return
    if recipe_id == "root_sub_parts":
        for d in _DV[dv_tok][:1]:
            base = {"u": "u", "dv": "2*" + re.sub(r"\bx\b", "u", d), "rest": None, "g": "sqrt(x)"}
            for lo, hi in ((("0", "pi^2") if dv_tok != "exp" else ("0", "1")),):
                yield {**base, "bounds": {"lower": lo, "upper": hi}} if want_def else {**base, "bounds": None}
            if want_indef:
                yield {**base, "bounds": None}
        return
    if recipe_id == "improper_log":
        for p in ("x^(-2)", "x^(-3)", "x^(-3/2)", "x", "x^2", "1", "x^(-1/2)", "x^3"):
            for lo, hi in (("1", "oo"), ("0", "1")):
                yield {"u": "ln(x)", "dv": p, "rest": None, "g": None, "bounds": {"lower": lo, "upper": hi}}
        return
    if recipe_id == "improper_exp_poly":
        for u_e, k in itertools.product(_U[u_tok], ("1", "2")):
            yield {"u": u_e, "dv": f"exp(-{k}*x)", "rest": None, "g": None, "bounds": {"lower": "0", "upper": "oo"}}
        return
    # the ordinary case: a u and a dv of the assigned kinds, with the constants the recipe text asks for
    u_pool, dv_pool = _U[u_tok], _DV.get(dv_tok, ["1"]) if dv_tok else ["1"]
    if recipe_id == "affine_exp":
        u_pool = ["2*x+1", "3*x-1", "2*x-1", "3*x+2", "2*x+3"]
    elif recipe_id == "cyclic_basic":
        u_pool = [u for u in u_pool if u.endswith("(x)") or u.endswith("(2*x)")]
        dv_pool = ["exp(x)", "exp(-x)"]
    elif recipe_id == "cyclic_const":
        u_pool = [u for u in u_pool if u.endswith("(2*x)") or u.endswith("(3*x)")]
        dv_pool = ["exp(2*x)", "exp(3*x)", "exp(-2*x)", "exp(-x)"]
    for u_e, d in itertools.product(u_pool, dv_pool):
        yield from with_bounds({"u": u_e, "dv": d, "rest": None, "g": None}, u_tok, dv_tok or "one")


def generate(recipe: dict, axes: dict, answers: set[str], calculator: str = "none", seed: int = 0,
             limit: int = 400) -> dict | None:
    """The first verified problem for this recipe's axes, trying the candidate replies in a seeded order.
    Returns {"payload", "result"} or None when none of the candidates passes."""
    rng = random.Random(seed)
    cands = list(_payloads(recipe["id"], axes, answers))
    rng.shuffle(cands)
    full = {"recipe": recipe["id"], **axes}
    for payload in cands[:limit]:
        b = payload["bounds"]
        r = by_parts.verify(payload["u"], payload["dv"], payload.get("rest"), payload.get("g"),
                            [b["lower"], b["upper"]] if b else None, full, calculator)
        if r["ok"] and r["answer"]["type"] in answers:
            return {"payload": payload, "result": r}
    return None
