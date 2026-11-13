"""Security tests for the local API: Host and Origin guards, body caps, string limits, error text.

Offline only: no network, no model call. Any test that would reach a model source records the
call instead, so a passing test also shows that no source was built. ANTHROPIC_API_KEY is
removed, and the build and replay directories are temporary.
"""

import json
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from core import bank_fallback  # noqa: E402
from core.entry import request_problems  # noqa: E402
from core.photo_reader import PNG_MAGIC, FakePhotoSource, PhotoSource, read_photo  # noqa: E402
from core.worksheet_types import GRADE_LABELS, Grade, GradedItem, WorksheetItem  # noqa: E402
from server import app as app_module  # noqa: E402
from server import guard, photo_api, worksheet_api  # noqa: E402

LOCAL_BASE_URL = "http://127.0.0.1:8000"
EVIL_ORIGIN = "http://evil.example"
LOCAL_ORIGIN = "http://localhost:3000"
EVIL_HOST = "evil.example"
PNG_BYTES = PNG_MAGIC + b"\x00" * 32
FAKE_TOPIC = "power_rule"
GENERIC_TEXT = "the source failed; see the server log"
SECRET_PATH = "/home/tutor/secret/keys/source.json"
PROBLEM_BODY = {"topic": FAKE_TOPIC, "level": 2, "mode": "fake"}
CHUNK_BYTES = 128 * 1024
OVER_STATEMENT = "x" * (worksheet_api.MAX_STATEMENT_CHARS + 1)
OVER_ANSWER = "x" * (worksheet_api.MAX_ANSWER_CHARS + 1)
OVER_NOTES = "x" * (worksheet_api.MAX_NOTES_CHARS + 1)


class RaisingSource(PhotoSource):
    """A photo source that fails with an error whose text must never reach a client."""

    name = "raising"
    source = "fake"

    def __init__(self, error: Exception) -> None:
        self._error = error

    def get_reading(self, image, media_type, topics):
        raise self._error


def write_gate(build_dir: Path, topic: str = FAKE_TOPIC) -> None:
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
def client(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ECHO_MODE", raising=False)
    monkeypatch.setattr(app_module, "BUILD_DIR", tmp_path / "build")
    monkeypatch.setattr(photo_api, "PHOTO_REPLAY_DIR", tmp_path / "replay")
    monkeypatch.setattr(worksheet_api, "WORKSHEET_REPLAY_DIR", tmp_path / "replay")
    return TestClient(app_module.app, base_url=LOCAL_BASE_URL)


@pytest.fixture
def built_sources(monkeypatch) -> list[str]:
    """Records every model source the worksheet route tries to build. Empty means no model call."""
    calls: list[str] = []
    real_build_source = worksheet_api.build_source

    def record(mode, path):
        if mode == "live":
            calls.append(mode)
            raise AssertionError("no live model source may be built for a rejected request")
        return real_build_source(mode, path)

    monkeypatch.setattr(worksheet_api, "build_source", record)
    return calls


def read_worksheet_post(client: TestClient, headers: dict, mode: str = "live"):
    return client.post(
        "/api/worksheet/read",
        files={"file": ("photo.png", PNG_BYTES, "image/png")},
        data={"mode": mode},
        headers=headers,
    )


def item(number: int, **overrides) -> dict:
    fields = {
        "number": number,
        "statement_latex": "x^{2}",
        "student_answer_latex": "2x",
        "topic_guess": None,
        "confidence": "medium",
        "notes": "",
    }
    fields.update(overrides)
    return fields


# ---------------------------------------------------------------------------
# Origin guard
# ---------------------------------------------------------------------------


def test_post_from_foreign_origin_is_403_and_builds_no_source(client, built_sources):
    response = read_worksheet_post(client, {"Origin": EVIL_ORIGIN})
    assert response.status_code == 403
    assert response.json() == {"error": "origin not allowed"}
    assert built_sources == []


def test_post_from_allowed_origin_passes_the_guard(client, built_sources):
    response = read_worksheet_post(client, {"Origin": LOCAL_ORIGIN}, mode="fake")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_post_without_origin_passes_the_guard(client, built_sources):
    response = read_worksheet_post(client, {}, mode="fake")
    assert response.status_code == 200


def test_foreign_origin_is_rejected_on_every_write_method(client):
    for method in ("put", "patch", "delete"):
        response = getattr(client, method)("/api/problems", headers={"Origin": EVIL_ORIGIN})
        assert response.status_code == 403, method


def test_get_health_works_with_no_origin_and_localhost_host(client):
    response = client.get("/api/health", headers={"Host": "127.0.0.1"})
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_get_health_from_foreign_origin_is_not_blocked_by_the_guard(client):
    response = client.get("/api/health", headers={"Origin": EVIL_ORIGIN})
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Host guard
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("host", [EVIL_HOST, "localhost.evil.example", "evil.example:8000"])
def test_foreign_host_is_400(client, host):
    response = client.get("/api/health", headers={"Host": host})
    assert response.status_code == 400
    assert response.json() == {"error": "host not allowed"}


def test_foreign_host_is_400_on_post_too(client, built_sources):
    response = client.post("/api/problems", json=PROBLEM_BODY, headers={"Host": EVIL_HOST})
    assert response.status_code == 400
    assert built_sources == []


@pytest.mark.parametrize("host", ["127.0.0.1:8000", "localhost", "localhost:3000", "127.0.0.1"])
def test_local_hosts_pass_the_host_guard(client, host):
    response = client.get("/api/health", headers={"Host": host})
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Body-size guard
# ---------------------------------------------------------------------------


def test_declared_length_over_photo_cap_is_413_on_photo_route(client, built_sources):
    body = b"x" * (guard.PHOTO_BODY_CAP_BYTES + 1)
    response = client.post(
        "/api/read-photo",
        content=body,
        headers={"Content-Type": "multipart/form-data; boundary=x"},
    )
    assert response.status_code == 413
    assert built_sources == []


def test_declared_length_over_json_cap_is_413_on_json_route(client):
    body = b" " * (guard.JSON_BODY_CAP_BYTES + 1)
    response = client.post(
        "/api/problems", content=body, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 413
    assert response.json() == {"error": "request body is too large"}


def _chunks(total_bytes: int) -> Iterator[bytes]:
    """Yields total_bytes in chunks with no Content-Length, so the body is streamed (chunked)."""
    sent = 0
    while sent < total_bytes:
        size = min(CHUNK_BYTES, total_bytes - sent)
        sent += size
        yield b" " * size


def test_chunked_body_over_json_cap_is_413_without_content_length(client):
    response = client.post(
        "/api/problems",
        content=_chunks(guard.JSON_BODY_CAP_BYTES + CHUNK_BYTES),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413


def test_chunked_body_under_json_cap_is_not_413(client):
    response = client.post(
        "/api/problems",
        content=_chunks(CHUNK_BYTES),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code != 413


def test_chunked_photo_body_over_photo_cap_is_413_and_builds_no_source(client, built_sources):
    response = client.post(
        "/api/worksheet/read",
        content=_chunks(guard.PHOTO_BODY_CAP_BYTES + CHUNK_BYTES),
        headers={"Content-Type": "multipart/form-data; boundary=x"},
    )
    assert response.status_code == 413
    assert built_sources == []


# ---------------------------------------------------------------------------
# String limits on worksheet request items
# ---------------------------------------------------------------------------


def grade_body(**overrides) -> dict:
    return {"reading": {"items": [item(1, **overrides)]}, "mode": "fake"}


@pytest.mark.parametrize(
    "overrides",
    [
        {"statement_latex": OVER_STATEMENT},
        {"student_answer_latex": OVER_ANSWER},
        {"notes": OVER_NOTES},
    ],
)
def test_over_long_item_text_is_422_on_grade(client, overrides):
    response = client.post("/api/worksheet/grade", json=grade_body(**overrides))
    assert response.status_code == 422


def test_over_long_statement_is_422_on_profile(client):
    graded = [{"item": item(1, statement_latex=OVER_STATEMENT), "grade": _unsure_grade()}]
    response = client.post("/api/worksheet/profile", json={"graded": graded})
    assert response.status_code == 422


def test_over_long_answer_is_422_on_regrade(client):
    graded = {"item": item(1, student_answer_latex=OVER_ANSWER), "grade": _unsure_grade()}
    response = client.post("/api/worksheet/regrade", json={"graded": graded, "mode": "fake"})
    assert response.status_code == 422


def test_statement_at_the_limit_is_accepted(client):
    at_limit = "x" * worksheet_api.MAX_STATEMENT_CHARS
    response = client.post("/api/worksheet/grade", json=grade_body(statement_latex=at_limit))
    assert response.status_code == 200


def _unsure_grade() -> dict:
    grade = Grade(
        verdict="unsure",
        method="ai_judgment",
        label=GRADE_LABELS["ai_judgment"],
        explanation="test",
    )
    return grade.model_dump(mode="json")


def test_worksheet_item_model_still_accepts_long_text_directly():
    # The limits live on the request models in server/worksheet_api.py; core types are unchanged.
    long_item = WorksheetItem(number=1, statement_latex=OVER_STATEMENT)
    assert len(long_item.statement_latex) > worksheet_api.MAX_STATEMENT_CHARS


# ---------------------------------------------------------------------------
# Error text: known errors keep their message, anything else gets the generic text
# ---------------------------------------------------------------------------


def test_unknown_exception_in_photo_source_gives_generic_text(monkeypatch):
    source = RaisingSource(RuntimeError(SECRET_PATH))
    result = read_photo(PNG_BYTES, source)
    assert result["status"] == "error"
    assert result["error"] == GENERIC_TEXT
    assert SECRET_PATH not in json.dumps(result)


def test_unknown_exception_in_photo_route_gives_generic_text(client, monkeypatch):
    monkeypatch.setattr(photo_api, "_photo_source", lambda mode, image: RaisingSource(OSError(SECRET_PATH)))
    response = client.post(
        "/api/read-photo",
        files={"file": ("photo.png", PNG_BYTES, "image/png")},
        data={"mode": "fake"},
    )
    assert response.status_code == 200
    assert response.json()["error"] == GENERIC_TEXT
    assert SECRET_PATH not in response.text


def test_known_photo_source_error_keeps_its_message():
    result = read_photo(PNG_BYTES, FakePhotoSource())
    assert result["error"] is None


def test_unknown_exception_in_draft_source_gives_generic_text(tmp_path):
    from core.drafter import DraftSource, generate

    class ExplodingDraftSource(DraftSource):
        name = "exploding"
        source = "fake"

        def get_drafts(self, topic, level, n, avoid):
            raise RuntimeError(SECRET_PATH)

    build_dir = tmp_path / "build"
    write_gate(build_dir)
    result = generate(FAKE_TOPIC, 2, ExplodingDraftSource(), build_dir=build_dir)
    assert result["error"] == GENERIC_TEXT
    assert SECRET_PATH not in json.dumps(result)


def test_saved_run_load_failure_note_has_no_path(tmp_path):
    build_dir = tmp_path / "build"
    write_gate(build_dir)
    missing = tmp_path / "private" / "secret_run.json"
    result = request_problems(
        FAKE_TOPIC, 2, mode="replay", replay_path=missing, build_dir=build_dir
    )
    notes = " ".join(result["notes"])
    assert "the saved run could not be loaded" in notes
    assert str(tmp_path) not in notes
    assert "secret_run" not in notes
