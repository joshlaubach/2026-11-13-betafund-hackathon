"""Server tests for POST /api/worksheet/ask. Offline only: no network and no live model call.

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

from core import ask, solvers  # noqa: E402
from core.drafter import AUTH_MESSAGE  # noqa: E402
from server import app as app_module  # noqa: E402
from server import worksheet_api  # noqa: E402

LOCAL_BASE_URL = "http://127.0.0.1:8000"  # the guard only accepts localhost Host headers
ROUTE = "/api/worksheet/ask"
FAKE_KEY = "sk-ant-TESTSECRET"
QUESTION = "why is this marked correct?"
ROW = {
    "statement_latex": "\\int 2x\\,dx",
    "student_answer_latex": "x^{2}+C",
    "reference_answer_latex": "x^{2}+C",
    "method": "bank_key",
    "verdict": "correct",
    "reason": "",
    "explanation": "The antiderivative of 2x is x squared plus C.",
    "label": "Checked against the bank key",
}
SCRIPTED_TEXT = "Echo's note on this part: " + ROW["explanation"] + " " + ROW["label"]


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


def post_ask(test_client: TestClient, mode: str = "fake", question: str = QUESTION, **row: str):
    body = {"question": question, "mode": mode, **ROW, **row}
    return test_client.post(ROUTE, json=body)


def forbid_model(monkeypatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a model client was constructed")

    monkeypatch.setattr(solvers.anthropic, "Anthropic", refuse)


def use_fake_model(monkeypatch, parsed: object) -> FakeClient:
    fake = FakeClient(parsed)
    monkeypatch.setattr(solvers.anthropic, "Anthropic", lambda *args, **kwargs: fake)
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE_KEY)
    return fake


def test_fake_mode_returns_the_scripted_explanation(client, monkeypatch):
    forbid_model(monkeypatch)

    body = post_ask(client, "fake").json()

    assert body == {"status": "ok", "answer": SCRIPTED_TEXT}


def test_replay_mode_returns_the_scripted_explanation_and_calls_no_model(client, monkeypatch):
    forbid_model(monkeypatch)

    body = post_ask(client, "replay").json()

    assert body == {"status": "ok", "answer": SCRIPTED_TEXT}


def test_mode_defaults_to_replay_when_omitted(client, monkeypatch):
    forbid_model(monkeypatch)

    response = client.post(ROUTE, json={"question": QUESTION, **ROW})

    assert response.json() == {"status": "ok", "answer": SCRIPTED_TEXT}


def test_row_fields_are_optional_and_default_to_empty(client, monkeypatch):
    forbid_model(monkeypatch)

    response = client.post(ROUTE, json={"question": QUESTION, "mode": "fake"})

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "answer": "Echo's note on this part:"}


def test_live_mode_returns_the_model_answer(client, monkeypatch):
    fake = use_fake_model(monkeypatch, {"answer": "It matches the answer key."})

    body = post_ask(client, "live").json()

    assert body == {"status": "ok", "answer": "It matches the answer key."}
    assert len(fake.messages.calls) == 1


def test_live_mode_without_a_key_returns_the_auth_message(client, monkeypatch):
    forbid_model(monkeypatch)

    body = post_ask(client, "live").json()

    assert body == {"status": "error", "error": AUTH_MESSAGE}


def test_live_empty_model_answer_returns_an_error_status(client, monkeypatch):
    use_fake_model(monkeypatch, {"answer": ""})

    body = post_ask(client, "live").json()

    assert body == {"status": "error", "error": ask.EMPTY_ANSWER_MESSAGE}


def test_empty_question_returns_an_error_status(client, monkeypatch):
    forbid_model(monkeypatch)

    response = post_ask(client, "fake", question="   ")

    assert response.status_code == 200
    assert response.json() == {"status": "error", "error": ask.EMPTY_QUESTION_MESSAGE}


def test_301_character_question_returns_an_error_status(client, monkeypatch):
    forbid_model(monkeypatch)

    body = post_ask(client, "fake", question="a" * 301).json()

    assert body == {"status": "error", "error": ask.TOO_LONG_QUESTION_MESSAGE}


def test_control_characters_in_question_return_an_error_status(client, monkeypatch):
    forbid_model(monkeypatch)

    body = post_ask(client, "fake", question="two\nlines").json()

    assert body == {"status": "error", "error": ask.CONTROL_QUESTION_MESSAGE}


def test_overlong_row_field_returns_an_error_status_and_calls_no_model(client, monkeypatch):
    forbid_model(monkeypatch)

    body = post_ask(client, "live", statement_latex="s" * 601).json()

    assert body == {"status": "error", "error": worksheet_api.ASK_ROW_INVALID_MESSAGE}


def test_unknown_mode_is_rejected_before_the_handler(client):
    response = post_ask(client, "bank")

    assert response.status_code == 422


def test_missing_question_is_rejected_before_the_handler(client):
    response = client.post(ROUTE, json={"mode": "fake", **ROW})

    assert response.status_code == 422


def test_non_string_question_is_rejected_before_the_handler(client):
    response = client.post(ROUTE, json={"question": 5, "mode": "fake", **ROW})

    assert response.status_code == 422


def test_get_is_not_allowed_on_the_ask_route(client):
    assert client.get(ROUTE).status_code == 405


def test_an_unexpected_failure_returns_the_internal_error_body(client, monkeypatch):
    def broken(*args: object, **kwargs: object) -> None:
        raise RuntimeError("secret detail")

    monkeypatch.setattr(worksheet_api, "answer", broken)

    response = post_ask(client, "fake")

    assert response.status_code == 500
    assert response.json() == {"error": "internal error"}
    assert "secret detail" not in response.text


def test_a_body_over_the_json_cap_is_rejected_by_the_guard(client, monkeypatch):
    forbid_model(monkeypatch)

    response = client.post(ROUTE, json={"question": "a" * (300 * 1024), "mode": "fake"})

    assert response.status_code == 413


def test_a_cross_site_origin_is_rejected_by_the_guard(client, monkeypatch):
    forbid_model(monkeypatch)

    response = client.post(
        ROUTE, json={"question": QUESTION, "mode": "fake"}, headers={"Origin": "http://evil.example"}
    )

    assert response.status_code == 403
