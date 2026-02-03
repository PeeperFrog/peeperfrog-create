#!/usr/bin/env python3
# Copyright (c) 2025 PeeperFrog
# Licensed under the Apache License, Version 2.0. See LICENSE file for details.
"""
PEEPERFROG CREATE IMAGE MCP SERVER - v0.1
Multi-provider image generation with quality tiers

Supported providers:
- gemini (Google): Pro (Gemini 3 Pro) and Fast (Gemini 2.5 Flash)
- openai: Pro and Fast (gpt-image-1)
- together: Pro (FLUX.1-pro) and Fast (FLUX.1-schnell)
"""

import sys
import json
import os
import base64
import requests
import subprocess
from datetime import datetime

# --- Configuration ---
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config.json")

def load_config():
    """Load configuration from config.json next to this script"""
    with open(CONFIG_PATH, 'r') as f:
        cfg = json.load(f)
    # Expand ~ and resolve relative paths against config directory
    config_dir = os.path.dirname(os.path.abspath(CONFIG_PATH))
    for key in ("images_dir", "batch_manager_script", "batch_generate_script", "webp_convert_script"):
        if key in cfg:
            cfg[key] = os.path.expanduser(cfg[key])
            if not os.path.isabs(cfg[key]):
                cfg[key] = os.path.join(config_dir, cfg[key])
    # Derived paths
    cfg["batch_dir"] = os.path.join(cfg["images_dir"], cfg.get("batch_subdir", "batch"))
    cfg["queue_file"] = os.path.join(cfg["images_dir"], cfg.get("queue_filename", "batch_queue.json"))
    return cfg

CFG = load_config()
MAX_REF_IMAGES = CFG.get("max_reference_images", 14)

# --- Pricing ---
PRICING_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pricing.json")

def load_pricing():
    """Load pricing data, return None if unavailable."""
    try:
        with open(PRICING_PATH, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

PRICING = load_pricing()

# --- Aspect Ratio Utilities ---

def parse_aspect_ratio(aspect_ratio):
    """Parse aspect ratio string (e.g., '16:9', '21:9', '2.35:1') into (width_ratio, height_ratio) floats."""
    if not aspect_ratio or ":" not in aspect_ratio:
        return (1.0, 1.0)
    try:
        parts = aspect_ratio.split(":")
        w = float(parts[0])
        h = float(parts[1])
        if w <= 0 or h <= 0:
            return (1.0, 1.0)
        return (w, h)
    except (ValueError, IndexError):
        return (1.0, 1.0)

def calculate_dimensions(aspect_ratio, image_size, max_dimension=None):
    """Calculate pixel dimensions for any aspect ratio and size tier.

    Args:
        aspect_ratio: String like '16:9', '21:9', '3:2', etc.
        image_size: 'small', 'medium', 'large', 'xlarge'
        max_dimension: Optional max for the largest side (overrides size tier)

    Returns:
        (width, height) tuple of integers
    """
    # Base dimensions for the largest side at each size tier
    size_bases = {
        "small": 512,
        "medium": 1024,
        "large": 1024,
        "xlarge": 2048
    }
    base = max_dimension or size_bases.get(image_size, 1024)

    w_ratio, h_ratio = parse_aspect_ratio(aspect_ratio)

    if w_ratio >= h_ratio:
        # Landscape or square: width is the base
        width = base
        height = int(round(base * h_ratio / w_ratio))
    else:
        # Portrait: height is the base
        height = base
        width = int(round(base * w_ratio / h_ratio))

    # Ensure dimensions are multiples of 8 (common requirement for image models)
    width = max(64, (width // 8) * 8)
    height = max(64, (height // 8) * 8)

    return (width, height)

def find_closest_openai_size(aspect_ratio):
    """Find the closest supported OpenAI size for a given aspect ratio.

    OpenAI gpt-image-1 supports: 1024x1024, 1536x1024, 1024x1536

    Returns:
        (size_string, actual_ratio) - e.g., ("1536x1024", "3:2")
    """
    w_ratio, h_ratio = parse_aspect_ratio(aspect_ratio)
    target_ratio = w_ratio / h_ratio

    # OpenAI supported sizes and their ratios
    sizes = [
        ("1024x1024", 1.0),      # 1:1
        ("1536x1024", 1.5),      # 3:2 (landscape)
        ("1024x1536", 0.667),    # 2:3 (portrait)
    ]

    # Find closest match
    best_size = "1024x1024"
    best_diff = float('inf')

    for size_str, ratio in sizes:
        diff = abs(target_ratio - ratio)
        if diff < best_diff:
            best_diff = diff
            best_size = size_str

    return best_size

def estimate_cost(provider, quality, image_size, aspect_ratio, num_reference_images=0, search_grounding=False, thinking_level=None, model_alias=None):
    """Estimate cost in USD for a single image generation. Returns None if pricing unavailable."""
    if not PRICING:
        return None

    providers = PRICING.get("providers", {})

    if provider == "gemini":
        size_map = {"small": "1K", "medium": "2K", "large": "2K", "xlarge": "4K"}
        gemini_size = size_map.get(image_size, "2K")
        if quality == "fast":
            gemini_size = "1K"
        model_key = PROVIDERS["gemini"]["models"][quality]
        model_pricing = providers.get("gemini", {}).get("models", {}).get(model_key, {})
        if not model_pricing:
            return None
        base = model_pricing.get("per_image_cost", {}).get(gemini_size, 0)
        text_cost = model_pricing.get("text_input_per_image_estimate", 0)
        ref_cost = num_reference_images * model_pricing.get("reference_image_cost_each", 0)
        grounding_cost = model_pricing.get("search_grounding_cost_per_query", 0) if search_grounding else 0
        thinking_cost = 0
        if thinking_level and quality == "pro":
            thinking_cost = model_pricing.get("thinking_token_overhead", {}).get(thinking_level.lower(), 0)
        return round(base + text_cost + ref_cost + grounding_cost + thinking_cost, 6)

    elif provider == "openai":
        openai_quality = "high" if quality == "pro" else "low"
        resolution = find_closest_openai_size(aspect_ratio)
        model_key = PROVIDERS["openai"]["models"][quality]
        model_pricing = providers.get("openai", {}).get("models", {}).get(model_key, {})
        if not model_pricing:
            return None
        per_image = model_pricing.get("per_image_cost", {}).get(openai_quality, {}).get(resolution, 0)
        text_cost = model_pricing.get("text_input_per_image_estimate", 0)
        return round(per_image + text_cost, 6)

    elif provider == "together":
        # Model alias overrides quality-based pricing
        if model_alias and model_alias in TOGETHER_MODELS:
            per_mp = TOGETHER_MODELS[model_alias]["cost_per_mp"]
        else:
            model_key = PROVIDERS["together"]["models"][quality]
            model_pricing = providers.get("together", {}).get("models", {}).get(model_key, {})
            if not model_pricing:
                return None
            per_mp = model_pricing.get("per_megapixel_cost", 0)
        # Calculate dimensions from any aspect ratio
        width, height = calculate_dimensions(aspect_ratio, image_size)
        return round((width * height / 1_000_000) * per_mp, 6)

    return None

# --- Provider configurations ---
PROVIDERS = {
    "gemini": {
        "models": {"pro": "gemini-3-pro-image-preview", "fast": "gemini-2.5-flash-image"},
        "env_key": "GEMINI_API_KEY",
        "supports_references": {"pro": True, "fast": False},
    },
    "openai": {
        "models": {"pro": "gpt-image-1", "fast": "gpt-image-1"},
        "env_key": "OPENAI_API_KEY",
        "supports_references": {"pro": False, "fast": False},
    },
    "together": {
        "models": {"pro": "black-forest-labs/FLUX.1-pro", "fast": "black-forest-labs/FLUX.1-schnell"},
        "env_key": "TOGETHER_API_KEY",
        "supports_references": {"pro": False, "fast": False},
    },
}

DEFAULT_PROVIDER = "gemini"

# --- Together AI model aliases ---
# When `model` param is set with provider="together", it overrides the quality-based selection.
# Steps=0 means omit from payload (let Together use defaults).
TOGETHER_MODELS = {
    "flux2-pro":              {"id": "black-forest-labs/FLUX.2-pro",               "cost_per_mp": 0.04,   "steps": 28},
    "flux2-dev":              {"id": "black-forest-labs/FLUX.2-dev",               "cost_per_mp": 0.025,  "steps": 28},
    "flux2-flex":             {"id": "black-forest-labs/FLUX.2-flex",              "cost_per_mp": 0.04,   "steps": 28},
    "flux1-kontext-pro":      {"id": "black-forest-labs/FLUX.1-Kontext-pro",       "cost_per_mp": 0.04,   "steps": 28},
    "flux1-kontext-max":      {"id": "black-forest-labs/FLUX.1-Kontext-max",       "cost_per_mp": 0.08,   "steps": 28},
    "flux1-pro":              {"id": "black-forest-labs/FLUX.1-pro",               "cost_per_mp": 0.04,   "steps": 28},
    "flux1-schnell":          {"id": "black-forest-labs/FLUX.1-schnell",           "cost_per_mp": 0.0027, "steps": 4},
    "imagen4":                {"id": "google/imagen-4.0-preview",                  "cost_per_mp": 0.04,   "steps": 0},
    "imagen4-fast":           {"id": "google/imagen-4.0-fast",                     "cost_per_mp": 0.02,   "steps": 0},
    "imagen4-ultra":          {"id": "google/imagen-4.0-ultra",                    "cost_per_mp": 0.06,   "steps": 0},
    "seedream3":              {"id": "bytedance/seedream-3.0",                     "cost_per_mp": 0.018,  "steps": 0},
    "seedream4":              {"id": "bytedance/seedream-4.0",                     "cost_per_mp": 0.03,   "steps": 0},
    "seededit":               {"id": "bytedance/seededit",                         "cost_per_mp": 0.03,   "steps": 0},
    "ideogram3":              {"id": "ideogram-ai/ideogram-3.0",                   "cost_per_mp": 0.06,   "steps": 0},
    "hidream-full":           {"id": "hidream-ai/HiDream-I1-Full",                 "cost_per_mp": 0.009,  "steps": 0},
    "hidream-dev":            {"id": "hidream-ai/HiDream-I1-Dev",                  "cost_per_mp": 0.0045, "steps": 0},
    "hidream-fast":           {"id": "hidream-ai/HiDream-I1-Fast",                 "cost_per_mp": 0.0032, "steps": 0},
    "juggernaut-pro":         {"id": "juggernaut/Juggernaut-Pro-Flux",             "cost_per_mp": 0.0049, "steps": 0},
    "juggernaut-lightning":   {"id": "juggernaut/Juggernaut-Lightning-Flux",       "cost_per_mp": 0.0017, "steps": 0},
    "dreamshaper":            {"id": "dreamshaper/Dreamshaper",                    "cost_per_mp": 0.0006, "steps": 0},
    "sdxl":                   {"id": "stabilityai/stable-diffusion-xl-base-1.0",   "cost_per_mp": 0.0019, "steps": 0},
    "sd3":                    {"id": "stabilityai/stable-diffusion-3-medium",      "cost_per_mp": 0.0019, "steps": 0},
    "qwen-image":             {"id": "qwen/qwen-image",                           "cost_per_mp": 0.0058, "steps": 0},
}

TOGETHER_MODEL_ALIASES = list(TOGETHER_MODELS.keys())

# --- Auto mode: capability matrix for model selection ---
# cost_per_image_1mp: normalized cost for a 1-megapixel image (for sorting)
# max_size: highest image_size this model supports (small < medium < large < xlarge)
# text/photo/illustration/general quality: 0=poor, 1=ok, 2=good, 3=excellent
AUTO_MODE_MODELS = {
    "dreamshaper":          {"provider": "together", "quality": "fast", "model_alias": "dreamshaper",          "cost_per_image_1mp": 0.0006, "max_size": "xlarge", "supports_references": False, "supports_grounding": False, "text_quality": 0, "photo_quality": 1, "illustration_quality": 2, "general_quality": 1},
    "juggernaut-lightning": {"provider": "together", "quality": "fast", "model_alias": "juggernaut-lightning", "cost_per_image_1mp": 0.0017, "max_size": "xlarge", "supports_references": False, "supports_grounding": False, "text_quality": 0, "photo_quality": 2, "illustration_quality": 1, "general_quality": 1},
    "sdxl":                 {"provider": "together", "quality": "fast", "model_alias": "sdxl",                 "cost_per_image_1mp": 0.0019, "max_size": "xlarge", "supports_references": False, "supports_grounding": False, "text_quality": 0, "photo_quality": 1, "illustration_quality": 2, "general_quality": 1},
    "sd3":                  {"provider": "together", "quality": "fast", "model_alias": "sd3",                  "cost_per_image_1mp": 0.0019, "max_size": "xlarge", "supports_references": False, "supports_grounding": False, "text_quality": 0, "photo_quality": 2, "illustration_quality": 2, "general_quality": 1},
    "flux1-schnell":        {"provider": "together", "quality": "fast", "model_alias": "flux1-schnell",        "cost_per_image_1mp": 0.0027, "max_size": "xlarge", "supports_references": False, "supports_grounding": False, "text_quality": 1, "photo_quality": 2, "illustration_quality": 2, "general_quality": 2},
    "hidream-fast":         {"provider": "together", "quality": "fast", "model_alias": "hidream-fast",         "cost_per_image_1mp": 0.0032, "max_size": "xlarge", "supports_references": False, "supports_grounding": False, "text_quality": 1, "photo_quality": 2, "illustration_quality": 2, "general_quality": 2},
    "hidream-dev":          {"provider": "together", "quality": "fast", "model_alias": "hidream-dev",          "cost_per_image_1mp": 0.0045, "max_size": "xlarge", "supports_references": False, "supports_grounding": False, "text_quality": 1, "photo_quality": 2, "illustration_quality": 2, "general_quality": 2},
    "juggernaut-pro":       {"provider": "together", "quality": "fast", "model_alias": "juggernaut-pro",       "cost_per_image_1mp": 0.0049, "max_size": "xlarge", "supports_references": False, "supports_grounding": False, "text_quality": 0, "photo_quality": 2, "illustration_quality": 1, "general_quality": 2},
    "qwen-image":           {"provider": "together", "quality": "fast", "model_alias": "qwen-image",           "cost_per_image_1mp": 0.0058, "max_size": "xlarge", "supports_references": False, "supports_grounding": False, "text_quality": 1, "photo_quality": 2, "illustration_quality": 2, "general_quality": 2},
    "hidream-full":         {"provider": "together", "quality": "fast", "model_alias": "hidream-full",         "cost_per_image_1mp": 0.009, "max_size": "xlarge", "supports_references": False, "supports_grounding": False, "text_quality": 1, "photo_quality": 2, "illustration_quality": 2, "general_quality": 2},
    "openai-fast":          {"provider": "openai",   "quality": "fast", "model_alias": None,                   "cost_per_image_1mp": 0.011, "max_size": "large",  "supports_references": False, "supports_grounding": False, "text_quality": 3, "photo_quality": 2, "illustration_quality": 2, "general_quality": 2},
    "seedream3":            {"provider": "together", "quality": "fast", "model_alias": "seedream3",            "cost_per_image_1mp": 0.018, "max_size": "xlarge", "supports_references": False, "supports_grounding": False, "text_quality": 1, "photo_quality": 3, "illustration_quality": 2, "general_quality": 2},
    "imagen4-fast":         {"provider": "together", "quality": "fast", "model_alias": "imagen4-fast",         "cost_per_image_1mp": 0.02,  "max_size": "xlarge", "supports_references": False, "supports_grounding": False, "text_quality": 2, "photo_quality": 3, "illustration_quality": 2, "general_quality": 2},
    "flux2-dev":            {"provider": "together", "quality": "fast", "model_alias": "flux2-dev",            "cost_per_image_1mp": 0.025, "max_size": "xlarge", "supports_references": False, "supports_grounding": False, "text_quality": 1, "photo_quality": 3, "illustration_quality": 3, "general_quality": 3},
    "seedream4":            {"provider": "together", "quality": "fast", "model_alias": "seedream4",            "cost_per_image_1mp": 0.03,  "max_size": "xlarge", "supports_references": False, "supports_grounding": False, "text_quality": 1, "photo_quality": 3, "illustration_quality": 2, "general_quality": 2},
    "gemini-fast":          {"provider": "gemini",   "quality": "fast", "model_alias": None,                   "cost_per_image_1mp": 0.039, "max_size": "small",  "supports_references": False, "supports_grounding": False, "text_quality": 1, "photo_quality": 2, "illustration_quality": 2, "general_quality": 2},
    "flux2-pro":            {"provider": "together", "quality": "pro",  "model_alias": "flux2-pro",            "cost_per_image_1mp": 0.04,  "max_size": "xlarge", "supports_references": False, "supports_grounding": False, "text_quality": 1, "photo_quality": 3, "illustration_quality": 3, "general_quality": 3},
    "flux1-kontext-pro":    {"provider": "together", "quality": "pro",  "model_alias": "flux1-kontext-pro",    "cost_per_image_1mp": 0.04,  "max_size": "xlarge", "supports_references": False, "supports_grounding": False, "text_quality": 1, "photo_quality": 3, "illustration_quality": 3, "general_quality": 3},
    "imagen4":              {"provider": "together", "quality": "pro",  "model_alias": "imagen4",              "cost_per_image_1mp": 0.04,  "max_size": "xlarge", "supports_references": False, "supports_grounding": False, "text_quality": 2, "photo_quality": 3, "illustration_quality": 2, "general_quality": 3},
    "ideogram3":            {"provider": "together", "quality": "pro",  "model_alias": "ideogram3",            "cost_per_image_1mp": 0.06,  "max_size": "xlarge", "supports_references": False, "supports_grounding": False, "text_quality": 3, "photo_quality": 2, "illustration_quality": 2, "general_quality": 2},
    "imagen4-ultra":        {"provider": "together", "quality": "pro",  "model_alias": "imagen4-ultra",        "cost_per_image_1mp": 0.06,  "max_size": "xlarge", "supports_references": False, "supports_grounding": False, "text_quality": 2, "photo_quality": 3, "illustration_quality": 3, "general_quality": 3},
    "flux1-kontext-max":    {"provider": "together", "quality": "pro",  "model_alias": "flux1-kontext-max",    "cost_per_image_1mp": 0.08,  "max_size": "xlarge", "supports_references": False, "supports_grounding": False, "text_quality": 1, "photo_quality": 3, "illustration_quality": 3, "general_quality": 3},
    "gemini-pro":           {"provider": "gemini",   "quality": "pro",  "model_alias": None,                   "cost_per_image_1mp": 0.134, "max_size": "xlarge", "supports_references": True,  "supports_grounding": True,  "text_quality": 2, "photo_quality": 3, "illustration_quality": 3, "general_quality": 3},
    "openai-pro":           {"provider": "openai",   "quality": "pro",  "model_alias": None,                   "cost_per_image_1mp": 0.167, "max_size": "large",  "supports_references": False, "supports_grounding": False, "text_quality": 3, "photo_quality": 3, "illustration_quality": 3, "general_quality": 3},
}

AUTO_MODE_TIERS = {
    "cheapest": 0.003,
    "budget":   0.01,
    "balanced": 0.04,
    "quality":  0.08,
    "best":     float("inf"),
}

SIZE_ORDER = {"small": 0, "medium": 1, "large": 2, "xlarge": 3}

def _auto_select_model(auto_mode, style_hint="general", image_size="large", needs_references=False, needs_grounding=False):
    """Select best model based on cost tier, style, and capability constraints.
    Returns (provider, quality, model_alias) or raises if no model matches."""
    max_cost = AUTO_MODE_TIERS.get(auto_mode)
    if max_cost is None:
        raise Exception(f"Unknown auto_mode: {auto_mode}. Options: {', '.join(AUTO_MODE_TIERS.keys())}")

    required_size = SIZE_ORDER.get(image_size, 2)
    style_key = f"{style_hint}_quality" if style_hint in ("text", "photo", "illustration") else "general_quality"

    candidates = []
    for name, m in AUTO_MODE_MODELS.items():
        if SIZE_ORDER.get(m["max_size"], 0) < required_size:
            continue
        if needs_references and not m["supports_references"]:
            continue
        if needs_grounding and not m["supports_grounding"]:
            continue
        if m["cost_per_image_1mp"] > max_cost:
            continue
        # Skip models whose API key is not configured
        env_key = PROVIDERS[m["provider"]]["env_key"]
        if not os.environ.get(env_key):
            continue
        candidates.append((name, m))

    if not candidates:
        raise Exception(f"No model matches auto_mode='{auto_mode}' with the given constraints (size={image_size}, references={needs_references}, grounding={needs_grounding})")

    # Sort: highest style quality first, then lowest cost
    candidates.sort(key=lambda x: (-x[1][style_key], x[1]["cost_per_image_1mp"]))
    chosen_name, chosen = candidates[0]
    return chosen["provider"], chosen["quality"], chosen["model_alias"], chosen_name

# --- MCP protocol ---
def send_message(message):
    json_str = json.dumps(message)
    sys.stdout.write(json_str + '\n')
    sys.stdout.flush()

def read_message():
    line = sys.stdin.readline()
    if not line:
        return None
    return json.loads(line)

# --- Helpers ---
def get_mime_type(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    return mime_map.get(ext, "image/png")

def _normalize_reference_images(reference_images=None, reference_image=None):
    """Accept either a list or a single path, return validated list (max MAX_REF_IMAGES)."""
    paths = []
    if reference_images:
        if isinstance(reference_images, str):
            paths = [reference_images]
        else:
            paths = list(reference_images)
    elif reference_image:
        paths = [reference_image]
    if len(paths) > MAX_REF_IMAGES:
        raise Exception(f"Too many reference images ({len(paths)}). Maximum is {MAX_REF_IMAGES}.")
    return paths

def _encode_reference_images(paths):
    """Return list of inlineData parts for the given image paths."""
    parts = []
    for p in paths:
        ref_path = os.path.expanduser(p)
        if not os.path.exists(ref_path):
            raise Exception(f"Reference image not found: {ref_path}")
        with open(ref_path, 'rb') as f:
            img_b64 = base64.b64encode(f.read()).decode('utf-8')
        parts.append({
            "inlineData": {
                "mimeType": get_mime_type(ref_path),
                "data": img_b64
            }
        })
    return parts

def _get_api_key(provider):
    """Get API key for the given provider, raise if not set."""
    env_key = PROVIDERS[provider]["env_key"]
    api_key = os.environ.get(env_key)
    if not api_key:
        raise Exception(f"{env_key} not set")
    return api_key

# --- Provider-specific generation ---

def _generate_gemini(prompt, aspect_ratio, image_size, quality, ref_paths, search_grounding=False, thinking_level=None, media_resolution=None):
    """Generate image using Google Gemini API."""
    api_key = _get_api_key("gemini")
    model = PROVIDERS["gemini"]["models"][quality]

    size_map = {"small": "1K", "medium": "2K", "large": "2K", "xlarge": "4K"}
    if quality == "fast" and image_size == "large":
        image_size = "small"
    gemini_size = size_map.get(image_size, "2K")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    parts = _encode_reference_images(ref_paths)
    parts.append({"text": prompt})

    image_config = {"aspectRatio": aspect_ratio}
    if quality == "pro":
        image_config["imageSize"] = gemini_size

    generation_config = {
        "responseModalities": ["TEXT", "IMAGE"],
        "imageConfig": image_config
    }

    # Media resolution control (LOW, MEDIUM, HIGH, AUTO)
    if media_resolution:
        generation_config["mediaResolution"] = media_resolution.upper()

    # Thinking level (Gemini 3 Pro: minimal, low, medium, high)
    if thinking_level and quality == "pro":
        generation_config["thinkingConfig"] = {"thinkingLevel": thinking_level.lower()}

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": generation_config
    }

    # Google Search grounding
    if search_grounding:
        payload["tools"] = [{"google_search": {}}]

    response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'})
    if response.status_code != 200:
        raise Exception(f"Gemini API error: {response.status_code} - {response.text}")

    data = response.json()
    image_data = None
    for part in data['candidates'][0]['content']['parts']:
        if 'inlineData' in part:
            image_data = part['inlineData']['data']
            break
    if not image_data:
        raise Exception("No image data in Gemini API response")

    return image_data, model, gemini_size


def _generate_openai(prompt, aspect_ratio, image_size, quality):
    """Generate image using OpenAI API (gpt-image-1)."""
    api_key = _get_api_key("openai")
    model = PROVIDERS["openai"]["models"][quality]

    # OpenAI only supports 3 fixed sizes - find closest match for any aspect ratio
    size = find_closest_openai_size(aspect_ratio)

    openai_quality = "high" if quality == "pro" else "low"

    payload = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "quality": openai_quality,
        "n": 1,
        "response_format": "b64_json",
    }

    response = requests.post(
        "https://api.openai.com/v1/images/generations",
        json=payload,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
    )
    if response.status_code != 200:
        raise Exception(f"OpenAI API error: {response.status_code} - {response.text}")

    data = response.json()
    image_data = data['data'][0]['b64_json']
    if not image_data:
        raise Exception("No image data in OpenAI API response")

    return image_data, model, size


def _generate_together(prompt, aspect_ratio, image_size, quality, model_alias=None):
    """Generate image using Together AI API (FLUX models + 20+ other models)."""
    api_key = _get_api_key("together")

    # Model override via alias
    if model_alias and model_alias in TOGETHER_MODELS:
        model_info = TOGETHER_MODELS[model_alias]
        model = model_info["id"]
        steps = model_info["steps"]
    else:
        model = PROVIDERS["together"]["models"][quality]
        steps = 4 if quality == "fast" else 28

    # Calculate dimensions from any aspect ratio
    width, height = calculate_dimensions(aspect_ratio, image_size)

    payload = {
        "model": model,
        "prompt": prompt,
        "width": width,
        "height": height,
        "n": 1,
        "response_format": "b64_json",
    }
    # Only include steps if > 0 (some models use their own defaults)
    if steps > 0:
        payload["steps"] = steps

    response = requests.post(
        "https://api.together.xyz/v1/images/generations",
        json=payload,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
    )
    if response.status_code != 200:
        raise Exception(f"Together API error: {response.status_code} - {response.text}")

    data = response.json()
    image_data = data['data'][0]['b64_json']
    if not image_data:
        raise Exception("No image data in Together API response")

    return image_data, model, f"{width}x{height}"


# --- Core functions ---

def generate_image(prompt, aspect_ratio="1:1", image_size="large", reference_image=None, reference_images=None, quality="pro", provider=None, search_grounding=False, thinking_level=None, media_resolution=None, model=None, auto_mode=None, style_hint="general"):
    """Generate image using the specified provider."""
    auto_selected = None
    if auto_mode:
        needs_refs = bool(reference_image or reference_images)
        sel_provider, sel_quality, sel_model_alias, auto_selected = _auto_select_model(
            auto_mode, style_hint, image_size, needs_refs, search_grounding)
        provider = sel_provider
        quality = sel_quality
        model = sel_model_alias
    else:
        # If model alias is set, force provider to together
        if model and model in TOGETHER_MODELS:
            provider = "together"
        provider = provider if provider in PROVIDERS else DEFAULT_PROVIDER
        quality = quality if quality in ("pro", "fast") else "pro"

    # Reference images only supported by certain providers/quality combos
    ref_paths = []
    if PROVIDERS[provider]["supports_references"].get(quality, False):
        ref_paths = _normalize_reference_images(reference_images, reference_image)

    # Dispatch to provider
    if provider == "gemini":
        image_data, used_model, resolution = _generate_gemini(prompt, aspect_ratio, image_size, quality, ref_paths, search_grounding, thinking_level, media_resolution)
    elif provider == "openai":
        image_data, used_model, resolution = _generate_openai(prompt, aspect_ratio, image_size, quality)
    elif provider == "together":
        image_data, used_model, resolution = _generate_together(prompt, aspect_ratio, image_size, quality, model)
    else:
        raise Exception(f"Unknown provider: {provider}")

    output_dir = CFG["images_dir"]
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{output_dir}/generated_image_{timestamp}.png"

    with open(filename, 'wb') as f:
        f.write(base64.b64decode(image_data))

    cost = estimate_cost(provider, quality, image_size, aspect_ratio, len(ref_paths), search_grounding, thinking_level, model)

    result = {
        "success": True,
        "image_path": filename,
        "provider": provider,
        "resolution": resolution,
        "aspect_ratio": aspect_ratio,
        "quality": quality,
        "model": used_model,
        "reference_images_used": len(ref_paths),
        "message": f"Image generated successfully ({provider}/{used_model}): {filename}"
    }
    if auto_selected:
        result["auto_mode"] = auto_mode
        result["auto_selected"] = auto_selected
        result["style_hint"] = style_hint
    if cost is not None:
        result["estimated_cost_usd"] = cost
    return result

def add_to_batch(prompt, filename=None, aspect_ratio="16:9", image_size="large", description="", reference_image=None, reference_images=None, quality="pro", provider=None, search_grounding=False, thinking_level=None, media_resolution=None, model=None, auto_mode=None, style_hint="general"):
    """Add image to batch queue with provider support."""
    if auto_mode:
        needs_refs = bool(reference_image or reference_images)
        sel_provider, sel_quality, sel_model_alias, _ = _auto_select_model(
            auto_mode, style_hint, image_size or "large", needs_refs, search_grounding)
        provider = sel_provider
        quality = sel_quality
        model = sel_model_alias
    else:
        if model and model in TOGETHER_MODELS:
            provider = "together"
        provider = provider if provider in PROVIDERS else DEFAULT_PROVIDER
        quality = quality if quality in ("pro", "fast") else "pro"

    ref_paths = []
    if PROVIDERS[provider]["supports_references"].get(quality, False):
        ref_paths = _normalize_reference_images(reference_images, reference_image)

    cmd = ["python3", CFG["batch_manager_script"], "add", prompt]
    if filename:
        cmd.append(filename)
    else:
        cmd.append("")
    cmd.append(aspect_ratio or "16:9")
    cmd.append(image_size or "large")
    if ref_paths:
        cmd.append(json.dumps(ref_paths))
    else:
        cmd.append("[]")
    cmd.append(quality)
    cmd.append(provider)
    # Pass Gemini-specific options as JSON
    gemini_opts = {}
    if search_grounding:
        gemini_opts["search_grounding"] = True
    if thinking_level:
        gemini_opts["thinking_level"] = thinking_level
    if media_resolution:
        gemini_opts["media_resolution"] = media_resolution
    cmd.append(json.dumps(gemini_opts))
    # Pass model alias as last arg
    cmd.append(model or "")

    result = subprocess.run(cmd, capture_output=True, text=True)
    batch_result = json.loads(result.stdout)
    cost = estimate_cost(provider, quality, image_size or "large", aspect_ratio or "16:9", len(ref_paths), search_grounding, thinking_level, model)
    if cost is not None:
        batch_result["estimated_cost_usd"] = cost
    return batch_result

def remove_from_batch(identifier):
    cmd = ["python3", CFG["batch_manager_script"], "remove", str(identifier)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(result.stdout)

def view_batch_queue():
    cmd = ["python3", CFG["batch_manager_script"], "view"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(result.stdout)

def run_batch():
    env = os.environ.copy()
    cmd = ["python3", CFG["batch_generate_script"], CFG["queue_file"], CFG["batch_dir"]]
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)

    return {
        "success": result.returncode == 0,
        "output": result.stdout,
        "error": result.stderr if result.returncode != 0 else None
    }

def convert_to_webp(quality=85, force=False):
    cmd = ["uv", "run", CFG["webp_convert_script"], CFG["images_dir"], "--batch", "--recursive", "--quality", str(quality)]
    if force:
        cmd.append("--force")
    result = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "success": result.returncode == 0,
        "output": result.stdout,
        "error": result.stderr if result.returncode != 0 else None
    }

def upload_to_wordpress(wp_url, directory="batch", limit=10):
    from pathlib import Path

    # Look up credentials from config.json wordpress section
    wp_sites = CFG.get("wordpress", {})
    # Normalize URL: strip trailing slash for matching
    normalized_url = wp_url.rstrip("/")
    site_cfg = wp_sites.get(normalized_url) or wp_sites.get(normalized_url + "/")
    if not site_cfg:
        raise Exception(f"No WordPress credentials found in config.json for '{wp_url}'. Add a 'wordpress' entry with user and password.")
    wp_user = site_cfg.get("user")
    wp_password = site_cfg.get("password")
    if not wp_user or not wp_password:
        raise Exception(f"WordPress config for '{wp_url}' is missing 'user' or 'password' in config.json.")

    batch_dir = os.path.join(CFG["images_dir"], directory)
    uploaded = []
    failed = []

    image_files = sorted(Path(batch_dir).glob("*.webp"), key=os.path.getmtime, reverse=True)[:limit]

    for img_path in image_files:
        try:
            filename = img_path.name
            with open(img_path, 'rb') as f:
                files = {'file': (filename, f, 'image/webp')}
                response = requests.post(
                    f"{normalized_url}/wp-json/wp/v2/media",
                    auth=(wp_user, wp_password),
                    files=files
                )
                if response.status_code == 201:
                    media_data = response.json()
                    uploaded.append({
                        "filename": filename,
                        "media_id": media_data['id'],
                        "url": media_data['source_url'],
                        "title": media_data['title']['rendered']
                    })
                else:
                    failed.append({"filename": filename, "error": f"HTTP {response.status_code}: {response.text}"})
        except Exception as e:
            failed.append({"filename": img_path.name, "error": str(e)})

    return {"success": len(failed) == 0, "uploaded": uploaded, "failed": failed, "total": len(uploaded) + len(failed)}

def get_generated_webp_images(directory="batch", limit=10):
    from pathlib import Path
    batch_dir = os.path.join(CFG["images_dir"], directory)
    images = []

    image_files = sorted(Path(batch_dir).glob("*.webp"), key=os.path.getmtime, reverse=True)[:limit]
    for img_path in image_files:
        with open(img_path, 'rb') as f:
            images.append({
                "filename": img_path.name,
                "base64": base64.b64encode(f.read()).decode('utf-8'),
                "path": str(img_path),
                "size": os.path.getsize(img_path)
            })

    return {"success": True, "images": images, "count": len(images)}

def estimate_image_cost(provider="gemini", quality="pro", aspect_ratio="1:1", image_size="large", num_reference_images=0, search_grounding=False, thinking_level=None, count=1, model=None, auto_mode=None, style_hint="general"):
    """Return a cost estimate without generating anything."""
    auto_selected = None
    if auto_mode:
        sel_provider, sel_quality, sel_model_alias, auto_selected = _auto_select_model(
            auto_mode, style_hint, image_size, num_reference_images > 0, search_grounding)
        provider = sel_provider
        quality = sel_quality
        model = sel_model_alias
    else:
        if model and model in TOGETHER_MODELS:
            provider = "together"
        provider = provider if provider in PROVIDERS else DEFAULT_PROVIDER
        quality = quality if quality in ("pro", "fast") else "pro"
    per_image = estimate_cost(provider, quality, image_size, aspect_ratio, num_reference_images, search_grounding, thinking_level, model)
    if per_image is None:
        return {"success": False, "error": "Pricing data unavailable"}
    total = round(per_image * count, 6)
    result = {
        "success": True,
        "provider": provider,
        "quality": quality,
        "image_size": image_size,
        "aspect_ratio": aspect_ratio,
        "reference_images": num_reference_images,
        "search_grounding": search_grounding,
        "thinking_level": thinking_level,
        "estimated_cost_per_image_usd": per_image,
        "count": count,
        "estimated_total_cost_usd": total
    }
    if auto_selected:
        result["auto_mode"] = auto_mode
        result["auto_selected"] = auto_selected
        result["style_hint"] = style_hint
    if model:
        result["model"] = model
        if model in TOGETHER_MODELS:
            result["model_id"] = TOGETHER_MODELS[model]["id"]
    return result

# --- MCP handlers ---
def handle_initialize(request_id):
    send_message({
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "peeperfrog-create", "version": "0.1.0"}
        }
    })

PROVIDER_ENUM = list(PROVIDERS.keys())
AUTO_MODE_ENUM = list(AUTO_MODE_TIERS.keys())
STYLE_HINT_ENUM = ["general", "photo", "illustration", "text"]

def handle_tools_list(request_id):
    send_message({
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "tools": [
                {
                    "name": "get_generated_webp_images",
                    "description": "Get base64 data of recently generated WebP images for uploading",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "directory": {"type": "string", "description": "Directory to scan (default: batch)", "default": "batch"},
                            "limit": {"type": "integer", "description": "Maximum number of images to return", "default": 10}
                        },
                        "required": []
                    }
                },
                {
                    "name": "generate_image",
                    "description": "Generate a single image immediately. Supports multiple providers: 'gemini' (default, Google Gemini), 'openai' (gpt-image-1), 'together' (FLUX models). Use quality='pro' for high-quality or 'fast' for cheaper/quicker generation.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "prompt": {"type": "string", "description": "Text description of the image to generate"},
                            "provider": {"type": "string", "description": "Image generation provider: 'gemini' (default), 'openai', or 'together'", "enum": PROVIDER_ENUM, "default": "gemini"},
                            "aspect_ratio": {"type": "string", "description": "Aspect ratio - any format supported (e.g., 1:1, 16:9, 21:9, 2.35:1, 3:2). OpenAI uses closest match from fixed sizes.", "default": "1:1"},
                            "image_size": {"type": "string", "description": "Image resolution: 'small', 'medium', 'large' (default), 'xlarge'", "enum": ["small", "medium", "large", "xlarge"], "default": "large"},
                            "quality": {"type": "string", "description": "Quality tier: 'pro' (high quality) or 'fast' (cheaper/quicker)", "enum": ["pro", "fast"], "default": "pro"},
                            "reference_image": {"type": "string", "description": "Optional single reference image file path (Gemini pro mode only)"},
                            "reference_images": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": f"Optional list of reference image file paths, max {MAX_REF_IMAGES} (Gemini pro mode only)",
                                "maxItems": MAX_REF_IMAGES
                            },
                            "search_grounding": {"type": "boolean", "description": "Enable Google Search grounding for factually accurate images (Gemini only). Uses real-time data for current events, real places, etc.", "default": False},
                            "thinking_level": {"type": "string", "description": "Thinking/reasoning depth for complex compositions (Gemini Pro only): 'minimal', 'low', 'medium', 'high'", "enum": ["minimal", "low", "medium", "high"]},
                            "media_resolution": {"type": "string", "description": "Media resolution control for input processing (Gemini only): 'low', 'medium', 'high', 'auto'", "enum": ["low", "medium", "high", "auto"]},
                            "model": {"type": "string", "description": "Together AI model alias. Overrides provider/quality. Options: " + ", ".join(TOGETHER_MODEL_ALIASES), "enum": TOGETHER_MODEL_ALIASES},
                            "auto_mode": {"type": "string", "description": "Auto-select the best model based on cost tier and constraints. Overrides provider/quality/model. Options: cheapest, budget, balanced, quality, best", "enum": AUTO_MODE_ENUM},
                            "style_hint": {"type": "string", "description": "Style preference for auto_mode model selection: 'general' (default), 'photo' (photorealistic), 'illustration' (art/drawings), 'text' (text in image matters)", "enum": STYLE_HINT_ENUM, "default": "general"}
                        },
                        "required": ["prompt"]
                    }
                },
                {
                    "name": "add_to_batch",
                    "description": "Add an image to the batch queue for later generation. Supports providers: 'gemini' (default), 'openai', 'together'.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "prompt": {"type": "string", "description": "Text description of the image to generate"},
                            "provider": {"type": "string", "description": "Image generation provider: 'gemini' (default), 'openai', or 'together'", "enum": PROVIDER_ENUM, "default": "gemini"},
                            "filename": {"type": "string", "description": "Optional filename for the image"},
                            "aspect_ratio": {"type": "string", "description": "Aspect ratio - any format supported (e.g., 1:1, 16:9, 21:9, 2.35:1, 3:2). OpenAI uses closest match from fixed sizes.", "default": "16:9"},
                            "image_size": {"type": "string", "description": "Image resolution: 'small', 'medium', 'large' (default), 'xlarge'", "enum": ["small", "medium", "large", "xlarge"], "default": "large"},
                            "quality": {"type": "string", "description": "Quality tier: 'pro' (default) or 'fast'", "enum": ["pro", "fast"], "default": "pro"},
                            "description": {"type": "string", "description": "Optional description/note for this image"},
                            "reference_image": {"type": "string", "description": "Optional single reference image file path (Gemini pro mode only)"},
                            "reference_images": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": f"Optional list of reference image file paths, max {MAX_REF_IMAGES} (Gemini pro mode only)",
                                "maxItems": MAX_REF_IMAGES
                            },
                            "search_grounding": {"type": "boolean", "description": "Enable Google Search grounding for factually accurate images (Gemini only)", "default": False},
                            "thinking_level": {"type": "string", "description": "Thinking/reasoning depth (Gemini Pro only): 'minimal', 'low', 'medium', 'high'", "enum": ["minimal", "low", "medium", "high"]},
                            "media_resolution": {"type": "string", "description": "Media resolution control for input processing (Gemini only): 'low', 'medium', 'high', 'auto'", "enum": ["low", "medium", "high", "auto"]},
                            "model": {"type": "string", "description": "Together AI model alias. Overrides provider/quality. Options: " + ", ".join(TOGETHER_MODEL_ALIASES), "enum": TOGETHER_MODEL_ALIASES},
                            "auto_mode": {"type": "string", "description": "Auto-select the best model based on cost tier and constraints. Overrides provider/quality/model.", "enum": AUTO_MODE_ENUM},
                            "style_hint": {"type": "string", "description": "Style preference for auto_mode: 'general', 'photo', 'illustration', 'text'", "enum": STYLE_HINT_ENUM, "default": "general"}
                        },
                        "required": ["prompt"]
                    }
                },
                {
                    "name": "remove_from_batch",
                    "description": "Remove an image from the batch queue by index (0, 1, 2...) or filename",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "identifier": {"type": "string", "description": "Either an integer index (0 for first item, 1 for second, etc.) or a filename string"}
                        },
                        "required": ["identifier"]
                    }
                },
                {
                    "name": "view_batch_queue",
                    "description": "View all images currently queued for batch generation",
                    "inputSchema": {"type": "object", "properties": {}, "required": []}
                },
                {
                    "name": "run_batch",
                    "description": "Execute batch generation for all queued images",
                    "inputSchema": {"type": "object", "properties": {}, "required": []}
                },
                {
                    "name": "estimate_image_cost",
                    "description": "Get a cost estimate for an image generation without actually generating it. Returns estimated USD cost based on provider, quality, size, and options.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "provider": {"type": "string", "description": "Image generation provider: 'gemini' (default), 'openai', or 'together'", "enum": PROVIDER_ENUM, "default": "gemini"},
                            "quality": {"type": "string", "description": "Quality tier: 'pro' or 'fast'", "enum": ["pro", "fast"], "default": "pro"},
                            "aspect_ratio": {"type": "string", "description": "Aspect ratio - any format supported (e.g., 1:1, 16:9, 21:9, 2.35:1, 3:2). OpenAI uses closest match from fixed sizes.", "default": "1:1"},
                            "image_size": {"type": "string", "description": "Image resolution: 'small', 'medium', 'large', 'xlarge'", "enum": ["small", "medium", "large", "xlarge"], "default": "large"},
                            "num_reference_images": {"type": "integer", "description": "Number of reference images (Gemini pro only)", "default": 0, "minimum": 0, "maximum": MAX_REF_IMAGES},
                            "search_grounding": {"type": "boolean", "description": "Whether Google Search grounding will be used (Gemini only)", "default": False},
                            "thinking_level": {"type": "string", "description": "Thinking level (Gemini Pro only): 'minimal', 'low', 'medium', 'high'", "enum": ["minimal", "low", "medium", "high"]},
                            "count": {"type": "integer", "description": "Number of images to estimate for (multiplies the per-image cost)", "default": 1, "minimum": 1},
                            "model": {"type": "string", "description": "Together AI model alias. Overrides provider/quality for pricing. Options: " + ", ".join(TOGETHER_MODEL_ALIASES), "enum": TOGETHER_MODEL_ALIASES},
                            "auto_mode": {"type": "string", "description": "Auto-select the best model based on cost tier. Overrides provider/quality/model.", "enum": AUTO_MODE_ENUM},
                            "style_hint": {"type": "string", "description": "Style preference for auto_mode: 'general', 'photo', 'illustration', 'text'", "enum": STYLE_HINT_ENUM, "default": "general"}
                        },
                        "required": []
                    }
                },
                {
                    "name": "convert_to_webp",
                    "description": "Convert generated images to WebP format for WordPress optimization. Scans images directory recursively and converts PNG/JPG to WebP.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "quality": {"type": "integer", "description": "WebP quality (0-100). Default 85", "default": 85, "minimum": 0, "maximum": 100},
                            "force": {"type": "boolean", "description": "Force reconversion even if .webp files already exist", "default": False}
                        },
                        "required": []
                    }
                },
                {
                    "name": "upload_to_wordpress",
                    "description": "Upload WebP images directly to WordPress media library. Credentials are read from config.json by URL.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "wp_url": {"type": "string", "description": "WordPress site URL (e.g., https://example.com). Must match an entry in config.json wordpress section."},
                            "directory": {"type": "string", "description": "Directory containing images (default: batch)", "default": "batch"},
                            "limit": {"type": "integer", "description": "Maximum number of images to upload", "default": 10}
                        },
                        "required": ["wp_url"]
                    }
                }
            ]
        }
    })

def handle_tool_call(request_id, tool_name, arguments):
    try:
        if tool_name == "generate_image":
            result = generate_image(
                arguments.get("prompt"),
                arguments.get("aspect_ratio", "1:1"),
                arguments.get("image_size", "large"),
                arguments.get("reference_image"),
                arguments.get("reference_images"),
                arguments.get("quality", "pro"),
                arguments.get("provider"),
                arguments.get("search_grounding", False),
                arguments.get("thinking_level"),
                arguments.get("media_resolution"),
                arguments.get("model"),
                arguments.get("auto_mode"),
                arguments.get("style_hint", "general")
            )
        elif tool_name == "add_to_batch":
            result = add_to_batch(
                arguments.get("prompt"),
                arguments.get("filename"),
                arguments.get("aspect_ratio", "16:9"),
                arguments.get("image_size", "large"),
                arguments.get("description", ""),
                arguments.get("reference_image"),
                arguments.get("reference_images"),
                arguments.get("quality", "pro"),
                arguments.get("provider"),
                arguments.get("search_grounding", False),
                arguments.get("thinking_level"),
                arguments.get("media_resolution"),
                arguments.get("model"),
                arguments.get("auto_mode"),
                arguments.get("style_hint", "general")
            )
        elif tool_name == "remove_from_batch":
            result = remove_from_batch(arguments.get("identifier"))
        elif tool_name == "view_batch_queue":
            result = view_batch_queue()
        elif tool_name == "run_batch":
            result = run_batch()
        elif tool_name == "estimate_image_cost":
            result = estimate_image_cost(
                arguments.get("provider", "gemini"),
                arguments.get("quality", "pro"),
                arguments.get("aspect_ratio", "1:1"),
                arguments.get("image_size", "large"),
                arguments.get("num_reference_images", 0),
                arguments.get("search_grounding", False),
                arguments.get("thinking_level"),
                arguments.get("count", 1),
                arguments.get("model"),
                arguments.get("auto_mode"),
                arguments.get("style_hint", "general")
            )
        elif tool_name == "convert_to_webp":
            result = convert_to_webp(arguments.get("quality", 85), arguments.get("force", False))
        elif tool_name == "get_generated_webp_images":
            result = get_generated_webp_images(arguments.get("directory", "batch"), arguments.get("limit", 10))
        elif tool_name == "upload_to_wordpress":
            result = upload_to_wordpress(
                arguments.get("wp_url"),
                arguments.get("directory", "batch"),
                arguments.get("limit", 10)
            )
        else:
            raise Exception(f"Unknown tool: {tool_name}")

        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"content": [{"type": "text", "text": json.dumps(result)}]}
        }
    except Exception as e:
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32000, "message": str(e)}
        }
    send_message(response)

def main():
    sys.stderr.write("PeeperFrog Create MCP Server v0.1 - Multi-Provider (Gemini/OpenAI/Together)\n")
    sys.stderr.flush()

    while True:
        try:
            message = read_message()
            if message is None:
                break

            method = message.get("method")
            request_id = message.get("id")

            if method == "initialize":
                handle_initialize(request_id)
            elif method == "tools/list":
                handle_tools_list(request_id)
            elif method == "tools/call":
                params = message.get("params", {})
                handle_tool_call(request_id, params.get("name"), params.get("arguments", {}))
            elif method == "notifications/initialized":
                pass

        except Exception as e:
            sys.stderr.write(f"Error: {str(e)}\n")
            sys.stderr.flush()

if __name__ == "__main__":
    main()
