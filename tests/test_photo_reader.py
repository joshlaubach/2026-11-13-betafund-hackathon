"""Tests for core/photo_reader.py. Offline only: no network, no API key.

Images are built in the test (a 1x1 PNG and a header-only JPEG), so no files are needed.
"""

import base64
import hashlib
import struct
import sys
import zlib
from pathlib import Path

import anthropic
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core import photo_reader  # noqa: E402
from core.photo_reader import (  # noqa: E402
    MAX_IMAGE_BYTES,
    STATUS_ERROR,
    STATUS_OK,
    STATUS_UNREADABLE,
    FakePhotoSource,
    LivePhotoSource,
    PhotoReading,
    PhotoSource,
    ReplayPhotoSource,
    bank_topic_ids,
    load_reading,
    read_photo,
    save_reading,
)

GOOD_READING = PhotoReading(
    problem_latex="3x^{4}+2x", topic_guess="power_rule", confidence="high", notes=""
)


def _chunk(kind: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(kind + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)


def make_png(red: int = 255) -> bytes:
    """A valid 1x1 RGB PNG; red sets the pixel colour so two photos differ."""
    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    pixel = zlib.compress(bytes([0, red, 0, 0]))
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", pixel)
        + _chunk(b"IEND", b"")
    )


JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"


class CountingSource(FakePhotoSource):
    """A fake source that records each call, so tests can prove it was never reached."""

    def __init__(self, reading: PhotoReading = GOOD_READING) -> None:
        super().__init__(reading)
        self.calls = 0

    def get_reading(self, image, media_type, topics):
        self.calls += 1
        return super().get_reading(image, media_type, topics)


class FakeUsage:
    input_tokens = 11
    output_tokens = 7


class FakeParsedResponse:
    def __init__(self, parsed: PhotoReading) -> None:
        self.stop_reason = "end_turn"
        self.parsed_output = parsed
        self.usage = FakeUsage()


class RecordingMessages:
    def __init__(self, parsed: PhotoReading) -> None:
        self.requests: list[dict] = []
        self._parsed = parsed

    def parse(self, **kwargs):
        self.requests.append(kwargs)
        return FakeParsedResponse(self._parsed)


class RecordingClient:
    def __init__(self, parsed: PhotoReading) -> None:
        self.messages = RecordingMessages(parsed)


# ---------------------------------------------------------------------------
# Fake source and the result shape
# ---------------------------------------------------------------------------


def test_fake_source_gives_ok_reading_with_checker_readable():
    png = make_png()
    result = read_photo(png, FakePhotoSource(GOOD_READING), topics=["power_rule"])
    assert result["status"] == STATUS_OK
    assert result["source"] == "fake"
    assert result["reading"]["problem_latex"] == "3x^{4}+2x"
    assert result["topic_guess_valid"] is True
    assert result["checker_readable"] is True
    assert result["checker_reason"] is None
    assert result["image_sha256"] == hashlib.sha256(png).hexdigest()
    assert result["error"] is None
    assert result["tokens"] is None


def test_bank_has_ninety_topic_ids():
    assert len(bank_topic_ids()) == 90


def test_topic_guess_outside_bank_becomes_none_with_note():
    reading = PhotoReading(
        problem_latex="x^{2}", topic_guess="not_a_bank_topic", confidence="medium", notes=""
    )
    result = read_photo(make_png(), FakePhotoSource(reading))
    assert result["status"] == STATUS_OK
    assert result["reading"]["topic_guess"] is None
    assert result["topic_guess_valid"] is False
    assert "not_a_bank_topic" in result["reading"]["notes"]


def test_null_topic_guess_is_kept_as_null_and_valid():
    reading = PhotoReading(problem_latex="x^{2}", topic_guess=None, confidence="low", notes="")
    result = read_photo(make_png(), FakePhotoSource(reading))
    assert result["reading"]["topic_guess"] is None
    assert result["topic_guess_valid"] is True


def test_empty_latex_is_unreadable_and_keeps_the_reading():
    reading = PhotoReading(problem_latex="   ", topic_guess=None, confidence="low", notes="smudged")
    result = read_photo(make_png(), FakePhotoSource(reading))
    assert result["status"] == STATUS_UNREADABLE
    assert result["error"] == photo_reader.EMPTY_PROBLEM_MESSAGE
    assert result["reading"]["notes"] == "smudged"
    assert result["checker_readable"] is False


def test_overlong_latex_is_unreadable():
    reading = PhotoReading(problem_latex="x+" * 600, topic_guess=None, confidence="low", notes="")
    result = read_photo(make_png(), FakePhotoSource(reading))
    assert result["status"] == STATUS_UNREADABLE
    assert result["error"] == photo_reader.LONG_PROBLEM_MESSAGE


def test_checker_readable_false_with_reason_for_unsupported_latex():
    reading = PhotoReading(problem_latex="\\int x\\,dx", topic_guess=None, confidence="high", notes="")
    result = read_photo(make_png(), FakePhotoSource(reading))
    assert result["status"] == STATUS_OK
    assert result["checker_readable"] is False
    assert "not supported" in result["checker_reason"]


# ---------------------------------------------------------------------------
# Image validation happens before any source call
# ---------------------------------------------------------------------------


def test_non_image_bytes_are_rejected_before_source_call():
    source = CountingSource()
    result = read_photo(b"hello, this is a text file", source)
    assert result["status"] == STATUS_ERROR
    assert "PNG, JPEG, WEBP, or GIF" in result["error"]
    assert source.calls == 0


def test_image_extension_does_not_matter_only_magic_bytes():
    source = CountingSource()
    result = read_photo(b"GIF-looking text but no header", source)
    assert result["status"] == STATUS_ERROR
    assert source.calls == 0


def test_empty_image_is_rejected_before_source_call():
    source = CountingSource()
    result = read_photo(b"", source)
    assert result["status"] == STATUS_ERROR
    assert result["error"] == photo_reader.EMPTY_IMAGE_MESSAGE
    assert source.calls == 0


def test_oversize_image_is_rejected_before_source_call():
    source = CountingSource()
    oversize = b"\x89PNG\r\n\x1a\n" + b"\x00" * MAX_IMAGE_BYTES
    result = read_photo(oversize, source)
    assert result["status"] == STATUS_ERROR
    assert result["error"] == photo_reader.TOO_LARGE_MESSAGE
    assert source.calls == 0


def test_jpeg_and_webp_and_gif_headers_are_detected():
    webp = b"RIFF\x00\x00\x00\x00WEBPVP8 "
    gif = b"GIF89a" + b"\x00" * 10
    assert photo_reader.detect_media_type(JPEG) == "image/jpeg"
    assert photo_reader.detect_media_type(webp) == "image/webp"
    assert photo_reader.detect_media_type(gif) == "image/gif"
    assert photo_reader.detect_media_type(make_png()) == "image/png"
    assert photo_reader.detect_media_type(b"RIFF\x00\x00\x00\x00WAVE") is None


def test_jpeg_is_accepted_by_fake_source():
    result = read_photo(JPEG, FakePhotoSource(GOOD_READING))
    assert result["status"] == STATUS_OK


# ---------------------------------------------------------------------------
# Live source: no key, and request shape
# ---------------------------------------------------------------------------


def test_no_key_gives_error_status_and_no_network(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    def forbidden_client():
        raise AssertionError("no network client may be built without a key")

    monkeypatch.setattr(photo_reader.anthropic, "Anthropic", forbidden_client)
    result = read_photo(make_png(), LivePhotoSource())
    assert result["status"] == STATUS_ERROR
    assert result["error"] == "API key missing or invalid"
    assert result["reading"] is None


def test_live_request_puts_image_block_before_text_block(monkeypatch):
    png = make_png()
    client = RecordingClient(GOOD_READING)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    monkeypatch.setattr(photo_reader.anthropic, "Anthropic", lambda: client)
    result = read_photo(png, LivePhotoSource(), topics=["power_rule", "u_substitution"])
    assert result["status"] == STATUS_OK
    assert result["reading"]["problem_latex"] == "3x^{4}+2x"
    assert result["tokens"] == {"input_tokens": 11, "output_tokens": 7}

    request = client.messages.requests[0]
    content = request["messages"][0]["content"]
    assert [block["type"] for block in content] == ["image", "text"]
    assert content[0]["source"] == {
        "type": "base64",
        "media_type": "image/png",
        "data": base64.standard_b64encode(png).decode("ascii"),
    }
    assert "power_rule" in content[1]["text"]
    assert request["output_format"] is PhotoReading
    assert "temperature" not in request and "tool_choice" not in request


def test_live_request_has_no_sampling_parameters(monkeypatch):
    client = RecordingClient(GOOD_READING)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    monkeypatch.setattr(photo_reader.anthropic, "Anthropic", lambda: client)
    read_photo(make_png(), LivePhotoSource(), topics=["power_rule"])
    request = client.messages.requests[0]
    assert not {"temperature", "top_p", "top_k", "tool_choice"} & set(request)


def test_live_auth_failure_is_mapped_to_error(monkeypatch):
    import httpx

    class FailingMessages:
        def parse(self, **kwargs):
            response = httpx.Response(401, request=httpx.Request("POST", "https://example.invalid"))
            raise anthropic.AuthenticationError("rejected", response=response, body=None)

    class FailingClient:
        messages = FailingMessages()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    monkeypatch.setattr(photo_reader.anthropic, "Anthropic", lambda: FailingClient())
    result = read_photo(make_png(), LivePhotoSource(), topics=["power_rule"])
    assert result["status"] == STATUS_ERROR
    assert result["error"] == "API key missing or invalid"


# ---------------------------------------------------------------------------
# Saved readings and replay
# ---------------------------------------------------------------------------


def test_replay_with_matching_hash_works(tmp_path):
    png = make_png()
    path = tmp_path / "reading.json"
    save_reading(path, hashlib.sha256(png).hexdigest(), GOOD_READING, "fake")
    source = ReplayPhotoSource(path)
    result = read_photo(png, source)
    assert result["status"] == STATUS_OK
    assert result["source"] == "replay (saved fake reading)"
    assert result["reading"]["problem_latex"] == "3x^{4}+2x"


def test_replay_with_different_photo_is_an_error(tmp_path):
    path = tmp_path / "reading.json"
    save_reading(path, hashlib.sha256(make_png(255)).hexdigest(), GOOD_READING, "live")
    result = read_photo(make_png(10), ReplayPhotoSource(path))
    assert result["status"] == STATUS_ERROR
    assert result["error"] == "saved reading is for a different photo"
    assert result["reading"] is None


def test_saved_reading_file_has_no_image_bytes_or_base64(tmp_path):
    png = make_png()
    path = tmp_path / "reading.json"
    save_reading(path, hashlib.sha256(png).hexdigest(), GOOD_READING, "live")
    raw = path.read_bytes()
    assert png not in raw
    assert base64.standard_b64encode(png) not in raw
    saved = load_reading(path)
    assert set(saved) >= {"topic", "reading", "source", "saved_at", "image_sha256"}
    assert saved["topic"] == "power_rule"
    assert saved["source"] == "live"


def test_save_reading_rejects_unknown_source(tmp_path):
    with pytest.raises(ValueError):
        save_reading(tmp_path / "r.json", "a" * 64, GOOD_READING, "mystery")


def test_load_reading_rejects_a_file_that_is_not_a_reading(tmp_path):
    path = tmp_path / "other.json"
    path.write_text('{"hello": "world"}', encoding="utf-8")
    with pytest.raises(ValueError):
        load_reading(path)


# ---------------------------------------------------------------------------
# Inputs are not mutated
# ---------------------------------------------------------------------------


def test_input_arguments_are_not_mutated():
    image = bytearray(make_png())
    image_before = bytes(image)
    topics = ["power_rule", "u_substitution"]
    topics_before = list(topics)
    reading = PhotoReading(problem_latex=" x^{2} ", topic_guess="made_up", confidence="low", notes="")
    dumped_before = reading.model_dump()
    source = FakePhotoSource(reading)
    read_photo(image, source, topics)
    assert bytes(image) == image_before
    assert topics == topics_before
    assert reading.model_dump() == dumped_before
    assert source._reading is reading


class PlainSourceReturningDict(PhotoSource):
    name = "dict-source"

    def get_reading(self, image, media_type, topics):
        return {"problem_latex": "x", "topic_guess": None, "confidence": "low", "notes": ""}


def test_source_returning_wrong_shape_is_an_error_not_a_crash():
    result = read_photo(make_png(), PlainSourceReturningDict(), topics=["power_rule"])
    assert result["status"] == STATUS_OK
    assert result["reading"]["problem_latex"] == "x"
