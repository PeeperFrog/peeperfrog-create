#!/usr/bin/env python3
"""Tests for webp-convert.py utility functions - pure utility, no API keys."""

import os
import sys
import tempfile
import shutil
import unittest

# Add tools dir to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

# Need pillow for tests - same as the script requires
try:
    from PIL import Image
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

# Import the module (file has a hyphen, so use importlib)
import importlib.util
spec = importlib.util.spec_from_file_location(
    "webp_convert",
    os.path.join(os.path.dirname(__file__), "..", "tools", "webp-convert.py"),
)
webp_convert = importlib.util.module_from_spec(spec)
spec.loader.exec_module(webp_convert)


@unittest.skipUnless(HAS_PILLOW, "Pillow not installed")
class TestConvertToWebp(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _create_png(self, name="test.png", size=(100, 100), mode="RGB"):
        path = os.path.join(self.tmpdir, name)
        img = Image.new(mode, size, color=(255, 0, 0))
        img.save(path, "PNG")
        return path

    def _create_jpg(self, name="test.jpg", size=(100, 100)):
        path = os.path.join(self.tmpdir, name)
        img = Image.new("RGB", size, color=(0, 255, 0))
        img.save(path, "JPEG")
        return path

    def test_convert_png_to_webp(self):
        png_path = self._create_png()
        result = webp_convert.convert_to_webp(png_path)
        self.assertIsNotNone(result)
        self.assertTrue(str(result).endswith(".webp"))
        self.assertTrue(os.path.exists(result))

    def test_convert_jpg_to_webp(self):
        jpg_path = self._create_jpg()
        result = webp_convert.convert_to_webp(jpg_path)
        self.assertIsNotNone(result)
        self.assertTrue(os.path.exists(result))

    def test_custom_output_path(self):
        png_path = self._create_png()
        out_path = os.path.join(self.tmpdir, "custom_output.webp")
        result = webp_convert.convert_to_webp(png_path, output_path=out_path)
        self.assertEqual(str(result), out_path)
        self.assertTrue(os.path.exists(out_path))

    def test_skip_existing(self):
        png_path = self._create_png()
        # First conversion
        webp_convert.convert_to_webp(png_path, skip_existing=False)
        # Second should skip
        result = webp_convert.convert_to_webp(png_path, skip_existing=True)
        self.assertIsNone(result)

    def test_force_reconvert(self):
        png_path = self._create_png()
        webp_convert.convert_to_webp(png_path, skip_existing=False)
        result = webp_convert.convert_to_webp(png_path, skip_existing=False)
        self.assertIsNotNone(result)

    def test_rgba_to_rgb_conversion(self):
        png_path = self._create_png(mode="RGBA")
        result = webp_convert.convert_to_webp(png_path)
        self.assertIsNotNone(result)
        # Verify it's a valid WebP
        img = Image.open(result)
        self.assertEqual(img.format, "WEBP")

    def test_quality_parameter(self):
        # Use a larger, more complex image so quality differences are measurable
        png_path = os.path.join(self.tmpdir, "complex.png")
        img = Image.new("RGB", (500, 500))
        # Add varied pixel data so compression has something to work with
        pixels = img.load()
        for x in range(500):
            for y in range(500):
                pixels[x, y] = ((x * 7) % 256, (y * 13) % 256, ((x + y) * 3) % 256)
        img.save(png_path, "PNG")
        low_q = os.path.join(self.tmpdir, "low.webp")
        high_q = os.path.join(self.tmpdir, "high.webp")
        webp_convert.convert_to_webp(png_path, output_path=low_q, quality=1)
        webp_convert.convert_to_webp(png_path, output_path=high_q, quality=100)
        # Lower quality should be smaller for complex images
        self.assertLess(os.path.getsize(low_q), os.path.getsize(high_q))

    def test_default_output_name(self):
        png_path = self._create_png("myimage.png")
        result = webp_convert.convert_to_webp(png_path)
        expected = os.path.join(self.tmpdir, "myimage.webp")
        self.assertEqual(str(result), expected)

    def test_nonexistent_input_returns_none(self):
        result = webp_convert.convert_to_webp("/nonexistent/path.png")
        self.assertIsNone(result)


@unittest.skipUnless(HAS_PILLOW, "Pillow not installed")
class TestBatchConvert(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _create_images(self, count=3):
        paths = []
        for i in range(count):
            path = os.path.join(self.tmpdir, f"image_{i}.png")
            img = Image.new("RGB", (50, 50), color=(i * 50, 0, 0))
            img.save(path, "PNG")
            paths.append(path)
        return paths

    def test_batch_converts_all(self):
        self._create_images(3)
        webp_convert.batch_convert(self.tmpdir, skip_existing=False)
        webp_files = list(f for f in os.listdir(self.tmpdir) if f.endswith(".webp"))
        self.assertEqual(len(webp_files), 3)

    def test_batch_skips_existing(self):
        self._create_images(2)
        webp_convert.batch_convert(self.tmpdir, skip_existing=False)
        # Second run should skip
        webp_convert.batch_convert(self.tmpdir, skip_existing=True)
        webp_files = list(f for f in os.listdir(self.tmpdir) if f.endswith(".webp"))
        self.assertEqual(len(webp_files), 2)

    def test_batch_recursive(self):
        subdir = os.path.join(self.tmpdir, "sub")
        os.makedirs(subdir)
        img = Image.new("RGB", (50, 50), color=(100, 100, 100))
        img.save(os.path.join(subdir, "nested.png"), "PNG")
        self._create_images(1)
        webp_convert.batch_convert(self.tmpdir, recursive=True, skip_existing=False)
        # Check both levels
        self.assertTrue(os.path.exists(os.path.join(subdir, "nested.webp")))

    def test_batch_empty_directory(self):
        empty_dir = os.path.join(self.tmpdir, "empty")
        os.makedirs(empty_dir)
        # Should not raise
        webp_convert.batch_convert(empty_dir)


if __name__ == "__main__":
    unittest.main()
