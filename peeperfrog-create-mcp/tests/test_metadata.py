#!/usr/bin/env python3
"""
Tests for metadata module.
"""
import unittest
import os
import json
import tempfile
import shutil
from datetime import datetime
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from metadata import (
    create_metadata_dict,
    write_metadata_file,
    read_metadata_file,
    copy_metadata_for_webp,
    update_wordpress_info
)


class TestMetadata(unittest.TestCase):
    def setUp(self):
        """Create temporary test directory."""
        self.test_dir = tempfile.mkdtemp()
        self.original_dir = os.path.join(self.test_dir, "original")
        self.webp_dir = os.path.join(self.test_dir, "webp")
        self.metadata_dir = os.path.join(self.test_dir, "metadata")
        self.json_dir = os.path.join(self.metadata_dir, "json")

        os.makedirs(self.original_dir)
        os.makedirs(self.webp_dir)
        os.makedirs(self.json_dir)

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_create_metadata_dict(self):
        """Test metadata dictionary creation."""
        metadata = create_metadata_dict(
            prompt="A beautiful sunset",
            title="Beautiful Sunset",
            description="A vibrant sunset over mountains",
            alternative_text="Orange and pink sunset",
            caption="Sunset in the mountains",
            provider="gemini",
            model="gemini-2.5-flash-image",
            aspect_ratio="16:9",
            image_size="large",
            quality=100,
            cost=0.039
        )

        self.assertEqual(metadata["prompt"], "A beautiful sunset")
        self.assertEqual(metadata["title"], "Beautiful Sunset")
        self.assertEqual(metadata["provider"], "gemini")
        self.assertEqual(metadata["quality"], 100)
        self.assertEqual(metadata["cost"], 0.039)
        self.assertIn("date_time_created", metadata)

        # Verify date format
        try:
            datetime.fromisoformat(metadata["date_time_created"])
        except ValueError:
            self.fail("date_time_created is not valid ISO format")

    def test_write_and_read_metadata(self):
        """Test writing and reading metadata files."""
        image_path = os.path.join(self.original_dir, "test_image.png")

        # Create fake image file
        with open(image_path, 'w') as f:
            f.write("fake image data")

        metadata = create_metadata_dict(
            prompt="Test prompt",
            title="Test Image",
            description="Test description",
            alternative_text="Test alt",
            caption="Test caption",
            provider="gemini",
            model="test-model",
            aspect_ratio="1:1",
            image_size="large",
            quality=100,
            cost=0.01
        )

        # Write metadata
        json_path = write_metadata_file(image_path, metadata)
        self.assertTrue(os.path.exists(json_path))
        self.assertTrue(json_path.endswith("test_image.png.json"))

        # Read metadata
        read_meta = read_metadata_file(image_path)
        self.assertIsNotNone(read_meta)
        self.assertEqual(read_meta["title"], "Test Image")
        self.assertEqual(read_meta["prompt"], "Test prompt")
        self.assertEqual(read_meta["cost"], 0.01)

    def test_copy_metadata_for_webp(self):
        """Test metadata copying for WebP conversion."""
        original_path = os.path.join(self.original_dir, "original.png")
        webp_path = os.path.join(self.webp_dir, "original.webp")

        # Create fake files
        with open(original_path, 'w') as f:
            f.write("fake PNG")
        with open(webp_path, 'w') as f:
            f.write("fake WebP")

        # Create original metadata
        original_metadata = create_metadata_dict(
            prompt="Test",
            title="Original",
            description="Original description",
            alternative_text="Alt text",
            caption="Caption",
            provider="gemini",
            model="test",
            aspect_ratio="16:9",
            image_size="large",
            quality=100,
            cost=0.039
        )
        write_metadata_file(original_path, original_metadata)

        # Copy to WebP with quality 85
        webp_json_path = copy_metadata_for_webp(original_path, webp_path, 85)
        self.assertIsNotNone(webp_json_path)
        self.assertTrue(os.path.exists(webp_json_path))

        # Read WebP metadata
        webp_meta = read_metadata_file(webp_path)
        self.assertIsNotNone(webp_meta)
        self.assertEqual(webp_meta["title"], "Original")
        self.assertEqual(webp_meta["quality"], 85)  # Updated quality
        self.assertNotEqual(webp_meta["date_time_created"], original_metadata["date_time_created"])

    def test_update_wordpress_info(self):
        """Test adding WordPress info to metadata."""
        image_path = os.path.join(self.original_dir, "wp_test.png")

        # Create fake image
        with open(image_path, 'w') as f:
            f.write("fake image")

        # Create initial metadata
        metadata = create_metadata_dict(
            prompt="WP test",
            title="WP Image",
            description="WordPress test",
            alternative_text="Alt",
            caption="Caption",
            provider="gemini",
            model="test",
            aspect_ratio="1:1",
            image_size="large",
            quality=100,
            cost=0.02
        )
        write_metadata_file(image_path, metadata)

        # Update with WordPress info
        result = update_wordpress_info(image_path, 123, "https://example.com/image.png")
        self.assertTrue(result)

        # Read updated metadata
        updated_meta = read_metadata_file(image_path)
        self.assertEqual(updated_meta["wordpress_media_id"], 123)
        self.assertEqual(updated_meta["wordpress_url"], "https://example.com/image.png")
        self.assertIn("wordpress_uploaded_at", updated_meta)

    def test_read_nonexistent_metadata(self):
        """Test reading metadata for non-existent file."""
        fake_path = os.path.join(self.original_dir, "nonexistent.png")
        metadata = read_metadata_file(fake_path)
        self.assertIsNone(metadata)

    def test_metadata_json_structure(self):
        """Test that metadata JSON has all required fields."""
        image_path = os.path.join(self.original_dir, "structure_test.png")
        with open(image_path, 'w') as f:
            f.write("fake")

        metadata = create_metadata_dict(
            prompt="Test",
            title="Test",
            description="Test",
            alternative_text="Test",
            caption="Test",
            provider="gemini",
            model="test",
            aspect_ratio="16:9",
            image_size="large",
            quality=100,
            cost=0.039
        )
        json_path = write_metadata_file(image_path, metadata)

        # Read raw JSON
        with open(json_path, 'r') as f:
            raw_json = json.load(f)

        # Check required fields
        required_fields = [
            "date_time_created",
            "prompt",
            "title",
            "description",
            "alternative_text",
            "caption",
            "provider",
            "model",
            "aspect_ratio",
            "image_size",
            "quality",
            "cost"
        ]

        for field in required_fields:
            self.assertIn(field, raw_json, f"Missing required field: {field}")


if __name__ == '__main__':
    unittest.main()
