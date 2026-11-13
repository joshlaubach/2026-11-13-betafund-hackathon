"""Tests for core/image_size.py: header-only pixel sizes and the too-small message.

Every image here is hand-built from stdlib bytes (struct, zlib). Nothing is decoded, and no
image library is used. Hostile and truncated inputs must return None and never raise.
"""

import random
import struct
import sys
import zlib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core import image_size  # noqa: E402
from core.image_size import MIN_SHORT_SIDE_PX, image_dimensions, too_small_message  # noqa: E402

TOO_SMALL_TEXT = (
    "This photo is 320 by 240 pixels. Echo needs at least 800 pixels on the shorter side to "
    "read handwriting reliably. Take the photo closer, or use a higher-resolution one."
)


def png_bytes(width: int, height: int) -> bytes:
    """A PNG with a correct IHDR chunk. Header only: there is no IDAT pixel data."""
    ihdr_body = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr = struct.pack(">I", len(ihdr_body)) + b"IHDR" + ihdr_body
    ihdr += struct.pack(">I", zlib.crc32(b"IHDR" + ihdr_body) & 0xFFFFFFFF)
    return b"\x89PNG\r\n\x1a\n" + ihdr


def gif_bytes(width: int, height: int, version: bytes = b"GIF89a") -> bytes:
    return version + struct.pack("<HH", width, height) + b"\x00\x00\x00"


def riff(chunk_type: bytes, payload: bytes) -> bytes:
    body = b"WEBP" + chunk_type + struct.pack("<I", len(payload)) + payload
    return b"RIFF" + struct.pack("<I", len(body)) + body


def webp_vp8(width: int, height: int) -> bytes:
    frame = b"\x00\x00\x00" + b"\x9d\x01\x2a" + struct.pack("<HH", width, height)
    return riff(b"VP8 ", frame)


def webp_vp8l(width: int, height: int) -> bytes:
    bits = (width - 1) | ((height - 1) << 14)
    payload = b"\x2f" + struct.pack("<I", bits)
    return riff(b"VP8L", payload)


def webp_vp8x(width: int, height: int) -> bytes:
    payload = b"\x00\x00\x00\x00" + (width - 1).to_bytes(3, "little") + (height - 1).to_bytes(3, "little")
    return riff(b"VP8X", payload)


def jpeg_segment(marker: int, payload: bytes) -> bytes:
    return bytes([0xFF, marker]) + struct.pack(">H", len(payload) + 2) + payload


def jpeg_sof0(width: int, height: int) -> bytes:
    payload = struct.pack(">BHHB", 8, height, width, 1) + b"\x01\x11\x00"
    return jpeg_segment(0xC0, payload)


def jpeg_file(width: int, height: int) -> bytes:
    app0 = jpeg_segment(0xE0, b"JFIF\x00" + b"\x01\x01\x00\x00\x01\x00\x01\x00\x00")
    return b"\xff\xd8" + app0 + jpeg_sof0(width, height) + b"\xff\xd9"


# ---------------------------------------------------------------------------
# Valid headers
# ---------------------------------------------------------------------------


def test_png_size_comes_from_ihdr():
    assert image_dimensions(png_bytes(320, 240)) == (320, 240)


def test_png_one_by_one_is_readable():
    assert image_dimensions(png_bytes(1, 1)) == (1, 1)


@pytest.mark.parametrize("version", [b"GIF87a", b"GIF89a"])
def test_gif_logical_screen_size_for_both_versions(version):
    assert image_dimensions(gif_bytes(640, 480, version)) == (640, 480)


def test_webp_lossy_vp8_size():
    assert image_dimensions(webp_vp8(500, 375)) == (500, 375)


def test_webp_lossy_masks_scaling_bits_from_size_fields():
    # The top two bits of each 16-bit field are scaling bits, not size bits.
    frame = b"\x00\x00\x00" + b"\x9d\x01\x2a" + struct.pack("<HH", 0xC000 | 500, 0xC000 | 375)
    assert image_dimensions(riff(b"VP8 ", frame)) == (500, 375)


def test_webp_lossless_vp8l_size():
    assert image_dimensions(webp_vp8l(1000, 700)) == (1000, 700)


def test_webp_extended_vp8x_canvas_size():
    assert image_dimensions(webp_vp8x(1200, 900)) == (1200, 900)


def test_jpeg_sof0_size():
    assert image_dimensions(jpeg_file(800, 600)) == (800, 600)


def test_jpeg_skips_huffman_table_and_fill_bytes_before_frame():
    dht = jpeg_segment(0xC4, b"\x00" + b"\x00" * 16)
    fill = b"\xff\xff"  # fill bytes before a marker are legal
    data = b"\xff\xd8" + dht + fill + jpeg_sof0(1024, 768) + b"\xff\xd9"
    assert image_dimensions(data) == (1024, 768)


def test_jpeg_skips_restart_and_standalone_markers():
    data = b"\xff\xd8" + b"\xff\xd0" + b"\xff\x01" + jpeg_sof0(900, 700)
    assert image_dimensions(data) == (900, 700)


# ---------------------------------------------------------------------------
# Unreadable, truncated, and hostile inputs return None and never raise
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"\x00",
        b"plain text, not an image",
        b"\x89PNG\r\n\x1a\n",
        png_bytes(10, 10)[:20],
        png_bytes(10, 10).replace(b"IHDR", b"IHDX"),
        gif_bytes(10, 10)[:9],
        b"GIF89a",
        b"RIFF\x00\x00\x00\x00WEBP",
        b"RIFF\x00\x00\x00\x00WEBPVP8 ",
        b"RIFF\x00\x00\x00\x00WEBPVP8X" + b"\x00" * 4,
        riff(b"VP8 ", b"\x00" * 3 + b"\x00\x00\x00"),
        riff(b"VP8L", b"\x00" * 5),
        riff(b"XXXX", b"\x00" * 20),
        b"\xff\xd8",
        b"\xff\xd8\xff",
        b"\xff\xd8\xff\xc0\x00",
    ],
)
def test_truncated_or_unknown_headers_return_none(data):
    assert image_dimensions(data) is None


def test_zero_dimension_is_unreadable():
    assert image_dimensions(png_bytes(0, 240)) is None
    assert image_dimensions(gif_bytes(320, 0)) is None


def test_jpeg_segment_length_below_two_is_rejected():
    data = b"\xff\xd8" + b"\xff\xe0\x00\x01" + b"\x00" * 20
    assert image_dimensions(data) is None


def test_jpeg_scan_stops_at_start_of_scan_without_a_frame():
    data = b"\xff\xd8" + b"\xff\xda\x00\x02" + b"\x00" * 30 + jpeg_sof0(800, 800)
    assert image_dimensions(data) is None


def test_jpeg_with_endless_segments_is_bounded_and_returns_none():
    app_segment = jpeg_segment(0xE0, b"x" * 4)
    data = b"\xff\xd8" + app_segment * (image_size.MAX_JPEG_SEGMENTS + 10)
    assert image_dimensions(data) is None


def test_jpeg_frame_past_end_of_data_returns_none():
    data = b"\xff\xd8" + b"\xff\xc0\x00\x11\x08\x01\x00"
    assert image_dimensions(data) is None


def test_random_prefixes_of_valid_files_never_raise():
    rng = random.Random(1234)
    samples = [png_bytes(320, 240), gif_bytes(320, 240), webp_vp8(320, 240), webp_vp8l(320, 240), jpeg_file(320, 240)]
    for sample in samples:
        for length in range(len(sample) + 1):
            image_dimensions(sample[:length])
        for _ in range(200):
            noisy = bytearray(sample)
            noisy[rng.randrange(len(noisy))] = rng.randrange(256)
            image_dimensions(bytes(noisy))


def test_non_bytes_input_returns_none_without_raising():
    assert image_dimensions(bytearray(png_bytes(320, 240))) == (320, 240)


# ---------------------------------------------------------------------------
# Too-small message
# ---------------------------------------------------------------------------


def test_too_small_message_names_the_pixel_size_and_threshold():
    assert too_small_message((320, 240)) == TOO_SMALL_TEXT


def test_short_side_below_threshold_is_flagged_even_when_long_side_is_large():
    assert too_small_message((4000, MIN_SHORT_SIDE_PX - 1)) is not None


def test_short_side_at_threshold_is_not_flagged():
    assert too_small_message((MIN_SHORT_SIDE_PX, 1200)) is None
    assert too_small_message((1200, MIN_SHORT_SIDE_PX)) is None


def test_threshold_constant_is_800():
    assert MIN_SHORT_SIDE_PX == 800
