"""Server tests for POST /api/practice/steps and /api/practice/check. Offline; no model call."""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from core import practice  # noqa: E402
from server import app as app_module  # noqa: E402

LOCAL_BASE_URL = "http://127.0.0.1:8000"  # the guard only accepts localhost Host headers
STEPS_ROUTE = "/api/practice/steps"
CHECK_ROUTE = "/api/practice/check"
LA_TOPIC = "algebraic"
LA_ID = "LA01"
LA_ANSWER = r"- \frac{1}{8}"
CHECK_KEYS = {
    "status",
    "verdict",
    "method",
    "checked_by",
    "checked_at",
    "explanation",
    "evidence",
}


@pytest.fixture
def client():
    return TestClient(app_module.app, base_url=LOCAL_BASE_URL)


def test_steps_route_returns_verified_steps_for_an_eligible_problem(client):
    body = client.post(STEPS_ROUTE, json={"topic": LA_TOPIC, "problem_id": LA_ID}).json()

    assert body["status"] == "ok"
    assert len(body["steps"]) == 3
    assert body["answer_latex"] == LA_ANSWER
    assert body["source"] == "bank"


def test_steps_route_unknown_id_returns_an_error_status(client):
    response = client.post(STEPS_ROUTE, json={"topic": LA_TOPIC, "problem_id": "NOPE99"})

    assert response.status_code == 200
    assert response.json()["status"] == "error"


def test_steps_route_wrong_topic_returns_an_error_status(client):
    body = client.post(STEPS_ROUTE, json={"topic": "chain_rule", "problem_id": LA_ID}).json()

    assert body["status"] == "error"


def test_steps_route_rejects_a_malformed_id_with_an_error_status(client):
    body = client.post(STEPS_ROUTE, json={"topic": LA_TOPIC, "problem_id": "LA 01"}).json()

    assert body["status"] == "error"


def test_steps_route_missing_field_is_a_validation_error(client):
    response = client.post(STEPS_ROUTE, json={"topic": LA_TOPIC})

    assert response.status_code == 422


def test_check_route_marks_an_equivalent_answer_correct(client):
    body = client.post(
        CHECK_ROUTE,
        json={"topic": LA_TOPIC, "problem_id": LA_ID, "answer_latex": r"\frac{-1}{8}"},
    ).json()

    assert body["status"] == "ok"
    assert body["verdict"] == "correct"


def test_check_route_returns_every_result_field(client):
    body = client.post(
        CHECK_ROUTE,
        json={"topic": LA_TOPIC, "problem_id": LA_ID, "answer_latex": "-1/8"},
    ).json()

    assert set(body) == CHECK_KEYS


def test_check_route_wrong_answer_is_incorrect_and_does_not_leak_the_reference(client):
    body = client.post(
        CHECK_ROUTE,
        json={"topic": LA_TOPIC, "problem_id": LA_ID, "answer_latex": "0"},
    ).json()

    assert body["verdict"] == "incorrect"
    assert "-1/8" not in str(body)
    assert r"\frac{1}{8}" not in str(body)


def test_check_route_unreadable_answer_is_unable_to_verify(client):
    body = client.post(
        CHECK_ROUTE,
        json={"topic": LA_TOPIC, "problem_id": LA_ID, "answer_latex": "__import__('os')"},
    ).json()

    assert body["verdict"] == "unable_to_verify"


def test_check_route_reference_path_marks_an_expression_correct(client):
    body = client.post(
        CHECK_ROUTE,
        json={"answer_latex": "x^{2}+1", "reference_latex": "x^{2} + 1"},
    ).json()

    assert body["verdict"] == "correct"
    assert "problem's own key as shown on the page" in body["explanation"]


def test_check_route_reference_path_missing_reference_is_an_error_status(client):
    body = client.post(CHECK_ROUTE, json={"answer_latex": "x"}).json()

    assert body["status"] == "error"


def test_check_route_missing_answer_is_a_validation_error(client):
    response = client.post(CHECK_ROUTE, json={"topic": LA_TOPIC, "problem_id": LA_ID})

    assert response.status_code == 422


def test_steps_route_internal_failure_returns_generic_500(client, monkeypatch):
    def boom(topic, problem_id):
        raise RuntimeError("secret detail /home/x/key")

    monkeypatch.setattr(practice, "get_steps", boom)

    response = client.post(STEPS_ROUTE, json={"topic": LA_TOPIC, "problem_id": LA_ID})

    assert response.status_code == 500
    assert response.json() == {"error": "internal error"}
    assert "secret" not in response.text


def test_check_route_internal_failure_returns_generic_500(client, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("secret detail /home/x/key")

    monkeypatch.setattr(practice, "check_answer", boom)

    response = client.post(
        CHECK_ROUTE,
        json={"topic": LA_TOPIC, "problem_id": LA_ID, "answer_latex": "0"},
    )

    assert response.status_code == 500
    assert response.json() == {"error": "internal error"}
    assert "secret" not in response.text
