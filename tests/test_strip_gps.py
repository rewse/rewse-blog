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

    def test_check_mode_fails_and_fix_mode_rewrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "photo.jpg"
            path.write_bytes(jpeg())
            self.assertEqual(strip_gps.main([str(path)]), 1)
            self.assertEqual(strip_gps.main(["--fix", str(path)]), 0)
            self.assertEqual(strip_gps.main([str(path)]), 0)


if __name__ == "__main__":
    unittest.main()
