"""Check core/latex_reader.py against the verified problem bank.

For each bank problem with answer type expression or numeric, level 1 to 4, and
a non-empty answer.latex, the LaTeX key is read by read_latex (after stripping a
trailing "+ C") and the bank's SymPy key is read by input_boundary.parse (with
"**" replaced by "^"). The two are compared numerically at fixed sample points.

Outcomes:
  matched              both read and agree at every comparable point
  MISMATCH             both read but disagree at a comparable point
  rejected             the reader raised BoundaryError on the LaTeX key
  sympy_side_rejected  the bank's SymPy key could not be read
  no_comparable_point  no sample point was finite and real on both sides

Exit code 1 if any MISMATCH, else 0. Run as: python scripts/check_latex_reader.py
"""

from __future__ import annotations

import re
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import sympy as sp  # noqa: E402

from core import input_boundary  # noqa: E402
from core.input_boundary import BoundaryError  # noqa: E402
from core.latex_reader import read_latex  # noqa: E402

BANK_PATH = REPO_ROOT / "docs" / "verified_problems.json"
ANSWER_TYPES = frozenset({"expression", "numeric"})
LEVELS = frozenset({1, 2, 3, 4})
TRAILING_CONSTANT = "+ C"
SAMPLE_POINTS = (0.3, 0.7, 1.3, 1.9, 2.6)
REL_TOLERANCE = 1e-9
ABS_FLOOR = 1e-12
SLOW_SECONDS = 5.0
TOP_REJECTIONS = 10
MISMATCHES_SHOWN = 10

MATCHED = "matched"
MISMATCH = "MISMATCH"
REJECTED = "rejected"
SYMPY_REJECTED = "sympy_side_rejected"
NO_POINT = "no_comparable_point"
OUTCOME_ORDER = (MATCHED, MISMATCH, REJECTED, SYMPY_REJECTED, NO_POINT)

X = sp.Symbol("x", real=True)


def strip_constant(latex: str) -> str:
    stripped = latex.strip()
    if stripped.endswith(TRAILING_CONSTANT):
        return stripped[: -len(TRAILING_CONSTANT)].rstrip()
    return stripped


def sympy_to_boundary_text(sympy_key: str) -> str:
    text = sympy_key.replace("**", "^")
    text = re.sub(r"\bAbs\b", "abs", text)
    return re.sub(r"\bE\b", "e", text)


def real_value(expr: sp.Basic) -> float | None:
    try:
        value = complex(sp.N(expr))
    except (TypeError, ValueError, OverflowError, ZeroDivisionError):
        return None
    if value.imag != 0 or not math.isfinite(value.real):
        return None
    return value.real


def comparable_pairs(left: sp.Basic, right: sp.Basic) -> list[tuple[float, float]]:
    if left.free_symbols | right.free_symbols:
        assignments = [{X: sp.Float(point)} for point in SAMPLE_POINTS]
    else:
        assignments = [{}]
    pairs = []
    for assignment in assignments:
        left_value = real_value(left.subs(assignment))
        right_value = real_value(right.subs(assignment))
        if left_value is not None and right_value is not None:
            pairs.append((left_value, right_value))
    return pairs


def values_agree(left: float, right: float) -> bool:
    scale = max(abs(left), abs(right))
    return abs(left - right) <= REL_TOLERANCE * scale + ABS_FLOOR


def check_problem(latex_key: str, sympy_key: str) -> tuple[str, str]:
    """Return (outcome, detail). The detail is the rejection message, if any."""
    try:
        reader_expr = read_latex(strip_constant(latex_key))
    except BoundaryError as error:
        return REJECTED, str(error)
    if not sympy_key:
        return SYMPY_REJECTED, "bank problem has no SymPy key"
    try:
        bank_expr = input_boundary.parse(sympy_to_boundary_text(sympy_key))
    except BoundaryError as error:
        return SYMPY_REJECTED, str(error)
    pairs = comparable_pairs(reader_expr, bank_expr)
    if not pairs:
        return NO_POINT, ""
    if all(values_agree(left, right) for left, right in pairs):
        return MATCHED, ""
    return MISMATCH, ""


def select_problems(bank: list[dict]) -> list[dict]:
    selected = []
    for problem in bank:
        answer = problem.get("answer") or {}
        latex = (answer.get("latex") or "").strip()
        if answer.get("type") in ANSWER_TYPES and problem.get("level") in LEVELS and latex:
            selected.append(problem)
    return selected


def print_counts(counts: Counter, total: int) -> None:
    print(f"problems checked: {total}")
    for outcome in OUTCOME_ORDER:
        print(f"  {outcome}: {counts.get(outcome, 0)}")


def print_top_rejections(messages: Counter, examples: dict[str, str]) -> None:
    print(f"top rejection messages (reader side, up to {TOP_REJECTIONS}):")
    for message, count in messages.most_common(TOP_REJECTIONS):
        print(f"  {count:4d}  {message}")
        print(f"        e.g. {examples[message]!r}")


def print_mismatches(mismatches: list[dict]) -> None:
    print(f"first {min(len(mismatches), MISMATCHES_SHOWN)} MISMATCH cases:")
    for case in mismatches[:MISMATCHES_SHOWN]:
        print(f"  topic={case['topic']} id={case['id']}")
        print(f"    latex={case['latex']!r}")
        print(f"    sympy={case['sympy']!r}")


def main() -> int:
    bank = json.loads(BANK_PATH.read_text(encoding="utf-8"))
    problems = select_problems(bank)
    counts: Counter = Counter()
    rejection_messages: Counter = Counter()
    rejection_examples: dict[str, str] = {}
    mismatches: list[dict] = []
    slow_cases: list[str] = []

    for problem in problems:
        answer = problem["answer"]
        started = time.perf_counter()
        outcome, detail = check_problem(answer["latex"], answer.get("sympy") or "")
        elapsed = time.perf_counter() - started
        counts[outcome] += 1
        if elapsed > SLOW_SECONDS:
            slow_cases.append(f"{problem['id']} took {elapsed:.1f}s")
        if outcome == REJECTED:
            rejection_messages[detail] += 1
            rejection_examples.setdefault(detail, answer["latex"])
        if outcome == MISMATCH:
            mismatches.append({
                "topic": problem.get("topic"),
                "id": problem.get("id"),
                "latex": answer["latex"],
                "sympy": answer.get("sympy"),
            })

    print_counts(counts, len(problems))
    print_top_rejections(rejection_messages, rejection_examples)
    print_mismatches(mismatches)
    print(f"slow cases over {SLOW_SECONDS}s: {len(slow_cases)}")
    for line in slow_cases:
        print(f"  {line}")
    return 1 if counts.get(MISMATCH, 0) > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
