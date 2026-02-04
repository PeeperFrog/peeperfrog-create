#!/usr/bin/env python3
# Copyright (c) 2025 PeeperFrog
# Licensed under the Apache License, Version 2.0. See LICENSE file for details.
"""
Batch image generation - v0.1
Multi-provider support: Gemini, OpenAI, Together AI (FLUX).
"""
import os
import json
import time
import base64
import csv
import requests
import subprocess
from datetime import datetime

# Load config from same directory as this script
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config.json")

# imagen-4 models only support fixed resolutions
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

def _parse_aspect_ratio(aspect_ratio):
    """Parse aspect ratio string (e.g., '16:9', '2.35:1') into (width_ratio, height_ratio) floats."""
    if ':' in aspect_ratio:
        parts = aspect_ratio.split(':')
        return float(parts[0]), float(parts[1])
    return 1.0, 1.0

def _get_imagen4_resolution(aspect_ratio, image_size):
    """Find the closest imagen-4 supported resolution for the requested aspect ratio and size."""
    w_ratio, h_ratio = _parse_aspect_ratio(aspect_ratio)
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
            size_penalty = 0 if mp >= 3.0 else 0.8
        elif image_size == "large":
            size_penalty = 0 if 0.8 <= mp <= 2.0 else 0.3
        else:
            size_penalty = 0 if mp <= 1.5 else 0.5

        score = ratio_diff + size_penalty

        if score < best_score:
            best_score = score
            best_match = (w, h)

    return best_match

def load_config():
    with open(CONFIG_PATH, 'r') as f:
        cfg = json.load(f)
    config_dir = os.path.dirname(os.path.abspath(CONFIG_PATH))
    for key in ("images_dir", "batch_manager_script"):
        if key in cfg:
            cfg[key] = os.path.expanduser(cfg[key])
            if not os.path.isabs(cfg[key]):
                cfg[key] = os.path.join(config_dir, cfg[key])
    return cfg

CFG = load_config()

# --- Pricing ---
PRICING_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pricing.json")

def load_pricing():
    try:
        with open(PRICING_PATH, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

PRICING = load_pricing()

# --- Generation Log ---
LOG_FILE = os.path.join(os.path.expanduser(CFG.get("images_dir", "~/Pictures/ai-generated-images")), "generation_log.csv")
LOG_HEADER = ["datetime", "filename", "status", "cost_usd", "provider", "quality", "aspect_ratio"]

def ensure_log_exists():
    """Create log file with header if it doesn't exist."""
    if not os.path.exists(LOG_FILE):
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(LOG_HEADER)

def log_generation(filename, status, cost_usd=None, provider=None, quality=None, aspect_ratio=None):
    """Append a generation record to the CSV log."""
    ensure_log_exists()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            timestamp,
            filename,
            status,
            f"{cost_usd:.6f}" if cost_usd is not None else "",
            provider or "",
            quality or "",
            aspect_ratio or ""
        ])

def get_cost_from_log(filename=None, start_datetime=None, end_datetime=None):
    """
    Query cost from generation log by filename or date/time range.

    Args:
        filename: Image filename (with or without .png extension)
        start_datetime: Start of date range (ISO format: YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)
        end_datetime: End of date range (ISO format: YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)

    Returns:
        dict with matching records and total cost
    """
    if not os.path.exists(LOG_FILE):
        return {"error": "Log file not found", "records": [], "total_cost": 0}

    # Normalize filename (strip extension)
    search_name = None
    if filename:
        search_name = filename.rsplit('.', 1)[0] if '.' in filename else filename

    # Parse date range
    start_dt = None
    end_dt = None
    if start_datetime:
        try:
            if len(start_datetime) == 10:  # YYYY-MM-DD
                start_dt = datetime.strptime(start_datetime, "%Y-%m-%d")
            else:
                start_dt = datetime.strptime(start_datetime, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return {"error": f"Invalid start_datetime format: {start_datetime}"}
    if end_datetime:
        try:
            if len(end_datetime) == 10:  # YYYY-MM-DD
                end_dt = datetime.strptime(end_datetime, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            else:
                end_dt = datetime.strptime(end_datetime, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return {"error": f"Invalid end_datetime format: {end_datetime}"}

    records = []
    total_cost = 0.0

    with open(LOG_FILE, 'r', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Check filename match
            if search_name:
                row_name = row["filename"].rsplit('.', 1)[0] if '.' in row["filename"] else row["filename"]
                if row_name != search_name:
                    continue

            # Check date range
            if start_dt or end_dt:
                try:
                    row_dt = datetime.strptime(row["datetime"], "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    continue
                if start_dt and row_dt < start_dt:
                    continue
                if end_dt and row_dt > end_dt:
                    continue

            records.append(row)
            if row["cost_usd"]:
                try:
                    total_cost += float(row["cost_usd"])
                except ValueError:
                    pass

    return {
        "records": records,
        "count": len(records),
        "total_cost": round(total_cost, 6),
        "log_file": LOG_FILE
    }

def estimate_cost(provider, quality, image_size, aspect_ratio, num_reference_images=0, search_grounding=False, thinking_level=None, model_alias=None):
    """Estimate cost in USD for a single image generation."""
    if not PRICING:
        return None
    providers = PRICING.get("providers", {})

    if provider == "gemini":
        size_map = {"small": "1K", "medium": "2K", "large": "2K", "xlarge": "4K"}
        gemini_size = "1K" if quality == "fast" else size_map.get(image_size, "2K")
        model_key = PROVIDERS["gemini"]["models"][quality]
        mp = providers.get("gemini", {}).get("models", {}).get(model_key, {})
        if not mp:
            return None
        base = mp.get("per_image_cost", {}).get(gemini_size, 0)
        ref_cost = num_reference_images * mp.get("reference_image_cost_each", 0)
        grounding_cost = mp.get("search_grounding_cost_per_query", 0) if search_grounding else 0
        thinking_cost = 0
        if thinking_level and quality == "pro":
            thinking_cost = mp.get("thinking_token_overhead", {}).get(thinking_level.lower(), 0)
        return round(base + mp.get("text_input_per_image_estimate", 0) + ref_cost + grounding_cost + thinking_cost, 6)

    elif provider == "openai":
        oq = "high" if quality == "pro" else "low"
        ar_map = {"1:1": "1024x1024", "16:9": "1536x1024", "9:16": "1024x1536", "4:3": "1536x1024", "3:4": "1024x1536"}
        res = ar_map.get(aspect_ratio, "1024x1024")
        model_key = PROVIDERS["openai"]["models"][quality]
        mp = providers.get("openai", {}).get("models", {}).get(model_key, {})
        if not mp:
            return None
        return round(mp.get("per_image_cost", {}).get(oq, {}).get(res, 0) + mp.get("text_input_per_image_estimate", 0), 6)

    elif provider == "together":
        if model_alias and model_alias in TOGETHER_MODELS:
            per_mp = TOGETHER_MODELS[model_alias]["cost_per_mp"]
        else:
            model_key = PROVIDERS["together"]["models"][quality]
            mp = providers.get("together", {}).get("models", {}).get(model_key, {})
            if not mp:
                return None
            per_mp = mp.get("per_megapixel_cost", 0)
        ar_sizes = {
            "1:1":  {"small": (512, 512),   "medium": (1024, 1024), "large": (1024, 1024), "xlarge": (2048, 2048)},
            "16:9": {"small": (576, 320),    "medium": (1024, 576),  "large": (1024, 576),  "xlarge": (1920, 1080)},
            "9:16": {"small": (320, 576),    "medium": (576, 1024),  "large": (576, 1024),  "xlarge": (1080, 1920)},
            "4:3":  {"small": (512, 384),    "medium": (1024, 768),  "large": (1024, 768),  "xlarge": (2048, 1536)},
            "3:4":  {"small": (384, 512),    "medium": (768, 1024),  "large": (768, 1024),  "xlarge": (1536, 2048)},
        }
        sizes = ar_sizes.get(aspect_ratio, ar_sizes["1:1"])
        w, h = sizes.get(image_size, sizes["large"])
        return round((w * h / 1_000_000) * per_mp, 6)

    return None

# --- Provider configs ---
PROVIDERS = {
    "gemini": {
        "models": {"pro": "gemini-3-pro-image-preview", "fast": "gemini-2.5-flash-image"},
        "env_key": "GEMINI_API_KEY",
    },
    "openai": {
        "models": {"pro": "gpt-image-1", "fast": "gpt-image-1"},
        "env_key": "OPENAI_API_KEY",
    },
    "together": {
        "models": {"pro": "black-forest-labs/FLUX.1-pro", "fast": "black-forest-labs/FLUX.1-schnell"},
        "env_key": "TOGETHER_API_KEY",
    },
}

# Together AI model aliases (same as image_server.py)
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

def get_mime_type(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif"}
    return mime_map.get(ext, "image/png")

def remove_from_queue(filename):
    cmd = ["python3", CFG["batch_manager_script"], "remove", filename]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  Removed from queue: {filename}")
    else:
        print(f"  Warning: Could not remove from queue: {filename}")

def encode_reference_images(ref_list):
    """Encode a list of reference image paths into inlineData parts."""
    parts = []
    for ref_path_raw in ref_list:
        ref_path = os.path.expanduser(ref_path_raw)
        if not os.path.exists(ref_path):
            raise Exception(f"Reference image not found: {ref_path}")
        with open(ref_path, 'rb') as rf:
            img_b64 = base64.b64encode(rf.read()).decode('utf-8')
        parts.append({"inlineData": {"mimeType": get_mime_type(ref_path), "data": img_b64}})
    return parts

# --- Provider-specific generation ---

def _generate_gemini(prompt, aspect_ratio, image_size, quality, reference_images, api_key, gemini_opts=None):
    model = PROVIDERS["gemini"]["models"][quality]
    size_map = {"small": "1K", "medium": "2K", "large": "2K", "xlarge": "4K"}
    gemini_size = size_map.get(image_size, "2K")

    parts = encode_reference_images(reference_images)
    parts.append({"text": prompt})

    image_config = {"aspectRatio": aspect_ratio}
    if quality == "pro":
        image_config["imageSize"] = gemini_size

    generation_config = {
        "responseModalities": ["TEXT", "IMAGE"],
        "imageConfig": image_config
    }

    opts = gemini_opts or {}

    if opts.get("media_resolution"):
        generation_config["mediaResolution"] = f"MEDIA_RESOLUTION_{opts['media_resolution'].upper()}"

    if opts.get("thinking_level") and quality == "pro":
        generation_config["thinkingConfig"] = {"thinkingLevel": opts["thinking_level"].lower()}

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": generation_config
    }

    if opts.get("search_grounding"):
        payload["tools"] = [{"google_search": {}}]

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
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


def _generate_openai(prompt, aspect_ratio, quality, api_key):
    model = PROVIDERS["openai"]["models"][quality]
    size_map = {
        "1:1": "1024x1024", "16:9": "1536x1024", "9:16": "1024x1536",
        "4:3": "1536x1024", "3:4": "1024x1536",
    }
    size = size_map.get(aspect_ratio, "1024x1024")
    openai_quality = "high" if quality == "pro" else "low"

    payload = {
        "model": model, "prompt": prompt, "size": size,
        "quality": openai_quality, "n": 1, "output_format": "png",
    }

    response = requests.post(
        "https://api.openai.com/v1/images/generations",
        json=payload,
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'}
    )
    if response.status_code != 200:
        raise Exception(f"OpenAI API error: {response.status_code} - {response.text}")

    data = response.json()
    return data['data'][0]['b64_json'], model, size


def _generate_together(prompt, aspect_ratio, image_size, quality, api_key, model_alias=None):
    if model_alias and model_alias in TOGETHER_MODELS:
        model_info = TOGETHER_MODELS[model_alias]
        model = model_info["id"]
        steps = model_info["steps"]
    else:
        model = PROVIDERS["together"]["models"][quality]
        steps = 4 if quality == "fast" else 28

    # imagen-4 models require specific fixed resolutions
    is_imagen4 = model_alias and model_alias.startswith("imagen4")
    if is_imagen4:
        width, height = _get_imagen4_resolution(aspect_ratio, image_size)
    else:
        ar_sizes = {
            "1:1":  {"small": (512, 512),   "medium": (1024, 1024), "large": (1024, 1024), "xlarge": (2048, 2048)},
            "16:9": {"small": (576, 320),    "medium": (1024, 576),  "large": (1024, 576),  "xlarge": (1920, 1080)},
            "9:16": {"small": (320, 576),    "medium": (576, 1024),  "large": (576, 1024),  "xlarge": (1080, 1920)},
            "4:3":  {"small": (512, 384),    "medium": (1024, 768),  "large": (1024, 768),  "xlarge": (2048, 1536)},
            "3:4":  {"small": (384, 512),    "medium": (768, 1024),  "large": (768, 1024),  "xlarge": (1536, 2048)},
        }
        sizes = ar_sizes.get(aspect_ratio, ar_sizes["1:1"])
        width, height = sizes.get(image_size, sizes["large"])

    payload = {
        "model": model, "prompt": prompt, "width": width, "height": height,
        "n": 1, "response_format": "b64_json",
    }
    if steps > 0:
        payload["steps"] = steps

    response = requests.post(
        "https://api.together.xyz/v1/images/generations",
        json=payload,
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'}
    )
    if response.status_code != 200:
        raise Exception(f"Together API error: {response.status_code} - {response.text}")

    data = response.json()
    return data['data'][0]['b64_json'], model, f"{width}x{height}"


def generate_images_batch(prompts_file, output_dir):
    prompts_data = json.load(open(prompts_file, 'r'))
    prompts = prompts_data.get('prompts', [])
    if not prompts:
        print("No prompts found in file")
        return

    print(f"Generating {len(prompts)} images...")
    delay = CFG.get("api_delay_seconds", 3)
    results = []

    for i, prompt_data in enumerate(prompts, 1):
        prompt = prompt_data.get('prompt')
        filename = prompt_data.get('filename', f'image_{i}.png')
        queue_filename = filename
        if not filename.endswith('.png'):
            filename = f"{filename}.png"
        aspect_ratio = prompt_data.get('aspect_ratio', '1:1')
        image_size = prompt_data.get('image_size', 'large')
        quality = prompt_data.get('quality', 'pro')
        provider = prompt_data.get('provider', 'gemini')

        model_alias = prompt_data.get('model')
        if model_alias and model_alias in TOGETHER_MODELS:
            provider = 'together'

        if provider not in PROVIDERS:
            provider = 'gemini'
        if quality not in ('pro', 'fast'):
            quality = 'pro'

        model = TOGETHER_MODELS[model_alias]["id"] if (model_alias and model_alias in TOGETHER_MODELS) else PROVIDERS[provider]["models"][quality]
        env_key = PROVIDERS[provider]["env_key"]
        api_key = os.environ.get(env_key)
        if not api_key:
            print(f"  Skipping: {env_key} not set for provider '{provider}'")
            results.append({"filename": filename, "status": "error", "error": f"{env_key} not set"})
            continue

        # Reference images (Gemini pro only)
        reference_images = []
        if provider == "gemini" and quality == "pro":
            reference_images = prompt_data.get('reference_images', [])
            if not reference_images:
                single = prompt_data.get('reference_image')
                if single:
                    reference_images = [single]

        print(f"\n[{i}/{len(prompts)}] Generating: {filename} [{provider}/{quality}]")
        print(f"Prompt: {prompt[:80]}...")
        print(f"Model: {model} | Aspect Ratio: {aspect_ratio}")
        if reference_images:
            print(f"Reference images: {len(reference_images)}")

        gemini_opts = prompt_data.get('gemini_opts')

        try:
            if provider == "gemini":
                image_data, model_used, resolution = _generate_gemini(prompt, aspect_ratio, image_size, quality, reference_images, api_key, gemini_opts)
            elif provider == "openai":
                image_data, model_used, resolution = _generate_openai(prompt, aspect_ratio, quality, api_key)
            elif provider == "together":
                image_data, model_used, resolution = _generate_together(prompt, aspect_ratio, image_size, quality, api_key, model_alias)
            else:
                raise Exception(f"Unknown provider: {provider}")

            output_path = os.path.join(output_dir, filename)
            with open(output_path, 'wb') as f:
                f.write(base64.b64decode(image_data))

            opts = gemini_opts or {}
            cost = estimate_cost(provider, quality, image_size, aspect_ratio, len(reference_images), opts.get("search_grounding", False), opts.get("thinking_level"), model_alias)
            result = {
                "filename": filename, "status": "success", "path": output_path,
                "provider": provider, "resolution": resolution, "aspect_ratio": aspect_ratio,
                "reference_images_used": len(reference_images)
            }
            if cost is not None:
                result["estimated_cost_usd"] = cost
            print(f"Saved to: {output_path}")
            remove_from_queue(queue_filename)
            log_generation(filename, "success", cost, provider, quality, aspect_ratio)

        except Exception as e:
            result = {"filename": filename, "status": "error", "error": str(e)}
            print(f"Error: {str(e)}")
            log_generation(filename, f"error: {str(e)[:50]}", None, provider, quality, aspect_ratio)

        results.append(result)

        if i < len(prompts):
            print(f"Waiting {delay} seconds...")
            time.sleep(delay)

    results_file = os.path.join(output_dir, 'batch_results.json')
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)

    total_cost = sum(r.get("estimated_cost_usd", 0) for r in results if r["status"] == "success")

    print(f"\n{'='*60}")
    print(f"Batch complete!")
    print(f"Total: {len(prompts)} images")
    print(f"Success: {sum(1 for r in results if r['status'] == 'success')}")
    print(f"Failed: {sum(1 for r in results if r['status'] == 'error')}")
    if total_cost > 0:
        print(f"Estimated total cost: ${total_cost:.4f}")
    print(f"Results saved to: {results_file}")
    print(f"{'='*60}")

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python3 batch_generate.py <prompts.json> [output_dir]")
        sys.exit(1)

    prompts_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(CFG["images_dir"], CFG.get("batch_subdir", "batch"))

    os.makedirs(output_dir, exist_ok=True)

    generate_images_batch(prompts_file, output_dir)
