"""Tests for server/. Offline only: no network, no model call. ANTHROPIC_API_KEY is removed
unless a test sets a fake value, and the build and replay directories are temporary.
"""

import hashlib
import json
import logging
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from core import bank_fallback  # noqa: E402
from core.bank_fallback import LABEL_BANK_FALLBACK  # noqa: E402
from core.entry import ORIGIN_BANK, ORIGIN_ECHO, STATUS_ERROR, STATUS_OK  # noqa: E402
from core.photo_reader import PNG_MAGIC, MAX_IMAGE_BYTES, PhotoReading, save_reading  # noqa: E402
from server import app as app_module  # noqa: E402
from server import photo_api  # noqa: E402

FAKE_KEY = "sk-ant-TESTSECRET"
GOOD_READING = PhotoReading(
    problem_latex="3x^{4}+2x", topic_guess="power_rule", confidence="high", notes=""
)
PNG_BYTES = PNG_MAGIC + b"\x00" * 32
FAKE_TOPIC = "power_rule"
BANK_TOPIC = "u_substitution"
PICKER_TOPICS = 90
CHECKER_KEYS = ("checker_readable", "checker_reason")
LOCAL_BASE_URL = "http://127.0.0.1:8000"  # the guard only accepts localhost Host headers


def write_gate(build_dir: Path, topic: str = FAKE_TOPIC, bank_hash: str | None = None) -> None:
    build_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "topic": topic,
        "enabled": True,
        "positive_failed": 0,
        "negative_failed": 0,
        "bank_sha256": bank_hash if bank_hash is not None else bank_fallback.bank_sha256(),
    }
    (build_dir / f"gate_{topic}.json").write_text(json.dumps(payload), encoding="utf-8")


def all_topics(client: TestClient) -> list[dict]:
    body = client.get("/api/topics").json()
    return [topic for course in body["courses"] for unit in course["units"] for topic in unit["topics"]]


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ECHO_MODE", raising=False)
    monkeypatch.setattr(app_module, "BUILD_DIR", tmp_path / "build")
    monkeypatch.setattr(photo_api, "PHOTO_REPLAY_DIR", tmp_path / "replay")
    return TestClient(app_module.app, base_url=LOCAL_BASE_URL)


@pytest.fixture
def gated_client(client, tmp_path):
    write_gate(tmp_path / "build")
    return client


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


def test_health_shape_and_key_value_never_appear(client, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE_KEY)
    responses = [
        client.get("/api/health"),
        client.get("/api/topics"),
        client.post("/api/problems", json={"topic": FAKE_TOPIC, "level": 2, "mode": "bank"}),
        client.post("/api/problems", json={"topic": FAKE_TOPIC, "level": 2, "mode": "live"}),
        client.post("/api/problems", json={"topic": "nope", "level": 9}),
    ]
    health = responses[0].json()
    assert health["ok"] is True
    assert health["live_available"] is True
    assert health["default_mode"] == "replay"
    assert health["echo_checked_topics"] == []
    assert set(health["coverage"]) == {
        "topics_in_bank",
        "topics_with_eligible",
        "echo_checked",
        "eligible_problems",
    }
    for response in responses:
        assert FAKE_KEY not in response.text


def test_health_live_unavailable_without_key(client):
    health = client.get("/api/health").json()
    assert health["live_available"] is False


def test_health_default_mode_follows_echo_mode_when_valid(client, monkeypatch):
    monkeypatch.setenv("ECHO_MODE", "fake")
    assert client.get("/api/health").json()["default_mode"] == "fake"
    monkeypatch.setenv("ECHO_MODE", "telepathy")
    assert client.get("/api/health").json()["default_mode"] == "replay"


# ---------------------------------------------------------------------------
# Topics
# ---------------------------------------------------------------------------


def test_topics_group_course_unit_topic_with_ninety_topics(client):
    body = client.get("/api/topics").json()
    assert body["courses"], "expected at least one course"
    for course in body["courses"]:
        assert set(course) == {"course", "units"}
        for unit in course["units"]:
            assert set(unit) == {"unit", "topics"}
    topics = all_topics(client)
    assert len(topics) == PICKER_TOPICS
    assert len({topic["id"] for topic in topics}) == PICKER_TOPICS
    assert all(set(topic) == {"id", "title", "usable", "echo_checked"} for topic in topics)


def test_power_rule_echo_checked_only_with_valid_gate(client, tmp_path):
    before = {topic["id"]: topic for topic in all_topics(client)}
    assert before[FAKE_TOPIC]["echo_checked"] is False
    assert before[FAKE_TOPIC]["usable"] is True

    write_gate(tmp_path / "build")
    after = {topic["id"]: topic for topic in all_topics(client)}
    assert after[FAKE_TOPIC]["echo_checked"] is True


def test_gate_bound_to_another_bank_does_not_count(client, tmp_path):
    write_gate(tmp_path / "build", bank_hash="0" * 64)
    topics = {topic["id"]: topic for topic in all_topics(client)}
    assert topics[FAKE_TOPIC]["echo_checked"] is False


# ---------------------------------------------------------------------------
# Read photo
# ---------------------------------------------------------------------------


def test_read_photo_fake_returns_reading_and_label_without_checker_fields(client):
    response = client.post(
        "/api/read-photo",
        files={"file": ("photo.png", PNG_BYTES, "image/png")},
        data={"mode": "fake"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == STATUS_OK
    assert body["reading"]["problem_latex"] == "3x^{4} + 2x"
    assert body["label"]
    assert "fake" in body["label"].lower() or "scripted" in body["label"].lower()
    for key in CHECKER_KEYS:
        assert key not in body


def test_read_photo_rejects_non_image(client):
    response = client.post(
        "/api/read-photo",
        files={"file": ("notes.txt", b"hello, this is not an image", "text/plain")},
        data={"mode": "fake"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == STATUS_ERROR
    assert "PNG, JPEG, WEBP, or GIF" in response.json()["error"]


def test_read_photo_over_five_megabytes_is_413(client):
    oversize = PNG_MAGIC + b"\x00" * MAX_IMAGE_BYTES
    response = client.post(
        "/api/read-photo",
        files={"file": ("big.png", oversize, "image/png")},
        data={"mode": "fake"},
    )
    assert response.status_code == 413
    assert "5 MB" in response.json()["error"]


def test_read_photo_replay_without_saved_reading_says_so(client):
    response = client.post(
        "/api/read-photo",
        files={"file": ("photo.png", PNG_BYTES, "image/png")},
        data={"mode": "replay"},
    )
    body = response.json()
    assert body["status"] == STATUS_ERROR
    assert "no saved reading exists for this photo" in body["error"]


def test_read_photo_replay_with_saved_reading_works(client, tmp_path):
    digest = hashlib.sha256(PNG_BYTES).hexdigest()
    replay_dir = tmp_path / "replay"
    save_reading(replay_dir / f"photo_{digest[:12]}.json", digest, GOOD_READING, "fake")
    response = client.post(
        "/api/read-photo",
        files={"file": ("photo.png", PNG_BYTES, "image/png")},
        data={"mode": "replay"},
    )
    body = response.json()
    assert body["status"] == STATUS_OK
    assert body["reading"]["problem_latex"] == "3x^{4}+2x"
    assert "no model was called" in body["label"]


def test_read_photo_rejects_bank_mode(client):
    response = client.post(
        "/api/read-photo",
        files={"file": ("photo.png", PNG_BYTES, "image/png")},
        data={"mode": "bank"},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Problems
# ---------------------------------------------------------------------------


def test_problems_fake_power_rule_level_two_gives_three_echo_checked(gated_client):
    response = gated_client.post(
        "/api/problems", json={"topic": FAKE_TOPIC, "level": 2, "mode": "fake"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == STATUS_OK
    assert len(body["problems"]) == 3
    assert all(problem["origin"] == ORIGIN_ECHO for problem in body["problems"])


def test_problems_bank_mode_for_u_substitution_is_bank_labeled(client):
    response = client.post("/api/problems", json={"topic": BANK_TOPIC, "level": 2, "mode": "bank"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == STATUS_OK
    assert body["problems"]
    assert all(problem["origin"] == ORIGIN_BANK for problem in body["problems"])
    assert all(problem["label"] == LABEL_BANK_FALLBACK for problem in body["problems"])


@pytest.mark.parametrize("level", [0, 5, "2"])
def test_problems_bad_level_is_error_status_with_http_200(client, level):
    response = client.post("/api/problems", json={"topic": FAKE_TOPIC, "level": level, "mode": "fake"})
    assert response.status_code == 200
    assert response.json()["status"] == STATUS_ERROR


def test_problems_disallowed_mode_is_422(client):
    response = client.post("/api/problems", json={"topic": FAKE_TOPIC, "level": 2, "mode": "telepathy"})
    assert response.status_code == 422


def test_problems_malformed_json_is_422(client):
    response = client.post(
        "/api/problems", content="{not json", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422


def test_unexpected_error_is_500_and_logged_without_body(client, monkeypatch, caplog):
    def broken(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(app_module, "request_problems", broken)
    with caplog.at_level(logging.ERROR, logger="server.app"):
        response = client.post(
            "/api/problems", json={"topic": FAKE_TOPIC, "level": 2, "mode": "fake"}
        )
    assert response.status_code == 500
    assert response.json() == {"error": "internal error"}
    assert "RuntimeError: boom" in caplog.text
    assert FAKE_TOPIC not in caplog.text


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------


def test_cors_allows_localhost_3000(client):
    response = client.get("/api/health", headers={"Origin": "http://localhost:3000"})
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_cors_blocks_unknown_origin(client):
    response = client.get("/api/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in response.headers
