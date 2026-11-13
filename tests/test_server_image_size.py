"""Server tests for the photo size check on /api/read-photo and /api/worksheet/read.

Offline only: no network and no model call. The reader is replaced with a spy so a test can
prove it was never reached. ANTHROPIC_API_KEY is removed, and the replay directories are
temporary.
"""

import struct
import sys
import zlib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from core import photo_reader  # noqa: E402
from core.photo_reader import PNG_MAGIC  # noqa: E402
from server import app as app_module  # noqa: E402
from server import photo_api  # noqa: E402
from server import worksheet_api  # noqa: E402

LOCAL_BASE_URL = "http://127.0.0.1:8000"  # the guard only accepts localhost Host headers
TOO_SMALL_TEXT = (
    "This photo is 320 by 240 pixels. Echo needs at least 800 pixels on the shorter side to "
    "read handwriting reliably. Take the photo closer, or use a higher-resolution one."
)
TINY_PNG = PNG_MAGIC + b"\x00" * 4  # magic only, no IHDR: the size is unreadable
MODE_LIVE = "live"
MODE_REPLAY = "replay"
MODE_FAKE = "fake"


def png_bytes(width: int, height: int) -> bytes:
    """A PNG whose IHDR carries width and height. Header only: enough for the size check."""
    ihdr_body = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr = struct.pack(">I", len(ihdr_body)) + b"IHDR" + ihdr_body
    ihdr += struct.pack(">I", zlib.crc32(b"IHDR" + ihdr_body) & 0xFFFFFFFF)
    return PNG_MAGIC + ihdr


def tiny_png_1x1() -> bytes:
    return png_bytes(1, 1)


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ECHO_SAVE_REPLAYS", raising=False)
    monkeypatch.setattr(app_module, "BUILD_DIR", tmp_path / "build")
    monkeypatch.setattr(photo_api, "PHOTO_REPLAY_DIR", tmp_path / "replay")
    monkeypatch.setattr(worksheet_api, "WORKSHEET_REPLAY_DIR", tmp_path / "replay")
    return TestClient(app_module.app, base_url=LOCAL_BASE_URL)


@pytest.fixture
def reader_calls(monkeypatch):
    """Spies on every reader entry point. Each call appends here, and the real reader still runs."""
    calls: list[str] = []
    real_live_get = photo_reader.LivePhotoSource.get_reading
    real_worksheet = worksheet_api.read_worksheet
    real_photo = photo_api.read_photo

    def live_get(self, image, media_type, topics):
        calls.append("live")
        return real_live_get(self, image, media_type, topics)

    def worksheet_spy(image, source, topics=None):
        calls.append("worksheet")
        return real_worksheet(image, source, topics)

    def photo_spy(image, source, topics=None):
        calls.append("photo")
        return real_photo(image, source, topics)

    monkeypatch.setattr(photo_reader.LivePhotoSource, "get_reading", live_get)
    monkeypatch.setattr(worksheet_api, "read_worksheet", worksheet_spy)
    monkeypatch.setattr(photo_api, "read_photo", photo_spy)
    return calls


def post_photo(client: TestClient, data: bytes, mode: str):
    return client.post(
        "/api/read-photo",
        files={"file": ("photo.png", data, "image/png")},
        data={"mode": mode},
    )


def post_worksheet(client: TestClient, data: bytes, mode: str):
    return client.post(
        "/api/worksheet/read",
        files={"file": ("photo.png", data, "image/png")},
        data={"mode": mode},
    )


@pytest.mark.parametrize("mode", [MODE_LIVE, MODE_REPLAY])
def test_small_photo_is_rejected_on_single_photo_route_before_any_reader(client, reader_calls, mode):
    response = post_photo(client, png_bytes(320, 240), mode)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    assert body["error"] == TOO_SMALL_TEXT
    assert body["reading"] is None
    assert reader_calls == []


@pytest.mark.parametrize("mode", [MODE_LIVE, MODE_REPLAY])
def test_small_photo_is_rejected_on_worksheet_route_before_any_reader(client, reader_calls, mode):
    response = post_worksheet(client, png_bytes(320, 240), mode)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    assert body["error"] == TOO_SMALL_TEXT
    assert body["reading"] is None
    assert reader_calls == []


def test_fake_mode_accepts_a_one_by_one_png_on_photo_route(client):
    response = post_photo(client, tiny_png_1x1(), MODE_FAKE)

    body = response.json()
    assert body["status"] == "ok"
    assert body["error"] is None
    assert body["reading"] is not None


def test_fake_mode_accepts_a_one_by_one_png_on_worksheet_route(client):
    response = post_worksheet(client, tiny_png_1x1(), MODE_FAKE)

    body = response.json()
    assert body["status"] == "ok"
    assert body["reading"] is not None


def test_fake_mode_reaches_the_reader_even_for_a_small_photo(client, reader_calls):
    response = post_photo(client, png_bytes(320, 240), MODE_FAKE)

    assert response.json()["status"] == "ok"
    assert reader_calls == ["photo"]


def test_unreadable_header_is_not_blocked_and_reaches_the_reader(client, reader_calls):
    # A PNG magic with no IHDR has no readable size, so the size check must not block it.
    response = post_photo(client, TINY_PNG, MODE_LIVE)

    body = response.json()
    assert body["error"] != TOO_SMALL_TEXT
    assert "photo" in reader_calls


def test_large_enough_photo_passes_the_size_check_and_reaches_the_reader(client, reader_calls):
    response = post_worksheet(client, png_bytes(1600, 1200), MODE_LIVE)

    assert response.json()["error"] != TOO_SMALL_TEXT
    assert reader_calls == ["worksheet"]
