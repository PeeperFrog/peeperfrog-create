#!/usr/bin/env python3
"""Tests for peeperfrog-create-mcp utility functions that don't require API keys."""

import os
import sys
import json
import base64
import tempfile
import shutil
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add src to path so we can import functions without triggering module-level config load
# We need to mock load_config and load_pricing before importing
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _mock_config():
    tmpdir = tempfile.mkdtemp()
    return {
        "images_dir": tmpdir,
        "batch_subdir": "batch",
        "queue_filename": "batch_queue.json",
        "batch_manager_script": "./src/batch_manager.py",
        "batch_generate_script": "./src/batch_generate.py",
        "webp_convert_script": "./scripts/webp-convert.py",
        "max_reference_images": 14,
        "api_delay_seconds": 3,
        "batch_dir": os.path.join(tmpdir, "batch"),
        "queue_file": os.path.join(tmpdir, "batch_queue.json"),
    }


def _mock_pricing():
    pricing_path = os.path.join(os.path.dirname(__file__), "..", "peeperfrog-create-mcp", "pricing.json")
    with open(pricing_path, "r") as f:
        return json.load(f)


# Patch config loading before import
_cfg = _mock_config()
_pricing = _mock_pricing()

# Patch the module-level config and pricing loading
sys.modules.pop("image_server", None)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "peeperfrog-create-mcp", "src"))

import importlib
with patch.dict(os.environ, {}, clear=False):
    # We need to patch open for config.json at module level
    original_open = open
    _config_path = os.path.join(os.path.dirname(__file__), "..", "peeperfrog-create-mcp", "src", "..", "config.json")

    # Create a temporary config.json for the module to load
    config_json_path = os.path.join(os.path.dirname(__file__), "..", "peeperfrog-create-mcp", "config.json")
    _created_config = False
    if not os.path.exists(config_json_path):
        _created_config = True
        with open(config_json_path, "w") as f:
            json.dump({
                "images_dir": _cfg["images_dir"],
                "batch_subdir": "batch",
                "queue_filename": "batch_queue.json",
                "batch_manager_script": "./src/batch_manager.py",
                "batch_generate_script": "./src/batch_generate.py",
                "webp_convert_script": "./scripts/webp-convert.py",
                "max_reference_images": 14,
                "api_delay_seconds": 3,
            }, f)

    import image_server

    # Restore PRICING from real pricing.json
    image_server.PRICING = _pricing


class TestGetMimeType(unittest.TestCase):
    def test_png(self):
        self.assertEqual(image_server.get_mime_type("image.png"), "image/png")

    def test_jpg(self):
        self.assertEqual(image_server.get_mime_type("photo.jpg"), "image/jpeg")

    def test_jpeg(self):
        self.assertEqual(image_server.get_mime_type("photo.jpeg"), "image/jpeg")

    def test_webp(self):
        self.assertEqual(image_server.get_mime_type("image.webp"), "image/webp")

    def test_gif(self):
        self.assertEqual(image_server.get_mime_type("animation.gif"), "image/gif")

    def test_unknown_defaults_to_png(self):
        self.assertEqual(image_server.get_mime_type("file.bmp"), "image/png")

    def test_uppercase_extension(self):
        self.assertEqual(image_server.get_mime_type("IMAGE.PNG"), "image/png")

    def test_path_with_directories(self):
        self.assertEqual(image_server.get_mime_type("/some/path/to/image.jpg"), "image/jpeg")

    def test_no_extension(self):
        self.assertEqual(image_server.get_mime_type("noextension"), "image/png")


class TestNormalizeReferenceImages(unittest.TestCase):
    def test_none_inputs(self):
        result = image_server._normalize_reference_images(None, None)
        self.assertEqual(result, [])

    def test_single_reference_image(self):
        result = image_server._normalize_reference_images(None, "/path/to/image.png")
        self.assertEqual(result, ["/path/to/image.png"])

    def test_list_of_reference_images(self):
        paths = ["/a.png", "/b.png", "/c.png"]
        result = image_server._normalize_reference_images(paths, None)
        self.assertEqual(result, paths)

    def test_string_treated_as_single_item_list(self):
        result = image_server._normalize_reference_images("/single.png", None)
        self.assertEqual(result, ["/single.png"])

    def test_list_takes_priority_over_single(self):
        result = image_server._normalize_reference_images(["/list.png"], "/single.png")
        self.assertEqual(result, ["/list.png"])

    def test_too_many_raises(self):
        paths = [f"/img{i}.png" for i in range(20)]
        with self.assertRaises(Exception) as ctx:
            image_server._normalize_reference_images(paths, None)
        self.assertIn("Too many reference images", str(ctx.exception))

    def test_exactly_max_allowed(self):
        max_ref = image_server.MAX_REF_IMAGES
        paths = [f"/img{i}.png" for i in range(max_ref)]
        result = image_server._normalize_reference_images(paths, None)
        self.assertEqual(len(result), max_ref)

    def test_empty_list(self):
        result = image_server._normalize_reference_images([], None)
        self.assertEqual(result, [])


class TestEncodeReferenceImages(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_encode_single_image(self):
        img_path = os.path.join(self.tmpdir, "test.png")
        content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        with open(img_path, "wb") as f:
            f.write(content)

        result = image_server._encode_reference_images([img_path])
        self.assertEqual(len(result), 1)
        self.assertIn("inlineData", result[0])
        self.assertEqual(result[0]["inlineData"]["mimeType"], "image/png")
        decoded = base64.b64decode(result[0]["inlineData"]["data"])
        self.assertEqual(decoded, content)

    def test_encode_jpeg(self):
        img_path = os.path.join(self.tmpdir, "test.jpg")
        with open(img_path, "wb") as f:
            f.write(b"\xff\xd8\xff" + b"\x00" * 50)

        result = image_server._encode_reference_images([img_path])
        self.assertEqual(result[0]["inlineData"]["mimeType"], "image/jpeg")

    def test_missing_file_raises(self):
        with self.assertRaises(Exception) as ctx:
            image_server._encode_reference_images(["/nonexistent/path.png"])
        self.assertIn("not found", str(ctx.exception))

    def test_empty_list(self):
        result = image_server._encode_reference_images([])
        self.assertEqual(result, [])

    def test_tilde_expansion(self):
        # Create file in tmpdir, use path with ~
        img_path = os.path.join(self.tmpdir, "tilde_test.png")
        with open(img_path, "wb") as f:
            f.write(b"\x89PNG" + b"\x00" * 20)

        # Patch expanduser to map ~ to tmpdir
        with patch("image_server.os.path.expanduser", side_effect=lambda p: p.replace("~", self.tmpdir)):
            result = image_server._encode_reference_images(["~/tilde_test.png"])
            self.assertEqual(len(result), 1)


class TestEstimateCost(unittest.TestCase):
    """Test cost estimation for all providers without API calls."""

    def test_gemini_pro_2k(self):
        cost = image_server.estimate_cost("gemini", "pro", "large", "1:1")
        self.assertIsNotNone(cost)
        self.assertAlmostEqual(cost, 0.1351, places=3)

    def test_gemini_pro_4k(self):
        cost = image_server.estimate_cost("gemini", "pro", "xlarge", "1:1")
        self.assertIsNotNone(cost)
        self.assertAlmostEqual(cost, 0.2411, places=3)

    def test_gemini_fast(self):
        cost = image_server.estimate_cost("gemini", "fast", "small", "1:1")
        self.assertIsNotNone(cost)
        self.assertAlmostEqual(cost, 0.03903, places=4)

    def test_gemini_with_references(self):
        base = image_server.estimate_cost("gemini", "pro", "large", "1:1", num_reference_images=0)
        with_refs = image_server.estimate_cost("gemini", "pro", "large", "1:1", num_reference_images=3)
        self.assertGreater(with_refs, base)

    def test_gemini_with_grounding(self):
        base = image_server.estimate_cost("gemini", "pro", "large", "1:1")
        with_grounding = image_server.estimate_cost("gemini", "pro", "large", "1:1", search_grounding=True)
        self.assertGreater(with_grounding, base)

    def test_gemini_with_thinking(self):
        base = image_server.estimate_cost("gemini", "pro", "large", "1:1")
        with_thinking = image_server.estimate_cost("gemini", "pro", "large", "1:1", thinking_level="high")
        self.assertGreater(with_thinking, base)

    def test_gemini_thinking_minimal_no_extra_cost(self):
        base = image_server.estimate_cost("gemini", "pro", "large", "1:1")
        with_minimal = image_server.estimate_cost("gemini", "pro", "large", "1:1", thinking_level="minimal")
        self.assertEqual(base, with_minimal)

    def test_gemini_thinking_ignored_for_fast(self):
        base = image_server.estimate_cost("gemini", "fast", "small", "1:1")
        with_thinking = image_server.estimate_cost("gemini", "fast", "small", "1:1", thinking_level="high")
        self.assertEqual(base, with_thinking)

    def test_openai_pro_square(self):
        cost = image_server.estimate_cost("openai", "pro", "large", "1:1")
        self.assertIsNotNone(cost)
        self.assertGreater(cost, 0.1)

    def test_openai_fast_square(self):
        cost = image_server.estimate_cost("openai", "fast", "large", "1:1")
        self.assertIsNotNone(cost)
        self.assertLess(cost, 0.05)

    def test_openai_landscape(self):
        cost = image_server.estimate_cost("openai", "pro", "large", "16:9")
        self.assertIsNotNone(cost)
        self.assertGreater(cost, 0.2)

    def test_together_pro_1mp(self):
        cost = image_server.estimate_cost("together", "pro", "large", "1:1")
        self.assertIsNotNone(cost)
        self.assertAlmostEqual(cost, 0.04 * 1024 * 1024 / 1_000_000, places=4)

    def test_together_fast_1mp(self):
        cost = image_server.estimate_cost("together", "fast", "large", "1:1")
        self.assertIsNotNone(cost)
        self.assertAlmostEqual(cost, 0.0027 * 1024 * 1024 / 1_000_000, places=5)

    def test_together_model_alias(self):
        cost = image_server.estimate_cost("together", "pro", "large", "1:1", model_alias="dreamshaper")
        self.assertIsNotNone(cost)
        # dreamshaper is $0.0006/MP
        expected = 0.0006 * (1024 * 1024) / 1_000_000
        self.assertAlmostEqual(cost, expected, places=5)

    def test_together_different_sizes(self):
        small = image_server.estimate_cost("together", "pro", "small", "1:1")
        large = image_server.estimate_cost("together", "pro", "large", "1:1")
        xlarge = image_server.estimate_cost("together", "pro", "xlarge", "1:1")
        self.assertLess(small, large)
        self.assertLess(large, xlarge)

    def test_together_different_aspect_ratios(self):
        square = image_server.estimate_cost("together", "pro", "large", "1:1")
        landscape = image_server.estimate_cost("together", "pro", "large", "16:9")
        # 1024x1024 vs 1024x576 -- square is more pixels
        self.assertGreater(square, landscape)

    def test_unknown_provider(self):
        cost = image_server.estimate_cost("unknown", "pro", "large", "1:1")
        self.assertIsNone(cost)

    def test_no_pricing_returns_none(self):
        original = image_server.PRICING
        image_server.PRICING = None
        cost = image_server.estimate_cost("gemini", "pro", "large", "1:1")
        self.assertIsNone(cost)
        image_server.PRICING = original


class TestAutoSelectModel(unittest.TestCase):
    """Test auto model selection logic."""

    def _set_all_keys(self):
        """Set all provider API keys in environment."""
        return patch.dict(os.environ, {
            "GEMINI_API_KEY": "test-key",
            "OPENAI_API_KEY": "test-key",
            "TOGETHER_API_KEY": "test-key",
        })

    def test_cheapest_tier(self):
        with self._set_all_keys():
            provider, quality, model_alias, name = image_server._auto_select_model("cheapest")
            self.assertIsNotNone(provider)
            self.assertIn(provider, ["gemini", "openai", "together"])

    def test_best_tier_returns_high_quality(self):
        with self._set_all_keys():
            provider, quality, model_alias, name = image_server._auto_select_model("best", "general")
            # Should pick a model with general_quality >= 3
            model_info = image_server.AUTO_MODE_MODELS[name]
            self.assertGreaterEqual(model_info["general_quality"], 3)

    def test_unknown_auto_mode_raises(self):
        with self._set_all_keys():
            with self.assertRaises(Exception) as ctx:
                image_server._auto_select_model("nonexistent")
            self.assertIn("Unknown auto_mode", str(ctx.exception))

    def test_text_style_prefers_text_models(self):
        with self._set_all_keys():
            _, _, _, name = image_server._auto_select_model("best", "text")
            model_info = image_server.AUTO_MODE_MODELS[name]
            self.assertGreaterEqual(model_info["text_quality"], 2)

    def test_photo_style(self):
        with self._set_all_keys():
            _, _, _, name = image_server._auto_select_model("best", "photo")
            model_info = image_server.AUTO_MODE_MODELS[name]
            self.assertGreaterEqual(model_info["photo_quality"], 3)

    def test_needs_references_filters(self):
        with self._set_all_keys():
            provider, _, _, name = image_server._auto_select_model("best", needs_references=True)
            model_info = image_server.AUTO_MODE_MODELS[name]
            self.assertTrue(model_info["supports_references"])

    def test_needs_grounding_filters(self):
        with self._set_all_keys():
            provider, _, _, name = image_server._auto_select_model("best", needs_grounding=True)
            model_info = image_server.AUTO_MODE_MODELS[name]
            self.assertTrue(model_info["supports_grounding"])

    def test_xlarge_size_filters(self):
        with self._set_all_keys():
            provider, _, _, name = image_server._auto_select_model("best", image_size="xlarge")
            model_info = image_server.AUTO_MODE_MODELS[name]
            self.assertEqual(model_info["max_size"], "xlarge")

    def test_no_api_keys_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            # Remove all keys
            for key in ["GEMINI_API_KEY", "OPENAI_API_KEY", "TOGETHER_API_KEY"]:
                os.environ.pop(key, None)
            with self.assertRaises(Exception) as ctx:
                image_server._auto_select_model("cheapest")
            self.assertIn("No model matches", str(ctx.exception))

    def test_only_gemini_key(self):
        env = {"GEMINI_API_KEY": "test-key"}
        with patch.dict(os.environ, env, clear=True):
            provider, _, _, _ = image_server._auto_select_model("best")
            self.assertEqual(provider, "gemini")


class TestEstimateImageCost(unittest.TestCase):
    """Test the high-level estimate_image_cost function."""

    def test_basic_gemini_estimate(self):
        result = image_server.estimate_image_cost("gemini", "pro", "1:1", "large")
        self.assertTrue(result["success"])
        self.assertIn("estimated_cost_per_image_usd", result)
        self.assertGreater(result["estimated_cost_per_image_usd"], 0)

    def test_count_multiplier(self):
        result = image_server.estimate_image_cost("gemini", "pro", "1:1", "large", count=5)
        self.assertTrue(result["success"])
        self.assertAlmostEqual(
            result["estimated_total_cost_usd"],
            result["estimated_cost_per_image_usd"] * 5,
            places=5,
        )

    def test_together_model_alias(self):
        result = image_server.estimate_image_cost("together", "pro", "1:1", "large", model="dreamshaper")
        self.assertTrue(result["success"])
        self.assertEqual(result["provider"], "together")
        self.assertIn("model_id", result)

    def test_auto_mode_estimate(self):
        with patch.dict(os.environ, {"TOGETHER_API_KEY": "test"}):
            result = image_server.estimate_image_cost(auto_mode="cheapest")
            self.assertTrue(result["success"])
            self.assertIn("auto_selected", result)

    def test_invalid_provider_falls_back_to_default(self):
        result = image_server.estimate_image_cost("invalid", "pro", "1:1", "large")
        # Should fall back to default provider (gemini)
        self.assertTrue(result["success"])
        self.assertEqual(result["provider"], "gemini")


class TestSendMessage(unittest.TestCase):
    """Test MCP protocol message sending."""

    def test_send_message_outputs_json(self):
        msg = {"jsonrpc": "2.0", "id": 1, "result": {"ok": True}}
        with patch("sys.stdout") as mock_stdout:
            mock_stdout.write = MagicMock()
            mock_stdout.flush = MagicMock()
            image_server.send_message(msg)
            written = mock_stdout.write.call_args[0][0]
            parsed = json.loads(written.strip())
            self.assertEqual(parsed, msg)


class TestReadMessage(unittest.TestCase):
    """Test MCP protocol message reading."""

    def test_read_valid_message(self):
        msg = {"jsonrpc": "2.0", "method": "initialize", "id": 1}
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.readline = MagicMock(return_value=json.dumps(msg) + "\n")
            result = image_server.read_message()
            self.assertEqual(result, msg)

    def test_read_empty_returns_none(self):
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.readline = MagicMock(return_value="")
            result = image_server.read_message()
            self.assertIsNone(result)


class TestProviderConstants(unittest.TestCase):
    """Test that provider configurations are consistent."""

    def test_all_providers_have_required_keys(self):
        for name, p in image_server.PROVIDERS.items():
            self.assertIn("models", p, f"{name} missing 'models'")
            self.assertIn("env_key", p, f"{name} missing 'env_key'")
            self.assertIn("supports_references", p, f"{name} missing 'supports_references'")
            self.assertIn("pro", p["models"], f"{name} missing 'pro' model")
            self.assertIn("fast", p["models"], f"{name} missing 'fast' model")

    def test_together_models_all_have_required_keys(self):
        for alias, info in image_server.TOGETHER_MODELS.items():
            self.assertIn("id", info, f"{alias} missing 'id'")
            self.assertIn("cost_per_mp", info, f"{alias} missing 'cost_per_mp'")
            self.assertIn("steps", info, f"{alias} missing 'steps'")

    def test_auto_mode_models_have_required_keys(self):
        required = ["provider", "quality", "model_alias", "cost_per_image_1mp", "max_size",
                     "supports_references", "supports_grounding", "text_quality",
                     "photo_quality", "illustration_quality", "general_quality"]
        for name, m in image_server.AUTO_MODE_MODELS.items():
            for key in required:
                self.assertIn(key, m, f"AUTO_MODE_MODELS[{name}] missing '{key}'")

    def test_auto_mode_tiers_ordered(self):
        tiers = list(image_server.AUTO_MODE_TIERS.values())
        for i in range(len(tiers) - 1):
            self.assertLessEqual(tiers[i], tiers[i + 1])

    def test_size_order_consistent(self):
        so = image_server.SIZE_ORDER
        self.assertLess(so["small"], so["medium"])
        self.assertLess(so["medium"], so["large"])
        self.assertLess(so["large"], so["xlarge"])


class TestHandleInitialize(unittest.TestCase):
    def test_initialize_response(self):
        with patch("sys.stdout") as mock_stdout:
            mock_stdout.write = MagicMock()
            mock_stdout.flush = MagicMock()
            image_server.handle_initialize(1)
            written = mock_stdout.write.call_args[0][0]
            parsed = json.loads(written.strip())
            self.assertEqual(parsed["id"], 1)
            self.assertIn("result", parsed)
            self.assertEqual(parsed["result"]["serverInfo"]["name"], "peeperfrog-create")


class TestHandleToolsList(unittest.TestCase):
    def test_tools_list_response(self):
        with patch("sys.stdout") as mock_stdout:
            mock_stdout.write = MagicMock()
            mock_stdout.flush = MagicMock()
            image_server.handle_tools_list(2)
            written = mock_stdout.write.call_args[0][0]
            parsed = json.loads(written.strip())
            tools = parsed["result"]["tools"]
            tool_names = [t["name"] for t in tools]
            self.assertIn("generate_image", tool_names)
            self.assertIn("estimate_image_cost", tool_names)
            self.assertIn("convert_to_webp", tool_names)
            self.assertIn("add_to_batch", tool_names)
            self.assertIn("view_batch_queue", tool_names)


# Cleanup temp config if we created it
def tearDownModule():
    if _created_config and os.path.exists(config_json_path):
        os.remove(config_json_path)
    # Clean up temp images dir
    if os.path.exists(_cfg["images_dir"]):
        shutil.rmtree(_cfg["images_dir"], ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
