"""Offline source of partial-fractions problems: a decomposition built from the assigned axes (how many linear
factors, the highest repeat, an irreducible quadratic and its power, a polynomial part), tried through the same
verifier a model reply goes through."""
import random

from app import partial_fractions

_QUADS = ["x^2+1", "x^2+4", "x^2+2*x+2", "x^2+x+1", "x^2-2*x+5", "x^2+9"]


def _lin(r: int) -> str:
    return "x" if r == 0 else f"(x-{r})" if r > 0 else f"(x+{-r})"


def _coef(rng, allow_one=True) -> int:
    return rng.choice([1, 2, 3, -1, -2, -3] if allow_one else [2, 3, -2, -3])


def _build(axes: dict, rng: random.Random) -> str:
    n_lin = int(axes.get("linear", rng.choice([1, 2, 3])))
    repeat = int(axes.get("repeat", 1))
    quad = axes.get("quad", False)
    qpow = int(axes.get("qpow", 1)) if quad else 0
    improper = axes.get("improper", False)
    roots = rng.sample(range(-3, 4), n_lin)
    parts = []
    for i, r in enumerate(roots):
        top = repeat if i == 0 else 1
        for p in range(1, top + 1):
            c = _coef(rng)
            parts.append(f"{c}/{_lin(r)}" + (f"^{p}" if p > 1 else ""))
    if quad:
        q = rng.choice(_QUADS)
        for p in range(1, qpow + 1):
            b, c = _coef(rng), rng.choice([0, 1, 2, -1, 1])
            num = f"{b}*x" + (f"+{c}" if c > 0 else f"{c}" if c < 0 else "")
            parts.append(f"({num})/({q})" + (f"^{p}" if p > 1 else ""))
    if improper:
        a, b = rng.choice([1, 2]), rng.choice([0, 1, -1, 2])
        parts.insert(0, f"{a}*x" + (f"+{b}" if b > 0 else f"{b}" if b < 0 else ""))
    return " + ".join(parts).replace("+ -", "- ").replace("+-", "-")


def _bounds(rng, answers):
    return [None] if "expression" in answers and not answers & {"numeric"} else [
        None, ["4", "6"], ["5", "7"], ["2", "3"], ["0", "1"], ["1", "2"], ["-1", "1"], ["4", "5"]]


def generate(recipe: dict, axes: dict, answers: set[str], calculator: str = "none", seed: int = 0,
             limit: int = 150) -> dict | None:
    rng = random.Random(seed)
    full = {"recipe": recipe["id"], **axes}
    want_indef = "expression" in answers
    want_def = bool(answers & {"numeric", "enum"})
    for _ in range(limit):
        d = _build(axes, rng)
        opts = []
        if want_indef:
            opts.append(None)
        if want_def:
            opts += [["4", "6"], ["5", "7"], ["2", "3"], ["0", "1"], ["-1", "1"], ["4", "5"]]
        rng.shuffle(opts)
        for b in opts[:3]:
            r = partial_fractions.verify(d, b, full, calculator)
            if r["ok"] and r["answer"]["type"] in answers:
                return {"payload": {"decomposition": d, "bounds": {"lower": b[0], "upper": b[1]} if b else None},
                        "result": r}
    return None
