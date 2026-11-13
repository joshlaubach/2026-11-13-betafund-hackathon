"""Read-only probe: could the derivative checker gate each bank topic like power_rule?

For each topic, the eligible bank problems (levels 1 to 4, passing the bank audit
in scripts/audit_bank.py, and the same answer-type selection as
scripts/gate_power_rule.py) are run through core.derivative_checker.check_derivative
exactly as gate_power_rule.py runs power_rule. Accepted problems then get the
core.corrupt negatives. Each topic is scored against the bar gate_power_rule.py
applies (its gate_reasons function and thresholds).

Writes build/gate_topics.json only. It enables and registers nothing.
Run as: python scripts/gate_topics.py [--topics TOPIC ...]   (exit code is always 0
for a completed report)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core.corrupt import CORRUPTION_KINDS, corrupt_key  # noqa: E402
from core.derivative_checker import (  # noqa: E402
    ACCEPTED,
    NO_COMPARABLE_POINTS,
    UNREADABLE_KEY,
    UNREADABLE_PROBLEM,
    WRONG_KEY,
    check_derivative,
    parse_derivative_statement,
)
from scripts.audit_bank import classify  # noqa: E402
from scripts.gate_power_rule import (  # noqa: E402
    ANSWER_TYPES,
    BANK_PATH,
    LEVELS,
    MAX_LEVELS_REQUIRED,
    MIN_PARSE_RATE,
    MIN_TESTED,
    gate_reasons,
)

OUTPUT_PATH = REPO_ROOT / "build" / "gate_topics.json"
DEFAULT_TOPICS = (
    "product_rule", "quotient_rule", "chain_rule", "trig", "exponential_log",
    "logarithmic", "second_derivatives", "higher_order", "inverse_trig",
    "dhyperbolic", "hyperbolic", "rules", "algebraic", "basic_antiderivatives",
    "difference_quotient", "implicit", "tangent_normal_lines",
)
EXAMPLES_PER_CATEGORY = 3
CHECKER_ERROR_PREFIX = "the checker could not finish"
PERCENT = 100.0

CAT_STATEMENT = "statement_not_parsable"
CAT_FUNCTION = "function_unreadable"
CAT_KEY = "key_unreadable"
CAT_MISMATCH = "mismatch"
CAT_NO_POINTS = "no_comparable_points"
CAT_ERROR = "checker_error"
OUTCOME_CATEGORY = {
    WRONG_KEY: CAT_MISMATCH,
    UNREADABLE_KEY: CAT_KEY,
    NO_COMPARABLE_POINTS: CAT_NO_POINTS,
}
UNSUPPORTED_CATEGORIES = frozenset({CAT_STATEMENT, CAT_FUNCTION, CAT_ERROR})

BAR_PASS = "PASS"
BAR_FAIL = "FAIL"
BAR_INSUFFICIENT = "INSUFFICIENT"

NEG_TRIED = "tried"
NEG_REJECTED = "rejected"
NEG_ACCEPTED = "accepted"
NEG_OTHER = "other"
NEG_SKIPPED = "skipped"
NEG_KEYS = (NEG_TRIED, NEG_REJECTED, NEG_ACCEPTED, NEG_OTHER, NEG_SKIPPED)

TABLE_HEADERS = (
    "topic", "eligible", "accepted", "accept%", "neg tried", "neg rejected",
    "neg accepted", "top non-accept category", "bar",
)


def eligible_pool(bank: list[dict], topic: str) -> tuple[list[dict], int]:
    """Return (eligible problems for topic, count of audit-eligible ones dropped by answer type)."""
    pool = []
    dropped_by_type = 0
    for problem in bank:
        if problem.get("topic") != topic or classify(problem) is not None:
            continue
        answer = problem.get("answer") or {}
        latex = (answer.get("latex") or "").strip()
        if answer.get("type") in ANSWER_TYPES and latex and problem.get("level") in LEVELS:
            pool.append(problem)
        else:
            dropped_by_type += 1
    return pool, dropped_by_type


def category_for(verdict: dict) -> str:
    """Map a non-accepted checker verdict to a category name."""
    if verdict["outcome"] == UNREADABLE_PROBLEM:
        if verdict["reason"].startswith(CHECKER_ERROR_PREFIX):
            return CAT_ERROR
        return CAT_FUNCTION
    return OUTCOME_CATEGORY.get(verdict["outcome"], CAT_ERROR)


def score_negatives(parsed: dict, key: str, problem_id: object) -> dict:
    """Run the core.corrupt negatives for one accepted problem, as gate_power_rule does."""
    counts = {name: 0 for name in NEG_KEYS}
    counts["accepted_examples"] = []
    for kind in CORRUPTION_KINDS:
        try:
            wrong = corrupt_key(key, kind)
        except Exception:  # counted as other, never silently dropped
            counts[NEG_OTHER] += 1
            counts[NEG_TRIED] += 1
            continue
        if wrong is None:
            counts[NEG_SKIPPED] += 1
            continue
        counts[NEG_TRIED] += 1
        outcome = check_derivative(parsed["function_latex"], wrong, parsed["at"])["outcome"]
        if outcome == WRONG_KEY:
            counts[NEG_REJECTED] += 1
        elif outcome == ACCEPTED:
            counts[NEG_ACCEPTED] += 1
            counts["accepted_examples"].append(f"{problem_id} kind {kind}: {wrong}")
        else:
            counts[NEG_OTHER] += 1
    return counts


def evaluate_problem(problem: dict) -> dict:
    """Run one eligible problem through the positive check (and negatives when accepted)."""
    record = {
        "id": problem.get("id"),
        "level": problem.get("level"),
        "statement": problem.get("statement"),
        "supported": False,
        "accepted": False,
        "category": None,
        "negatives": None,
    }
    parsed = parse_derivative_statement(problem.get("statement"))
    if parsed is None:
        record["category"] = CAT_STATEMENT
        return record
    key = problem["answer"]["latex"]
    verdict = check_derivative(parsed["function_latex"], key, parsed["at"])
    if verdict["outcome"] != UNREADABLE_PROBLEM:
        record["supported"] = True
    if verdict["ok"]:
        record["accepted"] = True
        record["negatives"] = score_negatives(parsed, key, problem.get("id"))
        return record
    record["category"] = category_for(verdict)
    return record


def bar_verdict(
    eligible: int,
    parse_rate: float,
    supported_count: int,
    levels_short: bool,
    reasons: list[str],
    failures: int,
) -> str:
    """Return PASS, FAIL, or INSUFFICIENT under the gate_power_rule bar.

    PASS is exactly the case where gate_reasons is empty, so PASS means the topic
    would be ENABLED by the power_rule rules.
    """
    if failures:
        return BAR_FAIL
    if eligible == 0 or supported_count < MIN_TESTED or levels_short:
        return BAR_INSUFFICIENT
    if parse_rate < MIN_PARSE_RATE:
        return BAR_FAIL
    if reasons:
        return BAR_FAIL
    return BAR_PASS


def summarize_topic(topic: str, records: list[dict], dropped_by_type: int) -> dict:
    """Build one topic row from its evaluated records."""
    eligible = len(records)
    supported = [record for record in records if record["supported"]]
    accepted = [record for record in records if record["accepted"]]
    negatives = {name: 0 for name in NEG_KEYS}
    accepted_examples: list[str] = []
    for record in accepted:
        for name in NEG_KEYS:
            negatives[name] += record["negatives"][name]
        accepted_examples.extend(record["negatives"]["accepted_examples"])
    positive_failed = len(supported) - len(accepted)
    negative_failed = negatives[NEG_TRIED] - negatives[NEG_REJECTED]
    parse_rate = len(supported) / eligible if eligible else 0.0
    levels_present = {record["level"] for record in records}
    supported_levels = {record["level"] for record in supported}
    levels_required = min(MAX_LEVELS_REQUIRED, len(levels_present))
    reasons = gate_reasons(
        eligible, parse_rate, len(supported), len(supported_levels), levels_required,
        positive_failed, negative_failed,
    )
    levels_short = len(supported_levels) < levels_required
    verdict = bar_verdict(
        eligible, parse_rate, len(supported), levels_short, reasons,
        positive_failed + negative_failed,
    )
    categories = category_table(records)
    return {
        "topic": topic,
        "eligible": eligible,
        "accepted": len(accepted),
        "accept_pct": round(PERCENT * len(accepted) / eligible, 2) if eligible else 0.0,
        "supported": len(supported),
        "parse_rate": round(parse_rate, 4),
        "dropped_by_answer_type": dropped_by_type,
        "levels_present": sorted(levels_present),
        "supported_levels": sorted(supported_levels),
        "negatives": negatives,
        "negatives_wrongly_accepted_examples": accepted_examples[:EXAMPLES_PER_CATEGORY],
        "categories": categories,
        "top_category": top_category(categories),
        "bar": verdict,
        "bar_reasons": reasons,
    }


def category_table(records: list[dict]) -> dict:
    """Per-category count and up to three example statements for non-accepted problems."""
    table: dict = {}
    for record in records:
        category = record["category"]
        if category is None:
            continue
        entry = table.setdefault(category, {"count": 0, "examples": []})
        entry["count"] += 1
        if len(entry["examples"]) < EXAMPLES_PER_CATEGORY:
            entry["examples"].append({"id": record["id"], "statement": record["statement"]})
    return table


def top_category(categories: dict) -> str:
    if not categories:
        return "-"
    counts = Counter({name: entry["count"] for name, entry in categories.items()})
    return counts.most_common(1)[0][0]


def probe_topic(bank: list[dict], topic: str) -> dict:
    pool, dropped_by_type = eligible_pool(bank, topic)
    records = [evaluate_problem(problem) for problem in pool]
    return summarize_topic(topic, records, dropped_by_type)


def format_table(rows: list[dict]) -> str:
    cells = [
        [
            row["topic"],
            str(row["eligible"]),
            str(row["accepted"]),
            f"{row['accept_pct']:.1f}",
            str(row["negatives"][NEG_TRIED]),
            str(row["negatives"][NEG_REJECTED]),
            str(row["negatives"][NEG_ACCEPTED]),
            row["top_category"],
            row["bar"],
        ]
        for row in rows
    ]
    widths = [
        max([len(header)] + [len(cell[index]) for cell in cells])
        for index, header in enumerate(TABLE_HEADERS)
    ]
    lines = [" | ".join(header.ljust(width) for header, width in zip(TABLE_HEADERS, widths))]
    lines.append("-+-".join("-" * width for width in widths))
    for cell in cells:
        lines.append(" | ".join(value.ljust(width) for value, width in zip(cell, widths)))
    return "\n".join(lines)


def write_output(rows: list[dict], topics: list[str], bank_hash: str, out_path: Path) -> None:
    payload = {
        "bank_sha256": bank_hash,
        "topics_requested": topics,
        "bar": {
            "min_parse_rate": MIN_PARSE_RATE,
            "min_tested": MIN_TESTED,
            "max_levels_required": MAX_LEVELS_REQUIRED,
            "source": "scripts/gate_power_rule.py gate_reasons and constants",
        },
        "topics": rows,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only per-topic derivative gate probe.")
    parser.add_argument("--topics", nargs="+", default=list(DEFAULT_TOPICS))
    return parser.parse_args(argv)


def run_probe(topics: list[str], out_path: Path | None = None) -> list[dict]:
    raw = BANK_PATH.read_bytes()
    bank = json.loads(raw.decode("utf-8"))
    rows = [probe_topic(bank, topic) for topic in topics]
    rows.sort(key=lambda row: (-row["accept_pct"], row["topic"]))
    target = out_path if out_path is not None else OUTPUT_PATH
    write_output(rows, topics, hashlib.sha256(raw).hexdigest(), target)
    return rows


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rows = run_probe(args.topics)
    print(format_table(rows) + f"\nWrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
