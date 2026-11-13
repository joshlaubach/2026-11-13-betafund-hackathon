"""Server tests for POST /api/tutor/chat. Offline only: no network and no live model call.

Replay and fake modes make no model call. Live mode is checked only for its missing-key path,
and no key is ever set here.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from core import tutor  # noqa: E402
from core.drafter import AUTH_MESSAGE  # noqa: E402
from server import app as app_module  # noqa: E402

LOCAL_BASE_URL = "http://127.0.0.1:8000"  # the guard only accepts localhost Host headers
ROUTE = "/api/tutor/chat"
MESSAGE = "Can you help me with the chain rule on this one?"
CONTEXT = {"topic": "chain_rule", "topic_title": "Chain rule", "level": 2}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ECHO_MODEL_FAST", raising=False)
    return TestClient(app_module.app, base_url=LOCAL_BASE_URL)


def post_chat(test_client: TestClient, **fields):
    body = {"message": MESSAGE, "context": CONTEXT, **fields}
    return test_client.post(ROUTE, json=body)


def test_replay_mode_returns_ok_with_a_grounded_reply(client):
    history = [{"role": "student", "text": "help"}, {"role": "tutor", "text": "What rule applies here?"}]
    body = post_chat(client, mode="replay", history=history).json()

    assert body["status"] == "ok"
    assert body["engine"] == "scripted"
    assert body["help_level"] == "hint"
    assert body["grounded"] is True
    assert body["sources"]
    assert "similar problem" in body["reply"]


def test_the_first_replay_reply_is_a_question_not_a_worked_example(client):
    body = post_chat(client, mode="replay").json()

    assert body["status"] == "ok"
    assert body["help_level"] == "ask"
    assert body["reply"].rstrip().endswith("?")
    assert body["sources"] == []


def test_fake_mode_returns_ok_and_makes_no_model_call(client, monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("a model call was made")

    monkeypatch.setattr(tutor, "call_model", refuse)

    response = post_chat(client, mode="fake")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_mode_defaults_to_replay_when_omitted(client):
    response = client.post(ROUTE, json={"message": MESSAGE, "context": CONTEXT})

    assert response.json()["engine"] == "scripted"


def test_response_actions_are_validated_and_capped(client):
    actions = post_chat(client, mode="replay").json()["actions"]

    assert len(actions) <= 4
    assert all(action["id"] in tutor.ACTION_IDS for action in actions)


def test_context_and_history_are_optional(client):
    response = client.post(ROUTE, json={"message": MESSAGE, "mode": "fake"})

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_history_is_passed_through_and_validated(client):
    history = [{"role": "student", "text": "what is the chain rule"}]

    body = client.post(ROUTE, json={"message": MESSAGE, "history": history, "mode": "fake"}).json()

    assert body["status"] == "ok"


def test_empty_message_returns_an_error_status_not_a_server_error(client):
    response = post_chat(client, message="   ", mode="fake")

    assert response.status_code == 200
    assert response.json()["status"] == "error"


def test_too_long_message_returns_an_error_status(client):
    body = post_chat(client, message="a" * 501, mode="fake").json()

    assert body["status"] == "error"
    assert "at most 500 characters" in body["error"]


def test_malformed_context_returns_an_error_status(client):
    body = post_chat(client, context={"level": 9}, mode="fake").json()

    assert body == {"status": "error", "error": tutor.BAD_CONTEXT_MESSAGE}


def test_live_mode_without_a_key_returns_a_plain_message_not_the_technical_cause(client):
    body = post_chat(client, mode="live").json()

    assert body == {"status": "error", "error": tutor.UNAVAILABLE_MESSAGE}
    assert AUTH_MESSAGE not in body["error"]


def test_unknown_mode_is_rejected_by_the_request_model(client):
    response = post_chat(client, mode="bank")

    assert response.status_code == 422


def test_unexpected_failure_returns_500_with_a_generic_body(client, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("secret detail that must not leak")

    monkeypatch.setattr(tutor, "chat", broken)

    response = post_chat(client, mode="fake")

    assert response.status_code == 500
    assert response.json() == {"error": "internal error"}
    assert "secret detail" not in response.text
