#!/usr/bin/env python3
"""Tests for batch_manager.py (peeperfrog-create-image version) - all pure utility, no API keys."""

import os
import sys
import json
import tempfile
import shutil
import unittest
from unittest.mock import patch

# Create temp queue file location
_tmpdir = tempfile.mkdtemp()
_queue_file = os.path.join(_tmpdir, "batch_queue.json")

# Create temp config for module import
_config_json_path = os.path.join(os.path.dirname(__file__), "..", "peeperfrog-create-image", "config.json")
_created_config = False
if not os.path.exists(_config_json_path):
    _created_config = True
    with open(_config_json_path, "w") as f:
        json.dump({
            "images_dir": _tmpdir,
            "batch_subdir": "batch",
            "queue_filename": "batch_queue.json",
            "batch_manager_script": "./src/batch_manager.py",
            "batch_generate_script": "./src/batch_generate.py",
            "webp_convert_script": "./scripts/webp-convert.py",
            "max_reference_images": 14,
            "api_delay_seconds": 3,
        }, f)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "peeperfrog-create-image", "src"))
import batch_manager

# Override the module's QUEUE_FILE to use our temp
batch_manager.QUEUE_FILE = _queue_file


class TestBatchManager(unittest.TestCase):
    def setUp(self):
        """Reset queue before each test."""
        if os.path.exists(_queue_file):
            os.remove(_queue_file)

    def test_ensure_queue_exists_creates_file(self):
        batch_manager.ensure_queue_exists()
        self.assertTrue(os.path.exists(_queue_file))
        with open(_queue_file) as f:
            data = json.load(f)
        self.assertEqual(data, {"prompts": []})

    def test_add_to_queue_basic(self):
        result = batch_manager.add_to_queue("A cat in a hat")
        self.assertTrue(result["success"])
        self.assertEqual(result["queue_size"], 1)
        self.assertIn("filename", result["added"])

    def test_add_to_queue_custom_filename(self):
        result = batch_manager.add_to_queue("A dog", filename="dog.png")
        self.assertEqual(result["added"]["filename"], "dog.png")

    def test_add_to_queue_with_params(self):
        result = batch_manager.add_to_queue(
            "A landscape",
            filename="landscape.png",
            aspect_ratio="16:9",
            image_size="xlarge",
            quality="pro",
            provider="gemini",
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["added"]["aspect_ratio"], "16:9")
        self.assertEqual(result["added"]["resolution"], "xlarge")

    def test_add_to_queue_with_reference_images(self):
        result = batch_manager.add_to_queue(
            "A portrait",
            reference_images=["/ref1.png", "/ref2.png"],
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["added"]["reference_images"], 2)

    def test_add_to_queue_with_gemini_opts(self):
        result = batch_manager.add_to_queue(
            "An infographic",
            provider="gemini",
            gemini_opts={"search_grounding": True, "thinking_level": "high"},
        )
        self.assertTrue(result["success"])
        # Verify stored in queue file
        with open(_queue_file) as f:
            queue = json.load(f)
        self.assertIn("gemini_opts", queue["prompts"][0])

    def test_add_to_queue_with_model(self):
        result = batch_manager.add_to_queue("A photo", provider="together", model="dreamshaper")
        self.assertTrue(result["success"])
        with open(_queue_file) as f:
            queue = json.load(f)
        self.assertEqual(queue["prompts"][0]["model"], "dreamshaper")

    def test_add_multiple_items(self):
        batch_manager.add_to_queue("First")
        batch_manager.add_to_queue("Second")
        result = batch_manager.add_to_queue("Third")
        self.assertEqual(result["queue_size"], 3)

    def test_view_queue_empty(self):
        result = batch_manager.view_queue()
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["prompts"], [])

    def test_view_queue_with_items(self):
        batch_manager.add_to_queue("Item 1")
        batch_manager.add_to_queue("Item 2")
        result = batch_manager.view_queue()
        self.assertEqual(result["total"], 2)
        self.assertEqual(len(result["prompts"]), 2)

    def test_remove_by_index(self):
        batch_manager.add_to_queue("First", filename="first.png")
        batch_manager.add_to_queue("Second", filename="second.png")
        result = batch_manager.remove_from_queue("0")
        self.assertTrue(result["success"])
        self.assertEqual(result["removed_count"], 1)
        self.assertIn("first.png", result["removed_files"])
        self.assertEqual(result["queue_size"], 1)

    def test_remove_by_filename(self):
        batch_manager.add_to_queue("First", filename="first.png")
        batch_manager.add_to_queue("Second", filename="second.png")
        result = batch_manager.remove_from_queue("second.png")
        self.assertTrue(result["success"])
        self.assertIn("second.png", result["removed_files"])

    def test_remove_invalid_index(self):
        batch_manager.add_to_queue("Only item")
        result = batch_manager.remove_from_queue("5")
        self.assertFalse(result["success"])
        self.assertIn("out of range", result["error"])

    def test_remove_nonexistent_filename(self):
        batch_manager.add_to_queue("Item")
        result = batch_manager.remove_from_queue("nonexistent.png")
        self.assertFalse(result["success"])
        self.assertIn("not found", result["error"])

    def test_remove_negative_index(self):
        batch_manager.add_to_queue("Item")
        result = batch_manager.remove_from_queue("-1")
        self.assertFalse(result["success"])

    def test_clear_queue(self):
        batch_manager.add_to_queue("First")
        batch_manager.add_to_queue("Second")
        result = batch_manager.clear_queue()
        self.assertTrue(result["success"])
        view = batch_manager.view_queue()
        self.assertEqual(view["total"], 0)

    def test_auto_generated_filename_has_timestamp(self):
        result = batch_manager.add_to_queue("Test prompt")
        filename = result["added"]["filename"]
        self.assertTrue(filename.startswith("batch_image_"))
        self.assertTrue(filename.endswith(".png"))

    def test_queue_preserves_all_fields(self):
        batch_manager.add_to_queue(
            "Full test",
            filename="full.png",
            aspect_ratio="4:3",
            image_size="medium",
            description="A description",
            quality="fast",
            provider="openai",
        )
        with open(_queue_file) as f:
            queue = json.load(f)
        entry = queue["prompts"][0]
        self.assertEqual(entry["prompt"], "Full test")
        self.assertEqual(entry["filename"], "full.png")
        self.assertEqual(entry["aspect_ratio"], "4:3")
        self.assertEqual(entry["image_size"], "medium")
        self.assertEqual(entry["quality"], "fast")
        self.assertEqual(entry["provider"], "openai")
        self.assertIn("added_at", entry)


def tearDownModule():
    if _created_config and os.path.exists(_config_json_path):
        os.remove(_config_json_path)
    shutil.rmtree(_tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
