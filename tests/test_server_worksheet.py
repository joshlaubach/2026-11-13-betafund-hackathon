"""Tests for the worksheet endpoints in server/worksheet_api.py. Offline only: no network, no model call.

ANTHROPIC_API_KEY is removed unless a test sets a fake value, and the build and replay
directories are temporary. Live paths run only with no key, or with a scripted solver or source.
"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from core.bank_fallback import BANK_PATH  # noqa: E402
from core.photo_reader import MAX_IMAGE_BYTES, PNG_MAGIC, sha256_hex  # noqa: E402
from core.worksheet import FakeSolver, FakeWorksheetSource, save_worksheet_reading  # noqa: E402
from core.worksheet_types import (  # noqa: E402
    GRADE_DISCLAIMER,
    GRADE_LABELS,
    GradedItem,
    WorksheetItem,
    WorksheetReading,
)
from scripts.audit_bank import load_bank  # noqa: E402
from server import app as app_module  # noqa: E402
from server import worksheet_api  # noqa: E402

FAKE_KEY = "sk-ant-TESTSECRET"
PNG_BYTES = PNG_MAGIC + b"\x00" * 32
LA01 = next(problem for problem in load_bank(BANK_PATH) if problem["id"] == "LA01")
BANK_STATEMENT = LA01["statement"]
BANK_ANSWER = LA01["answer"]["latex"]
BANK_TOPIC = LA01["topic"]
WRONG_ANSWER = "\\frac{1}{4}"
UNKNOWN_STATEMENT = "Find the area of a circle of radius $r$."
UNKNOWN_ANSWER = "\\pi r^{2}"
MAX_ITEMS = worksheet_api.MAX_ITEMS
UNSURE = "unsure"
NO_SAVED_READING_TEXT = "no saved reading exists for this photo"
UNREADABLE_TEXT = "the saved reading for this photo could not be read"
NO_SAVED_GRADE_TEXT = "no saved AI grade exists for this worksheet; switch to live mode"
JUDGE_FAILED_TEXT = "the AI judge could not give a verdict, so this mark is unsure."
UNGRADED_TEXT = "this mark could not be checked, so it is unsure."
REPLAY_PREFIX_LENGTH = 12
SAVED_NOTE = "saved in test"
TOO_MANY = MAX_ITEMS + 1
LOCAL_BASE_URL = "http://127.0.0.1:8000"  # the guard only accepts localhost Host headers


def make_item(number: int, statement: str, answer: str | None, topic: str | None = None) -> WorksheetItem:
    return WorksheetItem(
        number=number,
        statement_latex=statement,
        student_answer_latex=answer,
        topic_guess=topic,
    )


def make_reading(*items: WorksheetItem) -> WorksheetReading:
    return WorksheetReading(items=tuple(items))


def standard_reading() -> WorksheetReading:
    return make_reading(
        make_item(1, BANK_STATEMENT, BANK_ANSWER, BANK_TOPIC),
        make_item(2, UNKNOWN_STATEMENT, UNKNOWN_ANSWER, "power_rule"),
    )


def bank_mark(verdict: str, number: int = 1) -> dict:
    """A graded item the way the bank tier marks it, built by hand for profile tests."""
    return {
        "item": make_item(number, BANK_STATEMENT, BANK_ANSWER, BANK_TOPIC).model_dump(mode="json"),
        "grade": {
            "verdict": verdict,
            "method": "bank_key",
            "label": GRADE_LABELS["bank_key"],
            "reference_answer_latex": BANK_ANSWER,
            "explanation": "test mark",
            "bank_topic": BANK_TOPIC,
            "bank_id": "LA01",
        },
        "regraded": False,
        "changed_on_regrade": False,
    }


def replay_file(replay_dir: Path, prefix: str, digest: str) -> Path:
    return replay_dir / f"{prefix}{digest[:REPLAY_PREFIX_LENGTH]}.json"


def read_upload(client: TestClient, data: bytes, mode: str | None = "fake"):
    form = {} if mode is None else {"mode": mode}
    return client.post(
        "/api/worksheet/read",
        files={"file": ("photo.png", data, "image/png")},
        data=form,
    )


def grade_request(client: TestClient, reading: WorksheetReading, mode: str | None = "fake"):
    body = {"reading": reading.model_dump(mode="json")}
    if mode is not None:
        body["mode"] = mode
    return client.post("/api/worksheet/grade", json=body)


class ScriptedLiveSource(FakeWorksheetSource):
    """Stands in for the live reader: source is "live" so saving logic runs, but no model is called."""

    source = "live"
    name = "live (test double)"


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ECHO_SAVE_REPLAYS", raising=False)
    monkeypatch.setattr(app_module, "BUILD_DIR", tmp_path / "build")
    monkeypatch.setattr(worksheet_api, "WORKSHEET_REPLAY_DIR", tmp_path / "replay")
    return TestClient(app_module.app, base_url=LOCAL_BASE_URL)


@pytest.fixture
def replay_dir(tmp_path) -> Path:
    return tmp_path / "replay"


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


def test_read_fake_returns_reading_label_and_hash_only(client):
    response = read_upload(client, PNG_BYTES, "fake")
    body = response.json()
    assert response.status_code == 200
    assert set(body) == {"status", "source", "label", "reading", "error", "image_sha256"}
    assert body["status"] == "ok"
    assert len(body["reading"]["items"]) == 2
    assert body["image_sha256"] == sha256_hex(PNG_BYTES)
    assert "FAKE" in body["label"]


def test_read_non_image_returns_error_status(client):
    response = client.post(
        "/api/worksheet/read",
        files={"file": ("notes.txt", b"hello, this is not an image", "text/plain")},
        data={"mode": "fake"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "error"
    assert "PNG, JPEG, WEBP, or GIF" in response.json()["error"]


def test_read_over_five_megabytes_is_413(client):
    oversize = PNG_MAGIC + b"\x00" * MAX_IMAGE_BYTES
    response = read_upload(client, oversize, "fake")
    assert response.status_code == 413
    assert "5 MB" in response.json()["error"]


def test_read_replay_without_saved_file_says_so(client):
    response = read_upload(client, PNG_BYTES, "replay")
    body = response.json()
    assert body["status"] == "error"
    assert body["reading"] is None
    assert NO_SAVED_READING_TEXT in body["error"]


def test_read_defaults_to_replay_mode(client):
    body = read_upload(client, PNG_BYTES, None).json()
    assert body["status"] == "error"
    assert NO_SAVED_READING_TEXT in body["error"]


def test_read_replay_with_saved_file_returns_saved_reading(client, replay_dir):
    digest = sha256_hex(PNG_BYTES)
    saved = standard_reading()
    save_worksheet_reading(replay_file(replay_dir, "worksheet_", digest), digest, saved, "fake")
    body = read_upload(client, PNG_BYTES, "replay").json()
    assert body["status"] == "ok"
    assert body["reading"]["items"][0]["statement_latex"] == BANK_STATEMENT
    assert "REPLAY" in body["label"]


def test_read_replay_with_corrupt_saved_file_is_clear_error(client, replay_dir):
    digest = sha256_hex(PNG_BYTES)
    path = replay_file(replay_dir, "worksheet_", digest)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")
    body = read_upload(client, PNG_BYTES, "replay").json()
    assert body["status"] == "error"
    assert UNREADABLE_TEXT in body["error"]


def test_read_live_without_key_degrades_without_leaking(client, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "   ")
    response = read_upload(client, PNG_BYTES, "live")
    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "error"
    assert body["error"] == "API key missing or invalid"
    assert FAKE_KEY not in response.text


def test_read_live_success_saves_replay_only_when_enabled(client, monkeypatch, replay_dir):
    monkeypatch.setattr(
        worksheet_api,
        "build_source",
        lambda mode, path: ScriptedLiveSource(standard_reading()),
    )
    monkeypatch.setenv("ECHO_SAVE_REPLAYS", "1")
    body = read_upload(client, PNG_BYTES, "live").json()
    assert body["status"] == "ok"
    saved_path = replay_file(replay_dir, "worksheet_", sha256_hex(PNG_BYTES))
    saved = json.loads(saved_path.read_text(encoding="utf-8"))
    assert set(saved) == {"source", "saved_at", "image_sha256", "reading"}
    assert saved["source"] == "live"
    assert saved["image_sha256"] == sha256_hex(PNG_BYTES)
    assert PNG_MAGIC.decode("latin-1") not in saved_path.read_text(encoding="utf-8")


def test_read_live_success_saves_nothing_by_default(client, monkeypatch, replay_dir):
    monkeypatch.setattr(
        worksheet_api,
        "build_source",
        lambda mode, path: ScriptedLiveSource(standard_reading()),
    )
    body = read_upload(client, PNG_BYTES, "live").json()
    assert body["status"] == "ok"
    assert not replay_dir.exists() or not any(replay_dir.iterdir())


# ---------------------------------------------------------------------------
# Grade
# ---------------------------------------------------------------------------


def test_grade_fake_returns_labels_skills_recommendations_and_disclaimer(client):
    response = grade_request(client, standard_reading(), "fake")
    body = response.json()
    assert response.status_code == 200
    assert set(body) == {
        "graded", "skills", "unplaced", "summary", "recommendations", "disclaimer",
    }
    first, second = body["graded"]
    assert first["grade"]["method"] == "bank_key"
    assert first["grade"]["verdict"] == "correct"
    assert first["grade"]["label"] == GRADE_LABELS["bank_key"]
    assert second["grade"]["method"] == "ai_judgment"
    assert second["grade"]["label"] == GRADE_LABELS["ai_judgment"]
    assert second["grade"]["verdict"] == UNSURE
    assert body["summary"]["problems_seen"] == 2
    assert body["summary"]["verified_marks"] == 1
    assert body["summary"]["ai_marks"] == 1
    assert body["unplaced"] == 0
    assert {skill["topic"] for skill in body["skills"]} == {BANK_TOPIC, "power_rule"}
    assert body["recommendations"][0]["rank"] == 1
    assert body["disclaimer"] == GRADE_DISCLAIMER


def test_grade_replay_without_saved_file_grades_bank_and_marks_rest_unsure(client):
    body = grade_request(client, standard_reading(), "replay").json()
    first, second = body["graded"]
    assert first["grade"]["method"] == "bank_key"
    assert first["grade"]["verdict"] == "correct"
    assert second["grade"]["method"] == "ai_judgment"
    assert second["grade"]["verdict"] == UNSURE
    assert second["grade"]["explanation"] == NO_SAVED_GRADE_TEXT


def test_grade_replay_uses_saved_grades_file_when_present(client, replay_dir):
    reading = standard_reading()
    digest = worksheet_api.reading_sha256(reading)
    saved = [
        GradedItem.model_validate(
            {
                "item": reading.items[0].model_dump(mode="json"),
                "grade": {
                    "verdict": "incorrect",
                    "method": "ai_judgment",
                    "label": GRADE_LABELS["ai_judgment"],
                    "explanation": SAVED_NOTE,
                },
            }
        ),
        GradedItem.model_validate(
            {
                "item": reading.items[1].model_dump(mode="json"),
                "grade": {
                    "verdict": "correct",
                    "method": "ai_solve_sympy",
                    "label": GRADE_LABELS["ai_solve_sympy"],
                    "explanation": SAVED_NOTE,
                },
            }
        ),
    ]
    worksheet_api.save_grades(replay_file(replay_dir, "grades_", digest), digest, saved)
    body = grade_request(client, reading, "replay").json()
    assert [entry["grade"]["explanation"] for entry in body["graded"]] == [SAVED_NOTE, SAVED_NOTE]
    assert body["graded"][1]["grade"]["verdict"] == "correct"


def test_grade_unexpected_item_failure_does_not_crash_others(client, monkeypatch):
    real_grade_item = worksheet_api.grade_item

    def flaky(item, solver, bank=None, effort=None, budget=None):
        if item.number == 2:
            raise RuntimeError("boom")
        return real_grade_item(item, solver, bank=bank, effort=effort, budget=budget)

    monkeypatch.setattr(worksheet_api, "grade_item", flaky)
    response = grade_request(client, standard_reading(), "fake")
    body = response.json()
    assert response.status_code == 200
    assert [entry["item"]["number"] for entry in body["graded"]] == [1, 2]
    assert body["graded"][0]["grade"]["verdict"] == "correct"
    assert body["graded"][1]["grade"]["verdict"] == UNSURE
    assert body["graded"][1]["grade"]["explanation"] == UNGRADED_TEXT
    assert "boom" not in response.text


def test_grade_live_without_key_degrades_and_grades_bank_match(client):
    response = grade_request(client, standard_reading(), "live")
    body = response.json()
    assert response.status_code == 200
    assert body["graded"][0]["grade"]["verdict"] == "correct"
    assert body["graded"][1]["grade"]["verdict"] == UNSURE
    assert body["graded"][1]["grade"]["explanation"] == JUDGE_FAILED_TEXT
    assert FAKE_KEY not in response.text


def test_grade_live_saves_grades_only_when_enabled(client, monkeypatch, replay_dir):
    monkeypatch.setattr(worksheet_api, "build_solver", lambda mode: FakeSolver())
    monkeypatch.setenv("ECHO_SAVE_REPLAYS", "1")
    reading = standard_reading()
    response = grade_request(client, reading, "live")
    assert response.status_code == 200
    digest = worksheet_api.reading_sha256(reading)
    path = replay_file(replay_dir, "grades_", digest)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert set(saved) == {"source", "saved_at", "reading_sha256", "graded"}
    assert saved["source"] == "live"
    assert saved["reading_sha256"] == digest
    assert len(saved["graded"]) == 2
    assert PNG_MAGIC.decode("latin-1") not in path.read_text(encoding="utf-8")
    assert worksheet_api.load_grades(path, digest)[0].grade.verdict == "correct"


def test_grade_live_saves_nothing_by_default(client, monkeypatch, replay_dir):
    monkeypatch.setattr(worksheet_api, "build_solver", lambda mode: FakeSolver())
    assert grade_request(client, standard_reading(), "live").status_code == 200
    assert not replay_dir.exists() or not any(replay_dir.iterdir())


def test_save_and_load_grades_reject_other_reading(tmp_path):
    reading = standard_reading()
    digest = worksheet_api.reading_sha256(reading)
    path = tmp_path / "grades.json"
    worksheet_api.save_grades(path, digest, [])
    assert worksheet_api.load_grades(path, digest) == []
    with pytest.raises(ValueError):
        worksheet_api.load_grades(path, "0" * 64)


def test_grade_more_than_twenty_items_is_422(client):
    items = [make_item(number, UNKNOWN_STATEMENT, UNKNOWN_ANSWER) for number in range(1, TOO_MANY + 1)]
    response = grade_request(client, make_reading(*items), "fake")
    assert response.status_code == 422


def test_grade_bad_mode_is_422(client):
    response = grade_request(client, standard_reading(), "telepathy")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Regrade
# ---------------------------------------------------------------------------


def test_regrade_fake_marks_regraded_and_keeps_grade(client):
    graded = grade_request(client, standard_reading(), "fake").json()["graded"]
    body = client.post(
        "/api/worksheet/regrade", json={"graded": graded[1], "mode": "fake"}
    ).json()
    assert body["regraded"] is True
    assert body["changed_on_regrade"] is False
    assert body["grade"] == graded[1]["grade"]


def test_regrade_bank_key_grade_is_never_changed(client, monkeypatch):
    monkeypatch.setattr(worksheet_api, "build_solver", lambda mode: FakeSolver(verdict="correct"))
    graded = grade_request(client, standard_reading(), "replay").json()["graded"]
    body = client.post(
        "/api/worksheet/regrade", json={"graded": graded[0], "mode": "live"}
    ).json()
    assert body["regraded"] is True
    assert body["changed_on_regrade"] is False
    assert body["grade"]["method"] == "bank_key"


def test_regrade_live_ai_grade_can_change(client, monkeypatch):
    monkeypatch.setattr(worksheet_api, "build_solver", lambda mode: FakeSolver(verdict="correct"))
    graded = grade_request(client, standard_reading(), "replay").json()["graded"]
    body = client.post(
        "/api/worksheet/regrade", json={"graded": graded[1], "mode": "live"}
    ).json()
    assert body["regraded"] is True
    assert body["changed_on_regrade"] is True
    assert body["grade"]["verdict"] == "correct"


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


def test_profile_recomputes_skills_from_given_marks(client):
    marks = [bank_mark("correct"), bank_mark("incorrect", 2), bank_mark("incorrect", 3)]
    body = client.post("/api/worksheet/profile", json={"graded": marks}).json()
    assert len(body["graded"]) == 3
    assert body["skills"][0]["topic"] == BANK_TOPIC
    assert body["skills"][0]["status"] == "weak"
    assert body["summary"]["weak"] == 1
    assert body["summary"]["verified_marks"] == 3
    assert body["recommendations"][0]["topic"] == BANK_TOPIC
    assert body["recommendations"][0]["suggested_level"] == 1


def test_profile_changes_when_marks_change(client):
    marks = [bank_mark("correct"), bank_mark("correct", 2)]
    body = client.post("/api/worksheet/profile", json={"graded": marks}).json()
    assert body["skills"][0]["status"] == "solid"
    assert body["recommendations"] == []


def test_profile_more_than_twenty_items_is_422(client):
    marks = [bank_mark("correct", number) for number in range(1, TOO_MANY + 1)]
    response = client.post("/api/worksheet/profile", json={"graded": marks})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Secrets and CORS
# ---------------------------------------------------------------------------


def test_api_key_value_never_appears_in_any_response(client, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE_KEY)
    reading = standard_reading()
    graded = grade_request(client, reading, "fake").json()["graded"]
    responses = [
        read_upload(client, PNG_BYTES, "fake"),
        read_upload(client, PNG_BYTES, "replay"),
        grade_request(client, reading, "fake"),
        grade_request(client, reading, "replay"),
        client.post("/api/worksheet/regrade", json={"graded": graded[1], "mode": "fake"}),
        client.post("/api/worksheet/profile", json={"graded": graded}),
        grade_request(client, reading, "telepathy"),
    ]
    for response in responses:
        assert FAKE_KEY not in response.text


def test_cors_allows_localhost_3000_only(client):
    allowed = client.post(
        "/api/worksheet/profile", json={"graded": []}, headers={"Origin": "http://localhost:3000"}
    )
    blocked = client.post(
        "/api/worksheet/profile", json={"graded": []}, headers={"Origin": "http://evil.example"}
    )
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert "access-control-allow-origin" not in blocked.headers
