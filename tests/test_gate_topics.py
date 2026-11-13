"""Tests for scripts/gate_topics.py, the read-only per-topic derivative gate probe.

Synthetic-problem tests exercise the selection, category, and table logic with a
handful of fake bank entries. One smoke test runs the probe on power_rule and
checks it against scripts/gate_power_rule.py.
"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts import gate_power_rule  # noqa: E402
from scripts import gate_topics  # noqa: E402
from scripts.gate_topics import (  # noqa: E402
    BAR_FAIL,
    BAR_INSUFFICIENT,
    BAR_PASS,
    CAT_FUNCTION,
    CAT_KEY,
    CAT_MISMATCH,
    CAT_STATEMENT,
    bar_verdict,
    eligible_pool,
    evaluate_problem,
    format_table,
    main,
    probe_topic,
    summarize_topic,
)

STATEMENT_SQUARE = r"Find $f'(x)$ for $f(x) = x^{2}$."
STATEMENT_UNPARSABLE = "Evaluate the derivative of the given curve."
STATEMENT_FUNCTION_BAD = r"Find $f'(x)$ for $f(x) = 3^{x}$."


def make_problem(
    problem_id: str,
    statement: str,
    latex: str,
    level: int = 1,
    answer_type: str = "expression",
    topic: str = "power_rule",
) -> dict:
    return {
        "id": problem_id,
        "topic": topic,
        "level": level,
        "statement": statement,
        "answer": {"type": answer_type, "latex": latex},
    }


def test_eligible_pool_keeps_audited_levels_1_to_4_with_matching_answer_type():
    bank = [
        make_problem("A1", STATEMENT_SQUARE, "2 x"),
        make_problem("A2", STATEMENT_SQUARE, "2 x", level=5),
        make_problem("A3", "Find $f'(x)$ for $f(x) = x^{2}$ shown in the figure.", "2 x"),
        make_problem("A4", STATEMENT_SQUARE, "2 x", answer_type="enum"),
        make_problem("A5", STATEMENT_SQUARE, "   ", level=2),
        make_problem("A6", STATEMENT_SQUARE, "2 x", topic="other_topic"),
    ]

    pool, dropped_by_type = eligible_pool(bank, "power_rule")

    assert [problem["id"] for problem in pool] == ["A1"]
    assert dropped_by_type == 2


def test_eligible_pool_keys_by_topic_so_shared_ids_do_not_collide():
    bank = [
        make_problem("AE01", STATEMENT_SQUARE, "2 x", topic="power_rule"),
        make_problem("AE01", STATEMENT_SQUARE, "2 x", topic="rules"),
    ]

    pool, _ = eligible_pool(bank, "rules")

    assert len(pool) == 1
    assert pool[0]["topic"] == "rules"


def test_accepted_problem_runs_three_negatives_all_rejected():
    problem = make_problem("P1", STATEMENT_SQUARE, "2 x")

    record = evaluate_problem(problem)

    assert record["supported"] is True
    assert record["accepted"] is True
    assert record["category"] is None
    assert record["negatives"]["tried"] == 3
    assert record["negatives"]["rejected"] == 3
    assert record["negatives"]["accepted"] == 0


def test_non_accepted_problems_get_the_expected_categories():
    statement_bad = evaluate_problem(make_problem("S1", STATEMENT_UNPARSABLE, "2 x"))
    mismatch = evaluate_problem(make_problem("M1", STATEMENT_SQUARE, "3 x"))
    key_bad = evaluate_problem(make_problem("K1", STATEMENT_SQUARE, r"\foo{x}"))
    function_bad = evaluate_problem(make_problem("F1", STATEMENT_FUNCTION_BAD, "x"))

    assert statement_bad["category"] == CAT_STATEMENT
    assert statement_bad["supported"] is False
    assert mismatch["category"] == CAT_MISMATCH
    assert mismatch["supported"] is True
    assert mismatch["negatives"] is None
    assert key_bad["category"] == CAT_KEY
    assert key_bad["supported"] is True
    assert function_bad["category"] == CAT_FUNCTION
    assert function_bad["supported"] is False


def test_summarize_topic_counts_accepted_and_top_category():
    records = [
        evaluate_problem(make_problem("P1", STATEMENT_SQUARE, "2 x", level=1)),
        evaluate_problem(make_problem("P2", STATEMENT_SQUARE, "2 x", level=2)),
        evaluate_problem(make_problem("P3", STATEMENT_SQUARE, "3 x", level=3)),
        evaluate_problem(make_problem("P4", STATEMENT_UNPARSABLE, "2 x", level=4)),
    ]

    row = summarize_topic("power_rule", records, dropped_by_type=2)

    assert row["eligible"] == 4
    assert row["accepted"] == 2
    assert row["accept_pct"] == 50.0
    assert row["supported"] == 3
    assert row["dropped_by_answer_type"] == 2
    assert row["negatives"]["tried"] == 6
    assert row["negatives"]["rejected"] == 6
    assert row["top_category"] == CAT_MISMATCH
    assert row["categories"][CAT_STATEMENT]["count"] == 1
    assert row["categories"][CAT_MISMATCH]["examples"][0]["id"] == "P3"


def test_category_examples_are_capped_at_three():
    records = [
        evaluate_problem(make_problem(f"U{index}", STATEMENT_UNPARSABLE, "2 x"))
        for index in range(5)
    ]

    row = summarize_topic("power_rule", records, dropped_by_type=0)

    assert row["categories"][CAT_STATEMENT]["count"] == 5
    assert len(row["categories"][CAT_STATEMENT]["examples"]) == 3


def test_empty_topic_is_insufficient_with_no_top_category():
    row = summarize_topic("empty", [], dropped_by_type=0)

    assert row["eligible"] == 0
    assert row["accept_pct"] == 0.0
    assert row["top_category"] == "-"
    assert row["bar"] == BAR_INSUFFICIENT


def test_bar_verdict_pass_fail_insufficient():
    assert bar_verdict(40, 0.95, 38, False, [], 0) == BAR_PASS
    assert bar_verdict(40, 0.95, 38, False, [], 1) == BAR_FAIL
    assert bar_verdict(40, 0.50, 20, False, ["parse rate"], 0) == BAR_FAIL
    assert bar_verdict(5, 1.0, 5, False, ["only 5"], 0) == BAR_INSUFFICIENT
    assert bar_verdict(40, 1.0, 20, True, ["levels"], 0) == BAR_INSUFFICIENT


def test_bar_thresholds_are_the_power_rule_gate_constants():
    assert gate_topics.MIN_PARSE_RATE is gate_power_rule.MIN_PARSE_RATE
    assert gate_topics.MIN_TESTED is gate_power_rule.MIN_TESTED
    assert gate_topics.MAX_LEVELS_REQUIRED is gate_power_rule.MAX_LEVELS_REQUIRED


def test_format_table_prints_headers_and_one_line_per_row():
    rows = [
        summarize_topic("power_rule", [evaluate_problem(make_problem("P1", STATEMENT_SQUARE, "2 x"))], 0),
        summarize_topic("empty", [], 0),
    ]

    table = format_table(rows)
    lines = table.splitlines()

    assert lines[0].startswith("topic")
    assert "bar" in lines[0]
    assert lines[2].startswith("power_rule")
    assert lines[3].startswith("empty")


def test_probe_topic_on_fixture_bank_matches_gate_style_counts():
    bank = [
        make_problem("P1", STATEMENT_SQUARE, "2 x"),
        make_problem("P2", STATEMENT_SQUARE, "3 x"),
    ]

    row = probe_topic(bank, "power_rule")

    assert row["eligible"] == 2
    assert row["accepted"] == 1
    # One mismatch is a positive failure, which is FAIL before sample size is considered.
    assert row["bar"] == BAR_FAIL


def test_main_writes_report_only_to_the_output_path(tmp_path, monkeypatch, capsys):
    out_path = tmp_path / "gate_topics.json"
    monkeypatch.setattr(gate_topics, "OUTPUT_PATH", out_path)

    exit_code = main(["--topics", "power_rule"])

    assert exit_code == 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["topics"][0]["topic"] == "power_rule"
    assert "power_rule" in capsys.readouterr().out


def test_power_rule_probe_matches_gate_power_rule():
    raw = gate_power_rule.BANK_PATH.read_bytes()
    bank = json.loads(raw.decode("utf-8"))
    gate_records = [gate_power_rule.evaluate_problem(p) for p in gate_power_rule.select_problems(bank)]
    gate_summary = gate_power_rule.summarize(gate_records)

    row = probe_topic(bank, "power_rule")

    assert row["eligible"] == gate_summary["eligible"]
    assert row["accepted"] == gate_summary["positive_passed"]
    assert (row["bar"] == BAR_PASS) == gate_summary["enabled"]
