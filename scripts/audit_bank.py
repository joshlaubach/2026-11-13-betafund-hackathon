"""Audit the problem bank and report which problems are eligible.

A problem at level 5 is reported separately and never audited. A problem at
levels 1 to 4 is excluded when its statement is not self-contained:
  - figure_reference: it refers to a figure, diagram, table, or chart that is
    not given as text;
  - undefined_function: it applies f, g, or h without defining it (no "=" and
    no given/suppose/assume/let).

Standard library only. Run as: python -I scripts/audit_bank.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BANK = REPO_ROOT / "docs" / "verified_problems.json"
DEFAULT_OUT = REPO_ROOT / "build" / "audit_report.json"

MAX_LEVEL = 5
LEVEL_5 = 5
AUDITED_LEVELS = (1, 2, 3, 4)
REQUIRED_KEYS = ("id", "level", "statement")

REASON_LEVEL_5 = "level_5"
REASON_FIGURE = "figure_reference"
REASON_UNDEFINED = "undefined_function"
FAILURE_REASONS = (REASON_FIGURE, REASON_UNDEFINED)

EXIT_OK = 0
EXIT_WRITE_FAILED = 1
EXIT_BAD_INPUT = 2

FIGURE_PATTERN = re.compile(
    r"\b(?:figure|diagram)\b"
    r"|\bshown\s+(?:in|below|above)\b"
    r"|\b(?:in|from|using)\s+the\s+graph\b"
    r"|\b(?:in|from)\s+the\s+table\b"
    r"|\bthe\s+table\s+(?:below|above)\b"
    r"|\bthe\s+chart\b",
    re.IGNORECASE,
)

# A single-letter f, g, or h applied to an argument: f(x), f'(2), f{\left(x \right)}.
FUNCTION_APPLICATION_PATTERN = re.compile(
    r"(?<![A-Za-z\\])[fgh](?:'+|\^\{\\prime\})?\s*\{?\s*(?:\\left\s*)?\("
)

DEFINING_WORD_PATTERN = re.compile(r"\b(?:given|suppose|assume|let)\b", re.IGNORECASE)


def parse_level(problem: dict) -> int:
    """Return the problem's level as an int in 1..5, or raise ValueError."""
    raw = problem["level"]
    if isinstance(raw, bool) or not isinstance(raw, (int, str)):
        raise ValueError(f"entry {problem['id']!r} has invalid level {raw!r}")
    try:
        level = int(raw)
    except ValueError as error:
        raise ValueError(f"entry {problem['id']!r} has non-integer level {raw!r}") from error
    if not 1 <= level <= MAX_LEVEL:
        raise ValueError(f"entry {problem['id']!r} has out-of-range level {level}")
    return level


def uses_undefined_function(statement: str) -> bool:
    """True when the statement applies f, g, or h but supplies no definition."""
    if "=" in statement or DEFINING_WORD_PATTERN.search(statement):
        return False
    return FUNCTION_APPLICATION_PATTERN.search(statement) is not None


def classify(problem: dict) -> Optional[str]:
    """Return the exclusion reason for a problem, or None when it is eligible."""
    if parse_level(problem) == LEVEL_5:
        return REASON_LEVEL_5
    statement = problem["statement"]
    if FIGURE_PATTERN.search(statement):
        return REASON_FIGURE
    if uses_undefined_function(statement):
        return REASON_UNDEFINED
    return None


def validate_entries(entries: list) -> None:
    """Raise ValueError if any entry is not an object with the required keys."""
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"entry {index} is not a JSON object")
        missing = [key for key in REQUIRED_KEYS if key not in entry]
        if missing:
            raise ValueError(f"entry {index} lacks required key(s): {', '.join(missing)}")
        if not isinstance(entry["statement"], str):
            raise ValueError(f"entry {entry['id']!r} has a non-string statement")
        parse_level(entry)


def load_bank(path: Path) -> list:
    """Read and validate the bank file. Raises ValueError on any input problem."""
    bank_path = Path(path)
    try:
        text = bank_path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise ValueError(f"bank file not found: {bank_path}") from error
    except OSError as error:
        raise ValueError(f"cannot read bank file {bank_path}: {error}") from error
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"bank file is not valid JSON: {error}") from error
    if not isinstance(data, list):
        raise ValueError("bank file must contain a JSON list")
    validate_entries(data)
    return data


def excluded_rows(audited: list) -> list:
    """Build sorted excluded rows from (problem, reason) pairs."""
    rows = [
        {
            "id": str(problem["id"]),
            "topic": problem.get("topic", ""),
            "level": parse_level(problem),
            "reason": reason,
        }
        for problem, reason in audited
        if reason is not None
    ]
    return sorted(rows, key=lambda row: (row["id"], row["topic"], row["level"]))


def eligible_rows(eligible: list) -> list:
    """Build eligible rows {id, topic, level} sorted by (topic, id)."""
    rows = [
        {
            "id": str(problem["id"]),
            "topic": problem.get("topic", ""),
            "level": parse_level(problem),
        }
        for problem in eligible
    ]
    return sorted(rows, key=lambda row: (row["topic"], row["id"]))


def count_excluded_by_reason(rows: list) -> dict:
    counts = {reason: 0 for reason in FAILURE_REASONS}
    for row in rows:
        counts[row["reason"]] += 1
    return counts


def count_by_level(problems: list) -> dict:
    counts = {str(level): 0 for level in AUDITED_LEVELS}
    for problem in problems:
        counts[str(parse_level(problem))] += 1
    return counts


def count_by_topic_level(audited: list) -> dict:
    """Per-topic counts of eligible problems at each audited level (zero-filled)."""
    table: dict = {}
    for problem, reason in audited:
        topic = problem.get("topic", "")
        row = table.setdefault(topic, {str(level): 0 for level in AUDITED_LEVELS})
        if reason is None:
            row[str(parse_level(problem))] += 1
    return table


def build_report(bank: list) -> dict:
    """Classify every problem and assemble the report. Does not mutate bank."""
    level_5_count = 0
    audited: list = []
    for problem in bank:
        reason = classify(problem)
        if reason == REASON_LEVEL_5:
            level_5_count += 1
        else:
            audited.append((problem, reason))
    eligible = [problem for problem, reason in audited if reason is None]
    rows = excluded_rows(audited)
    return {
        "total": len(bank),
        "level_5_count": level_5_count,
        "audited_count": len(audited),
        "eligible_count": len(eligible),
        "eligible": eligible_rows(eligible),
        "excluded": rows,
        "excluded_by_reason": count_excluded_by_reason(rows),
        "eligible_by_level": count_by_level(eligible),
        "eligible_by_topic_level": count_by_topic_level(audited),
    }


def format_summary(report: dict, bank_path: Path, out_path: Path) -> str:
    by_level = report["eligible_by_level"]
    by_reason = report["excluded_by_reason"]
    lines = [
        f"Bank audit: {bank_path}",
        f"Total problems: {report['total']}",
        f"Level 5 (reported separately, not audited): {report['level_5_count']}",
        f"Levels 1-4 audited: {report['audited_count']}",
        f"Eligible: {report['eligible_count']}",
        f"Excluded: {len(report['excluded'])}",
    ]
    lines += [f"  {reason}: {by_reason[reason]}" for reason in FAILURE_REASONS]
    lines.append("Eligible by level: " + ", ".join(f"{lvl}={by_level[lvl]}" for lvl in by_level))
    lines.append(f"Report written to: {out_path}")
    return "\n".join(lines)


def write_report(report: dict, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    out_path.write_text(text, encoding="utf-8")


def parse_args(argv: Optional[list]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit the problem bank for self-contained statements.")
    parser.add_argument("--bank", type=Path, default=DEFAULT_BANK, help="path to the bank JSON list")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="path for the JSON report")
    return parser.parse_args(argv)


def main(argv: Optional[list] = None) -> int:
    args = parse_args(argv)
    try:
        bank = load_bank(args.bank)
    except ValueError as error:
        print(f"audit_bank: error: {error}", file=sys.stderr)
        return EXIT_BAD_INPUT
    report = build_report(bank)
    try:
        write_report(report, args.out)
    except OSError as error:
        print(f"audit_bank: error: cannot write report {args.out}: {error}", file=sys.stderr)
        return EXIT_WRITE_FAILED
    print(format_summary(report, args.bank, args.out))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
