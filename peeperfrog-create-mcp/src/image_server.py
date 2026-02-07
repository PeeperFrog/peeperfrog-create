#!/usr/bin/env python3
# Copyright (c) 2025 PeeperFrog Press
# Licensed under the Apache License, Version 2.0. See LICENSE file for details.
#
# Not affiliated with Google, Gemini, OpenAI, Together AI, or WordPress.
# All trademarks are property of their respective owners.
# THIS SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.
"""
PeeperFrog Create Image MCP Server - Version 1.0 Beta

Multi-provider image generation with quality tiers.
Part of PeeperFrog Create: https://github.com/PeeperFrog/peeperfrog-create

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
import traceback
from datetime import datetime
from batch_generate import log_generation, get_cost_from_log

# --- Configuration ---
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config.json")
ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")

def load_env():
    """Load .env file if present. Local .env takes precedence over environment."""
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    # Use setdefault so env vars passed by MCP client still work
                    os.environ.setdefault(key.strip(), value.strip())

# Load .env on import
load_env()

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
    cfg["webp_dir"] = os.path.join(cfg["images_dir"], cfg.get("webp_subdir", "webp"))
    cfg["queue_file"] = os.path.join(cfg["images_dir"], cfg.get("queue_filename", "batch_queue.json"))
    return cfg

CFG = load_config()
MAX_REF_IMAGES = CFG.get("max_reference_images", 14)

# --- Debug logging ---
DEBUG_ENABLED = CFG.get("debug", False)
DEBUG_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(CONFIG_PATH)), "debug.log")

def debug_log(message, level="INFO"):
    """Write debug message to log file if debug is enabled."""
    if not DEBUG_ENABLED:
        return
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        with open(DEBUG_LOG_PATH, 'a') as f:
            f.write(f"[{timestamp}] [{level}] {message}\n")
    except Exception:
        pass  # Fail silently - don't let logging break functionality

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

# --- Model-specific resolution constraints ---
# Some models (like imagen-4) only support fixed resolutions
# Format: list of (width, height) tuples
IMAGEN4_RESOLUTIONS = [
    (1024, 1024),   # 1:1 square
    (2048, 2048),   # 1:1 square large
    (768, 1408),    # 9:16 portrait
    (1536, 2816),   # 9:16 portrait large
    (1408, 768),    # 16:9 landscape
    (2816, 1536),   # 16:9 landscape large
    (896, 1280),    # ~7:10 portrait
    (1792, 2560),   # ~7:10 portrait large
    (1280, 896),    # ~10:7 landscape
    (2560, 1792),   # ~10:7 landscape large
]

def _get_imagen4_resolution(aspect_ratio, image_size):
    """Find the closest imagen-4 supported resolution for the requested aspect ratio and size."""
    w_ratio, h_ratio = parse_aspect_ratio(aspect_ratio)
    target_ratio = w_ratio / h_ratio

    best_match = None
    best_score = float('inf')

    for w, h in IMAGEN4_RESOLUTIONS:
        res_ratio = w / h
        ratio_diff = abs(res_ratio - target_ratio)

        # Calculate megapixels
        mp = w * h / 1_000_000

        # Size preference scoring
        if image_size == "xlarge":
            # For xlarge, strongly prefer 2x resolutions (>3MP)
            size_penalty = 0 if mp >= 3.0 else 0.8
        elif image_size == "large":
            # For large, prefer standard resolutions (~1MP)
            size_penalty = 0 if 0.8 <= mp <= 2.0 else 0.3
        else:
            # For small/medium, prefer lower resolutions
            size_penalty = 0 if mp <= 1.5 else 0.5

        score = ratio_diff + size_penalty

        if score < best_score:
            best_score = score
            best_match = (w, h)

    return best_match

# --- Auto mode: capability matrix for model selection ---
# cost_per_image_1mp: normalized cost for a 1-megapixel image (for sorting)
# max_size: highest image_size this model supports (small < medium < large < xlarge)
# text/photo/illustration/infographic/general quality: 0=poor, 1=ok, 2=good, 3=excellent
# infographic_quality: charts, graphs, data visualizations requiring precise layouts and numbers
AUTO_MODE_MODELS = {
    "dreamshaper":          {"provider": "together", "quality": "fast", "model_alias": "dreamshaper",          "cost_per_image_1mp": 0.0006, "max_size": "xlarge", "supports_references": False, "supports_grounding": False, "text_quality": 0, "photo_quality": 1, "illustration_quality": 2, "infographic_quality": 0, "general_quality": 1},
    "juggernaut-lightning": {"provider": "together", "quality": "fast", "model_alias": "juggernaut-lightning", "cost_per_image_1mp": 0.0017, "max_size": "xlarge", "supports_references": False, "supports_grounding": False, "text_quality": 0, "photo_quality": 2, "illustration_quality": 1, "infographic_quality": 0, "general_quality": 1},
    "sdxl":                 {"provider": "together", "quality": "fast", "model_alias": "sdxl",                 "cost_per_image_1mp": 0.0019, "max_size": "xlarge", "supports_references": False, "supports_grounding": False, "text_quality": 0, "photo_quality": 1, "illustration_quality": 2, "infographic_quality": 0, "general_quality": 1},
    "sd3":                  {"provider": "together", "quality": "fast", "model_alias": "sd3",                  "cost_per_image_1mp": 0.0019, "max_size": "xlarge", "supports_references": False, "supports_grounding": False, "text_quality": 0, "photo_quality": 2, "illustration_quality": 2, "infographic_quality": 0, "general_quality": 1},
    "flux1-schnell":        {"provider": "together", "quality": "fast", "model_alias": "flux1-schnell",        "cost_per_image_1mp": 0.0027, "max_size": "xlarge", "supports_references": False, "supports_grounding": False, "text_quality": 1, "photo_quality": 2, "illustration_quality": 2, "infographic_quality": 0, "general_quality": 2},
    "hidream-fast":         {"provider": "together", "quality": "fast", "model_alias": "hidream-fast",         "cost_per_image_1mp": 0.0032, "max_size": "xlarge", "supports_references": False, "supports_grounding": False, "text_quality": 1, "photo_quality": 2, "illustration_quality": 2, "infographic_quality": 0, "general_quality": 2},
    "hidream-dev":          {"provider": "together", "quality": "fast", "model_alias": "hidream-dev",          "cost_per_image_1mp": 0.0045, "max_size": "xlarge", "supports_references": False, "supports_grounding": False, "text_quality": 1, "photo_quality": 2, "illustration_quality": 2, "infographic_quality": 0, "general_quality": 2},
    "juggernaut-pro":       {"provider": "together", "quality": "fast", "model_alias": "juggernaut-pro",       "cost_per_image_1mp": 0.0049, "max_size": "xlarge", "supports_references": False, "supports_grounding": False, "text_quality": 0, "photo_quality": 2, "illustration_quality": 1, "infographic_quality": 0, "general_quality": 2},
    "qwen-image":           {"provider": "together", "quality": "fast", "model_alias": "qwen-image",           "cost_per_image_1mp": 0.0058, "max_size": "xlarge", "supports_references": False, "supports_grounding": False, "text_quality": 1, "photo_quality": 2, "illustration_quality": 2, "infographic_quality": 1, "general_quality": 2},
    "hidream-full":         {"provider": "together", "quality": "fast", "model_alias": "hidream-full",         "cost_per_image_1mp": 0.009, "max_size": "xlarge", "supports_references": False, "supports_grounding": False, "text_quality": 1, "photo_quality": 2, "illustration_quality": 2, "infographic_quality": 0, "general_quality": 2},
    "openai-fast":          {"provider": "openai",   "quality": "fast", "model_alias": None,                   "cost_per_image_1mp": 0.011, "max_size": "large",  "supports_references": False, "supports_grounding": False, "text_quality": 1, "photo_quality": 2, "illustration_quality": 2, "infographic_quality": 1, "general_quality": 2},
    "seedream3":            {"provider": "together", "quality": "fast", "model_alias": "seedream3",            "cost_per_image_1mp": 0.018, "max_size": "xlarge", "supports_references": False, "supports_grounding": False, "text_quality": 1, "photo_quality": 3, "illustration_quality": 2, "infographic_quality": 1, "general_quality": 2},
    "imagen4-fast":         {"provider": "together", "quality": "fast", "model_alias": "imagen4-fast",         "cost_per_image_1mp": 0.02,  "max_size": "xlarge", "supports_references": False, "supports_grounding": False, "text_quality": 2, "photo_quality": 3, "illustration_quality": 2, "infographic_quality": 1, "general_quality": 2},
    "flux2-dev":            {"provider": "together", "quality": "fast", "model_alias": "flux2-dev",            "cost_per_image_1mp": 0.025, "max_size": "xlarge", "supports_references": False, "supports_grounding": False, "text_quality": 2, "photo_quality": 3, "illustration_quality": 3, "infographic_quality": 1, "general_quality": 3},
    "seedream4":            {"provider": "together", "quality": "fast", "model_alias": "seedream4",            "cost_per_image_1mp": 0.03,  "max_size": "xlarge", "supports_references": False, "supports_grounding": False, "text_quality": 1, "photo_quality": 3, "illustration_quality": 2, "infographic_quality": 1, "general_quality": 2},
    "gemini-fast":          {"provider": "gemini",   "quality": "fast", "model_alias": None,                   "cost_per_image_1mp": 0.039, "max_size": "small",  "supports_references": False, "supports_grounding": False, "text_quality": 1, "photo_quality": 2, "illustration_quality": 2, "infographic_quality": 1, "general_quality": 2},
    "flux2-pro":            {"provider": "together", "quality": "pro",  "model_alias": "flux2-pro",            "cost_per_image_1mp": 0.04,  "max_size": "xlarge", "supports_references": False, "supports_grounding": False, "text_quality": 2, "photo_quality": 3, "illustration_quality": 3, "infographic_quality": 1, "general_quality": 3},
    "flux1-kontext-pro":    {"provider": "together", "quality": "pro",  "model_alias": "flux1-kontext-pro",    "cost_per_image_1mp": 0.04,  "max_size": "xlarge", "supports_references": False, "supports_grounding": False, "text_quality": 1, "photo_quality": 3, "illustration_quality": 3, "infographic_quality": 1, "general_quality": 3},
    "imagen4":              {"provider": "together", "quality": "pro",  "model_alias": "imagen4",              "cost_per_image_1mp": 0.04,  "max_size": "xlarge", "supports_references": False, "supports_grounding": False, "text_quality": 3, "photo_quality": 3, "illustration_quality": 2, "infographic_quality": 2, "general_quality": 3},
    "ideogram3":            {"provider": "together", "quality": "pro",  "model_alias": "ideogram3",            "cost_per_image_1mp": 0.06,  "max_size": "xlarge", "supports_references": False, "supports_grounding": False, "text_quality": 3, "photo_quality": 2, "illustration_quality": 3, "infographic_quality": 1, "general_quality": 3},
    "imagen4-ultra":        {"provider": "together", "quality": "pro",  "model_alias": "imagen4-ultra",        "cost_per_image_1mp": 0.06,  "max_size": "xlarge", "supports_references": False, "supports_grounding": False, "text_quality": 3, "photo_quality": 3, "illustration_quality": 3, "infographic_quality": 2, "general_quality": 3},
    "flux1-kontext-max":    {"provider": "together", "quality": "pro",  "model_alias": "flux1-kontext-max",    "cost_per_image_1mp": 0.08,  "max_size": "xlarge", "supports_references": False, "supports_grounding": False, "text_quality": 1, "photo_quality": 3, "illustration_quality": 3, "infographic_quality": 1, "general_quality": 3},
    "gemini-pro":           {"provider": "gemini",   "quality": "pro",  "model_alias": None,                   "cost_per_image_1mp": 0.134, "max_size": "xlarge", "supports_references": True,  "supports_grounding": True,  "text_quality": 3, "photo_quality": 3, "illustration_quality": 3, "infographic_quality": 3, "general_quality": 3},
    "openai-pro":           {"provider": "openai",   "quality": "pro",  "model_alias": None,                   "cost_per_image_1mp": 0.167, "max_size": "large",  "supports_references": False, "supports_grounding": False, "text_quality": 3, "photo_quality": 3, "illustration_quality": 3, "infographic_quality": 2, "general_quality": 3},
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

    # Infographics require gemini-pro which costs $0.134 - override tier to 'best' to ensure it's included
    if style_hint == "infographic" and max_cost < AUTO_MODE_TIERS["best"]:
        max_cost = AUTO_MODE_TIERS["best"]

    required_size = SIZE_ORDER.get(image_size, 2)
    style_key = f"{style_hint}_quality" if style_hint in ("text", "photo", "illustration", "infographic") else "general_quality"

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
    debug_log(f"Gemini generation starting: quality={quality}, aspect_ratio={aspect_ratio}, image_size={image_size}")
    api_key = _get_api_key("gemini")
    model = PROVIDERS["gemini"]["models"][quality]

    size_map = {"small": "1K", "medium": "2K", "large": "2K", "xlarge": "4K"}
    if quality == "fast" and image_size == "large":
        image_size = "small"
    gemini_size = size_map.get(image_size, "2K")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key=***"
    debug_log(f"Gemini API URL: {url}")

    parts = _encode_reference_images(ref_paths)
    parts.append({"text": prompt})

    image_config = {"aspectRatio": aspect_ratio}
    if quality == "pro":
        image_config["imageSize"] = gemini_size

    generation_config = {
        "responseModalities": ["TEXT", "IMAGE"],
        "imageConfig": image_config
    }

    # Media resolution control (MEDIA_RESOLUTION_LOW, MEDIA_RESOLUTION_MEDIUM, MEDIA_RESOLUTION_HIGH)
    if media_resolution:
        generation_config["mediaResolution"] = f"MEDIA_RESOLUTION_{media_resolution.upper()}"

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

    # Log payload without image data for debugging
    payload_log = json.dumps({k: v for k, v in payload.items() if k != "contents"})
    debug_log(f"Gemini request payload (partial): {payload_log}")

    actual_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    response = requests.post(actual_url, json=payload, headers={'Content-Type': 'application/json'})
    debug_log(f"Gemini response status: {response.status_code}")
    if response.status_code != 200:
        debug_log(f"Gemini API error response: {response.text}", "ERROR")
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
    debug_log(f"OpenAI generation starting: quality={quality}, aspect_ratio={aspect_ratio}")
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
    }

    debug_log(f"OpenAI request payload: {json.dumps(payload)}")

    response = requests.post(
        "https://api.openai.com/v1/images/generations",
        json=payload,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer ***'
        }
    )
    debug_log(f"OpenAI response status: {response.status_code}")
    if response.status_code != 200:
        debug_log(f"OpenAI API error response: {response.text}", "ERROR")
        raise Exception(f"OpenAI API error: {response.status_code} - {response.text}")

    data = response.json()

    # gpt-image-1 returns URLs (response_format not supported), download and convert to base64
    image_url = data['data'][0].get('url')
    if image_url:
        img_response = requests.get(image_url)
        if img_response.status_code != 200:
            raise Exception(f"Failed to download image from OpenAI URL: {img_response.status_code}")
        image_data = base64.b64encode(img_response.content).decode('utf-8')
    else:
        # Fallback for b64_json if ever supported in future
        image_data = data['data'][0].get('b64_json')

    if not image_data:
        raise Exception("No image data in OpenAI API response")

    return image_data, model, size


def _generate_together(prompt, aspect_ratio, image_size, quality, model_alias=None):
    """Generate image using Together AI API (FLUX models + 20+ other models)."""
    debug_log(f"Together generation starting: quality={quality}, aspect_ratio={aspect_ratio}, model_alias={model_alias}")
    api_key = _get_api_key("together")

    # Model override via alias
    if model_alias and model_alias in TOGETHER_MODELS:
        model_info = TOGETHER_MODELS[model_alias]
        model = model_info["id"]
        steps = model_info["steps"]
    else:
        model = PROVIDERS["together"]["models"][quality]
        steps = 4 if quality == "fast" else 28

    # Calculate dimensions - use model-specific resolution for imagen-4
    is_imagen4 = model_alias and model_alias.startswith("imagen4")
    if is_imagen4:
        width, height = _get_imagen4_resolution(aspect_ratio, image_size)
        debug_log(f"Using imagen-4 specific resolution: {width}x{height}")
    else:
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

    debug_log(f"Together request payload: {json.dumps(payload)}")

    response = requests.post(
        "https://api.together.xyz/v1/images/generations",
        json=payload,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer ***'
        }
    )
    debug_log(f"Together response status: {response.status_code}")
    if response.status_code != 200:
        debug_log(f"Together API error response: {response.text}", "ERROR")
        raise Exception(f"Together API error: {response.status_code} - {response.text}")

    data = response.json()
    image_data = data['data'][0]['b64_json']
    if not image_data:
        raise Exception("No image data in Together API response")

    return image_data, model, f"{width}x{height}"


# --- Core functions ---

def _convert_png_to_webp(png_path, webp_quality=85, webp_dir=None):
    """Convert a PNG file to WebP format using PIL.

    Args:
        png_path: Path to the source PNG file
        webp_quality: WebP quality 0-100 (default 85)
        webp_dir: Output directory for WebP files (default: CFG["webp_dir"])

    Returns:
        (webp_path, webp_size) tuple, or (None, 0) on failure
    """
    try:
        from PIL import Image
        target_dir = webp_dir or CFG["webp_dir"]
        os.makedirs(target_dir, exist_ok=True)
        basename = os.path.splitext(os.path.basename(png_path))[0]
        webp_path = os.path.join(target_dir, f"{basename}.webp")
        img = Image.open(png_path)
        if img.mode == 'RGBA':
            bg = Image.new('RGB', img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[3])
            img = bg
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        img.save(webp_path, 'webp', quality=webp_quality, method=6)
        return webp_path, os.path.getsize(webp_path)
    except Exception as e:
        debug_log(f"WebP conversion failed for {png_path}: {e}", "ERROR")
        return None, 0

def generate_image(prompt, aspect_ratio="1:1", image_size="large", reference_image=None, reference_images=None, quality="pro", provider=None, search_grounding=False, thinking_level=None, media_resolution=None, model=None, auto_mode=None, style_hint="general", convert_to_webp=True, webp_quality=85, upload_to_wordpress=False, wp_url=None):
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
        # Reference images require Gemini pro - override provider/quality if refs provided
        if (reference_image or reference_images) and not PROVIDERS[provider]["supports_references"].get(quality, False):
            provider = "gemini"
            quality = "pro"

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

    # WebP conversion
    webp_path = None
    webp_size = 0
    if convert_to_webp:
        webp_path, webp_size = _convert_png_to_webp(filename, webp_quality)

    result = {
        "success": True,
        "image_path": filename,
        "provider": provider,
        "resolution": resolution,
        "aspect_ratio": aspect_ratio,
        "quality": quality,
        "model": used_model,
        "reference_images_used": len(ref_paths),
        "message": f"Image generated successfully ({provider}/{used_model}): {filename}",
        "file_count": 1,
        "total_size_bytes": webp_size if webp_path else os.path.getsize(filename),
    }
    if webp_path:
        result["webp_path"] = webp_path
        result["webp_size"] = webp_size
    if auto_selected:
        result["auto_mode"] = auto_mode
        result["auto_selected"] = auto_selected
        result["style_hint"] = style_hint
    if cost is not None:
        result["estimated_cost_usd"] = cost
    # Log the generation
    log_generation(os.path.basename(filename), "success", cost, provider, quality, aspect_ratio)

    # WordPress upload if requested
    if upload_to_wordpress and wp_url:
        upload_file = webp_path if webp_path else filename
        try:
            wp_result = _upload_single_to_wordpress(upload_file, wp_url)
            result["wordpress_upload"] = wp_result
            # Add top-level fields for easy access
            if wp_result.get("success"):
                result["wordpress_url"] = wp_result.get("url")
                result["wordpress_media_id"] = wp_result.get("media_id")
        except Exception as e:
            result["wordpress_upload"] = {"success": False, "error": str(e)}

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
        # Reference images require Gemini pro - override provider/quality if refs provided
        if (reference_image or reference_images) and not PROVIDERS[provider]["supports_references"].get(quality, False):
            provider = "gemini"
            quality = "pro"

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
    # Add timing guidance based on queue size
    queue_size = batch_result.get("queue_size", 0)
    if queue_size > 0:
        est_minutes = round(queue_size * 48 / 60, 1)  # ~48 seconds per image average
        batch_result["run_batch_time_estimate"] = f"When you call run_batch, expect it to take approximately {est_minutes} minutes for {queue_size} images. This is normal - do not assume the call failed."
    return batch_result

def remove_from_batch(identifier):
    cmd = ["python3", CFG["batch_manager_script"], "remove", str(identifier)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(result.stdout)

def view_batch_queue():
    cmd = ["python3", CFG["batch_manager_script"], "view"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(result.stdout)

def run_batch(convert_to_webp=True, webp_quality=85, upload_to_wordpress=False, wp_url=None):
    # Count queue items for time estimate
    queue_size = 0
    try:
        with open(CFG["queue_file"], 'r') as f:
            queue_data = json.load(f)
            queue_size = len(queue_data) if isinstance(queue_data, list) else 0
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    if queue_size == 0:
        return {"success": False, "error": "Batch queue is empty. Use add_to_batch to queue images first."}

    env = os.environ.copy()
    cmd = ["python3", CFG["batch_generate_script"], CFG["queue_file"], CFG["batch_dir"]]
    if convert_to_webp:
        cmd.extend(["--convert-to-webp", "--webp-quality", str(webp_quality), "--webp-dir", CFG["webp_dir"]])

    # Send progress notification so the client knows we're working
    debug_log(f"Starting batch generation of {queue_size} images (estimated {queue_size * 45 + queue_size * 3} seconds)")

    result = subprocess.run(cmd, capture_output=True, text=True, env=env)

    # Parse batch_results.json for file paths and summary stats
    files = []
    total_size = 0
    webp_converted = 0
    batch_results = []
    results_file = os.path.join(CFG["batch_dir"], "batch_results.json")
    try:
        with open(results_file, 'r') as f:
            batch_results = json.load(f)
        for r in batch_results:
            if r.get("status") == "success":
                if r.get("webp_path"):
                    files.append(r["webp_path"])
                    total_size += r.get("webp_size", 0)
                    webp_converted += 1
                elif r.get("path"):
                    files.append(r["path"])
                    try:
                        total_size += os.path.getsize(r["path"])
                    except OSError:
                        pass
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    response = {
        "success": result.returncode == 0,
        "files": files,
        "summary": {
            "count": len(files),
            "total_size_bytes": total_size,
            "webp_converted": webp_converted,
        },
        "output": result.stdout,
        "error": result.stderr if result.returncode != 0 else None
    }

    # WordPress upload if requested
    if upload_to_wordpress and wp_url and files:
        uploaded = []
        failed = []
        # Build lookup from file path to batch_results index for updating
        results_by_file = {}
        for idx, r in enumerate(batch_results):
            if r.get("webp_path"):
                results_by_file[r["webp_path"]] = idx
            if r.get("path"):
                results_by_file[r["path"]] = idx

        for file_path in files:
            try:
                wp_result = _upload_single_to_wordpress(file_path, wp_url)
                if wp_result.get("success"):
                    uploaded.append(wp_result)
                    # Update batch_results with WordPress info
                    if file_path in results_by_file:
                        idx = results_by_file[file_path]
                        batch_results[idx]["wordpress_url"] = wp_result.get("url")
                        batch_results[idx]["wordpress_media_id"] = wp_result.get("media_id")
                else:
                    failed.append(wp_result)
            except Exception as e:
                failed.append({"filename": os.path.basename(file_path), "success": False, "error": str(e)})

        # Write updated batch_results.json with WordPress info
        if batch_results:
            try:
                with open(results_file, 'w') as f:
                    json.dump(batch_results, f, indent=2)
            except Exception:
                pass

        response["wordpress_upload"] = {
            "uploaded": uploaded,
            "failed": failed,
            "total_uploaded": len(uploaded),
            "total_failed": len(failed)
        }

    return response

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

def _normalize_url(url):
    """Normalize a URL: lowercase scheme and host, preserve path case, strip trailing slash."""
    from urllib.parse import urlparse, urlunparse
    parsed = urlparse(url if "://" in url else f"https://{url}")
    normalized = urlunparse((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        parsed.path,
        parsed.params,
        parsed.query,
        parsed.fragment,
    ))
    return normalized.rstrip("/")


def _get_wordpress_config(wp_url):
    """Look up WordPress config from config.json by URL.

    Returns:
        (normalized_url, user, password, alt_text_prefix)
    """
    wp_sites = CFG.get("wordpress", {})
    normalized_url = _normalize_url(wp_url)
    # Build a case-insensitive lookup: normalize each config key's domain
    site_cfg = None
    for cfg_url, cfg_val in wp_sites.items():
        if _normalize_url(cfg_url) == normalized_url:
            site_cfg = cfg_val
            break
    if not site_cfg:
        raise Exception(f"No WordPress credentials found in config.json for '{wp_url}'. Add a 'wordpress' entry with user and password.")
    wp_user = site_cfg.get("user")
    wp_password = site_cfg.get("password")
    if not wp_user or not wp_password:
        raise Exception(f"WordPress config for '{wp_url}' is missing 'user' or 'password' in config.json.")
    alt_text_prefix = site_cfg.get("alt_text_prefix", "")
    return normalized_url, wp_user, wp_password, alt_text_prefix


def _get_wordpress_credentials(wp_url):
    """Look up WordPress credentials from config.json by URL (legacy wrapper)."""
    normalized_url, wp_user, wp_password, _ = _get_wordpress_config(wp_url)
    return normalized_url, wp_user, wp_password


def _upload_single_to_wordpress(file_path, wp_url):
    """Upload a single image file to WordPress media library."""
    normalized_url, wp_user, wp_password, alt_text_prefix = _get_wordpress_config(wp_url)

    filename = os.path.basename(file_path)
    # Generate alt text from filename (strip extension, replace separators with spaces)
    base_name = os.path.splitext(filename)[0]
    alt_text_base = base_name.replace("-", " ").replace("_", " ")
    alt_text = f"{alt_text_prefix}{alt_text_base}" if alt_text_prefix else alt_text_base

    mime_type = "image/webp" if file_path.endswith(".webp") else get_mime_type(file_path)

    with open(file_path, 'rb') as f:
        files = {'file': (filename, f, mime_type)}
        data = {'alt_text': alt_text}
        response = requests.post(
            f"{normalized_url}/wp-json/wp/v2/media",
            auth=(wp_user, wp_password),
            files=files,
            data=data
        )

    if response.status_code == 201:
        media_data = response.json()
        return {
            "success": True,
            "alt_text": alt_text,
            "filename": filename,
            "media_id": media_data['id'],
            "url": media_data['source_url'],
            "title": media_data['title']['rendered']
        }
    else:
        return {
            "success": False,
            "filename": filename,
            "error": f"HTTP {response.status_code}: {response.text}"
        }


def upload_to_wordpress(wp_url, directory="webp", limit=10):
    from pathlib import Path

    # Look up credentials from config.json wordpress section
    normalized_url, wp_user, wp_password = _get_wordpress_credentials(wp_url)

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

def get_generated_webp_images(directory="webp", limit=10):
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


def get_media_id_map(directory="batch", output_format="json"):
    """Get metadata mapping for uploaded images without returning image data.

    Reads batch_results.json to extract WordPress upload metadata.
    Useful for getting media IDs to set featured images on posts.

    Args:
        directory: Subdirectory within images_dir (default: "batch")
        output_format: "json" (default), "yaml", or "python_dict"

    Returns:
        Mapping of filename to metadata (media_id, url, file_size, upload_timestamp)
    """
    from pathlib import Path

    batch_dir = os.path.join(CFG["images_dir"], directory)
    results_file = os.path.join(batch_dir, "batch_results.json")

    media_map = {}

    # Read batch_results.json for WordPress metadata
    try:
        with open(results_file, 'r') as f:
            batch_results = json.load(f)

        for r in batch_results:
            if r.get("status") != "success":
                continue

            # Determine which file to use (prefer webp)
            file_path = r.get("webp_path") or r.get("path")
            if not file_path:
                continue

            filename = os.path.basename(file_path)
            entry = {
                "file_path": file_path,
                "file_size": r.get("webp_size") or 0,
            }

            # Add WordPress metadata if uploaded
            if r.get("wordpress_media_id"):
                entry["wordpress_media_id"] = r["wordpress_media_id"]
                entry["wordpress_url"] = r.get("wordpress_url")

            # Try to get file modification time as upload timestamp
            if os.path.exists(file_path):
                entry["file_size"] = os.path.getsize(file_path)
                entry["modified_time"] = datetime.fromtimestamp(
                    os.path.getmtime(file_path)
                ).strftime("%Y-%m-%d %H:%M:%S")

            # Add generation metadata
            if r.get("provider"):
                entry["provider"] = r["provider"]
            if r.get("aspect_ratio"):
                entry["aspect_ratio"] = r["aspect_ratio"]

            media_map[filename] = entry

    except (FileNotFoundError, json.JSONDecodeError):
        # Fall back to scanning directory for files
        image_files = sorted(Path(batch_dir).glob("*.webp"), key=os.path.getmtime, reverse=True)
        for img_path in image_files:
            filename = img_path.name
            media_map[filename] = {
                "file_path": str(img_path),
                "file_size": os.path.getsize(img_path),
                "modified_time": datetime.fromtimestamp(
                    os.path.getmtime(img_path)
                ).strftime("%Y-%m-%d %H:%M:%S"),
            }

    # Format output
    if output_format == "yaml":
        try:
            import yaml
            formatted = yaml.dump(media_map, default_flow_style=False, sort_keys=False)
        except ImportError:
            formatted = json.dumps(media_map, indent=2)
            output_format = "json (yaml not available)"
    elif output_format == "python_dict":
        formatted = repr(media_map)
    else:
        formatted = json.dumps(media_map, indent=2)

    return {
        "success": True,
        "format": output_format,
        "count": len(media_map),
        "media_map": media_map,
        "formatted": formatted
    }


def list_wordpress_sites():
    """List WordPress sites available for image uploads.

    Returns URLs from config.json wordpress section.
    Credentials are stored in config.json, not exposed here.
    """
    sites = []

    if "wordpress" in CFG and isinstance(CFG["wordpress"], dict):
        sites = sorted(list(CFG["wordpress"].keys()))

    return {
        "success": True,
        "sites": sites,
        "count": len(sites),
        "note": "Use these URLs with upload_to_wordpress or generate_image with upload_to_wordpress=true"
    }


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
STYLE_HINT_ENUM = ["general", "photo", "illustration", "text", "infographic"]

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
                            "directory": {"type": "string", "description": "Directory to scan (default: webp)", "default": "webp"},
                            "limit": {"type": "integer", "description": "Maximum number of images to return", "default": 10}
                        },
                        "required": []
                    }
                },
                {
                    "name": "get_media_id_map",
                    "description": "Get metadata mapping for uploaded images without returning image data. Returns filename to WordPress media ID mapping, file sizes, and timestamps. Useful for setting featured images on posts.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "directory": {"type": "string", "description": "Directory to scan (default: batch)", "default": "batch"},
                            "output_format": {"type": "string", "description": "Output format: 'json' (default), 'yaml', or 'python_dict'", "enum": ["json", "yaml", "python_dict"], "default": "json"}
                        },
                        "required": []
                    }
                },
                {
                    "name": "generate_image",
                    "description": "Generate a single image immediately. Supports multiple providers: 'gemini' (default, Google Gemini), 'openai' (gpt-image-1), 'together' (FLUX models). Use quality='pro' for high-quality or 'fast' for cheaper/quicker generation. NOTE: Image generation takes 15-90 seconds per image depending on provider and quality. This is normal - do NOT assume the call has failed while it is still running. If reference images are provided, the provider will automatically be set to Gemini pro (the only provider that supports reference images).",
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
                            "media_resolution": {"type": "string", "description": "Media resolution control for input processing (Gemini only): 'low', 'medium', 'high'", "enum": ["low", "medium", "high"]},
                            "model": {"type": "string", "description": "Together AI model alias. Overrides provider/quality. Options: " + ", ".join(TOGETHER_MODEL_ALIASES), "enum": TOGETHER_MODEL_ALIASES},
                            "auto_mode": {"type": "string", "description": "Auto-select the best model based on cost tier and constraints. Overrides provider/quality/model. Options: cheapest, budget, balanced, quality, best", "enum": AUTO_MODE_ENUM},
                            "style_hint": {"type": "string", "description": "Style preference for auto_mode model selection: 'general' (default), 'photo' (photorealistic), 'illustration' (art/drawings), 'text' (text in image matters), 'infographic' (charts, graphs, data visualizations)", "enum": STYLE_HINT_ENUM, "default": "general"},
                            "convert_to_webp": {"type": "boolean", "description": "Convert generated image to WebP format immediately after generation", "default": True},
                            "webp_quality": {"type": "integer", "description": "WebP quality (0-100) when convert_to_webp is enabled", "default": 85, "minimum": 0, "maximum": 100},
                            "upload_to_wordpress": {"type": "boolean", "description": "Upload the generated image to WordPress immediately after generation", "default": False},
                            "wp_url": {"type": "string", "description": "WordPress site URL (e.g., https://example.com). Required if upload_to_wordpress is true. Must match an entry in config.json wordpress section."}
                        },
                        "required": ["prompt"]
                    }
                },
                {
                    "name": "add_to_batch",
                    "description": "Add an image to the batch queue for later generation. Supports providers: 'gemini' (default), 'openai', 'together'. If reference images are provided, the provider will automatically be set to Gemini pro (the only provider that supports reference images). Note: when you later call run_batch, expect 30-90 seconds per queued image.",
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
                            "media_resolution": {"type": "string", "description": "Media resolution control for input processing (Gemini only): 'low', 'medium', 'high'", "enum": ["low", "medium", "high"]},
                            "model": {"type": "string", "description": "Together AI model alias. Overrides provider/quality. Options: " + ", ".join(TOGETHER_MODEL_ALIASES), "enum": TOGETHER_MODEL_ALIASES},
                            "auto_mode": {"type": "string", "description": "Auto-select the best model based on cost tier and constraints. Overrides provider/quality/model.", "enum": AUTO_MODE_ENUM},
                            "style_hint": {"type": "string", "description": "Style preference for auto_mode: 'general', 'photo', 'illustration', 'text', 'infographic'", "enum": STYLE_HINT_ENUM, "default": "general"}
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
                    "description": "Execute batch generation for all queued images. IMPORTANT: This call takes a long time - typically 30-90 seconds PER IMAGE in the queue, plus API delays between images. A batch of 10 images can take 5-15 minutes. This is completely normal. Do NOT assume the call has failed or timed out - wait for it to complete. If you need to check progress while a batch is running, use view_batch_queue (items are removed as they complete) or get_generation_cost (logged as each image finishes).",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "convert_to_webp": {"type": "boolean", "description": "Convert each generated image to WebP immediately after generation", "default": True},
                            "webp_quality": {"type": "integer", "description": "WebP quality (0-100) when convert_to_webp is enabled", "default": 85, "minimum": 0, "maximum": 100},
                            "upload_to_wordpress": {"type": "boolean", "description": "Upload all generated images to WordPress after batch completes", "default": False},
                            "wp_url": {"type": "string", "description": "WordPress site URL (e.g., https://example.com). Required if upload_to_wordpress is true. Must match an entry in config.json wordpress section."}
                        },
                        "required": []
                    }
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
                            "style_hint": {"type": "string", "description": "Style preference for auto_mode: 'general', 'photo', 'illustration', 'text', 'infographic'", "enum": STYLE_HINT_ENUM, "default": "general"}
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
                            "directory": {"type": "string", "description": "Directory containing images (default: webp)", "default": "webp"},
                            "limit": {"type": "integer", "description": "Maximum number of images to upload", "default": 10}
                        },
                        "required": ["wp_url"]
                    }
                },
                {
                    "name": "list_wordpress_sites",
                    "description": "List WordPress sites configured for image uploads. Returns URLs only (credentials are stored securely in config.json). Use these URLs with upload_to_wordpress or generate_image with upload_to_wordpress=true.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                },
                {
                    "name": "get_generation_cost",
                    "description": "Query cost information from the generation log. Search by filename or date range. Returns matching records and total cost for auditing and cost tracking.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "filename": {"type": "string", "description": "Image filename (with or without .png extension) to look up"},
                            "start_datetime": {"type": "string", "description": "Start of date range (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)"},
                            "end_datetime": {"type": "string", "description": "End of date range (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)"}
                        },
                        "required": []
                    }
                }
            ]
        }
    })

def handle_tool_call(request_id, tool_name, arguments):
    debug_log(f"Tool call: {tool_name} with args: {json.dumps(arguments)}")
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
                arguments.get("style_hint", "general"),
                arguments.get("convert_to_webp", True),
                arguments.get("webp_quality", 85),
                arguments.get("upload_to_wordpress", False),
                arguments.get("wp_url")
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
            result = run_batch(
                arguments.get("convert_to_webp", True),
                arguments.get("webp_quality", 85),
                arguments.get("upload_to_wordpress", False),
                arguments.get("wp_url")
            )
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
            result = get_generated_webp_images(arguments.get("directory", "webp"), arguments.get("limit", 10))
        elif tool_name == "get_media_id_map":
            result = get_media_id_map(
                arguments.get("directory", "batch"),
                arguments.get("output_format", "json")
            )
        elif tool_name == "upload_to_wordpress":
            result = upload_to_wordpress(
                arguments.get("wp_url"),
                arguments.get("directory", "webp"),
                arguments.get("limit", 10)
            )
        elif tool_name == "list_wordpress_sites":
            result = list_wordpress_sites()
        elif tool_name == "get_generation_cost":
            result = get_cost_from_log(
                arguments.get("filename"),
                arguments.get("start_datetime"),
                arguments.get("end_datetime")
            )
        else:
            raise Exception(f"Unknown tool: {tool_name}")

        debug_log(f"Tool {tool_name} completed successfully")
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"content": [{"type": "text", "text": json.dumps(result)}]}
        }
    except Exception as e:
        debug_log(f"Tool {tool_name} failed: {str(e)}\n{traceback.format_exc()}", "ERROR")
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32000, "message": str(e)}
        }
    send_message(response)

def main():
    sys.stderr.write("PeeperFrog Create MCP Server v0.1 - Multi-Provider (Gemini/OpenAI/Together)\n")
    sys.stderr.flush()
    debug_log("Server starting")

    while True:
        try:
            message = read_message()
            if message is None:
                debug_log("Received EOF, shutting down")
                break

            method = message.get("method")
            request_id = message.get("id")
            debug_log(f"Received message: method={method}, id={request_id}")

            if method == "initialize":
                handle_initialize(request_id)
            elif method == "tools/list":
                handle_tools_list(request_id)
            elif method == "tools/call":
                params = message.get("params", {})
                handle_tool_call(request_id, params.get("name"), params.get("arguments", {}))
            elif method == "notifications/initialized":
                debug_log("Client initialized notification received")

        except Exception as e:
            debug_log(f"Main loop error: {str(e)}\n{traceback.format_exc()}", "ERROR")
            sys.stderr.write(f"Error: {str(e)}\n")
            sys.stderr.flush()

if __name__ == "__main__":
    main()
