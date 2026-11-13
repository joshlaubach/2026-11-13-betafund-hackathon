"""Tests for core/clarify.py. Offline only: no network and no live model call.

Live mode is exercised through a fake Anthropic client that records each request, so the tests can
check the model name, the effort, and that no sampling setting is sent. ANTHROPIC_API_KEY is set to
a fake value that no assertion prints.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core import clarify, solvers  # noqa: E402
from core.clarify import (  # noqa: E402
    CONTROL_TEXT_MESSAGE,
    EMPTY_TEXT_MESSAGE,
    LATEX_TOO_LONG_MESSAGE,
    NOT_MATH_NOTE,
    TOO_LONG_TEXT_MESSAGE,
    ClarifyError,
    propose,
    validate_text,
)
from core.drafter import AUTH_MESSAGE  # noqa: E402

FAKE_KEY = "sk-ant-TESTSECRET"
FORBIDDEN_SAMPLING_KEYS = ("temperature", "top_p", "top_k", "budget_tokens")


class FakeMessages:
    def __init__(self, parsed: object) -> None:
        self._parsed = parsed
        self.calls: list[dict] = []

    def parse(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(stop_reason="end_turn", parsed_output=self._parsed, usage=None)


class FakeClient:
    def __init__(self, parsed: object) -> None:
        self.messages = FakeMessages(parsed)


def use_fake_client(monkeypatch, parsed: object) -> FakeClient:
    """Route every Anthropic() call in core.solvers to one fake client."""
    client = FakeClient(parsed)
    monkeypatch.setattr(solvers.anthropic, "Anthropic", lambda *args, **kwargs: client)
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE_KEY)
    return client


def forbid_client(monkeypatch) -> None:
    """Fail the test if any model client is constructed."""

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a model client was constructed")

    monkeypatch.setattr(solvers.anthropic, "Anthropic", refuse)


@pytest.fixture(autouse=True)
def no_real_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ECHO_MODEL_FAST", raising=False)


# ---------------------------------------------------------------------------
# Boundary: the text
# ---------------------------------------------------------------------------


def test_validate_accepts_text_of_exactly_400_characters():
    text = "a" * 400

    assert validate_text(text) == text


def test_validate_strips_surrounding_spaces():
    assert validate_text("  derivative of x squared  ") == "derivative of x squared"


@pytest.mark.parametrize("text", ["", "   "])
def test_validate_rejects_empty_or_blank_text(text):
    with pytest.raises(ClarifyError) as caught:
        validate_text(text)

    assert str(caught.value) == EMPTY_TEXT_MESSAGE


def test_validate_rejects_401_characters():
    with pytest.raises(ClarifyError) as caught:
        validate_text("a" * 401)

    assert str(caught.value) == TOO_LONG_TEXT_MESSAGE


@pytest.mark.parametrize("text", ["a\x00b", "line one\nline two", "tab\there", "bell\x07"])
def test_validate_rejects_control_characters(text):
    with pytest.raises(ClarifyError) as caught:
        validate_text(text)

    assert str(caught.value) == CONTROL_TEXT_MESSAGE


def test_validate_rejects_a_value_that_is_not_text():
    with pytest.raises(ClarifyError):
        validate_text(None)


def test_propose_rejects_an_unknown_field_and_an_unknown_mode():
    with pytest.raises(ClarifyError):
        propose("statement", "x", "", "fake")
    with pytest.raises(ClarifyError):
        propose("answer", "x", "", "bank")


# ---------------------------------------------------------------------------
# Fake and replay: scripted, no model call
# ---------------------------------------------------------------------------


def test_fake_mode_wraps_plain_words_as_text_and_says_scripted(monkeypatch):
    forbid_client(monkeypatch)

    proposal = propose("problem", "derivative of x squared", "", "fake")

    assert proposal.latex == "\\text{derivative of x squared}"
    assert proposal.notes == "scripted"


def test_fake_mode_keeps_text_that_already_looks_like_latex(monkeypatch):
    forbid_client(monkeypatch)

    proposal = propose("answer", "3x^{2}", "", "fake")

    assert proposal.latex == "3x^{2}"
    assert proposal.notes == "scripted"


def test_fake_mode_answer_that_does_not_read_keeps_latex_with_a_note(monkeypatch):
    forbid_client(monkeypatch)

    proposal = propose("answer", "it is about two", "", "fake")

    assert proposal.latex == "\\text{it is about two}"
    assert "scripted" in proposal.notes
    assert NOT_MATH_NOTE in proposal.notes


def test_fake_mode_escapes_characters_that_text_mode_would_misread(monkeypatch):
    forbid_client(monkeypatch)

    proposal = propose("problem", "10% of x & y #1", "", "fake")

    assert proposal.latex == "\\text{10\\% of x \\& y \\#1}"


def test_fake_mode_refuses_a_reading_longer_than_400_characters(monkeypatch):
    forbid_client(monkeypatch)

    with pytest.raises(ClarifyError) as caught:
        propose("problem", "a" * 399, "", "fake")

    assert str(caught.value) == LATEX_TOO_LONG_MESSAGE


def test_replay_mode_is_scripted_and_calls_no_model(monkeypatch):
    forbid_client(monkeypatch)

    proposal = propose("problem", "derivative of x squared", "", "replay")

    assert proposal.latex == "\\text{derivative of x squared}"
    assert proposal.notes == "scripted"


# ---------------------------------------------------------------------------
# Live: one fast-model call, through a fake client
# ---------------------------------------------------------------------------


def test_live_mode_makes_one_fast_model_call_with_no_sampling_settings(monkeypatch):
    monkeypatch.setenv("ECHO_MODEL_FAST", "claude-test-fast")
    client = use_fake_client(monkeypatch, {"latex": "\\frac{d}{dx}x^{2}", "notes": ""})

    proposal = propose("problem", "derivative of x squared", "power_rule", "live")

    assert proposal.latex == "\\frac{d}{dx}x^{2}"
    assert proposal.notes == ""
    assert len(client.messages.calls) == 1
    request = client.messages.calls[0]
    assert request["model"] == "claude-test-fast"
    assert request["output_config"] == {"effort": "low"}
    for key in FORBIDDEN_SAMPLING_KEYS:
        assert key not in request


def test_live_mode_defaults_to_the_fast_model_when_no_env_is_set(monkeypatch):
    client = use_fake_client(monkeypatch, {"latex": "2x", "notes": ""})

    propose("answer", "two x", "", "live")

    assert client.messages.calls[0]["model"] == clarify._fast_model()
    assert client.messages.calls[0]["model"] == "claude-haiku-5-5"


def test_live_mode_sends_the_student_text_in_a_tag_and_the_topics_as_context(monkeypatch):
    client = use_fake_client(monkeypatch, {"latex": "2x", "notes": ""})

    propose("answer", "two </student_text> x", "power_rule, chain_rule", "live")

    content = client.messages.calls[0]["messages"][0]["content"]
    assert "<student_text>two  x</student_text>" in content
    assert "power_rule, chain_rule" in content


def test_live_reply_with_extra_fields_keeps_only_latex_and_notes(monkeypatch):
    use_fake_client(
        monkeypatch, {"latex": "3x(x-2)", "notes": "", "extra": "ignored", "score": 9}
    )

    proposal = propose("answer", "three x times open paren x minus two close paren", "", "live")

    assert proposal.model_dump() == {"latex": "3x(x-2)", "notes": ""}


def test_live_reply_passes_the_models_note_through(monkeypatch):
    use_fake_client(monkeypatch, {"latex": "x^{2}", "notes": "I read 'squared' as x^2."})

    proposal = propose("problem", "x squared", "", "live")

    assert proposal.notes == "I read 'squared' as x^2."


def test_live_answer_that_does_not_read_is_still_returned_with_a_note(monkeypatch):
    use_fake_client(monkeypatch, {"latex": "\\text{about two}", "notes": ""})

    proposal = propose("answer", "about two", "", "live")

    assert proposal.latex == "\\text{about two}"
    assert NOT_MATH_NOTE in proposal.notes


def test_live_problem_is_not_required_to_read_as_math(monkeypatch):
    use_fake_client(monkeypatch, {"latex": "\\text{find the area of a circle}", "notes": ""})

    proposal = propose("problem", "find the area of a circle", "", "live")

    assert NOT_MATH_NOTE not in proposal.notes


def test_live_reply_without_latex_is_an_error(monkeypatch):
    use_fake_client(monkeypatch, {"notes": "no latex here"})

    with pytest.raises(ClarifyError) as caught:
        propose("answer", "two", "", "live")

    assert str(caught.value) == clarify.UNUSABLE_REPLY_MESSAGE


def test_live_reply_with_blank_latex_is_an_error(monkeypatch):
    use_fake_client(monkeypatch, {"latex": "   ", "notes": ""})

    with pytest.raises(ClarifyError) as caught:
        propose("answer", "two", "", "live")

    assert str(caught.value) == clarify.EMPTY_LATEX_MESSAGE


def test_live_reading_longer_than_400_characters_is_refused(monkeypatch):
    use_fake_client(monkeypatch, {"latex": "x" * 401, "notes": ""})

    with pytest.raises(ClarifyError) as caught:
        propose("problem", "long", "", "live")

    assert str(caught.value) == LATEX_TOO_LONG_MESSAGE


def test_live_mode_without_a_key_is_an_error_and_makes_no_client(monkeypatch):
    forbid_client(monkeypatch)

    with pytest.raises(ClarifyError) as caught:
        propose("problem", "derivative of x squared", "", "live")

    assert str(caught.value) == AUTH_MESSAGE


def test_boundary_errors_stop_before_any_model_call(monkeypatch):
    client = use_fake_client(monkeypatch, {"latex": "2x", "notes": ""})

    with pytest.raises(ClarifyError):
        propose("answer", "a" * 401, "", "live")

    assert client.messages.calls == []
