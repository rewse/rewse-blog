#!/usr/bin/env python3
"""Finds or removes GPS metadata in JPEG files.

Without --fix, prints each file that carries GPS data and exits 1 if any does.
With --fix, removes the data in place and exits 0. Only metadata bytes change,
so the image is not re-encoded:

- In the Exif segment, every byte of the GPS IFD and its values is zeroed and
  the GPS pointer is removed from IFD0.
- An XMP segment that mentions GPS is dropped, since XMP is optional.
"""

from __future__ import annotations

import argparse
import pathlib
import struct
import sys

EXIF_HEADER = b"Exif\x00\x00"
XMP_HEADER = b"http://ns.adobe.com/xap/1.0/\x00"
GPS_IFD_TAG = 0x8825
TYPE_SIZES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8}


def _segments(data: bytes) -> list[tuple[int, int, int]]:
    """Returns (marker, start, end) of each segment before the image data."""
    if data[:2] != b"\xff\xd8":
        raise ValueError("not a JPEG file")
    segments = []
    pos = 2
    while pos + 4 <= len(data) and data[pos] == 0xFF:
        marker = data[pos + 1]
        if marker == 0xDA:  # Start of scan: the rest is image data.
            break
        (length,) = struct.unpack(">H", data[pos + 2 : pos + 4])
        segments.append((marker, pos, pos + 2 + length))
        pos += 2 + length
    return segments


def _strip_exif_gps(tiff: bytearray) -> bool:
    """Removes the GPS IFD from TIFF data in place; returns whether it had one."""
    order = {b"II": "<", b"MM": ">"}.get(bytes(tiff[:2]))
    if order is None:
        return False

    def read(fmt: str, offset: int) -> tuple[int, ...]:
        return struct.unpack_from(order + fmt, tiff, offset)

    (ifd0,) = read("I", 4)
    (count,) = read("H", ifd0)
    entries = ifd0 + 2
    for index in range(count):
        entry = entries + 12 * index
        tag, _, _, gps = read("HHII", entry)
        if tag != GPS_IFD_TAG:
            continue
        (gps_count,) = read("H", gps)
        for gps_index in range(gps_count):
            gps_entry = gps + 2 + 12 * gps_index
            _, kind, values, offset = read("HHII", gps_entry)
            size = TYPE_SIZES.get(kind, 1) * values
            if size > 4:
                tiff[offset : offset + size] = bytes(size)
        gps_end = gps + 2 + 12 * gps_count + 4
        tiff[gps:gps_end] = bytes(gps_end - gps)
        # Shift the later entries and the next-IFD offset up by one entry.
        tail_end = entries + 12 * count + 4
        tiff[entry : tail_end - 12] = tiff[entry + 12 : tail_end]
        tiff[tail_end - 12 : tail_end] = bytes(12)
        struct.pack_into(order + "H", tiff, ifd0, count - 1)
        return True
    return False


def strip_gps(data: bytes) -> bytes | None:
    """Returns the JPEG without GPS data, or None when it has none."""
    out = bytearray(data)
    changed = False
    # Walk backwards so dropping a segment keeps earlier offsets valid.
    for _, start, end in reversed(_segments(data)):
        payload = data[start + 4 : end]
        if payload.startswith(EXIF_HEADER):
            tiff = bytearray(payload[len(EXIF_HEADER) :])
            if _strip_exif_gps(tiff):
                out[start + 4 + len(EXIF_HEADER) : end] = tiff
                changed = True
        elif payload.startswith(XMP_HEADER) and b"GPS" in payload:
            del out[start:end]
            changed = True
    return bytes(out) if changed else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Find or remove GPS metadata in JPEG files."
    )
    parser.add_argument("--fix", action="store_true", help="remove the GPS data")
    parser.add_argument("files", nargs="+", type=pathlib.Path)
    args = parser.parse_args(argv)

    found = False
    for path in args.files:
        stripped = strip_gps(path.read_bytes())
        if stripped is None:
            continue
        if args.fix:
            path.write_bytes(stripped)
            print(f"removed GPS data: {path}")
        else:
            print(f"GPS data found: {path} (run scripts/strip_gps.py --fix)")
            found = True
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
