"""Strip metadata from uploaded photos before any model call or hash.

strip_metadata keeps every pixel-carrying byte and drops the metadata around them:
EXIF, XMP, IPTC, comments, text chunks, and any data after the image ends. For a JPEG
whose EXIF orientation is not 1, one minimal EXIF segment holding only the Orientation
tag is written back, so the photo still displays the right way up.

Parsing is done by hand with struct. Any input that is not a well-formed image of a
supported type is returned unchanged, and nothing here raises. Every loop moves forward
by at least one byte per step, so the work is bounded by the input length.
"""

from __future__ import annotations

import struct

# JPEG
JPEG_MAGIC = b"\xff\xd8"
JPEG_FILL = 0xFF
JPEG_EOI = 0xD9
JPEG_SOS = 0xDA
JPEG_APP_LOW = 0xE0
JPEG_APP_HIGH = 0xEF
JPEG_APP1 = 0xE1
JPEG_APP14 = 0xEE
JPEG_COM = 0xFE
JPEG_RST_LOW = 0xD0
JPEG_RST_HIGH = 0xD7
JPEG_TEM = 0x01
JPEG_SOI = 0xD8
JPEG_SEGMENT_MIN_LENGTH = 2
JPEG_ADOBE_ID = b"Adobe"  # APP14 sets the colour transform, so it is kept
JPEG_STUFFED_ZERO = 0x00
EXIF_HEADER = b"Exif\x00\x00"
EXIF_TIFF_MAGIC = 42
EXIF_IFD_POINTER_OFFSET = 4  # where the TIFF header stores the offset of IFD0
EXIF_IFD0_OFFSET = 8
EXIF_COUNT_SIZE = 2
EXIF_ENTRY_SIZE = 12
EXIF_ENTRY_VALUE_OFFSET = 8
EXIF_ORIENTATION_TAG = 0x0112
EXIF_SHORT_TYPE = 3
EXIF_ORIENTATION_MIN = 2  # 1 is the default and needs no tag; values outside 1 to 8 are ignored
EXIF_ORIENTATION_MAX = 8
EXIF_NEXT_IFD_SIZE = 4

# PNG
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
PNG_HEADER_SIZE = 8
PNG_CHUNK_OVERHEAD = 12  # length (4) + type (4) + CRC (4)
PNG_IEND = b"IEND"
PNG_DROPPED_TYPES = frozenset({b"eXIf", b"tEXt", b"zTXt", b"iTXt", b"tIME"})
PNG_KEPT_ANCILLARY = frozenset({b"tRNS", b"gAMA", b"cHRM", b"sRGB", b"iCCP", b"pHYs", b"sBIT", b"bKGD"})
PNG_ANCILLARY_BIT = 0x20  # set in the first type byte for ancillary chunks

# WebP
WEBP_RIFF = b"RIFF"
WEBP_WEBP = b"WEBP"
WEBP_RIFF_HEADER_SIZE = 12
WEBP_CHUNK_HEADER_SIZE = 8
WEBP_DROPPED_CHUNKS = frozenset({b"EXIF", b"XMP "})
WEBP_VP8X = b"VP8X"
WEBP_VP8X_FLAGS_INDEX = WEBP_CHUNK_HEADER_SIZE  # first payload byte of VP8X
WEBP_VP8X_CLEAR_MASK = 0xFF & ~(0x08 | 0x04)  # EXIF and XMP flag bits

# GIF
GIF_MAGICS = (b"GIF87a", b"GIF89a")
GIF_SCREEN_SIZE = 13  # signature (6) + logical screen descriptor (7)
GIF_PACKED_INDEX = 10  # packed-fields byte of the logical screen descriptor
GIF_GLOBAL_TABLE_FLAG = 0x80
GIF_LOCAL_TABLE_FLAG = 0x80
GIF_TABLE_SIZE_MASK = 0x07
GIF_TABLE_BASE_BYTES = 3
GIF_EXTENSION_INTRO = 0x21
GIF_IMAGE_INTRO = 0x2C
GIF_TRAILER = 0x3B
GIF_COMMENT_LABEL = 0xFE
GIF_APPLICATION_LABEL = 0xFF
GIF_EXTENSION_HEADER_SIZE = 2  # introducer + label
GIF_APP_ID_INDEX = 3  # after introducer, label, and the 11-byte block size
GIF_APP_ID_LENGTH = 11
GIF_IMAGE_DESCRIPTOR_SIZE = 10  # introducer + left, top, width, height (2 each) + packed
GIF_LZW_SIZE_BYTES = 1
GIF_KEPT_APP_ID = b"NETSCAPE2.0"
GIF_BLOCK_TERMINATOR = 0x00


class _Malformed(Exception):
    """Raised inside the walkers for any input that cannot be rewritten safely."""


def strip_metadata(data: bytes) -> bytes:
    """Return the image with metadata removed, or data unchanged when it cannot be stripped."""
    try:
        return _strip(bytes(data))
    except (_Malformed, struct.error, IndexError, ValueError):
        return data


def _strip(data: bytes) -> bytes:
    if data.startswith(JPEG_MAGIC):
        return _strip_jpeg(data)
    if data.startswith(PNG_MAGIC):
        return _strip_png(data)
    if data[:4] == WEBP_RIFF and data[8:12] == WEBP_WEBP:
        return _strip_webp(data)
    if data.startswith(GIF_MAGICS):
        return _strip_gif(data)
    return data


# ---------------------------------------------------------------------------
# JPEG
# ---------------------------------------------------------------------------


def _strip_jpeg(data: bytes) -> bytes:
    """Copy the segments, dropping APPn (except Adobe APP14) and COM. Ends at the first EOI."""
    orientation: int | None = None
    body = bytearray()
    pos = len(JPEG_MAGIC)
    while True:
        pos = _skip_fill(data, pos)
        if pos + 2 > len(data) or data[pos] != JPEG_FILL:
            raise _Malformed("expected a marker")
        marker = data[pos + 1]
        if marker == JPEG_EOI:
            header = JPEG_MAGIC + (_minimal_exif_segment(orientation) if orientation else b"")
            return header + bytes(body) + data[pos : pos + 2]
        if marker == JPEG_TEM or marker == JPEG_SOI or JPEG_RST_LOW <= marker <= JPEG_RST_HIGH:
            raise _Malformed("standalone marker outside entropy data")
        segment_end = _segment_end(data, pos)
        segment_body = data[pos + 4 : segment_end]
        if marker == JPEG_APP1 and orientation is None:
            orientation = _exif_orientation(segment_body)
        if not _is_dropped_jpeg_segment(marker, segment_body):
            body += data[pos:segment_end]
        pos = segment_end
        if marker == JPEG_SOS:
            entropy_end = _entropy_end(data, pos)
            body += data[pos:entropy_end]
            pos = entropy_end


def _skip_fill(data: bytes, pos: int) -> int:
    """Step past any run of 0xFF fill bytes that precede a marker."""
    while pos + 1 < len(data) and data[pos] == JPEG_FILL and data[pos + 1] == JPEG_FILL:
        pos += 1
    return pos


def _segment_end(data: bytes, pos: int) -> int:
    """End offset of the length-prefixed segment whose marker starts at pos."""
    if pos + 4 > len(data):
        raise _Malformed("truncated segment header")
    (length,) = struct.unpack_from(">H", data, pos + 2)
    if length < JPEG_SEGMENT_MIN_LENGTH:
        raise _Malformed("segment length too small")
    end = pos + 2 + length
    if end > len(data):
        raise _Malformed("segment runs past end of data")
    return end


def _is_dropped_jpeg_segment(marker: int, segment_body: bytes) -> bool:
    if marker == JPEG_COM:
        return True
    if JPEG_APP_LOW <= marker <= JPEG_APP_HIGH:
        return not (marker == JPEG_APP14 and segment_body.startswith(JPEG_ADOBE_ID))
    return False


def _entropy_end(data: bytes, start: int) -> int:
    """Offset of the next real marker after entropy-coded data that begins at start.

    Stuffed 0x00 bytes, RSTn restart markers and 0xFF fill are part of the scan and are skipped.
    """
    k = start
    while True:
        k = data.find(b"\xff", k)
        if k < 0 or k + 1 >= len(data):
            raise _Malformed("no marker after entropy data")
        following = data[k + 1]
        if following == JPEG_STUFFED_ZERO or JPEG_RST_LOW <= following <= JPEG_RST_HIGH:
            k += 2
        elif following == JPEG_FILL:
            k += 1
        else:
            return k


def _exif_orientation(segment_body: bytes) -> int | None:
    """The Orientation value (2 to 8) from an EXIF APP1 body, or None. Never raises."""
    if not segment_body.startswith(EXIF_HEADER):
        return None
    try:
        return _tiff_orientation(segment_body[len(EXIF_HEADER) :])
    except (struct.error, IndexError, ValueError):
        return None


def _tiff_orientation(tiff: bytes) -> int | None:
    order = {b"II": "<", b"MM": ">"}.get(tiff[:2])
    if order is None or struct.unpack_from(order + "H", tiff, 2)[0] != EXIF_TIFF_MAGIC:
        return None
    (ifd_offset,) = struct.unpack_from(order + "I", tiff, EXIF_IFD_POINTER_OFFSET)
    (count,) = struct.unpack_from(order + "H", tiff, ifd_offset)
    for index in range(count):
        entry = ifd_offset + EXIF_COUNT_SIZE + index * EXIF_ENTRY_SIZE
        tag, value_type = struct.unpack_from(order + "HH", tiff, entry)
        if tag == EXIF_ORIENTATION_TAG:
            return _orientation_value(tiff, order, entry, value_type)
    return None


def _orientation_value(tiff: bytes, order: str, entry: int, value_type: int) -> int | None:
    if value_type != EXIF_SHORT_TYPE:
        return None
    (value,) = struct.unpack_from(order + "H", tiff, entry + EXIF_ENTRY_VALUE_OFFSET)
    if EXIF_ORIENTATION_MIN <= value <= EXIF_ORIENTATION_MAX:
        return value
    return None


def _minimal_exif_segment(orientation: int) -> bytes:
    """An APP1 segment whose only tag is Orientation, in little-endian TIFF order."""
    entry = struct.pack("<HHI", EXIF_ORIENTATION_TAG, EXIF_SHORT_TYPE, 1)
    entry += struct.pack("<HH", orientation, 0)
    tiff = b"II" + struct.pack("<H", EXIF_TIFF_MAGIC) + struct.pack("<I", EXIF_IFD0_OFFSET)
    tiff += struct.pack("<H", 1) + entry + struct.pack("<I", 0)
    segment_body = EXIF_HEADER + tiff
    length = len(segment_body) + JPEG_SEGMENT_MIN_LENGTH
    return bytes((JPEG_FILL, JPEG_APP1)) + struct.pack(">H", length) + segment_body


# ---------------------------------------------------------------------------
# PNG
# ---------------------------------------------------------------------------


def _strip_png(data: bytes) -> bytes:
    """Copy chunks verbatim except metadata chunks. Stops after IEND, so trailing data is dropped."""
    out = bytearray(PNG_MAGIC)
    pos = PNG_HEADER_SIZE
    while pos < len(data):
        if pos + PNG_CHUNK_OVERHEAD > len(data):
            raise _Malformed("truncated PNG chunk")
        (length,) = struct.unpack_from(">I", data, pos)
        chunk_type = data[pos + 4 : pos + 8]
        end = pos + PNG_CHUNK_OVERHEAD + length
        if end > len(data) or not chunk_type.isalpha():
            raise _Malformed("bad PNG chunk")
        if not _is_dropped_png_chunk(chunk_type):
            out += data[pos:end]
        pos = end
        if chunk_type == PNG_IEND:
            return bytes(out)
    raise _Malformed("PNG has no IEND")


def _is_dropped_png_chunk(chunk_type: bytes) -> bool:
    if chunk_type in PNG_DROPPED_TYPES:
        return True
    is_ancillary = bool(chunk_type[0] & PNG_ANCILLARY_BIT)
    return is_ancillary and chunk_type not in PNG_KEPT_ANCILLARY


# ---------------------------------------------------------------------------
# WebP
# ---------------------------------------------------------------------------


def _strip_webp(data: bytes) -> bytes:
    """Drop EXIF and XMP chunks, clear their VP8X flag bits, and rewrite the RIFF size."""
    (riff_size,) = struct.unpack_from("<I", data, 4)
    riff_end = WEBP_CHUNK_HEADER_SIZE + riff_size
    if riff_end > len(data) or riff_size < len(WEBP_WEBP):
        raise _Malformed("bad RIFF size")
    chunks = bytearray()
    pos = WEBP_RIFF_HEADER_SIZE
    while pos < riff_end:
        fourcc, end = _webp_chunk_span(data, pos, riff_end)
        if fourcc not in WEBP_DROPPED_CHUNKS:
            chunks += _with_vp8x_flags_cleared(fourcc, data[pos:end])
        pos = end
    body = WEBP_WEBP + bytes(chunks)
    return WEBP_RIFF + struct.pack("<I", len(body)) + body


def _webp_chunk_span(data: bytes, pos: int, riff_end: int) -> tuple[bytes, int]:
    """The fourcc and end offset of the RIFF chunk at pos, pad byte included."""
    if pos + WEBP_CHUNK_HEADER_SIZE > riff_end:
        raise _Malformed("truncated WebP chunk header")
    fourcc = data[pos : pos + 4]
    (size,) = struct.unpack_from("<I", data, pos + 4)
    end = pos + WEBP_CHUNK_HEADER_SIZE + size + (size & 1)
    if end > riff_end:
        raise _Malformed("WebP chunk overruns RIFF")
    return fourcc, end


def _with_vp8x_flags_cleared(fourcc: bytes, chunk: bytes) -> bytes:
    if fourcc != WEBP_VP8X:
        return chunk
    raw = bytearray(chunk)
    raw[WEBP_VP8X_FLAGS_INDEX] &= WEBP_VP8X_CLEAR_MASK
    return bytes(raw)


# ---------------------------------------------------------------------------
# GIF
# ---------------------------------------------------------------------------


def _strip_gif(data: bytes) -> bytes:
    """Drop comment and non-NETSCAPE application extensions. Frames are copied verbatim."""
    out = bytearray(data[:GIF_SCREEN_SIZE])
    flags = data[GIF_PACKED_INDEX]
    pos = GIF_SCREEN_SIZE
    if flags & GIF_GLOBAL_TABLE_FLAG:
        pos = _gif_table_end(data, pos, flags)
        out += data[GIF_SCREEN_SIZE:pos]
    while True:
        if pos >= len(data):
            raise _Malformed("GIF has no trailer")
        block = data[pos]
        if block == GIF_TRAILER:
            return bytes(out) + data[pos : pos + 1]
        if block == GIF_EXTENSION_INTRO:
            pos = _gif_extension(data, pos, out)
        elif block == GIF_IMAGE_INTRO:
            pos = _gif_image(data, pos, out)
        else:
            raise _Malformed("unknown GIF block")


def _gif_table_end(data: bytes, pos: int, flags: int) -> int:
    end = pos + GIF_TABLE_BASE_BYTES * (1 << ((flags & GIF_TABLE_SIZE_MASK) + 1))
    if end > len(data):
        raise _Malformed("GIF colour table overruns data")
    return end


def _gif_extension(data: bytes, pos: int, out: bytearray) -> int:
    if pos + GIF_EXTENSION_HEADER_SIZE > len(data):
        raise _Malformed("truncated GIF extension")
    end = _gif_sub_blocks_end(data, pos + GIF_EXTENSION_HEADER_SIZE)
    if not _is_dropped_gif_extension(data, pos):
        out += data[pos:end]
    return end


def _is_dropped_gif_extension(data: bytes, pos: int) -> bool:
    label = data[pos + 1]
    if label == GIF_COMMENT_LABEL:
        return True
    if label != GIF_APPLICATION_LABEL:
        return False
    app_id = data[pos + GIF_APP_ID_INDEX : pos + GIF_APP_ID_INDEX + GIF_APP_ID_LENGTH]
    return app_id != GIF_KEPT_APP_ID


def _gif_image(data: bytes, pos: int, out: bytearray) -> int:
    descriptor_end = pos + GIF_IMAGE_DESCRIPTOR_SIZE
    if descriptor_end > len(data):
        raise _Malformed("truncated GIF image descriptor")
    flags = data[descriptor_end - 1]
    data_start = descriptor_end
    if flags & GIF_LOCAL_TABLE_FLAG:
        data_start = _gif_table_end(data, descriptor_end, flags)
    lzw_start = data_start + GIF_LZW_SIZE_BYTES
    if lzw_start > len(data):
        raise _Malformed("truncated GIF image data")
    end = _gif_sub_blocks_end(data, lzw_start)
    out += data[pos:end]
    return end


def _gif_sub_blocks_end(data: bytes, pos: int) -> int:
    """Offset just past a run of length-prefixed sub-blocks and their zero-length terminator."""
    while True:
        if pos >= len(data):
            raise _Malformed("GIF sub-blocks run past end")
        size = data[pos]
        pos += 1
        if size == GIF_BLOCK_TERMINATOR:
            return pos
        pos += size
        if pos > len(data):
            raise _Malformed("GIF sub-block overruns data")
