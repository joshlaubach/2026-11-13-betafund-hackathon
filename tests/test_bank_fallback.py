"""Tests for core/bank_fallback.py.

Synthetic banks (written to tmp_path and swapped in through BANK_PATH) cover the
serving rules. Real-bank tests load docs/verified_problems.json and check the
audit exclusions and the coverage counts.
"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core import bank_fallback  # noqa: E402
from core.bank_fallback import (  # noqa: E402
    LABEL_BANK_FALLBACK,
    LABEL_ECHO_CHECKED,
    LABEL_UNSUPPORTED,
    STATUS_BANK_FALLBACK,
    STATUS_ECHO_CHECKED,
    STATUS_UNSUPPORTED,
    describe_coverage,
    echo_checked_topics,
    serve,
)
from scripts.audit_bank import build_report, classify, load_bank, parse_level  # noqa: E402

REAL_BANK = REPO_ROOT / "docs" / "verified_problems.json"
ALL_LEVELS = (1, 2, 3, 4)


def make_problem(problem_id, topic="synthetic", level=1, statement=None):
    return {
        "course": "calc1",
        "unit": "test",
        "topic": topic,
        "topic_title": topic,
        "calculator": False,
        "id": problem_id,
        "level": level,
        "statement": statement or f"Evaluate the integral number {problem_id}.",
        "answer": {"type": "numeric", "latex": "1", "sympy": "1", "numeric": 1},
        "steps": [f"step for {problem_id}"],
        "method": "test",
        "source_file": "test",
    }


def use_bank(monkeypatch, tmp_path, problems):
    path = tmp_path / "bank.json"
    path.write_text(json.dumps(problems), encoding="utf-8")
    monkeypatch.setattr(bank_fallback, "BANK_PATH", path)
    return path


def write_gate(build_dir, topic, payload):
    build_dir.mkdir(parents=True, exist_ok=True)
    name = "gate_" + topic.replace("/", "_") + ".json"
    (build_dir / name).write_text(json.dumps(payload), encoding="utf-8")


def gate_payload(topic, **overrides):
    """A gate record that is fully trusted against the bank file as it is now."""
    payload = {
        "topic": topic,
        "enabled": True,
        "positive_failed": 0,
        "negative_failed": 0,
        "bank_sha256": bank_fallback.bank_sha256(),
    }
    payload.update(overrides)
    return payload


def keys_of(result):
    return [(problem["topic"], problem["id"]) for problem in result["problems"]]


@pytest.fixture
def build_dir(tmp_path):
    path = tmp_path / "build"
    path.mkdir()
    return path


# ---------------------------------------------------------------------------
# Gate files: echo_checked vs bank_fallback
# ---------------------------------------------------------------------------


def test_enabled_gate_makes_topic_echo_checked(monkeypatch, tmp_path, build_dir):
    use_bank(monkeypatch, tmp_path, [make_problem(f"P{n}", topic="power_rule", level=2) for n in range(3)])
    write_gate(build_dir, "power_rule", gate_payload("power_rule"))
    result = serve("power_rule", 2, build_dir=build_dir)
    assert result["status"] == STATUS_ECHO_CHECKED
    assert result["label"] == LABEL_ECHO_CHECKED
    assert len(result["problems"]) == 3


def test_legacy_gate_enabled_key_is_not_trusted(monkeypatch, tmp_path, build_dir):
    use_bank(monkeypatch, tmp_path, [make_problem("P1", topic="power_rule", level=1)])
    payload = gate_payload("power_rule")
    del payload["enabled"]
    payload["gate_enabled"] = True
    write_gate(build_dir, "power_rule", payload)
    assert echo_checked_topics(build_dir) == set()


def test_mismatched_filename_is_not_echo_checked(monkeypatch, tmp_path, build_dir):
    use_bank(monkeypatch, tmp_path, [make_problem("P1", topic="power_rule", level=1)])
    build_dir.mkdir(parents=True, exist_ok=True)
    (build_dir / "gate_other.json").write_text(
        json.dumps(gate_payload("power_rule")), encoding="utf-8"
    )
    assert echo_checked_topics(build_dir) == set()


@pytest.mark.parametrize(
    "overrides",
    [
        {"positive_failed": 1},
        {"negative_failed": 1},
        {"positive_failed": False},
        {"bank_sha256": "0" * 64},
        {"bank_sha256": None},
        {"enabled": "yes"},
    ],
)
def test_untrusted_gate_fields_are_not_echo_checked(monkeypatch, tmp_path, build_dir, overrides):
    use_bank(monkeypatch, tmp_path, [make_problem("P1", topic="power_rule", level=1)])
    write_gate(build_dir, "power_rule", gate_payload("power_rule", **overrides))
    assert echo_checked_topics(build_dir) == set()
    assert serve("power_rule", 1, build_dir=build_dir)["status"] == STATUS_BANK_FALLBACK


@pytest.mark.parametrize("missing", ["positive_failed", "negative_failed", "bank_sha256"])
def test_gate_missing_a_required_field_is_not_echo_checked(
    monkeypatch, tmp_path, build_dir, missing
):
    use_bank(monkeypatch, tmp_path, [make_problem("P1", topic="power_rule", level=1)])
    payload = gate_payload("power_rule")
    del payload[missing]
    write_gate(build_dir, "power_rule", payload)
    assert echo_checked_topics(build_dir) == set()


def test_gate_bound_to_current_bank_is_echo_checked(monkeypatch, tmp_path, build_dir):
    use_bank(monkeypatch, tmp_path, [make_problem("P1", topic="power_rule", level=1)])
    write_gate(build_dir, "power_rule", gate_payload("power_rule"))
    assert echo_checked_topics(build_dir) == {"power_rule"}


def test_no_gate_file_is_bank_fallback(monkeypatch, tmp_path, build_dir):
    use_bank(monkeypatch, tmp_path, [make_problem("P1", topic="power_rule", level=1)])
    result = serve("power_rule", 1, build_dir=build_dir)
    assert result["status"] == STATUS_BANK_FALLBACK
    assert result["label"] == LABEL_BANK_FALLBACK


def test_disabled_gate_is_not_echo_checked(monkeypatch, tmp_path, build_dir):
    use_bank(monkeypatch, tmp_path, [make_problem("P1", topic="power_rule", level=1)])
    write_gate(build_dir, "power_rule", gate_payload("power_rule", enabled=False))
    assert echo_checked_topics(build_dir) == set()
    assert serve("power_rule", 1, build_dir=build_dir)["status"] == STATUS_BANK_FALLBACK


@pytest.mark.parametrize(
    "content",
    [
        "{not json",
        "[1, 2, 3]",
        '{"gate_enabled": true}',
        '{"topic": 5, "gate_enabled": true}',
        "",
    ],
)
def test_corrupt_gate_file_is_not_echo_checked(monkeypatch, tmp_path, build_dir, content):
    use_bank(monkeypatch, tmp_path, [make_problem("P1", topic="power_rule", level=1)])
    (build_dir / "gate_power_rule.json").write_text(content, encoding="utf-8")
    assert echo_checked_topics(build_dir) == set()
    assert serve("power_rule", 1, build_dir=build_dir)["status"] == STATUS_BANK_FALLBACK


def test_missing_build_dir_gives_no_echo_topics(tmp_path):
    assert echo_checked_topics(tmp_path / "does_not_exist") == set()


def test_gate_names_only_its_own_topic(monkeypatch, tmp_path, build_dir):
    use_bank(monkeypatch, tmp_path, [make_problem("P1", topic="other", level=1)])
    write_gate(build_dir, "power_rule", gate_payload("power_rule"))
    assert serve("other", 1, build_dir=build_dir)["status"] == STATUS_BANK_FALLBACK


# ---------------------------------------------------------------------------
# Labels, unsupported, and argument errors
# ---------------------------------------------------------------------------


def test_labels_are_exact_text():
    assert LABEL_BANK_FALLBACK == "bank-verified, not Echo-checked"
    assert LABEL_ECHO_CHECKED == (
        "Echo-checked topic: AI drafts are verified by the checker; "
        "showing verified bank problems until drafts are generated"
    )
    assert LABEL_UNSUPPORTED == "Not supported yet: no usable verified problems for this topic"


def test_unknown_topic_is_unsupported(build_dir):
    result = serve("no_such_topic", 2, build_dir=build_dir)
    assert result == {
        "status": STATUS_UNSUPPORTED,
        "label": LABEL_UNSUPPORTED,
        "topic": "no_such_topic",
        "level": 2,
        "problems": [],
    }


def test_topic_with_only_level_5_is_unsupported(monkeypatch, tmp_path, build_dir):
    use_bank(monkeypatch, tmp_path, [make_problem("P1", topic="top", level=5)])
    result = serve("top", 1, build_dir=build_dir)
    assert result["status"] == STATUS_UNSUPPORTED
    assert result["problems"] == []


@pytest.mark.parametrize("level", [0, 5, -1, "2", True, None, 2.0])
def test_bad_level_raises_value_error(build_dir, level):
    with pytest.raises(ValueError):
        serve("power_rule", level, build_dir=build_dir)


@pytest.mark.parametrize("count", [0, -1, "3", True])
def test_bad_count_raises_value_error(build_dir, count):
    with pytest.raises(ValueError):
        serve("power_rule", 1, count=count, build_dir=build_dir)


# ---------------------------------------------------------------------------
# Selection: levels, fill-in, duplicates, determinism, audit exclusions
# ---------------------------------------------------------------------------


def test_string_level_in_bank_is_normalized_to_int(monkeypatch, tmp_path, build_dir):
    use_bank(monkeypatch, tmp_path, [make_problem("P1", topic="t", level="2")])
    result = serve("t", 2, build_dir=build_dir)
    assert result["problems"][0]["level"] == 2
    assert isinstance(result["problems"][0]["level"], int)
    assert "level_note" not in result["problems"][0]


def test_level_fill_in_sets_level_note(monkeypatch, tmp_path, build_dir):
    use_bank(
        monkeypatch,
        tmp_path,
        [
            make_problem("A", topic="t", level=1),
            make_problem("B", topic="t", level=2),
            make_problem("C", topic="t", level=3),
        ],
    )
    result = serve("t", 1, count=3, seed=0, build_dir=build_dir)
    levels = [problem["level"] for problem in result["problems"]]
    assert levels == [1, 2, 3]
    assert "level_note" not in result["problems"][0]
    for problem in result["problems"][1:]:
        assert problem["level_note"].startswith(f"actual level {problem['level']};")


def test_fewer_problems_than_count_returns_what_exists(monkeypatch, tmp_path, build_dir):
    use_bank(monkeypatch, tmp_path, [make_problem("A", topic="t", level=1)])
    result = serve("t", 1, count=3, build_dir=build_dir)
    assert result["status"] == STATUS_BANK_FALLBACK
    assert len(result["problems"]) == 1


def test_excluded_ids_are_never_served(monkeypatch, tmp_path, build_dir):
    use_bank(
        monkeypatch,
        tmp_path,
        [
            make_problem("FIG", topic="t", level=1, statement="The figure shows f(x) on [0, 2]."),
            make_problem("OK", topic="t", level=1),
            make_problem("FIG5", topic="t", level=5, statement="The figure shows the graph."),
        ],
    )
    result = serve("t", 1, count=10, build_dir=build_dir)
    assert [problem["id"] for problem in result["problems"]] == ["OK"]


def test_served_pairs_are_unique_when_ids_repeat_across_topics(monkeypatch, tmp_path, build_dir):
    use_bank(
        monkeypatch,
        tmp_path,
        [
            make_problem("AE01", topic="absolute_extrema", level=1),
            make_problem("AE01", topic="alternating_error", level=2),
            make_problem("AE02", topic="absolute_extrema", level=2),
        ],
    )
    result = serve("absolute_extrema", 1, count=10, build_dir=build_dir)
    assert keys_of(result) == [("absolute_extrema", "AE01"), ("absolute_extrema", "AE02")]


def test_served_problems_have_no_duplicates(monkeypatch, tmp_path, build_dir):
    use_bank(
        monkeypatch,
        tmp_path,
        [make_problem(f"P{n}", topic="t", level=1 + n % 4) for n in range(20)],
    )
    for seed in range(5):
        keys = keys_of(serve("t", 2, count=10, seed=seed, build_dir=build_dir))
        assert len(keys) == len(set(keys))


def test_same_seed_gives_same_output(monkeypatch, tmp_path, build_dir):
    use_bank(
        monkeypatch,
        tmp_path,
        [make_problem(f"P{n}", topic="t", level=1 + n % 2) for n in range(12)],
    )
    first = serve("t", 1, count=3, seed=7, build_dir=build_dir)
    second = serve("t", 1, count=3, seed=7, build_dir=build_dir)
    assert first == second


def test_bank_is_not_mutated_by_serving(monkeypatch, tmp_path, build_dir):
    path = use_bank(
        monkeypatch,
        tmp_path,
        [make_problem(f"P{n}", topic="t", level=1 + n % 2) for n in range(4)],
    )
    before = path.read_text(encoding="utf-8")
    result = serve("t", 1, count=3, build_dir=build_dir)
    result["problems"][0]["steps"].append("tampered")
    result["problems"][0]["statement"] = "tampered"
    assert path.read_text(encoding="utf-8") == before
    assert serve("t", 1, count=3, build_dir=build_dir)["problems"][0]["statement"] != "tampered"


# ---------------------------------------------------------------------------
# Real bank: docs/verified_problems.json
# ---------------------------------------------------------------------------


def test_real_bank_excluded_pairs_are_never_served(tmp_path):
    bank = load_bank(REAL_BANK)
    excluded = {
        (problem["topic"], problem["id"])
        for problem in bank
        if classify(problem) not in (None, "level_5")
    }
    assert excluded, "the real bank has audit exclusions"
    for topic in sorted({topic for topic, _ in excluded}):
        served = keys_of(serve(topic, 1, count=10_000, build_dir=tmp_path))
        assert not excluded & set(served)


def test_real_bank_served_problems_are_eligible(tmp_path):
    bank = load_bank(REAL_BANK)
    by_key = {(problem["topic"], problem["id"]): problem for problem in bank}
    result = serve("u_substitution", 2, count=3, seed=0, build_dir=tmp_path)
    assert result["status"] == STATUS_BANK_FALLBACK
    assert len(result["problems"]) == 3
    for topic, problem_id in keys_of(result):
        assert classify(by_key[(topic, problem_id)]) is None


def test_real_bank_pairs_unique_for_shared_id_topic(tmp_path):
    result = serve("absolute_extrema", 1, count=10_000, build_dir=tmp_path)
    keys = keys_of(result)
    assert len(keys) == len(set(keys))
    assert all(topic == "absolute_extrema" for topic, _ in keys)


def test_real_bank_coverage_matches_audit(tmp_path):
    coverage = describe_coverage(tmp_path)
    report = build_report(load_bank(REAL_BANK))
    assert coverage["topics_in_bank"] == 90
    assert coverage["eligible_problems"] == report["eligible_count"]
    assert coverage["topics_with_eligible"] == len({row["topic"] for row in report["eligible"]})
    assert coverage["echo_checked"] == 0


def test_real_bank_coverage_counts_echo_checked_topic(tmp_path):
    write_gate(tmp_path, "power_rule", gate_payload("power_rule"))
    assert describe_coverage(tmp_path)["echo_checked"] == 1


def test_real_bank_levels_are_ints_in_range(tmp_path):
    result = serve("u_substitution", 3, count=3, seed=1, build_dir=tmp_path)
    assert all(parse_level(problem) in ALL_LEVELS for problem in load_bank(REAL_BANK)
               if problem["topic"] == "u_substitution" and classify(problem) is None)
    assert all(problem["level"] in ALL_LEVELS for problem in result["problems"])
