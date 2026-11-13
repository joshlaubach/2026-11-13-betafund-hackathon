"""Worksheet endpoints for the Echo worksheet page: read, grade, regrade, and skill profile.

This module wraps core/worksheet.py and core/skills.py and adds no checking logic. Photo
bytes are held in memory only and are never written. Saved replays are written only when
ECHO_SAVE_REPLAYS=1 and the run was live: a reading file (save_worksheet_reading) or a
grades file (save_grades). Neither holds image bytes. Replay files are named by SHA-256
prefixes only; topic and level strings are never used as paths.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import UploadFile
from pydantic import BaseModel, field_validator
from starlette.concurrency import run_in_threadpool

from core.bank_fallback import BANK_PATH, REPO_ROOT
from core.drafter import SOURCE_LIVE
from core.photo_reader import SHA256_HEX_PATTERN, sha256_hex
from core.skills import build_profile, recommend, summarize
from core.worksheet import (
    BANK_METHOD,
    MAX_ITEMS,
    STATUS_OK,
    AnswerSolver,
    FakeSolver,
    ReplayWorksheetSource,
    WorksheetSource,
    grade_item,
    read_worksheet,
    regrade_item,
    save_worksheet_reading,
)
from core.worksheet_types import (
    GRADE_DISCLAIMER,
    GRADE_LABELS,
    Grade,
    GradedItem,
    WorksheetItem,
    WorksheetReading,
)
from scripts.audit_bank import classify, load_bank
from scripts.demo_worksheet import MODE_LIVE, MODE_REPLAY, build_solver, build_source, source_line
from server import photo_api

logger = logging.getLogger(__name__)

Mode = Literal["live", "replay", "fake"]
DEFAULT_MODE = "replay"
GRADE_WORKERS = 4
WORKSHEET_REPLAY_DIR: Path = REPO_ROOT / "replay"
READING_REPLAY_PREFIX = "worksheet_"
GRADES_REPLAY_PREFIX = "grades_"
REPLAY_HEX_LENGTH = 12
GRADES_SOURCE = SOURCE_LIVE
ENV_SAVE_REPLAYS = "ECHO_SAVE_REPLAYS"
SAVE_REPLAYS_ON = "1"
NO_SAVED_READING_MESSAGE = (
    "no saved reading exists for this photo; replay mode only works for a photo "
    "that has a saved reading"
)
UNREADABLE_SAVED_MESSAGE = "the saved reading for this photo could not be read"
NO_READING_LABEL = "No reading is available for this photo; no model was called"
NO_SAVED_GRADE_EXPLANATION = (
    "no saved AI grade exists for this worksheet; switch to live mode"
)
UNGRADED_EXPLANATION = "this mark could not be checked, so it is unsure."
TOO_MANY_ITEMS_MESSAGE = f"a worksheet can have at most {MAX_ITEMS} problems"
UNSURE = "unsure"
AI_JUDGMENT_METHOD = "ai_judgment"


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


def _check_item_count(items: Sequence[object]) -> None:
    if len(items) > MAX_ITEMS:
        raise ValueError(TOO_MANY_ITEMS_MESSAGE)


class GradeRequest(BaseModel):
    reading: WorksheetReading
    mode: Mode = DEFAULT_MODE

    @field_validator("reading")
    @classmethod
    def _limit_items(cls, reading: WorksheetReading) -> WorksheetReading:
        _check_item_count(reading.items)
        return reading


class ProfileRequest(BaseModel):
    graded: tuple[GradedItem, ...]

    @field_validator("graded")
    @classmethod
    def _limit_items(cls, graded: tuple[GradedItem, ...]) -> tuple[GradedItem, ...]:
        _check_item_count(graded)
        return graded


class RegradeRequest(BaseModel):
    graded: GradedItem
    mode: Mode = DEFAULT_MODE


# ---------------------------------------------------------------------------
# Saved replays
# ---------------------------------------------------------------------------


def reading_sha256(reading: WorksheetReading) -> str:
    """SHA-256 of the canonical JSON of a reading. It names the saved grades file."""
    canonical = json.dumps(
        reading.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return sha256_hex(canonical.encode("utf-8"))


def save_grades(path: Path | str, reading_digest: str, graded: Sequence[GradedItem]) -> None:
    """Write graded items to a JSON file. Holds the reading SHA-256 and the marks, never image bytes."""
    if not SHA256_HEX_PATTERN.fullmatch(reading_digest):
        raise ValueError("reading_sha256 must be a 64-character lowercase hex digest")
    payload = {
        "source": GRADES_SOURCE,
        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "reading_sha256": reading_digest,
        "graded": [entry.model_dump(mode="json") for entry in graded],
    }
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def load_grades(path: Path | str, reading_digest: str) -> list[GradedItem]:
    """Read saved grades for one reading. Raises ValueError when the file is not for that reading."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("source") != GRADES_SOURCE:
        raise ValueError(f"{path} is not a saved Echo worksheet grading")
    if data.get("reading_sha256") != reading_digest:
        raise ValueError(f"{path} is for a different reading")
    entries = data.get("graded")
    if not isinstance(entries, list):
        raise ValueError(f"{path} is missing its graded items")
    _check_item_count(entries)
    return [GradedItem.model_validate(entry) for entry in entries]


def _replay_path(prefix: str, digest: str) -> Path:
    return WORKSHEET_REPLAY_DIR / f"{prefix}{digest[:REPLAY_HEX_LENGTH]}.json"


def _save_replays_enabled() -> bool:
    return os.environ.get(ENV_SAVE_REPLAYS, "").strip() == SAVE_REPLAYS_ON


def _save_live_reading(digest: str, reading_payload: dict, source: WorksheetSource) -> None:
    if not _save_replays_enabled():
        return
    try:
        reading = WorksheetReading.model_validate(reading_payload)
        save_worksheet_reading(
            _replay_path(READING_REPLAY_PREFIX, digest), digest, reading, source.source
        )
    except (OSError, ValueError) as error:
        logger.error("could not save worksheet reading replay: %s", type(error).__name__)


def _save_live_grades(digest: str, graded: Sequence[GradedItem]) -> None:
    if not _save_replays_enabled():
        return
    try:
        save_grades(_replay_path(GRADES_REPLAY_PREFIX, digest), digest, graded)
    except (OSError, ValueError) as error:
        logger.error("could not save worksheet grades replay: %s", type(error).__name__)


def _saved_grades(digest: str) -> list[GradedItem] | None:
    path = _replay_path(GRADES_REPLAY_PREFIX, digest)
    if not path.exists():
        return None
    try:
        return load_grades(path, digest)
    except (OSError, ValueError) as error:
        logger.error("could not load saved worksheet grades: %s", type(error).__name__)
        return None


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


class _RefusingWorksheetSource(WorksheetSource):
    """A source that never reads: it reports why no reading is available."""

    name = "replay (no saved reading)"

    def __init__(self, message: str) -> None:
        self._message = message

    def get_reading(
        self, image: bytes, media_type: str, topics: tuple[str, ...]
    ) -> WorksheetReading:
        raise ValueError(self._message)


def _replay_source(digest: str) -> WorksheetSource:
    path = _replay_path(READING_REPLAY_PREFIX, digest)
    if not path.exists():
        return _RefusingWorksheetSource(NO_SAVED_READING_MESSAGE)
    try:
        return ReplayWorksheetSource(path)
    except (OSError, ValueError):
        return _RefusingWorksheetSource(UNREADABLE_SAVED_MESSAGE)


def _worksheet_source(mode: str, digest: str) -> WorksheetSource:
    if mode == MODE_REPLAY:
        return _replay_source(digest)
    return build_source(mode, None)


def _source_label(source: WorksheetSource, mode: str) -> str:
    """The plain-words source line that demo_worksheet prints, without its grading half."""
    if isinstance(source, _RefusingWorksheetSource):
        return NO_READING_LABEL
    reading_line, _separator, _grading = source_line(source, build_solver(mode)).partition("; ")
    return reading_line


async def read_uploaded_worksheet(upload: UploadFile, mode: str) -> dict[str, Any]:
    """Read an uploaded worksheet photo. Raises photo_api.UploadTooLarge past the cap."""
    image = await photo_api.read_capped(upload)
    digest = sha256_hex(image)
    source = _worksheet_source(mode, digest)
    result = await run_in_threadpool(read_worksheet, image, source)
    if mode == MODE_LIVE and result["status"] == STATUS_OK:
        await run_in_threadpool(_save_live_reading, digest, result["reading"], source)
    return {
        "status": result["status"],
        "source": result["source"],
        "label": _source_label(source, mode),
        "reading": result["reading"],
        "error": result["error"],
        "image_sha256": result["image_sha256"],
    }


# ---------------------------------------------------------------------------
# Grading
# ---------------------------------------------------------------------------


def _eligible_bank() -> tuple[dict, ...]:
    """Bank problems that pass the audit. Raises ValueError when the bank cannot be read."""
    return tuple(problem for problem in load_bank(BANK_PATH) if classify(problem) is None)


def _unsure(explanation: str) -> Grade:
    return Grade(
        verdict=UNSURE,
        method=AI_JUDGMENT_METHOD,
        label=GRADE_LABELS[AI_JUDGMENT_METHOD],
        explanation=explanation,
    )


def _grade_one(item: WorksheetItem, solver: AnswerSolver, problems: tuple[dict, ...]) -> GradedItem:
    try:
        return GradedItem(item=item, grade=grade_item(item, solver, bank=problems))
    except Exception as error:  # one item's failure must not crash the others
        logger.error("grading one worksheet item failed: %s", type(error).__name__)
        return GradedItem(item=item, grade=_unsure(UNGRADED_EXPLANATION))


def _replay_item(item: WorksheetItem, problems: tuple[dict, ...]) -> GradedItem:
    """Bank matches are graded deterministically; anything else needs a saved AI grade."""
    graded = _grade_one(item, FakeSolver(), problems)
    if graded.grade.method == BANK_METHOD:
        return graded
    return GradedItem(item=item, grade=_unsure(NO_SAVED_GRADE_EXPLANATION))


def _grade_all(
    items: Sequence[WorksheetItem], grade: Callable[[WorksheetItem], GradedItem]
) -> list[GradedItem]:
    """Grade items in parallel. pool.map keeps the worksheet order."""
    with ThreadPoolExecutor(max_workers=GRADE_WORKERS) as pool:
        return list(pool.map(grade, items))


def grade_payload(graded: list[GradedItem], build_dir: Path) -> dict[str, Any]:
    """The grade and profile response: marks, skills, summary, recommendations, disclaimer."""
    profile = build_profile(graded, build_dir)
    return {
        "graded": [entry.model_dump(mode="json") for entry in graded],
        "skills": [skill.model_dump(mode="json") for skill in profile.skills],
        "unplaced": profile.unplaced,
        "summary": summarize(profile),
        "recommendations": [
            rec.model_dump(mode="json") for rec in recommend(profile, build_dir=build_dir)
        ],
        "disclaimer": GRADE_DISCLAIMER,
    }


def grade_reading(body: GradeRequest, build_dir: Path) -> dict[str, Any]:
    problems = _eligible_bank()
    digest = reading_sha256(body.reading)
    if body.mode == MODE_REPLAY:
        graded = _saved_grades(digest)
        if graded is None:
            graded = _grade_all(body.reading.items, lambda item: _replay_item(item, problems))
        return grade_payload(graded, build_dir)
    solver = build_solver(body.mode)
    graded = _grade_all(body.reading.items, lambda item: _grade_one(item, solver, problems))
    if body.mode == MODE_LIVE:
        _save_live_grades(digest, graded)
    return grade_payload(graded, build_dir)


def profile_graded(body: ProfileRequest, build_dir: Path) -> dict[str, Any]:
    return grade_payload(list(body.graded), build_dir)


def regrade_graded(body: RegradeRequest) -> dict[str, Any]:
    """Live regrades use the live solver. Replay and fake keep the grade and mark it regraded."""
    if body.mode != MODE_LIVE:
        unchanged = body.graded.model_copy(update={"regraded": True, "changed_on_regrade": False})
        return unchanged.model_dump(mode="json")
    return regrade_item(body.graded, build_solver(body.mode)).model_dump(mode="json")
