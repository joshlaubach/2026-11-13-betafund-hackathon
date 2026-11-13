"""Read a photo of a calculus problem into a reading that a tutor confirms first.

Three photo sources share one interface, like core/drafter.py: LivePhotoSource
(Claude vision), ReplayPhotoSource (a saved reading on disk, matched to the photo
by its SHA-256), and FakePhotoSource (scripted). read_photo() checks the image
bytes before any source runs, keeps a topic guess only when it is a bank topic
id, and records whether the checker can read the transcribed LaTeX. It never
raises for a source failure and never solves the problem.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

import anthropic
from pydantic import BaseModel

from core.bank_fallback import BANK_PATH
from core.drafter import (
    AUTH_MESSAGE,
    DEFAULT_EFFORT,
    DEFAULT_MODEL,
    GENERIC_SOURCE_MESSAGE,
    MAX_TOKENS,
    SOURCE_FAKE,
    SOURCE_LIVE,
)
from core.input_boundary import BoundaryError
from core.latex_reader import MAX_LATEX_LENGTH, read_latex
from scripts.audit_bank import load_bank

logger = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MEGABYTE = 1024 * 1024
MEDIA_PNG = "image/png"
MEDIA_JPEG = "image/jpeg"
MEDIA_WEBP = "image/webp"
MEDIA_GIF = "image/gif"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff"
RIFF_MAGIC = b"RIFF"
WEBP_MARK = b"WEBP"
GIF_MAGICS = (b"GIF87a", b"GIF89a")
WEBP_MARK_SLICE = slice(8, 12)
SHA256_HEX_PATTERN = re.compile(r"[0-9a-f]{64}")
STATUS_OK = "ok"
STATUS_ERROR = "error"
STATUS_UNREADABLE = "unreadable"
READING_SOURCES = (SOURCE_LIVE, SOURCE_FAKE)
ENV_API_KEY = "ANTHROPIC_API_KEY"
OUTPUT_CONFIG_ARG = "output_config"
CONFIDENCE_LEVELS = ("low", "medium", "high")
NOT_BYTES_MESSAGE = "image must be bytes"
EMPTY_IMAGE_MESSAGE = "image is empty"
TOO_LARGE_MESSAGE = f"image is larger than {MAX_IMAGE_BYTES // MEGABYTE} MB"
UNKNOWN_TYPE_MESSAGE = "file is not a PNG, JPEG, WEBP, or GIF image"
REFUSAL_MESSAGE = "the model declined to read the photo"
EMPTY_MESSAGE = "the model returned no reading"
DIFFERENT_PHOTO_MESSAGE = "saved reading is for a different photo"
EMPTY_PROBLEM_MESSAGE = "no problem text was read from the photo"
LONG_PROBLEM_MESSAGE = f"problem text is longer than {MAX_LATEX_LENGTH} characters"

SYSTEM_PROMPT = (
    "You transcribe a student's handwritten or printed calculus problem for Echo. "
    "Write problem_latex in LaTeX with exactly what is written in the photo. "
    "Do not solve, simplify, complete, or correct the problem, even when it contains an error. "
    "If any part is illegible, cut off, or ambiguous, say which part in notes and lower confidence. "
    "Choose topic_guess only from the topic ids given in the request, or null if none fits. "
    "Return only the structured output requested."
)


class PhotoReading(BaseModel):
    problem_latex: str
    topic_guess: Optional[str]
    confidence: Literal["low", "medium", "high"]
    notes: str


class PhotoSourceError(Exception):
    """A photo source could not produce a reading. The message is shown to the user."""


class PhotoSource:
    """Base for photo sources. source is "live" or "fake"; name is for display."""

    name: str = "source"
    source: str = ""
    last_usage: Optional[dict] = None

    def get_reading(
        self, image: bytes, media_type: str, topics: tuple[str, ...]
    ) -> PhotoReading:
        raise NotImplementedError


FAKE_READING = PhotoReading(
    problem_latex="3x^{4} + 2x",
    topic_guess="power_rule",
    confidence="high",
    notes="scripted reading; no model read this photo",
)


class FakePhotoSource(PhotoSource):
    name = "fake"
    source = SOURCE_FAKE

    def __init__(self, reading: PhotoReading = FAKE_READING) -> None:
        self._reading = reading

    def get_reading(
        self, image: bytes, media_type: str, topics: tuple[str, ...]
    ) -> PhotoReading:
        return self._reading


class ReplayPhotoSource(PhotoSource):
    """Plays back a saved reading for the same photo. The original source is exposed as source."""

    def __init__(self, path: Path | str) -> None:
        saved = load_reading(path)
        self._saved = saved
        self.source = saved["source"]
        self.saved_at = saved.get("saved_at", "unknown time")
        self.name = f"replay (saved {self.source} reading)"

    def get_reading(
        self, image: bytes, media_type: str, topics: tuple[str, ...]
    ) -> PhotoReading:
        if sha256_hex(image) != self._saved["image_sha256"]:
            raise PhotoSourceError(DIFFERENT_PHOTO_MESSAGE)
        return self._saved["reading"]


class LivePhotoSource(PhotoSource):
    source = SOURCE_LIVE

    def __init__(self, model: str = DEFAULT_MODEL, effort: str = DEFAULT_EFFORT) -> None:
        self.model = model
        self.effort = effort
        self.name = f"live ({model}, effort {effort})"

    def get_reading(
        self, image: bytes, media_type: str, topics: tuple[str, ...]
    ) -> PhotoReading:
        self.last_usage = None
        if not os.environ.get(ENV_API_KEY, "").strip():
            raise PhotoSourceError(AUTH_MESSAGE)
        try:
            return self._parse(image, media_type, topics)
        except anthropic.AuthenticationError as error:
            raise PhotoSourceError(AUTH_MESSAGE) from error
        except anthropic.RateLimitError as error:
            raise PhotoSourceError("rate limited by the model service; try again later") from error
        except anthropic.APIConnectionError as error:
            raise PhotoSourceError("could not reach the model service") from error
        except anthropic.APIStatusError as error:
            raise PhotoSourceError(
                f"the model service returned HTTP {error.status_code}"
            ) from error

    def _parse(self, image: bytes, media_type: str, topics: tuple[str, ...]) -> PhotoReading:
        client = anthropic.Anthropic()
        request = {
            "model": self.model,
            "max_tokens": MAX_TOKENS,
            "system": SYSTEM_PROMPT,
            "messages": [
                {
                    "role": "user",
                    "content": _image_content(image, media_type, build_prompt(topics)),
                }
            ],
            "output_format": PhotoReading,
        }
        try:
            response = client.messages.parse(**request, output_config={"effort": self.effort})
        except TypeError as error:
            if OUTPUT_CONFIG_ARG not in str(error):
                raise
            response = client.messages.parse(**request)  # retry once without output_config
        self.last_usage = _usage_of(response)
        if response.stop_reason == "refusal":
            raise PhotoSourceError(REFUSAL_MESSAGE)
        if response.parsed_output is None:
            raise PhotoSourceError(EMPTY_MESSAGE)
        return response.parsed_output


def _image_content(image: bytes, media_type: str, prompt: str) -> list[dict]:
    """The image block comes before the text block, as the vision API expects."""
    encoded = base64.standard_b64encode(image).decode("ascii")
    return [
        {
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": encoded},
        },
        {"type": "text", "text": prompt},
    ]


def _usage_of(response: object) -> Optional[dict]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    return {
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
    }


def build_prompt(topics: tuple[str, ...]) -> str:
    return "\n".join(
        [
            "Transcribe the calculus problem in the photo.",
            "topic_guess must be one of these topic ids, or null: " + ", ".join(topics),
        ]
    )


def detect_media_type(image: bytes) -> Optional[str]:
    """The image type from its leading magic bytes, or None when it is not PNG, JPEG, WEBP, or GIF."""
    if image.startswith(PNG_MAGIC):
        return MEDIA_PNG
    if image.startswith(JPEG_MAGIC):
        return MEDIA_JPEG
    if image[:4] == RIFF_MAGIC and image[WEBP_MARK_SLICE] == WEBP_MARK:
        return MEDIA_WEBP
    if image.startswith(GIF_MAGICS):
        return MEDIA_GIF
    return None


def check_image(image: object) -> tuple[Optional[str], Optional[str]]:
    """(media_type, None) for a usable image; (None, message) for anything else."""
    if not isinstance(image, (bytes, bytearray)):
        return None, NOT_BYTES_MESSAGE
    if len(image) == 0:
        return None, EMPTY_IMAGE_MESSAGE
    if len(image) > MAX_IMAGE_BYTES:
        return None, TOO_LARGE_MESSAGE
    media_type = detect_media_type(bytes(image))
    if media_type is None:
        return None, UNKNOWN_TYPE_MESSAGE
    return media_type, None


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bank_topic_ids() -> tuple[str, ...]:
    """The sorted topic ids in the problem bank. Raises ValueError when the bank cannot be read."""
    return tuple(sorted({problem["topic"] for problem in load_bank(BANK_PATH)}))


def _topic_ids(topics: Optional[Sequence[str]]) -> tuple[str, ...]:
    if topics is None:
        return bank_topic_ids()
    return tuple(sorted(set(topics)))


def _join_notes(existing: str, extra: str) -> str:
    return " ".join(part for part in (existing.strip(), extra) if part)


def _normalized(reading: PhotoReading, topics: tuple[str, ...]) -> tuple[PhotoReading, bool]:
    """Strip the problem text and clear a topic guess that is not a bank topic. Never mutates input."""
    problem = reading.problem_latex.strip()
    guess = reading.topic_guess
    if guess is None or guess in topics:
        return reading.model_copy(update={"problem_latex": problem}), True
    note = f"topic guess {guess!r} is not a bank topic, so it was cleared"
    updated = {
        "problem_latex": problem,
        "topic_guess": None,
        "notes": _join_notes(reading.notes, note),
    }
    return reading.model_copy(update=updated), False


def _unreadable_message(problem: str) -> Optional[str]:
    if not problem:
        return EMPTY_PROBLEM_MESSAGE
    if len(problem) > MAX_LATEX_LENGTH:
        return LONG_PROBLEM_MESSAGE
    return None


def _checker_verdict(problem: str) -> tuple[bool, Optional[str]]:
    """Whether the checker can read the LaTeX, and the plain reason when it cannot."""
    try:
        read_latex(problem)
    except BoundaryError as error:
        return False, str(error)
    return True, None


def _digest(image: object) -> Optional[str]:
    if not isinstance(image, (bytes, bytearray)):
        return None
    return sha256_hex(bytes(image))


def _tokens(source: PhotoSource) -> Optional[dict]:
    usage = getattr(source, "last_usage", None)
    return dict(usage) if usage else None


def _result(
    status: str,
    source_name: str,
    digest: Optional[str],
    error: Optional[str] = None,
    reading: Optional[PhotoReading] = None,
    topic_valid: bool = False,
    checker: tuple[Optional[bool], Optional[str]] = (None, None),
    tokens: Optional[dict] = None,
) -> dict:
    checker_readable, checker_reason = checker
    return {
        "status": status,
        "source": source_name,
        "reading": reading.model_dump() if reading is not None else None,
        "topic_guess_valid": topic_valid,
        "checker_readable": checker_readable,
        "checker_reason": checker_reason,
        "image_sha256": digest,
        "error": error,
        "tokens": tokens,
    }


def read_photo(
    image: bytes, source: PhotoSource, topics: Optional[Sequence[str]] = None
) -> dict:
    """Read a photo of a calculus problem with source. Never raises for bad input or source failures."""
    digest = _digest(image)
    media_type, image_error = check_image(image)
    if image_error is not None:
        return _result(STATUS_ERROR, source.name, digest, error=image_error)
    try:
        allowed = _topic_ids(topics)
        raw = PhotoReading.model_validate(
            source.get_reading(bytes(image), media_type, allowed)
        )
    except PhotoSourceError as error:
        return _result(STATUS_ERROR, source.name, digest, error=str(error) or GENERIC_SOURCE_MESSAGE)
    except Exception as error:  # a photo-source failure must not crash the caller
        logger.error("photo source failed: %s: %s", type(error).__name__, error)
        return _result(STATUS_ERROR, source.name, digest, error=GENERIC_SOURCE_MESSAGE)
    reading, topic_valid = _normalized(raw, allowed)
    problem = reading.problem_latex
    checker = _checker_verdict(problem)
    unreadable = _unreadable_message(problem)
    status = STATUS_OK if unreadable is None else STATUS_UNREADABLE
    return _result(
        status,
        source.name,
        digest,
        error=unreadable,
        reading=reading,
        topic_valid=topic_valid,
        checker=checker,
        tokens=_tokens(source),
    )


def _is_sha256_hex(value: object) -> bool:
    return isinstance(value, str) and SHA256_HEX_PATTERN.fullmatch(value) is not None


def save_reading(
    path: Path | str, image_sha256: str, reading: PhotoReading, source: str
) -> None:
    """Write a reading to a JSON file. The image itself is never written. source is "live" or "fake"."""
    if source not in READING_SOURCES:
        raise ValueError(f"source must be one of {READING_SOURCES}, got {source!r}")
    if not _is_sha256_hex(image_sha256):
        raise ValueError("image_sha256 must be a 64-character lowercase hex digest")
    payload = {
        "topic": reading.topic_guess,
        "reading": reading.model_dump(),
        "source": source,
        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "image_sha256": image_sha256,
    }
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def load_reading(path: Path | str) -> dict:
    """Read a saved reading. Raises ValueError when the file is not a valid saved reading."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("source") not in READING_SOURCES:
        raise ValueError(f"{path} is not a saved Echo photo reading")
    if not _is_sha256_hex(data.get("image_sha256")):
        raise ValueError(f"{path} is missing its image_sha256")
    if not isinstance(data.get("reading"), dict):
        raise ValueError(f"{path} is missing its reading")
    reading = PhotoReading.model_validate(data["reading"])
    return {**data, "reading": reading}
