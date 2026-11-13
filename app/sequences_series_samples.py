"""Seeded offline pools for sequences and first series tests."""
import random

from app import sequences_series

R = range


def _payload(term, start=1, ratio=None):
    return {"term": term, "ratio": ratio, "start": str(start)}


def _nplus(offset):
    return "n" if offset == 0 else f"n+{offset}" if offset > 0 else f"n{offset}"


def _limits():
    return {
        "sl_rational_equal": [_payload(f"({a}*n+{b})/({c}*n+{d})") for a in R(1, 8) for b in R(1, 6)
                              for c in R(1, 7) for d in R(1, 4) if a * d != b * c],
        "sl_rational_zero": [_payload(f"({a}*n+{b})/(n^2+{c}*n+{d})") for a in R(1, 9) for b in R(1, 5)
                             for c in R(1, 5) for d in R(1, 4)],
        "sl_exponential": [_payload(f"{L}+{c}*({p}/{q})^n") for L in R(-3, 5) for c in R(1, 6)
                           for p, q in ((1, 2), (1, 3), (2, 3), (2, 5))],
        "sl_radical": [_payload(f"sqrt((n+{s})^2+{d})-(n+{s})") for s in R(0, 8) for d in R(1, 12)],
        "sl_alternating": [_payload(f"{L}+{c}*(-1)^n/(n+{s})^{p}") for L in R(-2, 4) for c in R(1, 5)
                           for s in R(1, 5) for p in (1, 2)],
        "sl_unbounded": [_payload(f"{a}*n^{p}+{b}") for a in R(1, 8) for p in (1, 2, 3) for b in R(-3, 5)],
        "sl_oscillating": [_payload(f"{L}+{c}*(-1)^n") for L in R(-8, 9) for c in R(1, 8)],
        "sl_radical_pair": [_payload(f"sqrt(n^2+{a}*n+{c})-sqrt(n^2+{b}*n+{d})")
                             for a in R(2, 10) for b in R(1, 8) for c in R(1, 5) for d in R(1, 4) if a != b],
    }


def _monotone():
    return {
        "mb_inc": [_payload(f"{L}-{c}/(n+{s})") for L in R(1, 9) for c in R(1, 8) for s in R(1, 6)],
        "mb_dec": [_payload(f"{L}+{c}/(n+{s})") for L in R(-3, 6) for c in R(1, 8) for s in R(1, 6)],
        "mb_geo": [_payload(f"{L}-{c}*({p}/{q})^n") for L in R(1, 8) for c in R(1, 6)
                   for p, q in ((1, 2), (1, 3), (2, 3), (2, 5))],
        "mb_unbounded": [_payload(f"{a}*n^{p}+{b}") for a in R(1, 8) for p in (1, 2, 3) for b in R(-3, 5)],
        "mb_oscillating": [_payload(f"{L}+{c}*(-1)^n") for L in R(-8, 9) for c in R(1, 8)],
        "mb_power": [_payload(f"{L}+{c}/(n+{s})^{p}") for L in R(-2, 6) for c in R(1, 7)
                     for s in R(1, 6) for p in (2, 3, 4)],
    }


def _recursive():
    contractions = [(1, 2), (1, 3), (2, 3), (2, 5), (3, 4)]
    negatives = [(-1, 2), (-1, 3), (-2, 3), (-2, 5), (-3, 4)]
    return {
        "rec_contraction": [_payload(f"({p}/{q})*a", s, f"{p}/{q}") for p, q in contractions for s in R(1, 21)],
        "rec_affine": [_payload(f"({p}/{q})*a+{c}", s, f"{p}/{q}") for p, q in contractions
                       for c in R(1, 8) for s in R(1, 12)],
        "rec_negative": [_payload(f"({p}/{q})*a+{c}", s, f"{p}/{q}") for p, q in negatives
                         for c in R(-3, 5) for s in R(1, 12)],
        "rec_divergent": [_payload(f"{r}*a+{c}", s, str(r)) for r in (-3, -2, -1, 1, 2, 3)
                          for c in R(-5, 6) for s in R(0, 21)
                          if not (r != 1 and s * (1 - r) == c) and not (r == 1 and c == 0)],
        "rec_fixed": [_payload(f"{r}*a+{(1 - r) * fixed}", fixed, str(r)) for r in (2, 3, 4)
                      for fixed in R(0, 21)],
        "rec_babylonian": [_payload(f"(a+{C}/a)/2", s) for C in (2, 3, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15, 17, 18, 19)
                           for s in R(1, 10)],
    }


def _geometric():
    conv = [(1, 2), (1, 3), (2, 3), (2, 5), (3, 4)]
    alt = [(-1, 2), (-1, 3), (-2, 3), (-2, 5), (-3, 4)]
    return {
        "geo_basic": [_payload(f"{A}*({p}/{q})^(n-1)", 1, f"{p}/{q}") for A in R(1, 21) for p, q in conv],
        "geo_shifted": [_payload(f"{A}*({p}/{q})^(n-{s})", s, f"{p}/{q}") for A in R(1, 12)
                        for p, q in conv for s in R(2, 8)],
        "geo_alternating": [_payload(f"{A}*({p}/{q})^(n-{s})", s, f"{p}/{q}") for A in R(1, 12)
                            for p, q in alt for s in R(1, 6)],
        "geo_divergent": [_payload(f"{A}*{r}^(n-{s})", s, str(r)) for A in R(1, 16) for r in (-3, -2, -1, 1, 2, 3)
                          for s in R(0, 4)],
        "geo_disguised": [_payload(f"{A}*{p}^(n-{s})/{q}^(n-{s})", s, f"{p}/{q}") for A in R(1, 15)
                          for p, q in conv + alt for s in R(1, 5)],
    }


def _telescoping():
    return {
        "tel_adjacent": [_payload(f"{c}*(1/(n+{s})-1/(n+{s + 1}))", k) for c in R(1, 11)
                         for s in R(0, 8) for k in R(1, 5)],
        "tel_gap": [_payload(f"{c}*(1/(n+{s})-1/(n+{s + g}))", k) for c in R(1, 9)
                    for s in R(0, 7) for g in (2, 3, 4) for k in R(1, 4)],
        "tel_rational": [_payload(f"{c * g}/((n+{s})*(n+{s + g}))", k) for c in R(1, 9)
                         for s in R(0, 7) for g in (1, 2, 3, 4) for k in R(1, 4)],
        "tel_square": [_payload(f"{c}*(1/(n+{s})^2-1/(n+{s + g})^2)", k) for c in R(1, 9)
                       for s in R(0, 7) for g in (1, 2, 3) for k in R(1, 4)],
        "tel_radical": [_payload(f"{c}*(sqrt(n+{s + g})-sqrt(n+{s}))", k) for c in R(1, 9)
                        for s in R(0, 7) for g in (1, 2, 3) for k in R(1, 4)],
        "tel_shifted": [_payload(f"{c}*(1/({_nplus(-d)})^2-1/({_nplus(g - d)})^2)", d + 1)
                        for c in R(1, 5) for d in R(1, 7) for g in (2, 3, 4)],
    }


def _p_series():
    return {
        "ps_divergent": [_payload(f"{c}/(n+{s})^{p}", k) for c in R(1, 11) for s in R(0, 7)
                         for p in ("1/2", "2/3", "1") for k in R(1, 5)],
        "ps_convergent": [_payload(f"{c}/(n+{s})^{p}", k) for c in R(1, 11) for s in R(0, 7)
                          for p in ("3/2", "3", "5") for k in R(1, 5)],
        "ps_square_value": [_payload(f"{c}/n^2", 1) for c in R(1, 81)],
        "ps_shifted_square": [_payload(f"{c}/(n+{s})^2", k) for c in R(1, 11) for s in R(0, 8) for k in R(1, 8)],
        "ps_fractional": [_payload(f"{c}/(n+{s})^{p}", k) for c in R(1, 11) for s in R(0, 7)
                          for p in ("4/3", "3/2", "5/2") for k in R(1, 5)],
        "ps_fourth_value": [_payload(f"{c}/({_nplus(first - start)})^4", start)
                            for c in R(1, 5) for start in R(2, 10) for first in (1, 2, 3)],
    }


TABLES = {"limits": _limits(), "monotone_bounded": _monotone(), "recursive": _recursive(),
          "geometric": _geometric(), "telescoping": _telescoping(), "p_series": _p_series()}


def generate(recipe, axes, answers, calculator="none", seed=0, topic=None, limit=240):
    rows = list(TABLES[topic].get(recipe["id"], ()))
    random.Random(seed).shuffle(rows)
    full_axes = {"recipe": recipe["id"], **axes}
    for payload in rows[:limit]:
        result = sequences_series.verify(topic, axes=full_axes, calculator=calculator, **payload)
        if result["ok"] and result["answer"]["type"] in answers:
            return {"payload": payload, "result": result}
    return None
