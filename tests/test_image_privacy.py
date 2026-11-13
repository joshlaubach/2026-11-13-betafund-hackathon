"""Tests for core/image_privacy.py: metadata is stripped and pixel data is kept.

Images are built byte by byte here, so no test needs a photo or an image library. The one
real-photo check skips when its file or PIL is missing.
"""

import io
import random
import struct
import sys
import zlib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core.image_privacy import strip_metadata  # noqa: E402

REAL_PHOTO = REPO_ROOT / "images" / "01-drone-mistake.jpeg"
GPS_MARKERS = (b"GPS-DAT", b"AcmePhone", b"GPSPHOTOSHOP", b"GPS-COMMENT")
SOI = b"\xff\xd8"
EOI = b"\xff\xd9"
ENTROPY = b"\x12\x34\xff\x00\x56\xff\xd0\x78\x9a\xff\x00\xbc"
ENTROPY_SECOND = b"\xde\xf0\xff\x00\x11"


def segment(marker: int, body: bytes) -> bytes:
    return bytes((0xFF, marker)) + struct.pack(">H", len(body) + 2) + body


def exif_tiff(order: str, orientation: int | None) -> bytes:
    """A TIFF block with Make, an optional Orientation, and a GPS IFD pointer. order is < or >."""
    byte_order = b"II" if order == "<" else b"MM"
    entry_count = 2 + (1 if orientation is not None else 0)
    ifd0_size = 2 + 12 * entry_count + 4
    make = b"AcmePhone\x00"
    make_offset = 8 + ifd0_size
    gps_ifd_offset = make_offset + len(make)
    gps_text = b"GPS-DAT\x00"
    gps_text_offset = gps_ifd_offset + 2 + 12 + 4

    entries = [struct.pack(order + "HHI", 0x010F, 2, len(make)) + struct.pack(order + "I", make_offset)]
    if orientation is not None:
        entries.append(struct.pack(order + "HHI", 0x0112, 3, 1) + struct.pack(order + "HH", orientation, 0))
    entries.append(struct.pack(order + "HHI", 0x8825, 4, 1) + struct.pack(order + "I", gps_ifd_offset))

    ifd0 = struct.pack(order + "H", entry_count) + b"".join(entries) + struct.pack(order + "I", 0)
    gps_ifd = (
        struct.pack(order + "H", 1)
        + struct.pack(order + "HHI", 0x001D, 2, len(gps_text))
        + struct.pack(order + "I", gps_text_offset)
        + struct.pack(order + "I", 0)
    )
    header = byte_order + struct.pack(order + "H", 42) + struct.pack(order + "I", 8)
    return header + ifd0 + make + gps_ifd + gps_text


def exif_segment(orientation: int | None, order: str = "<") -> bytes:
    return segment(0xE1, b"Exif\x00\x00" + exif_tiff(order, orientation))


def sof_segment(width: int = 1200, height: int = 900) -> bytes:
    return segment(0xC0, struct.pack(">BHHB", 8, height, width, 1) + bytes((1, 0x11, 0)))


def build_jpeg(orientation: int | None = 6, scans: tuple[bytes, ...] = (ENTROPY,), **sizes: int) -> bytes:
    """A JPEG with GPS-bearing EXIF, APP13, COM, and tables, then one SOS per scan, then EOI."""
    parts = [
        SOI,
        exif_segment(orientation),
        segment(0xED, b"Photoshop 3.0\x00GPSPHOTOSHOP"),
        segment(0xFE, b"GPS-COMMENT"),
        segment(0xDB, bytes([0]) + bytes([1]) * 64),
        sof_segment(**sizes),
        segment(0xC4, bytes([0x00]) + bytes(16)),
        segment(0xDD, struct.pack(">H", 1)),
    ]
    for entropy in scans:
        parts.append(segment(0xDA, bytes((1, 1, 0x00, 0, 63, 0))))
        parts.append(entropy)
    parts.append(EOI)
    return b"".join(parts)


def read_orientation(jpeg: bytes) -> int | None:
    """Independent reader: the Orientation value in the first Exif APP1, or None."""
    pos = 2
    while pos + 4 <= len(jpeg) and jpeg[pos] == 0xFF and jpeg[pos + 1] != 0xDA:
        marker = jpeg[pos + 1]
        (length,) = struct.unpack_from(">H", jpeg, pos + 2)
        body = jpeg[pos + 4 : pos + 2 + length]
        if marker == 0xE1 and body.startswith(b"Exif\x00\x00"):
            return _orientation_in_tiff(body[6:])
        pos += 2 + length
    return None


def _orientation_in_tiff(tiff: bytes) -> int | None:
    order = "<" if tiff[:2] == b"II" else ">"
    (ifd,) = struct.unpack_from(order + "I", tiff, 4)
    (count,) = struct.unpack_from(order + "H", tiff, ifd)
    for index in range(count):
        entry = ifd + 2 + 12 * index
        tag, _value_type = struct.unpack_from(order + "HH", tiff, entry)
        if tag == 0x0112:
            return struct.unpack_from(order + "H", tiff, entry + 8)[0]
    return None


def png_chunk(chunk_type: bytes, body: bytes) -> bytes:
    crc = zlib.crc32(chunk_type + body) & 0xFFFFFFFF
    return struct.pack(">I", len(body)) + chunk_type + body + struct.pack(">I", crc)


def png_chunks(data: bytes) -> list[tuple[bytes, bytes]]:
    """(type, raw chunk bytes) for each chunk, after checking every CRC."""
    chunks = []
    pos = 8
    while pos < len(data):
        (length,) = struct.unpack_from(">I", data, pos)
        chunk_type = data[pos + 4 : pos + 8]
        body = data[pos + 8 : pos + 8 + length]
        (crc,) = struct.unpack_from(">I", data, pos + 8 + length)
        assert crc == zlib.crc32(chunk_type + body) & 0xFFFFFFFF
        chunks.append((chunk_type, data[pos : pos + 12 + length]))
        pos += 12 + length
    return chunks


# ---------------------------------------------------------------------------
# JPEG
# ---------------------------------------------------------------------------


def test_jpeg_drops_gps_make_app13_and_comment_but_keeps_markers_and_bounds():
    original = build_jpeg(orientation=6)

    stripped = strip_metadata(original)

    assert stripped.startswith(SOI)
    assert stripped.endswith(EOI)
    for marker in GPS_MARKERS:
        assert marker not in stripped


def test_jpeg_keeps_frame_tables_scan_and_entropy_bytes_identical():
    original = build_jpeg(orientation=6)

    stripped = strip_metadata(original)

    for kept in (sof_segment(), segment(0xDB, bytes([0]) + bytes([1]) * 64), segment(0xDD, struct.pack(">H", 1))):
        assert kept in stripped
    assert segment(0xDA, bytes((1, 1, 0x00, 0, 63, 0))) in stripped
    assert ENTROPY in stripped


def test_jpeg_orientation_six_is_kept_as_one_exif_segment():
    stripped = strip_metadata(build_jpeg(orientation=6))

    assert read_orientation(stripped) == 6
    assert stripped.count(b"\xff\xe1") == 1


def test_big_endian_exif_orientation_eight_is_kept():
    original = build_jpeg(orientation=None)
    original = original.replace(exif_segment(None), segment(0xE1, b"Exif\x00\x00" + exif_tiff(">", 8)))

    stripped = strip_metadata(original)

    assert read_orientation(stripped) == 8


def test_no_orientation_writes_no_exif_segment():
    stripped = strip_metadata(build_jpeg(orientation=None))

    assert b"\xff\xe1" not in stripped
    assert read_orientation(stripped) is None


def test_orientation_one_is_default_and_writes_no_exif_segment():
    stripped = strip_metadata(build_jpeg(orientation=1))

    assert b"\xff\xe1" not in stripped


def test_progressive_style_multi_scan_keeps_every_scan_in_order():
    original = build_jpeg(orientation=6, scans=(ENTROPY, ENTROPY_SECOND))

    stripped = strip_metadata(original)

    first = stripped.index(ENTROPY)
    second = stripped.index(ENTROPY_SECOND)
    assert first < second
    assert stripped.count(segment(0xDA, bytes((1, 1, 0x00, 0, 63, 0)))) == 2
    assert stripped.endswith(EOI)


def test_bytes_after_the_final_eoi_are_dropped():
    original = build_jpeg(orientation=6) + b"\xff\xd8GPS-TRAILER-DATA"

    stripped = strip_metadata(original)

    assert stripped.endswith(EOI)
    assert b"GPS-TRAILER-DATA" not in stripped


def test_fill_bytes_before_a_marker_are_skipped():
    original = build_jpeg(orientation=6).replace(b"\xff\xdb", b"\xff\xff\xdb", 1)

    stripped = strip_metadata(original)

    assert stripped.endswith(EOI)
    assert segment(0xDB, bytes([0]) + bytes([1]) * 64) in stripped


def test_truncated_jpeg_is_returned_unchanged():
    original = build_jpeg(orientation=6)

    for cut in (len(original) // 2, len(original) - 10, 5):
        assert strip_metadata(original[:cut]) == original[:cut]


def test_jpeg_truncated_inside_entropy_data_is_returned_unchanged():
    original = build_jpeg(orientation=6)
    without_eoi = original[:-2]

    assert strip_metadata(without_eoi) == without_eoi


def test_non_image_bytes_are_returned_unchanged():
    assert strip_metadata(b"not an image at all") == b"not an image at all"
    assert strip_metadata(b"") == b""


def test_random_bytes_never_raise_and_non_images_come_back_unchanged():
    rng = random.Random(20261112)
    for _ in range(200):
        length = rng.randint(0, 300)
        blob = bytes(rng.randrange(256) for _ in range(length))
        result = strip_metadata(blob)
        assert isinstance(result, bytes)
        if not blob.startswith((SOI, b"\x89PNG", b"RIFF", b"GIF8")):
            assert result == blob


def test_random_bytes_after_jpeg_magic_never_raise():
    rng = random.Random(7)
    for _ in range(200):
        blob = SOI + bytes(rng.randrange(256) for _ in range(rng.randint(0, 300)))
        assert isinstance(strip_metadata(blob), bytes)


# ---------------------------------------------------------------------------
# PNG
# ---------------------------------------------------------------------------


def test_png_drops_text_and_exif_chunks_and_keeps_critical_chunks_with_valid_crcs():
    ihdr = png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1200, 900, 8, 2, 0, 0, 0))
    idat = png_chunk(b"IDAT", zlib.compress(b"\x00" * 16))
    iend = png_chunk(b"IEND", b"")
    text = png_chunk(b"tEXt", b"Comment\x00GPS-PNG-TEXT")
    exif = png_chunk(b"eXIf", b"GPS-PNG-EXIF")
    unknown = png_chunk(b"prVt", b"GPS-PNG-PRIVATE")
    phys = png_chunk(b"pHYs", struct.pack(">IIB", 2835, 2835, 1))
    original = b"\x89PNG\r\n\x1a\n" + ihdr + text + exif + unknown + phys + idat + iend

    stripped = strip_metadata(original)

    assert b"GPS-PNG" not in stripped
    chunk_types = [chunk_type for chunk_type, _raw in png_chunks(stripped)]
    assert chunk_types == [b"IHDR", b"pHYs", b"IDAT", b"IEND"]
    raw_by_type = dict(png_chunks(stripped))
    assert raw_by_type[b"IHDR"] == ihdr
    assert raw_by_type[b"IDAT"] == idat
    assert raw_by_type[b"IEND"] == iend


def test_png_without_iend_is_returned_unchanged():
    original = b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", bytes(13))

    assert strip_metadata(original) == original


# ---------------------------------------------------------------------------
# WebP and GIF
# ---------------------------------------------------------------------------


def riff(form_body: bytes) -> bytes:
    return b"RIFF" + struct.pack("<I", len(form_body)) + form_body


def webp_chunk(fourcc: bytes, body: bytes) -> bytes:
    pad = b"\x00" * (len(body) & 1)
    return fourcc + struct.pack("<I", len(body)) + body + pad


def test_webp_drops_exif_and_xmp_chunks_clears_flags_and_fixes_riff_size():
    vp8x = webp_chunk(b"VP8X", bytes([0x08 | 0x04 | 0x10, 0, 0, 0]) + bytes(6))
    image = webp_chunk(b"VP8 ", b"\x00" * 10)
    exif = webp_chunk(b"EXIF", b"GPS-WEBP-EXIF")
    xmp = webp_chunk(b"XMP ", b"GPS-WEBP-XMP")
    original = riff(b"WEBP" + vp8x + image + exif + xmp)

    stripped = strip_metadata(original)

    assert b"GPS-WEBP" not in stripped
    assert stripped == riff(b"WEBP" + webp_chunk(b"VP8X", bytes([0x10, 0, 0, 0]) + bytes(6)) + image)


def test_gif_drops_comment_and_non_netscape_app_extensions_only():
    header = b"GIF89a" + struct.pack("<HHBBB", 1, 1, 0x00, 0, 0)
    comment = b"\x21\xfe" + bytes([9]) + b"GPS-GIF!!" + b"\x00"
    xmp_app = b"\x21\xff\x0b" + b"XMP DataXMP" + bytes([4]) + b"GPS!" + b"\x00"
    netscape = b"\x21\xff\x0b" + b"NETSCAPE2.0" + bytes([3, 1, 0, 0]) + b"\x00"
    image = b"\x2c" + struct.pack("<HHHHB", 0, 0, 1, 1, 0) + bytes([2]) + bytes([2, 0x4C, 0x01]) + b"\x00"
    original = header + comment + xmp_app + netscape + image + b"\x3b"

    stripped = strip_metadata(original)

    assert b"GPS-GIF" not in stripped
    assert b"XMP Data" not in stripped
    assert netscape in stripped
    assert image in stripped
    assert stripped.endswith(b"\x3b")


# ---------------------------------------------------------------------------
# Real photo
# ---------------------------------------------------------------------------


def test_real_photo_decodes_to_identical_pixels_after_stripping():
    if not REAL_PHOTO.exists():
        pytest.skip("images/01-drone-mistake.jpeg is not present")
    Image = pytest.importorskip("PIL.Image")
    ImageChops = pytest.importorskip("PIL.ImageChops")
    original = REAL_PHOTO.read_bytes()

    stripped = strip_metadata(original)

    before = Image.open(io.BytesIO(original))
    after = Image.open(io.BytesIO(stripped))
    before.load()
    after.load()
    assert before.size == after.size
    assert ImageChops.difference(before.convert("RGB"), after.convert("RGB")).getbbox() is None
    assert after.getexif().get(0x0112, 1) == before.getexif().get(0x0112, 1)
