"""Server tests: the bytes the readers and replay lookup receive have no metadata.

Offline only: no network and no model call. Readers are wrapped with spies that record the
image bytes they were handed. The real reader still runs in fake mode. ANTHROPIC_API_KEY is
removed and the replay directories are temporary.
"""

import hashlib
import struct
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from core import photo_reader  # noqa: E402
from server import app as app_module  # noqa: E402
from server import photo_api  # noqa: E402
from server import worksheet_api  # noqa: E402

LOCAL_BASE_URL = "http://127.0.0.1:8000"  # the guard only accepts localhost Host headers
MODE_LIVE = "live"
MODE_REPLAY = "replay"
MODE_FAKE = "fake"
TOO_SMALL_PREFIX = "This photo is 320 by 240 pixels."
PRIVATE_MARKERS = (b"GPS", b"AcmePhone")


def gps_jpeg(width: int, height: int) -> bytes:
    """A small JPEG whose EXIF carries a Make string and a GPS IFD pointer, plus an APP13 and COM."""
    make = b"AcmePhone\x00"
    tiff_ifd0_size = 2 + 12 * 2 + 4
    make_offset = 8 + tiff_ifd0_size
    gps_offset = make_offset + len(make)
    gps_text = b"GPS-DAT\x00"
    gps_text_offset = gps_offset + 2 + 12 + 4
    ifd0 = struct.pack("<H", 2)
    ifd0 += struct.pack("<HHI", 0x010F, 2, len(make)) + struct.pack("<I", make_offset)
    ifd0 += struct.pack("<HHI", 0x8825, 4, 1) + struct.pack("<I", gps_offset)
    ifd0 += struct.pack("<I", 0)
    gps_ifd = struct.pack("<H", 1) + struct.pack("<HHI", 0x001D, 2, len(gps_text))
    gps_ifd += struct.pack("<I", gps_text_offset) + struct.pack("<I", 0)
    tiff = b"II" + struct.pack("<HI", 42, 8) + ifd0 + make + gps_ifd + gps_text

    def segment(marker: int, body: bytes) -> bytes:
        return bytes((0xFF, marker)) + struct.pack(">H", len(body) + 2) + body

    sof = struct.pack(">BHHB", 8, height, width, 1) + bytes((1, 0x11, 0))
    return b"".join(
        [
            b"\xff\xd8",
            segment(0xE1, b"Exif\x00\x00" + tiff),
            segment(0xED, b"Photoshop 3.0\x00GPSPHOTOSHOP"),
            segment(0xFE, b"GPS-COMMENT"),
            segment(0xC0, sof),
            segment(0xDA, bytes((1, 1, 0x00, 0, 63, 0))),
            b"\x12\x34\xff\x00\x56",
            b"\xff\xd9",
        ]
    )


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ECHO_SAVE_REPLAYS", raising=False)
    monkeypatch.setattr(app_module, "BUILD_DIR", tmp_path / "build")
    monkeypatch.setattr(photo_api, "PHOTO_REPLAY_DIR", tmp_path / "replay")
    monkeypatch.setattr(worksheet_api, "WORKSHEET_REPLAY_DIR", tmp_path / "replay")
    return TestClient(app_module.app, base_url=LOCAL_BASE_URL)


@pytest.fixture
def seen_photo_bytes(monkeypatch):
    """Records every image the photo reader is handed. The real reader still runs."""
    seen: list[bytes] = []
    real_read_photo = photo_api.read_photo

    def spy(image, source, topics=None):
        seen.append(bytes(image))
        return real_read_photo(image, source, topics)

    monkeypatch.setattr(photo_api, "read_photo", spy)
    return seen


@pytest.fixture
def seen_worksheet_bytes(monkeypatch):
    seen: list[bytes] = []
    real_read_worksheet = worksheet_api.read_worksheet

    def spy(image, source, topics=None):
        seen.append(bytes(image))
        return real_read_worksheet(image, source, topics)

    monkeypatch.setattr(worksheet_api, "read_worksheet", spy)
    return seen


def post_photo(client: TestClient, data: bytes, mode: str):
    return client.post("/api/read-photo", files={"file": ("photo.jpg", data, "image/jpeg")}, data={"mode": mode})


def post_worksheet(client: TestClient, data: bytes, mode: str):
    return client.post("/api/worksheet/read", files={"file": ("photo.jpg", data, "image/jpeg")}, data={"mode": mode})


def test_photo_route_hands_the_reader_bytes_with_no_gps_or_make(client, seen_photo_bytes):
    response = post_photo(client, gps_jpeg(1200, 900), MODE_FAKE)

    assert response.json()["status"] == "ok"
    assert len(seen_photo_bytes) == 1
    received = seen_photo_bytes[0]
    assert received.startswith(b"\xff\xd8")
    for marker in PRIVATE_MARKERS:
        assert marker not in received


def test_worksheet_route_hands_the_reader_bytes_with_no_gps_or_make(client, seen_worksheet_bytes):
    response = post_worksheet(client, gps_jpeg(1200, 900), MODE_FAKE)

    assert response.json()["status"] == "ok"
    assert len(seen_worksheet_bytes) == 1
    for marker in PRIVATE_MARKERS:
        assert marker not in seen_worksheet_bytes[0]


def test_replay_hash_is_computed_over_the_stripped_bytes(client, seen_photo_bytes):
    original = gps_jpeg(1200, 900)

    response = post_photo(client, original, MODE_REPLAY)

    received = seen_photo_bytes[0]
    assert received != original
    assert response.json()["image_sha256"] == hashlib.sha256(received).hexdigest()
    assert response.json()["image_sha256"] != hashlib.sha256(original).hexdigest()


def test_replay_lookup_on_worksheet_route_uses_the_stripped_hash(client, monkeypatch, seen_worksheet_bytes):
    looked_up: list[str] = []
    real_replay_path = worksheet_api._replay_path

    def spy(prefix, digest):
        looked_up.append(digest)
        return real_replay_path(prefix, digest)

    monkeypatch.setattr(worksheet_api, "_replay_path", spy)
    post_worksheet(client, gps_jpeg(1200, 900), MODE_REPLAY)

    received = seen_worksheet_bytes[0]
    assert looked_up == [hashlib.sha256(received).hexdigest()]


def test_size_check_still_runs_on_the_stripped_bytes(client, seen_photo_bytes):
    response = post_photo(client, gps_jpeg(320, 240), MODE_LIVE)

    body = response.json()
    assert body["error"].startswith(TOO_SMALL_PREFIX)
    assert seen_photo_bytes == []
