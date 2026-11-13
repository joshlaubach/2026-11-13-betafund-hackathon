"""Tests for scripts/audit_bank.py.

Synthetic-problem tests exercise the pure classification and report functions.
Real-bank tests load docs/verified_problems.json and check the audit outcome
recorded in PLAN.md.
"""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.audit_bank import (  # noqa: E402
    build_report,
    classify,
    load_bank,
    main,
)

SCRIPT = REPO_ROOT / "scripts" / "audit_bank.py"
BANK_PATH = REPO_ROOT / "docs" / "verified_problems.json"

KNOWN_EXCLUDED_IDS = (
    {"OS19", "OS22", "OS29", "OS35", "OS39"}
    | {f"RG{n:02d}" for n in range(1, 21)}
    | {f"IG{n:02d}" for n in range(1, 21)}
)
ALLOWED_REASONS = {"figure_reference", "undefined_function"}


def make_problem(statement, level=1, problem_id="T01", topic="test_topic"):
    return {
        "id": problem_id,
        "topic": topic,
        "level": level,
        "statement": statement,
    }


# ---------------------------------------------------------------------------
# classify: synthetic problems
# ---------------------------------------------------------------------------


def test_figure_reference_is_excluded_as_figure_reference():
    problem = make_problem("The figure shows the graph of $y = f(x)$. Find the area.")
    assert classify(problem) == "figure_reference"


def test_graph_with_explicit_equation_is_not_flagged():
    problem = make_problem("Sketch the graph of $f(x) = x^2$ and find its vertex.")
    assert classify(problem) is None


def test_limit_of_undefined_function_is_undefined_function():
    problem = make_problem(r"Evaluate $\lim_{x \to 4} f(x)$.")
    assert classify(problem) == "undefined_function"


def test_function_application_with_equals_is_eligible():
    problem = make_problem(r"Evaluate $\lim_{x \to 4} f(x)$ where $f(x) = x^2$.")
    assert classify(problem) is None


def test_function_application_with_given_is_eligible():
    problem = make_problem(r"Given $\int_0^2 f(x)\,dx = 5$, find $\int_0^2 3 f(x)\,dx$. Assume f is integrable. f(x) is continuous.")
    assert classify(problem) is None


def test_function_application_with_given_word_only_is_eligible():
    problem = make_problem("Given that f(2) is known, find the derivative of f at 2.")
    assert classify(problem) is None


def test_figure_and_undefined_both_apply_gives_figure_reference():
    problem = make_problem("The figure shows f(x) for 0 <= x <= 2. Find the area.")
    assert classify(problem) == "figure_reference"


def test_word_given_matches_whole_words_only_in_any_case():
    problem = make_problem("GIVEN the values, find f(3) for the curve.")
    assert classify(problem) is None


@pytest.mark.parametrize(
    "statement",
    [
        "Use the table below to find the average rate of change.",
        "Use the values in the table to estimate the limit.",
        "Read the value from the chart.",
        "Using the graph, estimate the slope at x = 2.",
        "The region is shown in the diagram.",
        "The region is shown below.",
        "The region is shown above.",
        "Read the extrema from the graph of the function.",
        "Use the table above.",
    ],
)
def test_figure_phrases_are_flagged(statement):
    assert classify(make_problem(statement)) == "figure_reference"


def test_plain_problem_is_eligible():
    assert classify(make_problem(r"Evaluate $\int_0^1 x\,dx$.")) is None


def test_level_5_is_classified_as_level_5_even_with_figure_text():
    problem = make_problem("The figure shows the graph of y = f(x).", level=5)
    assert classify(problem) == "level_5"


def test_function_application_inside_latex_form_is_detected():
    problem = make_problem(r"Find $\frac{d}{dx} f{\left(x \right)}$ at $x = 1$.")
    assert classify(problem) is None
    problem_no_equals = make_problem(r"Find $\frac{d}{dx} f{\left(x \right)}$ at the point.")
    assert classify(problem_no_equals) == "undefined_function"


def test_derivative_application_is_detected():
    problem = make_problem("Find f'(2) for the curve.")
    assert classify(problem) == "undefined_function"


# ---------------------------------------------------------------------------
# build_report: synthetic bank
# ---------------------------------------------------------------------------


def test_level_5_goes_only_to_level_5_count():
    bank = [
        make_problem("Evaluate the integral.", level=5, problem_id="L5"),
        make_problem("Evaluate the integral.", level=1, problem_id="L1"),
    ]
    report = build_report(bank)
    assert report["level_5_count"] == 1
    assert report["total"] == 2
    assert report["audited_count"] == 1
    assert [entry["id"] for entry in report["eligible"]] == ["L1"]
    assert report["excluded"] == []


def test_report_counts_and_reasons_on_synthetic_bank():
    bank = [
        make_problem("The figure shows f(x).", level=2, problem_id="B"),
        make_problem(r"Evaluate $\lim_{x \to 4} f(x)$.", level=3, problem_id="A"),
        make_problem("Evaluate $\\int_0^1 x\\,dx$.", level=4, problem_id="C"),
    ]
    report = build_report(bank)
    assert [entry["id"] for entry in report["eligible"]] == ["C"]
    assert report["eligible_count"] == 1
    assert [row["id"] for row in report["excluded"]] == ["A", "B"]
    assert report["excluded"][0]["reason"] == "undefined_function"
    assert report["excluded"][1]["reason"] == "figure_reference"
    assert report["excluded_by_reason"] == {"figure_reference": 1, "undefined_function": 1}
    assert report["eligible_by_level"] == {"1": 0, "2": 0, "3": 0, "4": 1}
    assert report["eligible_by_topic_level"]["test_topic"] == {"1": 0, "2": 0, "3": 0, "4": 1}


def test_build_report_does_not_mutate_input():
    bank = [
        make_problem("The figure shows f(x).", level=2, problem_id="B"),
        make_problem("Evaluate $\\int_0^1 x\\,dx$.", level=5, problem_id="C"),
    ]
    snapshot = copy.deepcopy(bank)
    build_report(bank)
    assert bank == snapshot


def test_main_returns_2_for_missing_file(tmp_path):
    code = main(["--bank", str(tmp_path / "missing.json"), "--out", str(tmp_path / "r.json")])
    assert code == 2


def test_cli_exits_2_for_missing_file(tmp_path):
    result = subprocess.run(
        [sys.executable, "-I", str(SCRIPT), "--bank", str(tmp_path / "missing.json"),
         "--out", str(tmp_path / "r.json")],
        capture_output=True, text=True,
    )
    assert result.returncode == 2
    assert result.stderr.strip() != ""


def test_cli_exits_2_for_invalid_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("[{not json", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-I", str(SCRIPT), "--bank", str(bad), "--out", str(tmp_path / "r.json")],
        capture_output=True, text=True,
    )
    assert result.returncode == 2
    assert result.stderr.strip() != ""


def test_load_bank_rejects_non_list(tmp_path):
    path = tmp_path / "obj.json"
    path.write_text(json.dumps({"id": "X"}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_bank(path)


@pytest.mark.parametrize("missing_key", ["id", "level", "statement"])
def test_load_bank_rejects_entry_missing_required_key(tmp_path, missing_key):
    entry = make_problem("Evaluate $\\int_0^1 x\\,dx$.")
    del entry[missing_key]
    path = tmp_path / "bank.json"
    path.write_text(json.dumps([entry]), encoding="utf-8")
    with pytest.raises(ValueError):
        load_bank(path)


def test_cli_exits_2_for_entry_missing_id(tmp_path):
    entry = make_problem("Evaluate $\\int_0^1 x\\,dx$.")
    del entry["id"]
    bank = tmp_path / "bank.json"
    bank.write_text(json.dumps([entry]), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-I", str(SCRIPT), "--bank", str(bank), "--out", str(tmp_path / "r.json")],
        capture_output=True, text=True,
    )
    assert result.returncode == 2


def test_cli_writes_report_for_small_bank(tmp_path):
    bank = tmp_path / "bank.json"
    bank.write_text(json.dumps([make_problem("Evaluate $\\int_0^1 x\\,dx$.")]), encoding="utf-8")
    out = tmp_path / "nested" / "report.json"
    result = subprocess.run(
        [sys.executable, "-I", str(SCRIPT), "--bank", str(bank), "--out", str(out)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["eligible_count"] == 1


# ---------------------------------------------------------------------------
# Real bank: docs/verified_problems.json
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_report():
    bank = load_bank(BANK_PATH)
    return build_report(bank)


def test_real_bank_totals(real_report):
    assert real_report["total"] == 3510
    assert real_report["level_5_count"] == 60
    assert real_report["audited_count"] == 3450


def test_known_ids_are_excluded(real_report):
    excluded_ids = {row["id"] for row in real_report["excluded"]}
    missing = sorted(KNOWN_EXCLUDED_IDS - excluded_ids)
    assert missing == []


def test_c44_01_is_eligible(real_report):
    topics = {p["topic"] for p in load_bank(BANK_PATH) if p["id"] == "C44-01"}
    assert topics, "C44-01 must exist in the bank"
    eligible_pairs = {(e["topic"], e["id"]) for e in real_report["eligible"]}
    for topic in topics:
        assert (topic, "C44-01") in eligible_pairs
    assert "C44-01" not in {row["id"] for row in real_report["excluded"]}


def test_eligible_has_exactly_eligible_count_entries(real_report):
    assert len(real_report["eligible"]) == real_report["eligible_count"]


def test_eligible_entries_have_id_topic_level(real_report):
    for entry in real_report["eligible"]:
        assert {"id", "topic", "level"} <= set(entry)


def test_eligible_topic_id_pairs_are_distinct(real_report):
    pairs = [(e["topic"], e["id"]) for e in real_report["eligible"]]
    assert len(pairs) == len(set(pairs))


def test_eligible_contains_shared_id_in_both_topics(real_report):
    pairs = {(e["topic"], e["id"]) for e in real_report["eligible"]}
    assert ("absolute_extrema", "AE01") in pairs
    assert ("alternating_error", "AE01") in pairs


def test_report_has_no_eligible_ids_key(real_report):
    assert "eligible_ids" not in real_report


def test_synthetic_shared_id_in_two_topics_gives_two_entries():
    bank = [
        make_problem("Evaluate $\\int_0^1 x\\,dx$.", level=1, problem_id="AE01", topic="absolute_extrema"),
        make_problem("Evaluate $\\int_0^1 x\\,dx$.", level=2, problem_id="AE01", topic="alternating_error"),
    ]
    report = build_report(bank)
    assert report["eligible"] == [
        {"id": "AE01", "topic": "absolute_extrema", "level": 1},
        {"id": "AE01", "topic": "alternating_error", "level": 2},
    ]


def test_eligible_plus_excluded_equals_audited(real_report):
    assert real_report["eligible_count"] + len(real_report["excluded"]) == real_report["audited_count"]


def test_excluded_reasons_are_allowed(real_report):
    reasons = {row["reason"] for row in real_report["excluded"]}
    assert reasons <= ALLOWED_REASONS


def test_real_report_has_every_required_key(real_report):
    required = {
        "total", "level_5_count", "audited_count", "eligible_count", "eligible",
        "excluded", "excluded_by_reason", "eligible_by_level", "eligible_by_topic_level",
    }
    assert required <= set(real_report)


def test_real_bank_is_not_mutated():
    bank = load_bank(BANK_PATH)
    snapshot = copy.deepcopy(bank)
    build_report(bank)
    assert bank == snapshot
