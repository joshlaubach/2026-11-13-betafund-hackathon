"""Tests for core/drafter.py. No network and no API key: FakeSource, ReplaySource, and a
mocked Anthropic client only. Gate files are written to tmp_path and bound to the real bank.
"""

import json
import sys
from pathlib import Path

import anthropic
import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core import bank_fallback  # noqa: E402
from core import drafter  # noqa: E402
from core.derivative_checker import WRONG_KEY, UNREADABLE_PROBLEM, parse_derivative_statement  # noqa: E402
from core.drafter import (  # noqa: E402
    LABEL_ACCEPTED,
    STATUS_ERROR,
    STATUS_OK,
    STATUS_UNSUPPORTED,
    Draft,
    DraftError,
    DraftSource,
    FakeSource,
    LiveSource,
    ReplaySource,
    build_statement,
    generate,
    load_run,
    save_run,
)

GOOD_ONE = Draft(function_latex="3x^{4} + 2x", evaluate_at=None, key_latex="12 x^{3} + 2")
GOOD_TWO = Draft(function_latex="x^{3} - 4x", evaluate_at="2", key_latex="8")
GOOD_THREE = Draft(function_latex="\\sqrt{x} + 4x^{3}", evaluate_at=None,
                   key_latex="\\frac{1}{2 \\sqrt{x}} + 12 x^{2}")
GOOD_FOUR = Draft(function_latex="x^{5} + x", evaluate_at=None, key_latex="5 x^{4} + 1")
WRONG = Draft(function_latex="5x^{3} - x", evaluate_at=None, key_latex="15 x^{2}")


class RaisingSource(DraftSource):
    name = "raising"
    source = "fake"

    def __init__(self, error: Exception) -> None:
        self._error = error

    def get_drafts(self, topic, level, n, avoid):
        raise self._error


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
# Accept, reject, duplicates, shortfall
# ---------------------------------------------------------------------------


def test_all_right_drafts_give_first_three_accepted_with_label(gated_dir):
    source = FakeSource([GOOD_ONE, GOOD_TWO, GOOD_THREE, GOOD_FOUR])
    result = generate("power_rule", 2, source, build_dir=gated_dir)
    assert result["status"] == STATUS_OK
    assert len(result["accepted"]) == 3
    assert all(item["label"] == LABEL_ACCEPTED for item in result["accepted"])
    assert result["shortfall"] == 0
    assert result["accepted"][0]["statement"] == "Find $f'(x)$ for $f(x) = 3x^{4} + 2x$."
    assert result["accepted"][1]["statement"] == (
        "Find $f'(2)$ for $f(x) = x^{3} - 4x$. Give an exact answer."
    )
    assert result["accepted"][0]["checker"]["outcome"] == "accepted"
    assert result["accepted"][0]["checker"]["samples"]


def test_wrong_key_is_rejected_with_checker_numbers(gated_dir):
    result = generate("power_rule", 1, FakeSource([WRONG]), build_dir=gated_dir)
    assert result["accepted"] == []
    rejected = result["rejected"][0]
    assert rejected["outcome"] == WRONG_KEY
    assert "checker computes" in rejected["reason"]
    assert "label" not in rejected


def test_duplicate_function_is_skipped_and_reported(gated_dir):
    repeat = Draft(function_latex="3x^{4}   +  2x", evaluate_at=None, key_latex="12 x^{3} + 2")
    result = generate("power_rule", 2, FakeSource([GOOD_ONE, repeat]), build_dir=gated_dir)
    assert len(result["accepted"]) == 1
    assert result["rejected"] == []
    assert result["duplicates"] == ["3x^{4}   +  2x"]


def test_duplicate_of_avoid_list_is_skipped(gated_dir):
    result = generate(
        "power_rule", 2, FakeSource([GOOD_ONE]), avoid=["3x^{4} + 2x"], build_dir=gated_dir
    )
    assert result["accepted"] == []
    assert len(result["duplicates"]) == 1


def test_fewer_than_three_accepted_sets_shortfall_without_fabricating(gated_dir):
    result = generate(
        "power_rule", 2, FakeSource([GOOD_ONE, WRONG, GOOD_TWO]), build_dir=gated_dir
    )
    assert len(result["accepted"]) == 2
    assert result["shortfall"] == 1
    assert len(result["rejected"]) == 1


def test_hostile_function_is_rejected_without_exception(gated_dir):
    hostile = Draft(function_latex="__import__('os')", evaluate_at=None, key_latex="0")
    result = generate("power_rule", 1, FakeSource([hostile]), build_dir=gated_dir)
    assert result["status"] == STATUS_OK
    assert result["accepted"] == []
    assert result["rejected"][0]["outcome"] == UNREADABLE_PROBLEM


def test_build_statement_matches_bank_shapes():
    general = build_statement("x^{3}", None)
    at_point = build_statement("x^{3}", "2")
    assert parse_derivative_statement(general) == {"function_latex": "x^{3}", "at": None}
    assert parse_derivative_statement(at_point) == {"function_latex": "x^{3}", "at": "2"}


# ---------------------------------------------------------------------------
# Unsupported topics and source failures
# ---------------------------------------------------------------------------


def test_topic_other_than_power_rule_is_unsupported(gated_dir):
    result = generate("u_substitution", 2, FakeSource([GOOD_ONE]), build_dir=gated_dir)
    assert result["status"] == STATUS_UNSUPPORTED
    assert result["accepted"] == []


def test_power_rule_without_gate_file_is_unsupported(empty_dir):
    result = generate("power_rule", 2, FakeSource([GOOD_ONE]), build_dir=empty_dir)
    assert result["status"] == STATUS_UNSUPPORTED
    assert result["accepted"] == []


def test_source_runtime_error_gives_error_status_without_crash(gated_dir):
    result = generate("power_rule", 2, RaisingSource(RuntimeError("boom")), build_dir=gated_dir)
    assert result["status"] == STATUS_ERROR
    assert result["error"] == "the source failed; see the server log"
    assert "boom" not in result["error"]
    assert result["accepted"] == []
    assert result["drafted"] == 0


def test_anthropic_authentication_error_from_source_gives_error_status(gated_dir):
    response = httpx.Response(401, request=httpx.Request("POST", "https://example.invalid"))
    error = anthropic.AuthenticationError("API key missing or invalid", response=response, body=None)
    result = generate("power_rule", 2, RaisingSource(error), build_dir=gated_dir)
    assert result["status"] == STATUS_ERROR
    assert result["error"] == "the source failed; see the server log"


def test_live_source_without_key_gives_error_and_no_network(gated_dir, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = generate("power_rule", 2, LiveSource(), build_dir=gated_dir)
    assert result["status"] == STATUS_ERROR
    assert result["error"] == "API key missing or invalid"


def test_live_source_auth_failure_from_client_is_mapped(gated_dir, monkeypatch):
    class FailingMessages:
        def parse(self, **kwargs):
            response = httpx.Response(401, request=httpx.Request("POST", "https://example.invalid"))
            raise anthropic.AuthenticationError("rejected", response=response, body=None)

    class FakeClient:
        messages = FailingMessages()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-real-key")
    monkeypatch.setattr(drafter.anthropic, "Anthropic", lambda: FakeClient())
    result = generate("power_rule", 2, LiveSource(), build_dir=gated_dir)
    assert result["status"] == STATUS_ERROR
    assert result["error"] == "API key missing or invalid"


# ---------------------------------------------------------------------------
# Saved runs and replay
# ---------------------------------------------------------------------------


def test_save_and_load_round_trip_keeps_source_label(tmp_path):
    path = tmp_path / "replay" / "run.json"
    save_run(path, "power_rule", 2, [GOOD_ONE, WRONG], "fake")
    run = load_run(path)
    assert run["source"] == "fake"
    assert run["topic"] == "power_rule"
    assert run["level"] == 2
    assert run["drafts"] == [GOOD_ONE, WRONG]


def test_save_run_rejects_unknown_source(tmp_path):
    with pytest.raises(ValueError):
        save_run(tmp_path / "run.json", "power_rule", 2, [GOOD_ONE], "mystery")


def test_replay_of_fake_run_is_labeled_fake(tmp_path, gated_dir):
    path = tmp_path / "fake_run.json"
    save_run(path, "power_rule", 2, [GOOD_ONE, GOOD_TWO, GOOD_THREE], "fake")
    source = ReplaySource(path)
    assert source.source == "fake"
    assert source.name == "replay (saved fake run)"
    result = generate("power_rule", 2, source, build_dir=gated_dir)
    assert result["status"] == STATUS_OK
    assert len(result["accepted"]) == 3


def test_replay_of_live_run_is_labeled_live(tmp_path):
    path = tmp_path / "live_run.json"
    save_run(path, "power_rule", 2, [GOOD_ONE], "live")
    source = ReplaySource(path)
    assert source.source == "live"
    assert source.name == "replay (saved live run)"


def test_replay_for_other_topic_or_level_is_an_error(tmp_path, gated_dir):
    path = tmp_path / "run.json"
    save_run(path, "power_rule", 2, [GOOD_ONE], "fake")
    result = generate("power_rule", 3, ReplaySource(path), build_dir=gated_dir)
    assert result["status"] == STATUS_ERROR
    assert "level 2" in result["error"]


def test_load_run_rejects_a_file_that_is_not_a_run(tmp_path):
    path = tmp_path / "other.json"
    path.write_text(json.dumps({"hello": "world"}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_run(path)
