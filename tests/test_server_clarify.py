"""Server tests for POST /api/worksheet/clarify. Offline only: no network and no live model call.

A fake Anthropic client stands in for the model in live mode. ANTHROPIC_API_KEY is removed unless a
test sets a fake value, and the fake value is never printed.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from core import clarify, solvers  # noqa: E402
from core.drafter import AUTH_MESSAGE  # noqa: E402
from server import app as app_module  # noqa: E402

LOCAL_BASE_URL = "http://127.0.0.1:8000"  # the guard only accepts localhost Host headers
ROUTE = "/api/worksheet/clarify"
FAKE_KEY = "sk-ant-TESTSECRET"
DERIVATIVE_TEXT = "derivative of x squared"


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


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ECHO_MODEL_FAST", raising=False)
    return TestClient(app_module.app, base_url=LOCAL_BASE_URL)


def post_clarify(test_client: TestClient, field: str, text: str, mode: str):
    return test_client.post(ROUTE, json={"field": field, "text": text, "mode": mode})


def forbid_model(monkeypatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a model client was constructed")

    monkeypatch.setattr(solvers.anthropic, "Anthropic", refuse)


def use_fake_model(monkeypatch, parsed: object) -> FakeClient:
    fake = FakeClient(parsed)
    monkeypatch.setattr(solvers.anthropic, "Anthropic", lambda *args, **kwargs: fake)
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE_KEY)
    return fake


def test_fake_mode_returns_a_scripted_reading(client, monkeypatch):
    forbid_model(monkeypatch)

    body = post_clarify(client, "problem", DERIVATIVE_TEXT, "fake").json()

    assert body == {"status": "ok", "latex": "\\text{derivative of x squared}", "notes": "scripted"}


def test_replay_mode_returns_a_scripted_reading_and_calls_no_model(client, monkeypatch):
    forbid_model(monkeypatch)

    body = post_clarify(client, "problem", DERIVATIVE_TEXT, "replay").json()

    assert body["status"] == "ok"
    assert body["notes"] == "scripted"


def test_empty_text_returns_an_error_status(client, monkeypatch):
    forbid_model(monkeypatch)

    response = post_clarify(client, "answer", "   ", "fake")

    assert response.status_code == 200
    assert response.json() == {"status": "error", "error": clarify.EMPTY_TEXT_MESSAGE}


def test_401_characters_returns_an_error_status(client, monkeypatch):
    forbid_model(monkeypatch)

    body = post_clarify(client, "answer", "a" * 401, "fake").json()

    assert body == {"status": "error", "error": clarify.TOO_LONG_TEXT_MESSAGE}


def test_control_characters_return_an_error_status(client, monkeypatch):
    forbid_model(monkeypatch)

    body = post_clarify(client, "answer", "two\x00x", "fake").json()

    assert body == {"status": "error", "error": clarify.CONTROL_TEXT_MESSAGE}


def test_unknown_field_is_rejected_before_the_handler(client):
    response = post_clarify(client, "statement", DERIVATIVE_TEXT, "fake")

    assert response.status_code == 422


def test_live_mode_returns_the_model_reading_without_extra_fields(client, monkeypatch):
    fake = use_fake_model(
        monkeypatch, {"latex": "3x(x-2)", "notes": "", "extra": "ignored"}
    )

    body = post_clarify(client, "answer", "three x times open paren x minus two close paren", "live").json()

    assert body == {"status": "ok", "latex": "3x(x-2)", "notes": ""}
    assert len(fake.messages.calls) == 1


def test_live_mode_without_a_key_returns_the_auth_message(client, monkeypatch):
    forbid_model(monkeypatch)

    body = post_clarify(client, "problem", DERIVATIVE_TEXT, "live").json()

    assert body == {"status": "error", "error": AUTH_MESSAGE}


def test_live_reply_without_latex_returns_an_error_status(client, monkeypatch):
    use_fake_model(monkeypatch, {"notes": "nothing"})

    body = post_clarify(client, "problem", DERIVATIVE_TEXT, "live").json()

    assert body == {"status": "error", "error": clarify.UNUSABLE_REPLY_MESSAGE}
