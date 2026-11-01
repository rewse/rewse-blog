"""Tests scripts/strip_gps.py against a synthetic JPEG."""

import importlib.util
import pathlib
import struct
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "strip_gps.py"
spec = importlib.util.spec_from_file_location("strip_gps", SCRIPT)
assert spec is not None and spec.loader is not None
strip_gps = importlib.util.module_from_spec(spec)
spec.loader.exec_module(strip_gps)

LATITUDE = struct.pack("<6I", 35, 1, 4150998, 100000, 0, 1)
SCAN = b"\xff\xda\x00\x08scan-data\xff\xd9"


def segment(marker: int, payload: bytes) -> bytes:
    return bytes([0xFF, marker]) + struct.pack(">H", len(payload) + 2) + payload


def exif_with_gps() -> bytes:
    """Returns little-endian TIFF data: IFD0 (Orientation, GPS pointer) + GPS IFD."""
    ifd0 = 8
    gps = ifd0 + 2 + 12 * 2 + 4
    latitude = gps + 2 + 12 * 2 + 4
    tiff = b"II" + struct.pack("<HI", 42, ifd0)
    tiff += struct.pack("<H", 2)
    tiff += struct.pack("<HHIHH", 0x0112, 3, 1, 6, 0)
    tiff += struct.pack("<HHII", 0x8825, 4, 1, gps)
    tiff += struct.pack("<I", 0)
    tiff += struct.pack("<H", 2)
    tiff += struct.pack("<HHI4s", 1, 2, 2, b"N\x00\x00\x00")
    tiff += struct.pack("<HHII", 2, 5, 3, latitude)
    tiff += struct.pack("<I", 0)
    return tiff + LATITUDE


def jpeg(xmp: bytes = b"<x:xmpmeta><exif:GPSLatitude>35</exif:GPSLatitude>") -> bytes:
    return (
        b"\xff\xd8"
        + segment(0xE1, strip_gps.EXIF_HEADER + exif_with_gps())
        + segment(0xE1, strip_gps.XMP_HEADER + xmp)
        + SCAN
    )


class StripGpsTest(unittest.TestCase):
    def test_removes_exif_gps_and_keeps_other_tags(self):
        out = strip_gps.strip_gps(jpeg())
        self.assertIsNotNone(out)
        assert out is not None
        self.assertNotIn(LATITUDE, out)
        self.assertNotIn(b"N\x00\x00\x00", out)
        tiff = out.index(strip_gps.EXIF_HEADER) + len(strip_gps.EXIF_HEADER)
        (count,) = struct.unpack_from("<H", out, tiff + 8)
        self.assertEqual(count, 1)
        tag, _, _, value = struct.unpack_from("<HHIH", out, tiff + 10)
        self.assertEqual((tag, value), (0x0112, 6))
        self.assertTrue(out.endswith(SCAN))

    def test_drops_xmp_that_mentions_gps(self):
        out = strip_gps.strip_gps(jpeg())
        assert out is not None
        self.assertNotIn(strip_gps.XMP_HEADER, out)

    def test_keeps_xmp_without_gps(self):
        out = strip_gps.strip_gps(jpeg(xmp=b"<x:xmpmeta/>"))
        assert out is not None
        self.assertIn(strip_gps.XMP_HEADER + b"<x:xmpmeta/>", out)

    def test_returns_none_when_already_clean(self):
        out = strip_gps.strip_gps(jpeg())
        assert out is not None
        self.assertIsNone(strip_gps.strip_gps(out))

    def test_skips_fill_bytes_before_markers(self):
        data = jpeg()
        padded = b"\xff\xd8\xff\xff" + data[2:]
        out = strip_gps.strip_gps(padded)
        self.assertIsNotNone(out)
        assert out is not None
        self.assertNotIn(LATITUDE, out)
        self.assertNotIn(strip_gps.XMP_HEADER, out)

    def test_skips_standalone_markers(self):
        data = jpeg()
        out = strip_gps.strip_gps(b"\xff\xd8\xff\x01\xff\xd0" + data[2:])
        self.assertIsNotNone(out)
        assert out is not None
        self.assertNotIn(LATITUDE, out)

    def test_rejects_segment_past_end_of_file(self):
        with self.assertRaises(ValueError):
            strip_gps.strip_gps(b"\xff\xd8\xff\xe1\x7f\xff" + b"\x00" * 16)

    def test_rejects_file_without_start_of_scan(self):
        data = jpeg()
        with self.assertRaises(ValueError):
            strip_gps.strip_gps(data[: data.index(SCAN)])

    def test_rejects_garbage_between_segments(self):
        data = jpeg()
        scan = data.index(SCAN)
        with self.assertRaises(ValueError):
            strip_gps.strip_gps(data[:scan] + b"\x00" + data[scan:])

    def test_rejects_unknown_exif_byte_order(self):
        tiff = b"XX" + exif_with_gps()[2:]
        data = b"\xff\xd8" + segment(0xE1, strip_gps.EXIF_HEADER + tiff) + SCAN
        with self.assertRaises(ValueError):
            strip_gps.strip_gps(data)

    def test_rejects_exif_offsets_out_of_range(self):
        tiff = bytearray(exif_with_gps())
        # Point the GPS latitude value past the end of the TIFF data.
        struct.pack_into("<I", tiff, 8 + 2 + 12 * 2 + 4 + 2 + 12 + 8, 0xFFFFFF)
        data = b"\xff\xd8" + segment(0xE1, strip_gps.EXIF_HEADER + bytes(tiff)) + SCAN
        with self.assertRaises(ValueError):
            strip_gps.strip_gps(data)

    def test_check_mode_fails_on_unparsable_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "photo.jpg"
            path.write_bytes(b"\xff\xd8\xff\xe1\x7f\xff")
            self.assertEqual(strip_gps.main([str(path)]), 1)

    def test_check_mode_fails_and_fix_mode_rewrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "photo.jpg"
            path.write_bytes(jpeg())
            self.assertEqual(strip_gps.main([str(path)]), 1)
            self.assertEqual(strip_gps.main(["--fix", str(path)]), 0)
            self.assertEqual(strip_gps.main([str(path)]), 0)


if __name__ == "__main__":
    unittest.main()
