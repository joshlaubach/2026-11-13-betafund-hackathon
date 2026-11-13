"""Offline source of trigonometric and hyperbolic problems: for a recipe and its assigned axes (family, m, n, k,
tech), the replies a good model would give, tried in a seeded order until the verifier accepts one (see
app/calc2/by_parts_samples.py for the same idea)."""
import itertools
import random

from app.calc2 import trigfam

_NAMES = {False: {"s": "sin", "c": "cos", "t": "tan", "e": "sec"},
          True: {"s": "sinh", "c": "cosh", "t": "tanh", "e": "sech"}}
_TRIG_BOUNDS = [("0", "pi/2"), ("0", "pi"), ("0", "pi/4"), ("0", "pi/3"), ("0", "pi/6"), ("0", "2*pi")]
_HYP_BOUNDS = [("0", "ln(2)"), ("0", "ln(3)"), ("0", "1"), ("0", "2*ln(2)")]


def _bounds(k: int, hyp: bool, kind: str | None):
    if hyp:
        return _HYP_BOUNDS
    out = []
    for lo, hi in _TRIG_BOUNDS:
        out.append((lo, hi if k == 1 else f"({hi})/{k}"))
    return out


def _arg(k: int) -> str:
    return "x" if k == 1 else f"{k}*x"


def _payloads(axes: dict, answers: set[str], hyp: bool):
    nm = _NAMES[hyp]
    fam = axes.get("family")
    k_list = [axes["k"]] if "k" in axes else [1]
    want_indef = "expression" in answers and axes.get("bounds") in (None, "indef")
    want_def = bool(answers & {"numeric", "enum"}) and axes.get("bounds") in (None, "def")

    def emit(f, k):
        if want_indef:
            yield {"f": f, "bounds": None}
        if want_def:
            for lo, hi in _bounds(k, hyp, None):
                yield {"f": f, "bounds": {"lower": lo, "upper": hi}}

    m_list = [axes["m"]] if "m" in axes else [0, 1, 2, 3, 4]
    n_list = [axes["n"]] if "n" in axes else [0, 1, 2, 3, 4]
    for k, m, n, c in itertools.product(k_list, m_list, n_list, (1, 2, 3)):
        if fam == "sc":
            a = _arg(k)
            parts = []
            if m:
                parts.append(f"{nm['s']}({a})^{m}" if m > 1 else f"{nm['s']}({a})")
            if n:
                parts.append(f"{nm['c']}({a})^{n}" if n > 1 else f"{nm['c']}({a})")
            if not parts:
                continue
            f = "*".join(parts)
        elif fam == "ts":
            a = _arg(k)
            parts = []
            if m:
                parts.append(f"{nm['t']}({a})^{m}" if m > 1 else f"{nm['t']}({a})")
            if n:
                parts.append(f"{nm['e']}({a})^{n}" if n > 1 else f"{nm['e']}({a})")
            if not parts:
                continue
            f = "*".join(parts)
        elif fam == "prod":
            if m >= n or m < 1:
                continue
            for p, q in (("sin", "cos"), ("cos", "sin"), ("sin", "sin"), ("cos", "cos")):
                f = f"{p}({m}*x)*{q}({n}*x)"
                yield from emit(f if c == 1 else f"{c}*{f}", 1)
            continue
        elif fam == "inv":
            a = n or 1
            t = axes.get("tech")
            f = {"inv_sinh": f"1/sqrt(x^2+{a * a})", "inv_cosh": f"1/sqrt(x^2-{a * a})",
                 "inv_tanh": f"1/({a * a}-x^2)"}[t]
            if t == "inv_cosh":
                if want_indef:
                    yield {"f": f if c == 1 else f"{c}*{f}", "bounds": None}
                if want_def:
                    yield {"f": f if c == 1 else f"{c}*{f}", "bounds": {"lower": str(a + 1), "upper": str(2 * a + 2)}}
                continue
            yield from emit(f if c == 1 else f"{c}*{f}", 1) if t == "inv_sinh" else _inv_tanh(f, c, a, want_indef, want_def)
            continue
        else:
            continue
        yield from emit(f if c == 1 else f"{c}*{f}", k)


def _inv_tanh(f, c, a, want_indef, want_def):
    g = f if c == 1 else f"{c}*{f}"
    if want_indef:
        yield {"f": g, "bounds": None}
    if want_def:
        yield {"f": g, "bounds": {"lower": "0", "upper": str(max(a - 1, 1)) if a > 1 else "1/2"}}


def generate(recipe: dict, axes: dict, answers: set[str], calculator: str = "none", seed: int = 0,
             limit: int = 300, hyp: bool = False) -> dict | None:
    rng = random.Random(seed)
    cands = list(_payloads(axes, answers, hyp))
    rng.shuffle(cands)
    full = {"recipe": recipe["id"], **axes}
    for payload in cands[:limit]:
        b = payload["bounds"]
        r = trigfam.verify(payload["f"], [b["lower"], b["upper"]] if b else None, full, calculator, hyp)
        if r["ok"] and r["answer"]["type"] in answers:
            return {"payload": payload, "result": r}
    return None
