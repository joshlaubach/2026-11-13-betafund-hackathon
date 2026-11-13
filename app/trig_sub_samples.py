"""Offline source of trigonometric-substitution problems built from the assigned axes (kind, a, p, degree of the
numerator, shift h), tried through the same verifier a model reply goes through."""
import itertools
import random

from app import trig_substitution

_NUM = {0: "1", 1: "x", 2: "x^2", 3: "x^3", 4: "x^4"}
_TRIPLES = {3: [5], 4: [5], 5: [13], 1: [], 2: []}      # x with a rational sqrt(x^2 - a^2)


def _bounds(kind: str, a: int, h: int):
    out = []
    if kind == "a2-x2":
        out += [("0", "1") if a > 1 else ("0", "1/2"), ("0", str(a)) if h == 0 and False else ("0", f"{a}/2"),
                ("0", "1/2") if a >= 1 else ("0", "0")]
        out += [("0", f"{a}/2"), ("0", "1"), ("-1", "1")]
        out = [b for b in out if True]
    elif kind == "a2+x2":
        out += [("0", "1"), ("0", str(a)), ("0", "2"), ("0", "4"), ("1", "2"), ("0", "3")]
        if a == 3:
            out.append(("0", "4"))
    else:
        for x in _TRIPLES.get(a, []):
            out.append((str(a), str(x)))
        out += [(str(a + 1), str(a + 2)), (str(2 * a), str(3 * a)), (str(a + 1), str(2 * a + 2))]
    if h:
        out = [(f"{int(lo.split('/')[0]) - h}" if lo.isdigit() else lo, hi) for lo, hi in out]
    return list(dict.fromkeys(out))


def _axes_choices(axes: dict, rng):
    kinds = [axes["kind"]] if "kind" in axes else ["a2-x2", "a2+x2", "x2-a2"]
    ps = [axes["p"]] if "p" in axes else [-1, -3, 1, 3]
    degs = [axes["num_deg"]] if "num_deg" in axes else [0, 2]
    hs = [axes["h"]] if "h" in axes else [0]
    a_s = [axes["a"]] if "a" in axes else [1, 2, 3, 4]
    combos = list(itertools.product(kinds, a_s, degs, ps, hs))
    rng.shuffle(combos)
    return combos


def generate(recipe: dict, axes: dict, answers: set[str], calculator: str = "none", seed: int = 0,
             limit: int = 120) -> dict | None:
    rng = random.Random(seed)
    full = {"recipe": recipe["id"], **axes}
    tries = 0
    for kind, a, deg, p, h in _axes_choices(axes, rng):
        opts = []
        if "expression" in answers:
            opts.append(None)
        if answers & {"numeric", "enum"}:
            opts += [list(b) for b in _bounds(kind, a, h)]
        for b in opts:
            tries += 1
            if tries > limit:
                return None
            r = trig_substitution.verify(kind, str(a), _NUM[deg], str(p), str(h) if h else None, b, full, calculator)
            if r["ok"] and r["answer"]["type"] in answers:
                return {"payload": {"kind": kind, "a": str(a), "num": _NUM[deg], "p": str(p),
                                    "h": str(h) if h else None,
                                    "bounds": {"lower": b[0], "upper": b[1]} if b else None}, "result": r}
    return None
