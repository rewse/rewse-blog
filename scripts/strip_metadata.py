#!/usr/bin/env python3
"""Finds or removes metadata in JPEG and PNG files.

Published originals are served as they are, so they must not carry camera
serial numbers, edit history, source file names, or location data. Only a
copyright notice and an author name are kept.

Without --fix, prints each file that carries other metadata and exits 1 if
any does. With --fix, rewrites those files in place and exits 0. Either mode
exits 1 when a file cannot be parsed or has an unsupported format, so it is
never passed as clean. Only metadata bytes change, so the pixels are not
re-encoded:

- JPEG keeps APP0 JFIF (without a thumbnail), APP2 ICC profiles, and APP14
  Adobe, which tells decoders the color transform. Every other APPn segment
  (Exif, XMP, Photoshop/IPTC, C2PA, ...) and every comment is dropped. When
  the Exif IFD0 had Copyright, Artist, or an Orientation other than 1, a new
  Exif segment with only those tags takes the place of the first dropped one.
- PNG drops the caBX, eXIf, iTXt, tEXt, tIME, and zTXt chunks and anything
  after IEND, and keeps every other chunk, including iCCP, sRGB, gAMA, cHRM,
  and pHYs. A Copyright or Author text, or the eXIf Copyright or Artist, is
  written back as a single tEXt chunk each (iTXt when the text is not
  Latin-1) at the position of the first dropped chunk.
"""

from __future__ import annotations

import argparse
import pathlib
import struct
import sys
import zlib

ADOBE_HEADER = b"Adobe\x00"
EXIF_HEADER = b"Exif\x00\x00"
ICC_HEADER = b"ICC_PROFILE\x00"
JFIF_HEADER = b"JFIF\x00"
JFIF_LENGTH = 14  # Identifier through the thumbnail size, without pixels.
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
XMP_HEADER = b"http://ns.adobe.com/xap/1.0/\x00"

ARTIST_TAG = 0x013B
COPYRIGHT_TAG = 0x8298
ORIENTATION_TAG = 0x0112
KEPT_EXIF_TAGS = (ORIENTATION_TAG, ARTIST_TAG, COPYRIGHT_TAG)
TYPE_SIZES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8}

DROPPED_PNG_CHUNKS = frozenset({b"caBX", b"eXIf", b"iTXt", b"tEXt", b"tIME", b"zTXt"})
TEXT_CHUNKS = frozenset({b"iTXt", b"tEXt", b"zTXt"})
PNG_TEXT_KEYS = {b"Copyright": COPYRIGHT_TAG, b"Author": ARTIST_TAG}


def jpeg_segments(data: bytes) -> list[tuple[int, int, int]]:
    """Returns (marker, start, end) of each segment before the image data.

    Raises ValueError unless the walk reaches the start of scan, so a file
    that cannot be parsed is never reported as clean.
    """
    if data[:2] != b"\xff\xd8":
        raise ValueError("not a JPEG file")
    segments = []
    pos = 2
    while True:
        if pos >= len(data) or data[pos] != 0xFF:
            raise ValueError(f"expected a JPEG marker at offset {pos}")
        # Any number of 0xFF fill bytes may precede a marker.
        while pos < len(data) and data[pos] == 0xFF:
            pos += 1
        if pos >= len(data):
            raise ValueError("JPEG ends before the start of scan")
        marker = data[pos]
        start = pos - 1
        pos += 1
        if marker == 0xDA:  # Start of scan: the rest is image data.
            return segments
        if marker == 0x01 or 0xD0 <= marker <= 0xD7:  # TEM and RSTn: no length.
            continue
        if marker in (0x00, 0xD8, 0xD9):
            raise ValueError(f"unexpected JPEG marker 0x{marker:02X} at {start}")
        if pos + 2 > len(data):
            raise ValueError("JPEG ends inside a segment header")
        (length,) = struct.unpack(">H", data[pos : pos + 2])
        end = pos + length
        if length < 2 or end > len(data):
            raise ValueError(f"JPEG segment at offset {start} runs past the end")
        segments.append((marker, start, end))
        pos = end


def read_kept_exif(tiff: bytes) -> dict[int, tuple[int, int, bytes]]:
    """Returns {tag: (type, count, value)} for the kept tags in IFD0.

    Orientation is returned only when it is not 1. Raises ValueError when the
    data is not TIFF or an offset points outside it.
    """
    order = {b"II": "<", b"MM": ">"}.get(tiff[:2])
    if order is None:
        raise ValueError("Exif data has an unknown byte order")

    def read(fmt: str, offset: int) -> tuple[int, ...]:
        if offset + struct.calcsize(order + fmt) > len(tiff):
            raise ValueError(f"Exif offset {offset} is out of range")
        return struct.unpack_from(order + fmt, tiff, offset)

    (ifd0,) = read("I", 4)
    (count,) = read("H", ifd0)
    kept = {}
    for index in range(count):
        tag, kind, values = read("HHI", ifd0 + 2 + 12 * index)
        if tag not in KEPT_EXIF_TAGS:
            continue
        size = TYPE_SIZES.get(kind, 1) * values
        offset = ifd0 + 2 + 12 * index + 8
        if size > 4:
            (offset,) = read("I", offset)
        if offset + size > len(tiff):
            raise ValueError(f"Exif offset {offset} is out of range")
        value = tiff[offset : offset + size]
        if tag == ORIENTATION_TAG:
            if kind != 3 or values != 1:
                continue
            (orientation,) = struct.unpack(order + "H", value)
            if orientation == 1:
                continue
            value = struct.pack("<H", orientation)
        kept[tag] = (kind, values, value)
    return kept


def build_exif(tags: dict[int, tuple[int, int, bytes]]) -> bytes:
    """Returns a little-endian Exif payload whose IFD0 holds only the tags."""
    entries = sorted(tags.items())
    heap_offset = 8 + 2 + 12 * len(entries) + 4
    ifd = struct.pack("<H", len(entries))
    heap = b""
    for tag, (kind, values, value) in entries:
        if len(value) > 4:
            ifd += struct.pack("<HHII", tag, kind, values, heap_offset + len(heap))
            heap += value + b"\x00" * (len(value) % 2)  # Keep offsets even.
        else:
            ifd += struct.pack("<HHI", tag, kind, values) + value.ljust(4, b"\x00")
    ifd += struct.pack("<I", 0)
    return EXIF_HEADER + b"II" + struct.pack("<HI", 42, 8) + ifd + heap


def _segment(marker: int, payload: bytes) -> bytes:
    if len(payload) + 2 > 0xFFFF:
        raise ValueError("kept Exif tags do not fit in one segment")
    return bytes([0xFF, marker]) + struct.pack(">H", len(payload) + 2) + payload


def _strip_jpeg(data: bytes) -> bytes:
    kept_tags: dict[int, tuple[int, int, bytes]] = {}
    out = bytearray(data[:2])
    insert_at = None
    cursor = 2
    for marker, start, end in jpeg_segments(data):
        out += data[cursor:start]
        cursor = end
        payload = data[start + 4 : end]
        is_app = 0xE0 <= marker <= 0xEF
        if marker == 0xE0 and payload.startswith(JFIF_HEADER):
            if len(payload) > JFIF_LENGTH:
                # Drop the embedded thumbnail, which can show an unedited frame.
                out += _segment(marker, payload[: JFIF_LENGTH - 2] + b"\x00\x00")
            else:
                out += data[start:end]
        elif (marker == 0xE2 and payload.startswith(ICC_HEADER)) or (
            marker == 0xEE and payload.startswith(ADOBE_HEADER)
        ):
            out += data[start:end]
        elif is_app or marker == 0xFE:
            if insert_at is None:
                insert_at = len(out)
            if marker == 0xE1 and payload.startswith(EXIF_HEADER):
                kept_tags.update(read_kept_exif(payload[len(EXIF_HEADER) :]))
        else:
            out += data[start:end]
    out += data[cursor:]
    if kept_tags and insert_at is not None:
        out[insert_at:insert_at] = _segment(0xE1, build_exif(kept_tags))
    return bytes(out)


def _png_text(kind: bytes, payload: bytes) -> tuple[bytes, str] | None:
    """Returns (keyword, text) of a text chunk, or None if it is not readable."""
    keyword, sep, rest = payload.partition(b"\x00")
    if not sep:
        return None
    try:
        if kind == b"tEXt":
            return keyword, rest.decode("latin-1")
        if kind == b"zTXt":
            return keyword, zlib.decompress(rest[1:]).decode("latin-1")
        compressed, _method = rest[0], rest[1]
        _language, _, rest = rest[2:].partition(b"\x00")
        _translated, _, text = rest.partition(b"\x00")
        if compressed:
            text = zlib.decompress(text)
        return keyword, text.decode()
    except (IndexError, UnicodeDecodeError, zlib.error):
        return None


def _exif_text(value: bytes) -> str:
    # Exif ASCII may hold UTF-8 in practice, and Copyright may hold a second
    # NUL-separated string for the editor.
    parts = [part for part in value.split(b"\x00") if part]
    return " / ".join(part.decode("utf-8", "replace") for part in parts)


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    crc = zlib.crc32(kind + payload)
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", crc)


def _text_chunk(keyword: bytes, text: str) -> bytes:
    try:
        encoded = text.encode("latin-1")
    except UnicodeEncodeError:
        return _png_chunk(b"iTXt", keyword + b"\x00\x00\x00\x00\x00" + text.encode())
    return _png_chunk(b"tEXt", keyword + b"\x00" + encoded)


def _strip_png(data: bytes) -> bytes:
    texts: dict[int, str] = {}
    exif_texts: dict[int, str] = {}
    out = bytearray(PNG_SIGNATURE)
    insert_at = None
    pos = len(PNG_SIGNATURE)
    while True:
        if pos + 8 > len(data):
            raise ValueError("PNG ends before IEND")
        (length,) = struct.unpack_from(">I", data, pos)
        kind = data[pos + 4 : pos + 8]
        end = pos + 12 + length
        if end > len(data):
            raise ValueError(f"PNG chunk at offset {pos} runs past the end")
        payload = data[pos + 8 : pos + 8 + length]
        if kind in DROPPED_PNG_CHUNKS:
            if insert_at is None:
                insert_at = len(out)
            if kind in TEXT_CHUNKS:
                parsed = _png_text(kind, payload)
                if parsed and parsed[0] in PNG_TEXT_KEYS and parsed[1]:
                    texts.setdefault(PNG_TEXT_KEYS[parsed[0]], parsed[1])
            elif kind == b"eXIf":
                for tag, (_, _, value) in read_kept_exif(payload).items():
                    if tag != ORIENTATION_TAG and _exif_text(value):
                        exif_texts[tag] = _exif_text(value)
        else:
            out += data[pos:end]
        pos = end
        if kind == b"IEND":
            break
    kept = {**exif_texts, **texts}
    if kept and insert_at is not None:
        chunks = b""
        for keyword, tag in PNG_TEXT_KEYS.items():
            if tag in kept:
                chunks += _text_chunk(keyword, kept[tag])
        out[insert_at:insert_at] = chunks
    return bytes(out)


def strip_metadata(data: bytes) -> bytes | None:
    """Returns the image without metadata, or None when it has none to remove.

    Raises ValueError for a file that cannot be parsed or is not JPEG or PNG.
    """
    if data.startswith(b"\xff\xd8"):
        stripped = _strip_jpeg(data)
    elif data.startswith(PNG_SIGNATURE):
        stripped = _strip_png(data)
    else:
        raise ValueError("unsupported image format; convert it to JPEG or PNG")
    return None if stripped == data else stripped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Find or remove metadata in JPEG and PNG files."
    )
    parser.add_argument("--fix", action="store_true", help="remove the metadata")
    parser.add_argument("files", nargs="+", type=pathlib.Path)
    args = parser.parse_args(argv)

    found = False
    for path in args.files:
        try:
            stripped = strip_metadata(path.read_bytes())
        except ValueError as error:
            print(f"cannot parse {path}: {error}", file=sys.stderr)
            found = True
            continue
        if stripped is None:
            continue
        if args.fix:
            path.write_bytes(stripped)
            print(f"removed metadata: {path}")
        else:
            print(f"metadata found: {path} (run scripts/strip_metadata.py --fix)")
            found = True
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
