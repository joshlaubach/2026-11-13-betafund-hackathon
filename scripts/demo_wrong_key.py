"""Demo: the power_rule checker accepts a correct key and rejects a wrong one.

Uses bank problem PR01 of topic power_rule. Plain text output.
Run as: python scripts/demo_wrong_key.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core.corrupt import corrupt_key  # noqa: E402
from core.derivative_checker import WRONG_KEY, check_derivative, parse_derivative_statement  # noqa: E402

BANK_PATH = REPO_ROOT / "docs" / "verified_problems.json"
TOPIC = "power_rule"
PROBLEM_ID = "PR01"
AI_STYLE_KEY = "4x^{3} + 6x"
WRONG_KEY_KIND = 0


def find_problem(bank: list[dict]) -> dict:
    for problem in bank:
        if problem.get("topic") == TOPIC and problem.get("id") == PROBLEM_ID:
            return problem
    raise SystemExit(f"problem {TOPIC} {PROBLEM_ID} not found in the bank")


def print_verdict(label: str, key: str, verdict: dict) -> None:
    print(f"{label}: {key}")
    print(f"  outcome: {verdict['outcome']} (ok={verdict['ok']})")
    print(f"  reason: {verdict['reason']}")
    print("  checker log:")
    print(f"    derivative computed by SymPy: {verdict['true_answer']}")
    for x_value, true_value, key_value in verdict["samples"]:
        print(f"    x = {x_value:g}: checker {true_value:.6g}, key {key_value:.6g}")


def main() -> int:
    bank = json.loads(BANK_PATH.read_text(encoding="utf-8"))
    problem = find_problem(bank)
    parsed = parse_derivative_statement(problem["statement"])
    if parsed is None:
        raise SystemExit(f"statement of {PROBLEM_ID} is not a recognized derivative statement")
    print(f"problem: {TOPIC} {PROBLEM_ID}")
    print(f"statement: {problem['statement']}")
    print()
    accepted = check_derivative(parsed["function_latex"], AI_STYLE_KEY, parsed["at"])
    print_verdict("correct AI-style key", AI_STYLE_KEY, accepted)
    print()
    wrong_key = corrupt_key(problem["answer"]["latex"], WRONG_KEY_KIND)
    if wrong_key is None:
        raise SystemExit("could not build a wrong key for this problem")
    rejected = check_derivative(parsed["function_latex"], wrong_key, parsed["at"])
    print_verdict("wrong key (bank key plus 1)", wrong_key, rejected)
    return 0 if accepted["ok"] and rejected["outcome"] == WRONG_KEY else 1


if __name__ == "__main__":
    sys.exit(main())
