"""Mixed integration strategy: the model names the technique that solves the integral and gives that technique's
structure; the server dispatches to the verifier of that technique, so the answer, the steps and the checks are
the single-technique ones, and records which technique was used.

The level of a strategy problem is the difficulty of RECOGNIZING the technique: the statement never says which
one applies, the worked solution begins by naming it, and a decoy (an integral that looks like it needs another
technique) is what raises the level. The server verifies that the integral is solved by the named technique, and
that no simpler technique in the pool applies: a u-substitution problem is rejected if it is posed under another name only
when the model's structure is wrong; a "decoy" claim itself is a tutor judgment (soft).
"""
from app.calc2 import by_parts, partial_fractions, trig_substitution, trigfam
from app.calc1 import usub
from app.shared.integral_core import Reject

TECHNIQUES = ("u_substitution", "by_parts", "partial_fractions", "trig_integrals", "trig_substitution", "hyperbolic")
NAMES = {
    "u_substitution": "substitution (u-substitution)", "by_parts": "integration by parts",
    "partial_fractions": "partial fractions", "trig_integrals": "a trigonometric-integral identity",
    "trig_substitution": "trigonometric substitution", "hyperbolic": "hyperbolic functions and identities",
}


def verify(technique: str, bounds=None, axes: dict | None = None, calculator: str = "none", **fields) -> dict:
    try:
        return _verify(technique, bounds, axes or {}, calculator, fields)
    except Reject as r:
        return {"ok": False, "cause": r.cause, "reason": r.reason, "cap": r.cap}


def _need(fields, *names):
    miss = [n for n in names if fields.get(n) in (None, "")]
    if miss:
        raise Reject("slip", f"technique fields missing: {', '.join(miss)}")
    return [fields[n] for n in names]


def _verify(technique, bounds, axes, calculator, f):
    if technique not in TECHNIQUES:
        raise Reject("slip", f"technique must be one of {', '.join(TECHNIQUES)}")
    if "technique" in axes and str(axes["technique"]) != technique:
        raise Reject("redraw", f"axes: the server assigned technique = {axes['technique']} (not {technique})")
    if technique == "u_substitution":
        g, R = _need(f, "g", "R")
        res = usub.verify(g, R, bounds, False, None)
    elif technique == "by_parts":
        u, dv = _need(f, "u", "dv")
        res = by_parts.verify(u, dv, f.get("rest"), f.get("g"), bounds, None, calculator)
    elif technique == "partial_fractions":
        (d,) = _need(f, "decomposition")
        res = partial_fractions.verify(d, bounds, None, calculator)
    elif technique in ("trig_integrals", "hyperbolic"):
        (fs,) = _need(f, "f")
        res = trigfam.verify(fs, bounds, None, calculator, technique == "hyperbolic")
    else:
        kind, a, num, p = _need(f, "kind", "a", "num", "p")
        res = trig_substitution.verify(kind, a, num, p, f.get("h"), bounds, None, calculator)
    if not res["ok"]:
        return res
    res["steps"] = [{"text": f"Recognize the technique: this integral is solved by {NAMES[technique]}.",
                     "latex": "", "sympy": None}] + list(res["steps"])
    res["raw"] = {**res["raw"], "technique": technique}
    res["shape"] = f"{technique}|" + res["shape"]
    return res
