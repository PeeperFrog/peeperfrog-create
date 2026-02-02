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
import requests
import subprocess

# Load config from same directory as this script
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config.json")

def load_config():
    with open(CONFIG_PATH, 'r') as f:
        cfg = json.load(f)
    for key in ("images_dir", "batch_manager_script"):
        if key in cfg:
            cfg[key] = os.path.expanduser(cfg[key])
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
        generation_config["mediaResolution"] = opts["media_resolution"].upper()

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
        "quality": openai_quality, "n": 1, "response_format": "b64_json",
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

        except Exception as e:
            result = {"filename": filename, "status": "error", "error": str(e)}
            print(f"Error: {str(e)}")

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
