"""Photo reading for POST /api/read-photo: capped upload read, source choice, public result shape.

The image is held in memory only. It is never written to disk by this module and
its bytes are never logged. Replay looks up replay/photo_<12 hex>.json by SHA-256.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import UploadFile
from starlette.concurrency import run_in_threadpool

from core.bank_fallback import REPO_ROOT
from core.photo_reader import (
    MAX_IMAGE_BYTES,
    TOO_LARGE_MESSAGE,
    FakePhotoSource,
    LivePhotoSource,
    PhotoSource,
    PhotoSourceError,
    ReplayPhotoSource,
    read_photo,
    sha256_hex,
)

PHOTO_REPLAY_DIR: Path = REPO_ROOT / "replay"
PHOTO_REPLAY_PREFIX = "photo_"
PHOTO_REPLAY_HEX_LENGTH = 12
READ_CHUNK_BYTES = 64 * 1024
CHECKER_FIELDS = ("checker_readable", "checker_reason")
MODE_LIVE = "live"
MODE_REPLAY = "replay"
MODE_FAKE = "fake"
NO_SAVED_READING_MESSAGE = (
    "no saved reading exists for this photo; replay mode only works for a photo "
    "that has a saved reading"
)
UNREADABLE_SAVED_MESSAGE = "the saved reading for this photo could not be read"


class UploadTooLarge(Exception):
    """The upload grew past MAX_IMAGE_BYTES while being read."""


class _RefusingSource(PhotoSource):
    """A source that never reads: it reports why no reading is available."""

    name = "replay (no saved reading)"

    def __init__(self, message: str) -> None:
        self._message = message

    def get_reading(self, image: bytes, media_type: str, topics: tuple[str, ...]) -> Any:
        raise PhotoSourceError(self._message)


async def read_capped(upload: UploadFile) -> bytes:
    """Read the upload in chunks, stopping as soon as it passes the size cap."""
    buffer = bytearray()
    while True:
        chunk = await upload.read(READ_CHUNK_BYTES)
        if not chunk:
            return bytes(buffer)
        buffer.extend(chunk)
        if len(buffer) > MAX_IMAGE_BYTES:
            raise UploadTooLarge(TOO_LARGE_MESSAGE)


def _replay_path(image: bytes) -> Path:
    digest = sha256_hex(image)
    return PHOTO_REPLAY_DIR / f"{PHOTO_REPLAY_PREFIX}{digest[:PHOTO_REPLAY_HEX_LENGTH]}.json"


def _replay_source(image: bytes) -> PhotoSource:
    path = _replay_path(image)
    if not path.exists():
        return _RefusingSource(NO_SAVED_READING_MESSAGE)
    try:
        return ReplayPhotoSource(path)
    except (OSError, ValueError):
        return _RefusingSource(UNREADABLE_SAVED_MESSAGE)


def _photo_source(mode: str, image: bytes) -> PhotoSource:
    if mode == MODE_FAKE:
        return FakePhotoSource()
    if mode == MODE_LIVE:
        return LivePhotoSource()
    return _replay_source(image)


def _label(source: PhotoSource) -> str:
    """The plain-words line that says where the reading came from."""
    if isinstance(source, FakePhotoSource):
        return "Scripted reading; no model read this photo"
    if isinstance(source, LivePhotoSource):
        return "Read by the live model; check the transcription before you continue"
    if isinstance(source, ReplayPhotoSource):
        return (
            f"Replay of a saved {source.source} reading from {source.saved_at}; "
            "no model was called"
        )
    return "No reading is available for this photo; no model was called"


def _public_result(result: dict, label: str) -> dict[str, Any]:
    """The read_photo result without the checker fields, plus the source label."""
    public = {key: value for key, value in result.items() if key not in CHECKER_FIELDS}
    return {**public, "label": label}


async def read_uploaded_photo(upload: UploadFile, mode: str) -> dict[str, Any]:
    """Read an uploaded photo with the source for mode. Raises UploadTooLarge past the cap."""
    image = await read_capped(upload)
    source = _photo_source(mode, image)
    result = await run_in_threadpool(read_photo, image, source)
    return _public_result(result, _label(source))
