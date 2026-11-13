"""Read a photo's pixel size from its header, and say when it is too small to read.

PNG, GIF, WEBP, and JPEG sizes come from header bytes only. No image library is used and
no pixel data is decoded. Every reader returns None for anything it cannot parse, and
none of them raise. The JPEG scan is bounded by MAX_JPEG_SEGMENTS.
"""

from __future__ import annotations

import struct

MIN_SHORT_SIDE_PX = 800
MAX_JPEG_SEGMENTS = 256
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
PNG_IHDR = b"IHDR"
PNG_IHDR_TYPE_SLICE = slice(12, 16)
PNG_SIZE_OFFSET = 16
PNG_MIN_LENGTH = 24
GIF_MAGICS = (b"GIF87a", b"GIF89a")
GIF_MIN_LENGTH = 10
JPEG_MAGIC = b"\xff\xd8"
JPEG_SOI = 0xD8
JPEG_EOI = 0xD9
JPEG_SOS = 0xDA
JPEG_FILL = 0xFF
JPEG_TEM = 0x01
JPEG_RST_LOW = 0xD0
JPEG_RST_HIGH = 0xD7
JPEG_SOF_LOW = 0xC0
JPEG_SOF_HIGH = 0xCF
JPEG_NOT_SOF = (0xC4, 0xC8, 0xCC)  # DHT, JPG, DAC share the C0-CF range but are not frames
JPEG_SOF_HEADER_LENGTH = 9
RIFF_MAGIC = b"RIFF"
WEBP_MARK = b"WEBP"
WEBP_CHUNK_SLICE = slice(12, 16)
WEBP_VP8_CHUNK = b"VP8 "
WEBP_VP8L_CHUNK = b"VP8L"
WEBP_VP8X_CHUNK = b"VP8X"
WEBP_VP8_START_CODE = b"\x9d\x01\x2a"
WEBP_VP8_START_SLICE = slice(23, 26)
WEBP_VP8_SIZE_SLICE = slice(26, 30)
WEBP_VP8_MIN_LENGTH = 30
WEBP_VP8L_SIGNATURE = 0x2F
WEBP_VP8L_MIN_LENGTH = 25
WEBP_VP8X_MIN_LENGTH = 30
WEBP_VP8X_WIDTH_SLICE = slice(24, 27)
WEBP_VP8X_HEIGHT_SLICE = slice(27, 30)
SIZE_MASK_14_BITS = 0x3FFF
VP8L_WIDTH_MASK = 0x3FFF
VP8L_HEIGHT_SHIFT = 14
ONE = 1
UINT16_BE = ">H"
UINT32_PAIR_BE = ">II"
UINT16_PAIR_LE = "<HH"
UINT16_PAIR_BE = ">HH"
TOO_SMALL_TEMPLATE = (
    "This photo is {width} by {height} pixels. Echo needs at least {minimum} pixels on the "
    "shorter side to read handwriting reliably. Take the photo closer, or use a "
    "higher-resolution one."
)


def _png_size(data: bytes) -> tuple[int, int] | None:
    if len(data) < PNG_MIN_LENGTH or data[PNG_IHDR_TYPE_SLICE] != PNG_IHDR:
        return None
    width, height = struct.unpack_from(UINT32_PAIR_BE, data, PNG_SIZE_OFFSET)
    return width, height


def _gif_size(data: bytes) -> tuple[int, int] | None:
    if len(data) < GIF_MIN_LENGTH:
        return None
    width, height = struct.unpack_from(UINT16_PAIR_LE, data, 6)
    return width, height


def _webp_vp8_size(data: bytes) -> tuple[int, int] | None:
    if len(data) < WEBP_VP8_MIN_LENGTH or data[WEBP_VP8_START_SLICE] != WEBP_VP8_START_CODE:
        return None
    width, height = struct.unpack_from(UINT16_PAIR_LE, data, WEBP_VP8_SIZE_SLICE.start)
    return width & SIZE_MASK_14_BITS, height & SIZE_MASK_14_BITS


def _webp_vp8l_size(data: bytes) -> tuple[int, int] | None:
    if len(data) < WEBP_VP8L_MIN_LENGTH or data[20] != WEBP_VP8L_SIGNATURE:
        return None
    bits = int.from_bytes(data[21:25], "little")
    width = (bits & VP8L_WIDTH_MASK) + ONE
    height = ((bits >> VP8L_HEIGHT_SHIFT) & VP8L_WIDTH_MASK) + ONE
    return width, height


def _webp_vp8x_size(data: bytes) -> tuple[int, int] | None:
    if len(data) < WEBP_VP8X_MIN_LENGTH:
        return None
    width = int.from_bytes(data[WEBP_VP8X_WIDTH_SLICE], "little") + ONE
    height = int.from_bytes(data[WEBP_VP8X_HEIGHT_SLICE], "little") + ONE
    return width, height


_WEBP_READERS = {
    WEBP_VP8_CHUNK: _webp_vp8_size,
    WEBP_VP8L_CHUNK: _webp_vp8l_size,
    WEBP_VP8X_CHUNK: _webp_vp8x_size,
}


def _webp_size(data: bytes) -> tuple[int, int] | None:
    if len(data) < WEBP_CHUNK_SLICE.stop or data[8:12] != WEBP_MARK:
        return None
    reader = _WEBP_READERS.get(data[WEBP_CHUNK_SLICE])
    return reader(data) if reader is not None else None


def _is_standalone_jpeg_marker(marker: int) -> bool:
    return marker == JPEG_TEM or JPEG_RST_LOW <= marker <= JPEG_RST_HIGH or marker == JPEG_SOI


def _is_jpeg_frame_marker(marker: int) -> bool:
    return JPEG_SOF_LOW <= marker <= JPEG_SOF_HIGH and marker not in JPEG_NOT_SOF


def _jpeg_frame_size(data: bytes, pos: int) -> tuple[int, int] | None:
    if pos + JPEG_SOF_HEADER_LENGTH > len(data):
        return None
    height, width = struct.unpack_from(UINT16_PAIR_BE, data, pos + 5)
    return width, height


def _jpeg_size(data: bytes) -> tuple[int, int] | None:
    """Walk the marker segments from the start of the file, bounded by MAX_JPEG_SEGMENTS."""
    pos = len(JPEG_MAGIC)
    for _ in range(MAX_JPEG_SEGMENTS):
        if pos + 2 > len(data) or data[pos] != JPEG_FILL:
            return None
        marker = data[pos + 1]
        if marker == JPEG_FILL:  # fill byte: skip one and look again
            pos += 1
            continue
        if _is_jpeg_frame_marker(marker):
            return _jpeg_frame_size(data, pos)
        if marker in (JPEG_EOI, JPEG_SOS):
            return None
        if _is_standalone_jpeg_marker(marker):
            pos += 2
            continue
        if pos + 4 > len(data):
            return None
        (length,) = struct.unpack_from(UINT16_BE, data, pos + 2)
        if length < 2:
            return None
        pos += 2 + length
    return None


def _usable(size: tuple[int, int] | None) -> tuple[int, int] | None:
    if size is None or size[0] == 0 or size[1] == 0:
        return None
    return size


def image_dimensions(data: bytes) -> tuple[int, int] | None:
    """(width, height) in pixels from the header, or None when unreadable. Never raises."""
    try:
        return _usable(_dimensions_of(bytes(data)))
    except (struct.error, ValueError, TypeError, IndexError):
        return None


def _dimensions_of(data: bytes) -> tuple[int, int] | None:
    if data.startswith(PNG_MAGIC):
        return _png_size(data)
    if data.startswith(GIF_MAGICS):
        return _gif_size(data)
    if data[:4] == RIFF_MAGIC:
        return _webp_size(data)
    if data.startswith(JPEG_MAGIC):
        return _jpeg_size(data)
    return None


def too_small_message(dimensions: tuple[int, int]) -> str | None:
    """The user-facing message when the shorter side is below MIN_SHORT_SIDE_PX, else None."""
    width, height = dimensions
    if min(width, height) >= MIN_SHORT_SIDE_PX:
        return None
    return TOO_SMALL_TEMPLATE.format(width=width, height=height, minimum=MIN_SHORT_SIDE_PX)
