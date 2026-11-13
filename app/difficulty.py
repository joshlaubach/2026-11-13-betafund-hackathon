"""Provisional difficulty score from the raw measures the verifier returns.

Five axes in [0, 1], a weighted sum, and bin edges that turn the score into a
level 1-5. Everything here is a guess (VERSION "v0"); nothing gates on it. Phase 3
refits the weights against human ratings. Because the raw measures are stored on
every attempt, a better function can re-level old problems.
"""
from bisect import bisect_right

VERSION = "v0"
DEFAULT_WEIGHTS = {"seeing_the_move": 0.30, "algebra_mess": 0.20, "steps": 0.15,
                   "combined_techniques": 0.25, "error_traps": 0.10}
DEFAULT_BINS = [0.2, 0.4, 0.6, 0.8]

# SymPy manualintegrate rules that mean "another technique beyond a plain table integral".
_EXTRA_TECHNIQUE = {"PartsRule", "CyclicPartsRule", "TrigSubstitutionRule", "RewriteRule",
                    "SqrtQuadraticRule", "SqrtQuadraticDenomRule", "ReciprocalSqrtQuadraticRule"}


def _clip(v: float) -> float:
    return max(0.0, min(1.0, v))


def axes(raw: dict) -> dict[str, float]:
    seeing = 0.8 if raw["n_terms_R"] > 1 else 0.4 if raw["const_factor"] else 0.0
    seeing += 0.2 if not raw["g_polynomial"] else 0.0
    extra = len(_EXTRA_TECHNIQUE & set(raw["rules"] or []))
    traps = raw["definite"] + raw["const_factor"] + 2 * raw["has_discontinuity"]
    return {
        "seeing_the_move": _clip(seeing),
        "algebra_mess": _clip((raw["ops_integrand"] + raw["ops_F"]) / 50),
        "steps": _clip((raw["steps"] - 3) / 5),
        "combined_techniques": _clip(extra / 2),
        "error_traps": _clip(traps / 3),
    }


def features(raw: dict, weights: dict[str, float] | None = None,
             bins: list[float] | None = None) -> dict:
    a = axes(raw)
    w = weights if weights and set(weights) == set(a) else DEFAULT_WEIGHTS
    score = sum(w[k] * v for k, v in a.items())
    return {"version": VERSION, "raw": raw, "axes": a, "score": round(score, 4),
            "level": 1 + bisect_right(bins or DEFAULT_BINS, score)}
