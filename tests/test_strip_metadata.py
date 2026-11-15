"""Tests scripts/strip_metadata.py against synthetic JPEG and PNG files."""

import pathlib
import struct
import tempfile
import unittest
import zlib

from scripts import strip_metadata

COPYRIGHT = "\u00a9 Shibata, Tats".encode() + b"\x00"
ARTIST = b"Tats Shibata\x00"
BODY_SERIAL = b"3012345\x00"
LENS_SERIAL = b"20098765\x00"
LATITUDE = struct.pack("<6I", 35, 1, 4150998, 100000, 0, 1)
ICC = strip_metadata.ICC_HEADER + b"\x01\x01" + b"icc-profile-bytes"
JFIF = b"JFIF\x00\x01\x02\x00\x00\x01\x00\x01\x00\x00"
DQT = b"\xff\xdb\x00\x08\x00quant"
SCAN = b"\xff\xda\x00\x08scan-data\xff\xd9"
XMP = (
    strip_metadata.XMP_HEADER
    + b"<x:xmpmeta><crs:RawFileName>DSC_0001.NEF</crs:RawFileName>"
    + b"<stEvt:softwareAgent>Lightroom</stEvt:softwareAgent></x:xmpmeta>"
)
PHOTOSHOP = b"Photoshop 3.0\x008BIM\x04\x04\x00\x00\x00\x00\x00\x0ciptc-caption"


def segment(marker: int, payload: bytes) -> bytes:
    return bytes([0xFF, marker]) + struct.pack(">H", len(payload) + 2) + payload


def tiff(order: str, ifd0: list[tuple[int, int, int, bytes]]) -> bytes:
    """Returns TIFF data whose IFD0 holds the entries plus an Exif IFD and GPS IFD.

    Each entry is (tag, type, count, value bytes). The Exif IFD holds the body
    and lens serial numbers, and the GPS IFD holds a latitude.
    """
    prefix = b"II" if order == "<" else b"MM"
    sub_ifd = [
        (
            "exif",
            0x8769,
            [
                (0xA431, 2, len(BODY_SERIAL), BODY_SERIAL),
                (0xA435, 2, len(LENS_SERIAL), LENS_SERIAL),
            ],
        ),
        ("gps", 0x8825, [(0x0002, 5, 3, LATITUDE)]),
    ]
    entries = list(ifd0) + [(tag, 4, 1, b"") for _, tag, _ in sub_ifd]
    entries.sort()
    ifd0_size = 2 + 12 * len(entries) + 4
    data_offset = 8 + ifd0_size
    heap = b""
    head = struct.pack(order + "H", len(entries))
    sub_offsets = {}
    # Lay out the sub-IFDs after IFD0's out-of-line values.
    values = {}
    for tag, _, _, value in entries:
        if len(value) > 4:
            values[tag] = data_offset + len(heap)
            heap += value
    cursor = data_offset + len(heap)
    sub_data = b""
    for _, tag, sub_entries in sub_ifd:
        sub_offsets[tag] = cursor + len(sub_data)
        start = sub_offsets[tag]
        body = struct.pack(order + "H", len(sub_entries))
        tail = b""
        tail_offset = start + 2 + 12 * len(sub_entries) + 4
        for sub_tag, kind, count, value in sub_entries:
            if len(value) > 4:
                body += struct.pack(
                    order + "HHII", sub_tag, kind, count, tail_offset + len(tail)
                )
                tail += value
            else:
                body += struct.pack(order + "HHI", sub_tag, kind, count)
                body += value.ljust(4, b"\x00")
        body += struct.pack(order + "I", 0)
        sub_data += body + tail
    for tag, kind, count, value in entries:
        if tag in sub_offsets:
            head += struct.pack(order + "HHII", tag, kind, count, sub_offsets[tag])
        elif tag in values:
            head += struct.pack(order + "HHII", tag, kind, count, values[tag])
        else:
            head += struct.pack(order + "HHI", tag, kind, count)
            head += value.ljust(4, b"\x00")
    head += struct.pack(order + "I", 0)
    return prefix + struct.pack(order + "HI", 42, 8) + head + heap + sub_data


def orientation(value: int, order: str = "<") -> tuple[int, int, int, bytes]:
    return (0x0112, 3, 1, struct.pack(order + "H", value))


def camera_exif(order: str = "<", orient: int = 1) -> bytes:
    return strip_metadata.EXIF_HEADER + tiff(
        order,
        [
            orientation(orient, order),
            (0x010F, 2, 6, b"NIKON\x00"),
            (0x013B, 2, len(ARTIST), ARTIST),
            (0x8298, 2, len(COPYRIGHT), COPYRIGHT),
        ],
    )


def camera_jpeg(exif: bytes | None = None) -> bytes:
    return (
        b"\xff\xd8"
        + segment(0xE0, JFIF)
        + segment(0xE1, exif if exif is not None else camera_exif())
        + segment(0xE1, XMP)
        + segment(0xE2, ICC)
        + segment(0xEB, b"JP\x00\x00c2pa-manifest")
        + segment(0xED, PHOTOSHOP)
        + segment(0xFE, b"comment")
        + DQT
        + SCAN
    )


def clean_jpeg() -> bytes:
    return b"\xff\xd8" + segment(0xE0, JFIF) + segment(0xE2, ICC) + DQT + SCAN


def read_ifd0(data: bytes) -> dict[int, tuple[int, int, bytes]]:
    """Returns {tag: (type, count, value bytes)} from the JPEG's single Exif."""
    exif = [
        data[start + 4 : end]
        for marker, start, end in strip_metadata.jpeg_segments(data)
        if marker == 0xE1
    ]
    assert len(exif) == 1 and exif[0].startswith(strip_metadata.EXIF_HEADER)
    body = exif[0][len(strip_metadata.EXIF_HEADER) :]
    order = "<" if body[:2] == b"II" else ">"
    (offset,) = struct.unpack_from(order + "I", body, 4)
    (count,) = struct.unpack_from(order + "H", body, offset)
    entries = {}
    for index in range(count):
        tag, kind, values, raw = struct.unpack_from(
            order + "HHI4s", body, offset + 2 + 12 * index
        )
        size = strip_metadata.TYPE_SIZES[kind] * values
        if size > 4:
            (pointer,) = struct.unpack(order + "I", raw)
            raw = body[pointer : pointer + size]
        entries[tag] = (kind, values, raw[:size])
    return entries


def chunk(kind: bytes, payload: bytes) -> bytes:
    crc = zlib.crc32(kind + payload)
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", crc)


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
IHDR = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
IDAT = chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00"))
IEND = chunk(b"IEND", b"")
ICCP = chunk(b"iCCP", b"Display P3\x00\x00" + zlib.compress(b"icc"))
PHYS = chunk(b"pHYs", struct.pack(">IIB", 2835, 2835, 1))
SRGB = chunk(b"sRGB", b"\x00")


def camera_png(*extra: bytes) -> bytes:
    return (
        PNG_SIGNATURE
        + IHDR
        + ICCP
        + SRGB
        + PHYS
        + chunk(b"iTXt", b"XML:com.adobe.xmp\x00\x00\x00\x00\x00" + XMP[29:])
        + chunk(b"tEXt", b"Software\x00Snipping Tool")
        + chunk(b"zTXt", b"Comment\x00\x00" + zlib.compress(b"hidden"))
        + chunk(b"tIME", b"\x07\xea\x01\x02\x03\x04\x05")
        + chunk(b"eXIf", camera_exif()[len(strip_metadata.EXIF_HEADER) :])
        + b"".join(extra)
        + IDAT
        + IEND
    )


def png_chunks(data: bytes) -> list[tuple[bytes, bytes]]:
    chunks = []
    pos = len(PNG_SIGNATURE)
    while pos < len(data):
        (length,) = struct.unpack_from(">I", data, pos)
        chunks.append((data[pos + 4 : pos + 8], data[pos + 8 : pos + 8 + length]))
        pos += 12 + length
    return chunks


class JpegTest(unittest.TestCase):
    def test_removes_serials_xmp_photoshop_and_comments(self) -> None:
        out = strip_metadata.strip_metadata(camera_jpeg())
        assert out is not None
        for leaked in (
            BODY_SERIAL,
            LENS_SERIAL,
            LATITUDE,
            b"NIKON",
            b"DSC_0001.NEF",
            b"Lightroom",
            b"8BIM",
            b"c2pa",
            b"comment",
            strip_metadata.XMP_HEADER,
        ):
            self.assertNotIn(leaked, out)

    def test_keeps_jfif_icc_and_image_data(self) -> None:
        data = camera_jpeg()
        out = strip_metadata.strip_metadata(data)
        assert out is not None
        self.assertTrue(out.startswith(b"\xff\xd8" + segment(0xE0, JFIF)))
        self.assertIn(segment(0xE2, ICC), out)
        self.assertTrue(out.endswith(DQT + SCAN))
        self.assertEqual(out[out.index(DQT) :], data[data.index(DQT) :])

    def test_keeps_copyright_and_artist_only(self) -> None:
        out = strip_metadata.strip_metadata(camera_jpeg())
        assert out is not None
        self.assertEqual(
            read_ifd0(out),
            {
                0x013B: (2, len(ARTIST), ARTIST),
                0x8298: (2, len(COPYRIGHT), COPYRIGHT),
            },
        )

    def test_reads_big_endian_exif(self) -> None:
        out = strip_metadata.strip_metadata(camera_jpeg(camera_exif(">")))
        assert out is not None
        self.assertEqual(read_ifd0(out)[0x8298], (2, len(COPYRIGHT), COPYRIGHT))

    def test_keeps_orientation_other_than_one(self) -> None:
        out = strip_metadata.strip_metadata(camera_jpeg(camera_exif(orient=6)))
        assert out is not None
        self.assertEqual(read_ifd0(out)[0x0112], (3, 1, struct.pack("<H", 6)))

    def test_keeps_orientation_without_copyright(self) -> None:
        exif = strip_metadata.EXIF_HEADER + tiff("<", [orientation(8)])
        out = strip_metadata.strip_metadata(camera_jpeg(exif))
        assert out is not None
        self.assertEqual(read_ifd0(out), {0x0112: (3, 1, struct.pack("<H", 8))})

    def test_drops_exif_without_kept_tags(self) -> None:
        exif = strip_metadata.EXIF_HEADER + tiff("<", [orientation(1)])
        out = strip_metadata.strip_metadata(camera_jpeg(exif))
        assert out is not None
        self.assertNotIn(strip_metadata.EXIF_HEADER, out)
        self.assertEqual(out, clean_jpeg())

    def test_drops_jfif_thumbnail(self) -> None:
        thumbnail = JFIF[:-2] + b"\x01\x01" + b"\x10\x20\x30"
        data = b"\xff\xd8" + segment(0xE0, thumbnail) + DQT + SCAN
        out = strip_metadata.strip_metadata(data)
        self.assertEqual(out, b"\xff\xd8" + segment(0xE0, JFIF) + DQT + SCAN)

    def test_keeps_adobe_color_transform(self) -> None:
        adobe = segment(0xEE, b"Adobe\x00\x64\x40\x00\x00\x00\x00\x01")
        data = b"\xff\xd8" + adobe + segment(0xED, PHOTOSHOP) + DQT + SCAN
        self.assertEqual(
            strip_metadata.strip_metadata(data), b"\xff\xd8" + adobe + DQT + SCAN
        )

    def test_returns_none_when_already_stripped(self) -> None:
        out = strip_metadata.strip_metadata(camera_jpeg())
        assert out is not None
        self.assertIsNone(strip_metadata.strip_metadata(out))

    def test_returns_none_for_clean_file(self) -> None:
        self.assertIsNone(strip_metadata.strip_metadata(clean_jpeg()))

    def test_skips_fill_bytes_and_standalone_markers(self) -> None:
        data = b"\xff\xd8\xff\xff\xff\x01" + camera_jpeg()[2:]
        out = strip_metadata.strip_metadata(data)
        assert out is not None
        self.assertNotIn(b"8BIM", out)
        self.assertIn(COPYRIGHT, out)

    def test_rejects_segment_past_end_of_file(self) -> None:
        with self.assertRaises(ValueError):
            strip_metadata.strip_metadata(b"\xff\xd8\xff\xe1\x7f\xff" + bytes(16))

    def test_rejects_file_without_start_of_scan(self) -> None:
        data = camera_jpeg()
        with self.assertRaises(ValueError):
            strip_metadata.strip_metadata(data[: data.index(SCAN)])

    def test_rejects_garbage_between_segments(self) -> None:
        data = camera_jpeg()
        scan = data.index(SCAN)
        with self.assertRaises(ValueError):
            strip_metadata.strip_metadata(data[:scan] + b"\x00" + data[scan:])

    def test_rejects_unknown_exif_byte_order(self) -> None:
        exif = camera_exif()
        bad = exif[:6] + b"XX" + exif[8:]
        with self.assertRaises(ValueError):
            strip_metadata.strip_metadata(camera_jpeg(bad))

    def test_rejects_exif_offset_out_of_range(self) -> None:
        exif = bytearray(camera_exif())
        tiff_start = len(strip_metadata.EXIF_HEADER)
        (count,) = struct.unpack_from("<H", exif, tiff_start + 8)
        for index in range(count):
            entry = tiff_start + 10 + 12 * index
            if struct.unpack_from("<H", exif, entry)[0] == 0x8298:
                struct.pack_into("<I", exif, entry + 8, 0xFFFFFF)
        with self.assertRaises(ValueError):
            strip_metadata.strip_metadata(camera_jpeg(bytes(exif)))


class PngTest(unittest.TestCase):
    def test_removes_text_time_and_exif_chunks(self) -> None:
        out = strip_metadata.strip_metadata(camera_png())
        assert out is not None
        kinds = [kind for kind, _ in png_chunks(out)]
        self.assertEqual(
            kinds,
            [b"IHDR", b"iCCP", b"sRGB", b"pHYs", b"tEXt", b"tEXt", b"IDAT", b"IEND"],
        )
        for leaked in (b"Snipping", b"xmpmeta", b"NIKON", BODY_SERIAL, b"hidden"):
            self.assertNotIn(leaked, out)

    def test_keeps_exif_copyright_as_text(self) -> None:
        out = strip_metadata.strip_metadata(camera_png())
        assert out is not None
        texts = [payload for kind, payload in png_chunks(out) if kind == b"tEXt"]
        self.assertEqual(
            texts,
            [b"Copyright\x00\xa9 Shibata, Tats", b"Author\x00Tats Shibata"],
        )

    def test_keeps_text_copyright_and_author(self) -> None:
        data = (
            PNG_SIGNATURE
            + IHDR
            + chunk(b"tEXt", b"Author\x00Tats")
            + chunk(b"iTXt", b"Copyright\x00\x00\x00\x00\x00\xe6\x9f\xb4\xe7\x94\xb0")
            + chunk(b"tEXt", b"Software\x00GIMP")
            + IDAT
            + IEND
        )
        out = strip_metadata.strip_metadata(data)
        assert out is not None
        self.assertEqual(
            [(kind, payload) for kind, payload in png_chunks(out)][1:3],
            [
                (b"iTXt", b"Copyright\x00\x00\x00\x00\x00\xe6\x9f\xb4\xe7\x94\xb0"),
                (b"tEXt", b"Author\x00Tats"),
            ],
        )
        self.assertNotIn(b"GIMP", out)

    def test_keeps_image_data_bytes(self) -> None:
        out = strip_metadata.strip_metadata(camera_png())
        assert out is not None
        self.assertTrue(out.endswith(IDAT + IEND))
        self.assertTrue(out.startswith(PNG_SIGNATURE + IHDR + ICCP + SRGB + PHYS))

    def test_new_chunks_have_valid_crc(self) -> None:
        out = strip_metadata.strip_metadata(camera_png())
        assert out is not None
        pos = len(PNG_SIGNATURE)
        while pos < len(out):
            (length,) = struct.unpack_from(">I", out, pos)
            (crc,) = struct.unpack_from(">I", out, pos + 8 + length)
            self.assertEqual(crc, zlib.crc32(out[pos + 4 : pos + 8 + length]))
            pos += 12 + length

    def test_returns_none_when_already_stripped(self) -> None:
        out = strip_metadata.strip_metadata(camera_png())
        assert out is not None
        self.assertIsNone(strip_metadata.strip_metadata(out))

    def test_returns_none_for_clean_file(self) -> None:
        data = PNG_SIGNATURE + IHDR + ICCP + PHYS + IDAT + IEND
        self.assertIsNone(strip_metadata.strip_metadata(data))

    def test_drops_data_after_iend(self) -> None:
        data = PNG_SIGNATURE + IHDR + IDAT + IEND
        out = strip_metadata.strip_metadata(data + b"trailing")
        self.assertEqual(out, data)

    def test_rejects_truncated_chunk(self) -> None:
        with self.assertRaises(ValueError):
            strip_metadata.strip_metadata(PNG_SIGNATURE + IHDR + IDAT[:-3])

    def test_rejects_missing_iend(self) -> None:
        with self.assertRaises(ValueError):
            strip_metadata.strip_metadata(PNG_SIGNATURE + IHDR + IDAT)


class FormatTest(unittest.TestCase):
    def test_rejects_unsupported_formats(self) -> None:
        for data in (b"GIF89a" + bytes(16), b"RIFF\x00\x00\x00\x00WEBPVP8 "):
            with self.assertRaises(ValueError):
                strip_metadata.strip_metadata(data)


class MainTest(unittest.TestCase):
    def test_check_mode_fails_and_fix_mode_rewrites(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            jpeg = pathlib.Path(tmp) / "photo.jpg"
            png = pathlib.Path(tmp) / "screen.png"
            jpeg.write_bytes(camera_jpeg())
            png.write_bytes(camera_png())
            self.assertEqual(strip_metadata.main([str(jpeg), str(png)]), 1)
            self.assertEqual(strip_metadata.main(["--fix", str(jpeg), str(png)]), 0)
            self.assertEqual(strip_metadata.main([str(jpeg), str(png)]), 0)

    def test_check_mode_leaves_files_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "photo.jpg"
            path.write_bytes(camera_jpeg())
            strip_metadata.main([str(path)])
            self.assertEqual(path.read_bytes(), camera_jpeg())

    def test_fix_mode_leaves_clean_file_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "photo.jpg"
            path.write_bytes(clean_jpeg())
            before = path.stat().st_mtime_ns
            self.assertEqual(strip_metadata.main(["--fix", str(path)]), 0)
            self.assertEqual(path.read_bytes(), clean_jpeg())
            self.assertEqual(path.stat().st_mtime_ns, before)

    def test_fails_on_unparsable_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "photo.jpg"
            path.write_bytes(b"\xff\xd8\xff\xe1\x7f\xff")
            self.assertEqual(strip_metadata.main(["--fix", str(path)]), 1)


if __name__ == "__main__":
    unittest.main()
