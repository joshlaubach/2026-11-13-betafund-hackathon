"""Tests for core/entry.py. Offline only: FakeSource-style fake mode, replay files in
tmp_path, and synthetic banks swapped in through BANK_PATH. No network. ANTHROPIC_API_KEY
is removed wherever a live path is exercised.
"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core import bank_fallback  # noqa: E402
from core.bank_fallback import LABEL_BANK_FALLBACK, LABEL_UNSUPPORTED  # noqa: E402
from core.drafter import FAKE_DRAFTS, LABEL_ACCEPTED, Draft, build_statement, save_run  # noqa: E402
from core.entry import (  # noqa: E402
    ORIGIN_BANK,
    ORIGIN_ECHO,
    ORIGIN_REPLAY,
    STATUS_ERROR,
    STATUS_OK,
    STATUS_UNSUPPORTED,
    request_problems,
)

REAL_BANK = REPO_ROOT / "docs" / "verified_problems.json"
GOOD_ONE = Draft(function_latex="3x^{4} + 2x", evaluate_at=None, key_latex="12 x^{3} + 2")
GOOD_TWO = Draft(function_latex="x^{3} - 4x", evaluate_at="2", key_latex="8")
GOOD_THREE = Draft(
    function_latex="\\sqrt{x} + 4x^{3}",
    evaluate_at=None,
    key_latex="\\frac{1}{2 \\sqrt{x}} + 12 x^{2}",
)
WRONG = Draft(function_latex="5x^{3} - x", evaluate_at=None, key_latex="15 x^{2}")
WRONG_KEYS = [draft.key_latex for draft in FAKE_DRAFTS if draft.key_latex in ("15 x^{2}", "10x^{4} + 14x")]


def make_problem(problem_id, topic="power_rule", level=2, statement=None):
    return {
        "course": "calc1",
        "unit": "test",
        "topic": topic,
        "topic_title": topic,
        "calculator": False,
        "id": problem_id,
        "level": level,
        "statement": statement or f"Evaluate the integral number {problem_id}.",
        "answer": {"type": "numeric", "latex": f"ans {problem_id}", "sympy": "1", "numeric": 1},
        "steps": [f"step for {problem_id}"],
        "method": "test",
        "source_file": "test",
    }


def use_bank(monkeypatch, tmp_path, problems):
    path = tmp_path / "bank.json"
    path.write_text(json.dumps(problems), encoding="utf-8")
    monkeypatch.setattr(bank_fallback, "BANK_PATH", path)
    return path


def write_gate(build_dir: Path, topic: str = "power_rule") -> None:
    build_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "topic": topic,
        "enabled": True,
        "positive_failed": 0,
        "negative_failed": 0,
        "bank_sha256": bank_fallback.bank_sha256(),
    }
    (build_dir / f"gate_{topic}.json").write_text(json.dumps(payload), encoding="utf-8")


def statements(result: dict) -> list[str]:
    return [problem["statement"] for problem in result["problems"]]


@pytest.fixture
def gated_dir(tmp_path):
    path = tmp_path / "build"
    write_gate(path)
    return path


@pytest.fixture
def empty_dir(tmp_path):
    path = tmp_path / "build"
    path.mkdir()
    return path


# ---------------------------------------------------------------------------
# Fake mode and the checker label
# ---------------------------------------------------------------------------


def test_fake_mode_returns_three_labeled_echo_checked_problems(gated_dir):
    result = request_problems("power_rule", 2, mode="fake", build_dir=gated_dir)
    assert result["status"] == STATUS_OK
    assert result["mode_used"] == "fake"
    assert len(result["problems"]) == 3
    assert all(problem["origin"] == ORIGIN_ECHO for problem in result["problems"])
    assert all(problem["label"] == LABEL_ACCEPTED for problem in result["problems"])
    assert result["counts"] == {"echo_checked": 3, "bank_fallback": 0}
    assert all(problem["checker"]["outcome"] == "accepted" for problem in result["problems"])
    assert all(problem["steps"] == [] for problem in result["problems"])


def test_wrong_key_draft_never_appears_in_problems(gated_dir):
    assert WRONG_KEYS, "fake drafts include wrong keys to reject"
    result = request_problems("power_rule", 2, mode="fake", build_dir=gated_dir)
    answers = [problem["answer_latex"] for problem in result["problems"]]
    assert not set(WRONG_KEYS) & set(answers)
    assert build_statement("5x^{3} - x", None) not in statements(result)


def test_wrong_key_in_replay_run_is_not_served(tmp_path, gated_dir):
    path = tmp_path / "run.json"
    save_run(path, "power_rule", 2, [WRONG, GOOD_ONE, GOOD_TWO, GOOD_THREE], "fake")
    result = request_problems(
        "power_rule", 2, mode="replay", replay_path=path, build_dir=gated_dir
    )
    assert len(result["problems"]) == 3
    assert "15 x^{2}" not in [problem["answer_latex"] for problem in result["problems"]]


# ---------------------------------------------------------------------------
# Shortfall filled from the bank
# ---------------------------------------------------------------------------


def test_shortfall_is_filled_from_bank_with_bank_label_only(monkeypatch, tmp_path, gated_dir):
    use_bank(monkeypatch, tmp_path, [make_problem(f"P{n}", level=2) for n in range(4)])
    write_gate(gated_dir)  # the gate is bound to the bank file, so rewrite it after the swap
    path = tmp_path / "run.json"
    save_run(path, "power_rule", 2, [GOOD_ONE], "fake")
    result = request_problems(
        "power_rule", 2, mode="replay", replay_path=path, count=3, build_dir=gated_dir
    )
    assert result["status"] == STATUS_OK
    assert result["counts"] == {"echo_checked": 1, "bank_fallback": 2}
    bank_items = [problem for problem in result["problems"] if problem["origin"] == ORIGIN_BANK]
    assert len(bank_items) == 2
    assert all(problem["label"] == LABEL_BANK_FALLBACK for problem in bank_items)
    assert all(problem["label"] != LABEL_ACCEPTED for problem in bank_items)
    assert all("id" in problem for problem in bank_items)


def test_bank_fill_skips_statement_already_accepted(monkeypatch, tmp_path, gated_dir):
    accepted_statement = build_statement("3x^{4} + 2x", None)
    bank = [make_problem("DUP", level=2, statement=accepted_statement)]
    bank += [make_problem(f"P{n}", level=2) for n in range(3)]
    use_bank(monkeypatch, tmp_path, bank)
    write_gate(gated_dir)
    path = tmp_path / "run.json"
    save_run(path, "power_rule", 2, [GOOD_ONE], "fake")
    result = request_problems(
        "power_rule", 2, mode="replay", replay_path=path, count=3, build_dir=gated_dir
    )
    assert len(result["problems"]) == 3
    assert len(set(statements(result))) == 3
    bank_statements = [p["statement"] for p in result["problems"] if p["origin"] == ORIGIN_BANK]
    assert accepted_statement not in bank_statements


def test_fill_never_exceeds_count(monkeypatch, tmp_path, gated_dir):
    use_bank(monkeypatch, tmp_path, [make_problem(f"P{n}", level=2) for n in range(6)])
    result = request_problems("power_rule", 2, mode="bank", count=2, build_dir=gated_dir)
    assert len(result["problems"]) == 2


# ---------------------------------------------------------------------------
# Bank-only paths and unsupported
# ---------------------------------------------------------------------------


def test_non_echo_checked_topic_returns_bank_problems_only(tmp_path):
    result = request_problems("u_substitution", 2, mode="fake", build_dir=tmp_path)
    assert result["status"] == STATUS_OK
    assert result["mode_used"] == "bank"
    assert len(result["problems"]) == 3
    assert all(problem["origin"] == ORIGIN_BANK for problem in result["problems"])
    assert all(problem["label"] == LABEL_BANK_FALLBACK for problem in result["problems"])
    assert any("not Echo-checked yet" in note for note in result["notes"])


def test_bank_mode_on_echo_checked_topic_uses_bank_label(monkeypatch, tmp_path, gated_dir):
    use_bank(monkeypatch, tmp_path, [make_problem(f"P{n}", level=2) for n in range(3)])
    result = request_problems("power_rule", 2, mode="bank", build_dir=gated_dir)
    assert result["mode_used"] == "bank"
    assert all(problem["label"] == LABEL_BANK_FALLBACK for problem in result["problems"])


def test_topic_with_no_usable_problems_is_unsupported(empty_dir):
    result = request_problems("no_such_topic", 2, mode="bank", build_dir=empty_dir)
    assert result["status"] == STATUS_UNSUPPORTED
    assert result["problems"] == []
    assert result["mode_used"] is None
    assert LABEL_UNSUPPORTED in result["notes"]


def test_power_rule_without_gate_and_no_bank_problems_is_unsupported(monkeypatch, tmp_path, empty_dir):
    use_bank(monkeypatch, tmp_path, [make_problem("P1", topic="other", level=2)])
    result = request_problems("power_rule", 2, mode="fake", build_dir=empty_dir)
    assert result["status"] == STATUS_UNSUPPORTED
    assert LABEL_UNSUPPORTED in result["notes"]


# ---------------------------------------------------------------------------
# Bad input returns an error, never an exception
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("level", [0, 5, -1, True, "2", None, 2.0])
def test_bad_level_returns_error_result(empty_dir, level):
    result = request_problems("power_rule", level, mode="fake", build_dir=empty_dir)
    assert result["status"] == STATUS_ERROR
    assert result["problems"] == []
    assert result["notes"]


@pytest.mark.parametrize("count", [0, -1, True, "3"])
def test_bad_count_returns_error_result(empty_dir, count):
    result = request_problems("power_rule", 2, mode="fake", count=count, build_dir=empty_dir)
    assert result["status"] == STATUS_ERROR
    assert result["problems"] == []


def test_unknown_mode_returns_error_result(empty_dir):
    result = request_problems("power_rule", 2, mode="telepathy", build_dir=empty_dir)
    assert result["status"] == STATUS_ERROR


# ---------------------------------------------------------------------------
# Source failures fall back with a note
# ---------------------------------------------------------------------------


def test_live_without_key_falls_back_to_bank_with_note(monkeypatch, tmp_path, gated_dir):
    use_bank(monkeypatch, tmp_path, [make_problem(f"P{n}", level=2) for n in range(3)])
    write_gate(gated_dir)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = request_problems("power_rule", 2, mode="live", build_dir=gated_dir)
    assert result["status"] == STATUS_OK
    assert any("ANTHROPIC_API_KEY" in note for note in result["notes"])
    assert len(result["problems"]) == 3
    assert all(problem["origin"] == ORIGIN_BANK for problem in result["problems"])
    assert all(problem["label"] == LABEL_BANK_FALLBACK for problem in result["problems"])


def test_replay_with_mismatched_level_falls_back_with_note(monkeypatch, tmp_path, gated_dir):
    use_bank(monkeypatch, tmp_path, [make_problem(f"P{n}", level=3) for n in range(3)])
    write_gate(gated_dir)
    path = tmp_path / "run.json"
    save_run(path, "power_rule", 2, [GOOD_ONE, GOOD_TWO, GOOD_THREE], "fake")
    result = request_problems(
        "power_rule", 3, mode="replay", replay_path=path, build_dir=gated_dir
    )
    assert any("replay source failed" in note and "level 2" in note for note in result["notes"])
    assert all(problem["origin"] == ORIGIN_BANK for problem in result["problems"])


def test_replay_file_that_is_missing_falls_back_with_note(monkeypatch, tmp_path, gated_dir):
    use_bank(monkeypatch, tmp_path, [make_problem(f"P{n}", level=2) for n in range(3)])
    write_gate(gated_dir)
    result = request_problems(
        "power_rule", 2, mode="replay", replay_path=tmp_path / "missing.json", build_dir=gated_dir
    )
    assert any("replay source failed" in note for note in result["notes"])
    assert result["status"] == STATUS_OK
    assert result["counts"]["echo_checked"] == 0


# ---------------------------------------------------------------------------
# Replay origin and notes
# ---------------------------------------------------------------------------


def test_replay_of_live_run_is_labeled_replay_with_checker_label(tmp_path, gated_dir):
    path = tmp_path / "live.json"
    save_run(path, "power_rule", 2, [GOOD_ONE, GOOD_TWO, GOOD_THREE], "live")
    result = request_problems(
        "power_rule", 2, mode="replay", replay_path=path, build_dir=gated_dir
    )
    assert result["status"] == STATUS_OK
    assert all(problem["origin"] == ORIGIN_REPLAY for problem in result["problems"])
    assert all(problem["label"] == LABEL_ACCEPTED for problem in result["problems"])
    assert any("REPLAY of a LIVE run" in note for note in result["notes"])


def test_replay_of_fake_run_note_says_fake(tmp_path, gated_dir):
    path = tmp_path / "fake.json"
    save_run(path, "power_rule", 2, [GOOD_ONE, GOOD_TWO, GOOD_THREE], "fake")
    result = request_problems(
        "power_rule", 2, mode="replay", replay_path=path, build_dir=gated_dir
    )
    assert any("REPLAY of a FAKE run" in note for note in result["notes"])
    assert all(problem["origin"] == ORIGIN_REPLAY for problem in result["problems"])


# ---------------------------------------------------------------------------
# Inputs and bank are never mutated
# ---------------------------------------------------------------------------


def test_inputs_and_bank_are_not_mutated(monkeypatch, tmp_path, gated_dir):
    bank_path = use_bank(monkeypatch, tmp_path, [make_problem(f"P{n}", level=2) for n in range(4)])
    write_gate(gated_dir)
    run_path = tmp_path / "run.json"
    save_run(run_path, "power_rule", 2, [GOOD_ONE], "fake")
    drafts_before = [draft.model_dump() for draft in FAKE_DRAFTS]
    bank_before = bank_path.read_bytes()
    run_before = run_path.read_bytes()

    first = request_problems("power_rule", 2, mode="fake", build_dir=gated_dir)
    first["problems"][0]["steps"].append("tampered")
    first["problems"][0]["checker"]["samples"] = "tampered"
    request_problems("power_rule", 2, mode="replay", replay_path=run_path, build_dir=gated_dir)

    assert [draft.model_dump() for draft in FAKE_DRAFTS] == drafts_before
    assert bank_path.read_bytes() == bank_before
    assert run_path.read_bytes() == run_before
    again = request_problems("power_rule", 2, mode="fake", build_dir=gated_dir)
    assert again["problems"][0]["steps"] == []
    assert again["problems"][0]["checker"]["samples"] != "tampered"
