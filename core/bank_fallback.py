"""Serve labeled bank problems for topics the Echo checker does not cover yet.

A topic is echo_checked only when a gate file in build_dir says its gate is
enabled. Every other topic that has an eligible bank problem is served as
bank_fallback. A topic with no eligible problem at all is unsupported.
Eligibility comes from scripts/audit_bank.py. Standard library only.
"""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path
from typing import Optional, Union

from scripts.audit_bank import (
    AUDITED_LEVELS,
    build_report,
    classify,
    load_bank,
    parse_level,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_DIR = REPO_ROOT / "build"
BANK_PATH = REPO_ROOT / "docs" / "verified_problems.json"

GATE_PREFIX = "gate_"
GATE_GLOB = GATE_PREFIX + "*.json"
GATE_ENABLED_KEY = "enabled"
GATE_FAILURE_KEYS = ("positive_failed", "negative_failed")
GATE_HASH_KEY = "bank_sha256"

STATUS_ECHO_CHECKED = "echo_checked"
STATUS_BANK_FALLBACK = "bank_fallback"
STATUS_UNSUPPORTED = "unsupported"

LABEL_BANK_FALLBACK = "bank-verified, not Echo-checked"
LABEL_ECHO_CHECKED = (
    "Echo-checked topic: AI drafts are verified by the checker; "
    "showing verified bank problems until drafts are generated"
)
LABEL_UNSUPPORTED = "Not supported yet: no usable verified problems for this topic"

BuildDir = Union[str, Path]


def _read_json(path: Path) -> object:
    """Return the parsed JSON in path, or None when it is unreadable or invalid."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def bank_sha256() -> Optional[str]:
    """SHA-256 of the current bank file bytes, or None when the bank cannot be read."""
    try:
        return hashlib.sha256(BANK_PATH.read_bytes()).hexdigest()
    except OSError:
        return None


def _is_zero_count(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value == 0


def _gate_is_trusted(path: Path, data: object, bank_hash: Optional[str]) -> bool:
    """True only for a gate record that is enabled, failure-free, and bound to the current bank.

    The file must be named gate_<topic>.json for the topic it records, and its
    bank_sha256 must equal the hash of the bank file as it is now. Any missing
    or mistyped field means the gate is not trusted.
    """
    if not isinstance(data, dict) or not isinstance(data.get("topic"), str):
        return False
    if bank_hash is None or data.get(GATE_HASH_KEY) != bank_hash:
        return False
    if path.stem != GATE_PREFIX + data["topic"]:
        return False
    if data.get(GATE_ENABLED_KEY) is not True:
        return False
    return all(_is_zero_count(data.get(key)) for key in GATE_FAILURE_KEYS)


def echo_checked_topics(build_dir: BuildDir = BUILD_DIR) -> set[str]:
    """Topics whose gate file in build_dir is trusted. Missing or corrupt files do not count."""
    bank_hash = bank_sha256()
    topics: set[str] = set()
    for path in Path(build_dir).glob(GATE_GLOB):
        data = _read_json(path)
        if _gate_is_trusted(path, data, bank_hash):
            topics.add(data["topic"])
    return topics


def _validate_level(level: object) -> int:
    if isinstance(level, bool) or not isinstance(level, int) or level not in AUDITED_LEVELS:
        raise ValueError(f"level must be one of {AUDITED_LEVELS}, got {level!r}")
    return level


def _validate_count(count: object) -> int:
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ValueError(f"count must be a positive integer, got {count!r}")
    return count


def _eligible_problems() -> list[dict]:
    """Bank problems that pass the audit. Reads the bank fresh; never mutates it."""
    bank = load_bank(BANK_PATH)
    return [problem for problem in bank if classify(problem) is None]


def _pool_by_level(topic: str) -> dict[int, list[dict]]:
    """Eligible problems of one topic grouped by level, one per (topic, id)."""
    by_level: dict[int, list[dict]] = {level: [] for level in AUDITED_LEVELS}
    seen: set[str] = set()
    for problem in _eligible_problems():
        if problem["topic"] != topic:
            continue
        problem_id = str(problem["id"])
        if problem_id in seen:
            continue
        seen.add(problem_id)
        by_level[parse_level(problem)].append(problem)
    return by_level


def _level_order(level: int) -> list[int]:
    """The requested level first, then the other levels nearest first (lower wins ties)."""
    others = sorted(
        (other for other in AUDITED_LEVELS if other != level),
        key=lambda other: (abs(other - level), other),
    )
    return [level, *others]


def _choose(
    by_level: dict[int, list[dict]], level: int, count: int, seed: Optional[int]
) -> list[tuple[dict, int]]:
    """Pick up to count (problem, actual_level) pairs, deterministic for a given seed."""
    rng = random.Random(seed)
    chosen: list[tuple[dict, int]] = []
    for actual in _level_order(level):
        candidates = sorted(by_level[actual], key=lambda problem: str(problem["id"]))
        rng.shuffle(candidates)
        for problem in candidates:
            if len(chosen) == count:
                return chosen
            chosen.append((problem, actual))
    return chosen


def _shape(problem: dict, requested: int, actual: int) -> dict:
    """Output record for one problem. Copies mutable fields so the bank is never shared."""
    answer = problem.get("answer") or {}
    shaped = {
        "topic": problem["topic"],
        "id": str(problem["id"]),
        "level": actual,
        "statement": problem["statement"],
        "answer_latex": answer.get("latex", ""),
        "steps": list(problem.get("steps") or []),
    }
    if actual != requested:
        shaped["level_note"] = (
            f"actual level {actual}; no unused level {requested} problem is left for this topic"
        )
    return shaped


def _result(status: str, label: str, topic: str, level: int, problems: list[dict]) -> dict:
    return {
        "status": status,
        "label": label,
        "topic": topic,
        "level": level,
        "problems": problems,
    }


def serve(
    topic: str,
    level: int,
    count: int = 3,
    seed: Optional[int] = None,
    build_dir: BuildDir = BUILD_DIR,
) -> dict:
    """Serve up to count eligible bank problems for topic, nearest level first.

    Raises ValueError for a level outside 1 to 4 or a non-positive count.
    An unknown topic, or one with no eligible problem, returns unsupported.
    """
    requested = _validate_level(level)
    limit = _validate_count(count)
    chosen = _choose(_pool_by_level(topic), requested, limit, seed)
    if not chosen:
        return _result(STATUS_UNSUPPORTED, LABEL_UNSUPPORTED, topic, requested, [])
    if topic in echo_checked_topics(build_dir):
        status, label = STATUS_ECHO_CHECKED, LABEL_ECHO_CHECKED
    else:
        status, label = STATUS_BANK_FALLBACK, LABEL_BANK_FALLBACK
    problems = [_shape(problem, requested, actual) for problem, actual in chosen]
    return _result(status, label, topic, requested, problems)


def describe_coverage(build_dir: BuildDir = BUILD_DIR) -> dict:
    """Counts for the coverage line: bank topics, servable topics, echo-checked, eligible problems."""
    bank = load_bank(BANK_PATH)
    report = build_report(bank)
    bank_topics = {problem["topic"] for problem in bank}
    eligible_topics = {row["topic"] for row in report["eligible"]}
    echo_topics = echo_checked_topics(build_dir) & bank_topics
    return {
        "topics_in_bank": len(bank_topics),
        "topics_with_eligible": len(eligible_topics),
        "echo_checked": len(echo_topics),
        "eligible_problems": report["eligible_count"],
    }
