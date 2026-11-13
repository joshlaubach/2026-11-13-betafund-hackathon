"""Bank gate for the power_rule derivative checker (levels 1 to 4).

A problem is supported when its statement can be read as a derivative problem
and its function reads with core.latex_reader. An unreadable statement is listed
as unsupported and lowers the parse rate. An unreadable bank key is NOT a
support decision: it is a positive failure.

Positive test: the bank key must be accepted for every supported problem.
Negative test: each corrupted key (core.corrupt) must be rejected as wrong_key.

Run as: python scripts/gate_power_rule.py   (exit 0 only when GATE: ENABLED)
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core.corrupt import CORRUPTION_KINDS, corrupt_key  # noqa: E402
from core.derivative_checker import (  # noqa: E402
    UNREADABLE_PROBLEM,
    WRONG_KEY,
    check_derivative,
    parse_derivative_statement,
)

BANK_PATH = REPO_ROOT / "docs" / "verified_problems.json"
OUTPUT_PATH = REPO_ROOT / "build" / "gate_power_rule.json"
TOPIC = "power_rule"
ANSWER_TYPES = frozenset({"expression", "numeric"})
LEVELS = frozenset({1, 2, 3, 4})
MIN_PARSE_RATE = 0.90
MIN_TESTED = 8
MAX_LEVELS_REQUIRED = 3
SUPPORTED = "supported"
UNSUPPORTED = "unsupported"


def select_problems(bank: list[dict]) -> list[dict]:
    selected = []
    for problem in bank:
        answer = problem.get("answer") or {}
        latex = (answer.get("latex") or "").strip()
        if (
            problem.get("topic") == TOPIC
            and problem.get("level") in LEVELS
            and answer.get("type") in ANSWER_TYPES
            and latex
        ):
            selected.append(problem)
    return selected


def evaluate_problem(problem: dict) -> dict:
    record = {
        "topic": problem.get("topic"),
        "id": problem.get("id"),
        "level": problem.get("level"),
        "status": UNSUPPORTED,
        "positive_ok": None,
        "negative_passed": 0,
        "negative_skipped": 0,
        "negative_failed": 0,
        "reasons": [],
    }
    parsed = parse_derivative_statement(problem.get("statement"))
    if parsed is None:
        record["reasons"].append("statement shape is not recognized")
        return record
    key = problem["answer"]["latex"]
    positive = check_derivative(parsed["function_latex"], key, parsed["at"])
    if positive["outcome"] == UNREADABLE_PROBLEM:
        record["reasons"].append(f"{positive['outcome']}: {positive['reason']}")
        return record
    record["status"] = SUPPORTED
    record["positive_ok"] = positive["ok"]
    if not positive["ok"]:
        record["reasons"].append(f"positive: {positive['outcome']}: {positive['reason']}")
    for kind in CORRUPTION_KINDS:
        score_negative(record, parsed, key, kind)
    return record


def score_negative(record: dict, parsed: dict, key: str, kind: int) -> None:
    wrong = corrupt_key(key, kind)
    if wrong is None:
        record["negative_skipped"] += 1
        return
    verdict = check_derivative(parsed["function_latex"], wrong, parsed["at"])
    if verdict["outcome"] == WRONG_KEY:
        record["negative_passed"] += 1
        return
    record["negative_failed"] += 1
    record["reasons"].append(
        f"negative kind {kind}: key {wrong!r} gave {verdict['outcome']}: {verdict['reason']}"
    )


def summarize(records: list[dict]) -> dict:
    eligible = len(records)
    supported = [record for record in records if record["status"] == SUPPORTED]
    positive_passed = sum(1 for record in supported if record["positive_ok"])
    positive_failed = len(supported) - positive_passed
    negative_passed = sum(record["negative_passed"] for record in supported)
    negative_failed = sum(record["negative_failed"] for record in supported)
    negative_skipped = sum(record["negative_skipped"] for record in supported)
    parse_rate = len(supported) / eligible if eligible else 0.0
    levels_present = sorted({record["level"] for record in records})
    supported_levels = sorted({record["level"] for record in supported})
    levels_required = min(MAX_LEVELS_REQUIRED, len(levels_present))
    reasons = gate_reasons(
        eligible, parse_rate, len(supported), len(supported_levels), levels_required,
        positive_failed, negative_failed,
    )
    per_level = {
        str(level): {
            "eligible": sum(1 for record in records if record["level"] == level),
            "supported": sum(1 for record in supported if record["level"] == level),
        }
        for level in levels_present
    }
    return {
        "topic": TOPIC,
        "eligible": eligible,
        "supported": len(supported),
        "unsupported": eligible - len(supported),
        "parse_rate": round(parse_rate, 4),
        "per_level": per_level,
        "positive_passed": positive_passed,
        "positive_failed": positive_failed,
        "negative_passed": negative_passed,
        "negative_failed": negative_failed,
        "negative_skipped": negative_skipped,
        "levels_with_tested": len(supported_levels),
        "levels_required": levels_required,
        "enabled": not reasons,
        "reasons": reasons,
    }


def gate_reasons(
    eligible: int,
    parse_rate: float,
    supported_count: int,
    supported_level_count: int,
    levels_required: int,
    positive_failed: int,
    negative_failed: int,
) -> list[str]:
    reasons = []
    if eligible == 0:
        reasons.append("no eligible problems")
    if parse_rate < MIN_PARSE_RATE:
        reasons.append(f"parse rate {parse_rate:.3f} is below {MIN_PARSE_RATE:.2f}")
    if supported_count < MIN_TESTED:
        reasons.append(f"only {supported_count} supported problems; need {MIN_TESTED}")
    if supported_level_count < levels_required:
        reasons.append(
            f"supported problems span {supported_level_count} levels; need {levels_required}"
        )
    if positive_failed:
        reasons.append(f"{positive_failed} positive failures")
    if negative_failed:
        reasons.append(f"{negative_failed} negative failures")
    return reasons


def failing_records(records: list[dict]) -> list[dict]:
    return [
        record
        for record in records
        if record["status"] == SUPPORTED
        and (record["positive_ok"] is False or record["negative_failed"])
    ]


def print_report(summary: dict, records: list[dict]) -> None:
    print(f"topic: {TOPIC}")
    print(f"eligible problems (levels 1-4): {summary['eligible']}")
    print("per level (eligible / supported):")
    for level, counts in summary["per_level"].items():
        print(f"  level {level}: {counts['eligible']} / {counts['supported']}")
    print(f"supported: {summary['supported']}  unsupported: {summary['unsupported']}")
    print(f"parse rate: {summary['parse_rate']:.3f} (needs >= {MIN_PARSE_RATE:.2f})")
    print(f"positive: pass {summary['positive_passed']} fail {summary['positive_failed']}")
    print(
        f"negative: pass {summary['negative_passed']} fail {summary['negative_failed']}"
        f" skipped {summary['negative_skipped']}"
    )
    print(
        f"levels with gate-tested problems: {summary['levels_with_tested']}"
        f" (needs {summary['levels_required']})"
    )
    print("unsupported problems:")
    for record in records:
        if record["status"] == UNSUPPORTED:
            print(f"  {record['topic']} {record['id']}: {record['reasons'][0]}")
    print("failing problems:")
    for record in failing_records(records):
        print(f"  {record['topic']} {record['id']}")
        for reason in record["reasons"]:
            print(f"    {reason}")
    if summary["enabled"]:
        print("GATE: ENABLED")
    else:
        print("GATE: NOT ENABLED")
        for reason in summary["reasons"]:
            print(f"  - {reason}")


def write_output(summary: dict, records: list[dict], bank_hash: str) -> None:
    payload = dict(summary)
    payload["bank_sha256"] = bank_hash
    payload["failing"] = [
        {"topic": record["topic"], "id": record["id"], "reasons": record["reasons"]}
        for record in failing_records(records)
    ]
    payload["unsupported"] = [
        {"topic": record["topic"], "id": record["id"], "reasons": record["reasons"]}
        for record in records
        if record["status"] == UNSUPPORTED
    ]
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    raw_bank = BANK_PATH.read_bytes()
    bank = json.loads(raw_bank.decode("utf-8"))
    bank_hash = hashlib.sha256(raw_bank).hexdigest()
    records = [evaluate_problem(problem) for problem in select_problems(bank)]
    summary = summarize(records)
    print_report(summary, records)
    write_output(summary, records, bank_hash)
    return 0 if summary["enabled"] else 1


if __name__ == "__main__":
    sys.exit(main())
