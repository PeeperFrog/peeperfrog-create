---
name: image-manual-control
description: Generate images with full manual control over provider, model, quality, and advanced features
---

# Image Generation -- Manual Control

**Purpose:** Generate AI images with explicit control over which provider, model, and settings are used. Access all provider-specific features like Gemini thinking levels, search grounding, and media resolution.

**Use this skill when:** You need a specific provider/model, want Gemini-only features, or need full control over generation parameters.

**See also:** Use **image-auto-mode** skill when you just want the best image for a budget without choosing models manually.

---

## Providers & Models

### Provider Overview

| Provider | Quality Tiers | Reference Images | Max Resolution | Cost Range |
|----------|--------------|------------------|----------------|------------|
| **gemini** (default) | Pro: Gemini 3 Pro, Fast: Gemini 2.5 Flash | Up to 14 (Pro only) | 4K (Pro), 1K (Fast) | $0.039 - $0.24/image |
| **openai** | Pro: high quality, Fast: low quality | Not supported | 1536x1024 | $0.011 - $0.25/image |
| **together** | Pro: FLUX.1-pro, Fast: FLUX.1-schnell + 20 model aliases | Not supported | 2048x2048 | $0.0006 - $0.08/MP |

### Gemini

**Pro** (`provider: "gemini", quality: "pro"`):
- Model: Gemini 3 Pro Image Preview
- Resolutions: 1K, 2K (default), 4K
- Reference images: up to 14
- Search grounding: yes
- Thinking levels: minimal, low, medium, high
- Media resolution control: low, medium, high, auto
- Best text rendering among Gemini tiers
- Cost: $0.134-$0.24/image depending on resolution

**Fast** (`provider: "gemini", quality: "fast"`):
- Model: Gemini 2.5 Flash Image
- Resolution: 1024x1024 only (ignores image_size)
- No reference images, no search grounding, no thinking levels
- Poor text rendering with complex text
- Cost: $0.039/image

### OpenAI

**Pro** (`provider: "openai", quality: "pro"`):
- Model: gpt-image-1 (high quality)
- Excellent text rendering (best of all providers)
- Fixed resolutions by aspect ratio (max 1536x1024)
- No reference images
- Cost: $0.167-$0.25/image

**Fast** (`provider: "openai", quality: "fast"`):
- Model: gpt-image-1 (low quality)
- Still good text rendering
- Cost: $0.011-$0.016/image

### Together AI

**Default tiers:**
- **Pro** (`provider: "together", quality: "pro"`): FLUX.1-pro, $0.04/MP
- **Fast** (`provider: "together", quality: "fast"`): FLUX.1-schnell, $0.0027/MP

**Model aliases** -- use the `model` parameter to pick a specific model:

| Alias | Cost/MP | Notes |
|-------|---------|-------|
| `dreamshaper` | $0.0006 | Cheapest. Decent illustrations. |
| `juggernaut-lightning` | $0.0017 | Fast, good photos |
| `sdxl` | $0.0019 | Stable Diffusion XL |
| `sd3` | $0.0019 | Stable Diffusion 3 |
| `flux1-schnell` | $0.0027 | Fast FLUX, good all-rounder |
| `hidream-fast` | $0.0032 | Budget quality |
| `hidream-dev` | $0.0045 | Mid-tier HiDream |
| `juggernaut-pro` | $0.0049 | Better Juggernaut |
| `qwen-image` | $0.0058 | Qwen image model |
| `hidream-full` | $0.009 | Full HiDream |
| `seedream3` | $0.018 | Great photorealism |
| `imagen4-fast` | $0.02 | Google Imagen 4 fast |
| `flux2-dev` | $0.025 | FLUX 2 dev, excellent quality |
| `seedream4` | $0.03 | ByteDance Seedream 4 |
| `seededit` | $0.03 | ByteDance image editing |
| `flux2-pro` | $0.04 | FLUX 2 pro, top FLUX quality |
| `flux2-flex` | $0.04 | FLUX 2 flex variant |
| `flux1-kontext-pro` | $0.04 | Kontext pro |
| `imagen4` | $0.04 | Google Imagen 4 preview |
| `ideogram3` | $0.06 | Best text rendering (Together) |
| `imagen4-ultra` | $0.06 | Google Imagen 4 ultra |
| `flux1-kontext-max` | $0.08 | Kontext max, highest FLUX quality |

```javascript
// Use a specific Together model
peeperfrog-create:generate_image({
  prompt: "A sunset",
  model: "ideogram3"  // Forces provider to "together" automatically
})
```

---

## Core Parameters

| Parameter | Values | Default | Notes |
|-----------|--------|---------|-------|
| `prompt` | string | (required) | Image description |
| `provider` | "gemini", "openai", "together" | "gemini" | Ignored if `model` is set |
| `quality` | "pro", "fast" | "pro" | Ignored if `model` is set |
| `model` | Any Together alias | none | Overrides provider/quality |
| `aspect_ratio` | Any ratio (e.g., "1:1", "16:9", "21:9", "2.35:1") | "1:1" | OpenAI uses closest match |
| `image_size` | "small", "medium", "large", "xlarge" | "large" | Gemini Fast always 1K |
| `convert_to_webp` | boolean | true | Auto-convert to WebP after generation |
| `webp_quality` | 0-100 | 85 | WebP quality when convert_to_webp is enabled |

## Reference Images (Gemini Pro Only)

```javascript
// Single reference
peeperfrog-create:generate_image({
  prompt: "Product (see reference image) in modern kitchen setting",
  provider: "gemini",
  quality: "pro",
  reference_image: "/path/to/product.png"
})

// Multiple references (up to 14)
peeperfrog-create:generate_image({
  prompt: "Product A (ref 1) next to Product B (ref 2)",
  provider: "gemini",
  quality: "pro",
  reference_images: ["/path/to/productA.png", "/path/to/productB.png"]
})
```

**Rules:**
- Only works with `provider: "gemini"` and `quality: "pro"`
- Silently ignored on all other providers/quality tiers
- Max 14 images (configurable in server config.json)
- Supported formats: PNG, JPG, JPEG, WebP, GIF
- Each reference adds ~$0.0011 to cost

**Prompt style with references:**
- Cite references: "Product (see reference image) in setting"
- Don't describe product details -- let the reference provide them
- Focus on scene, composition, lighting

---

## Gemini-Only Features

### Search Grounding

Uses real-time Google Search data for factually accurate images. Only on Gemini Pro.

```javascript
peeperfrog-create:generate_image({
  prompt: "Current Tokyo skyline with real landmarks, accurate weather",
  provider: "gemini",
  quality: "pro",
  search_grounding: true
})
```

Cost: +$0.014 per query.

### Thinking Levels

Configurable reasoning depth for complex compositions. Only on Gemini Pro.

| Level | Overhead | Use for |
|-------|----------|---------|
| `minimal` | $0 | Simple images |
| `low` | $0.003 | Moderate complexity |
| `medium` | $0.006 | Complex scenes |
| `high` | $0.012 | Intricate compositions, detailed layouts |

```javascript
peeperfrog-create:generate_image({
  prompt: "Detailed architectural blueprint of a modern house with labeled rooms",
  provider: "gemini",
  quality: "pro",
  thinking_level: "high"
})
```

### Media Resolution

Controls input processing resolution for reference images. Only on Gemini Pro.

```javascript
peeperfrog-create:generate_image({
  prompt: "Product in setting",
  provider: "gemini",
  quality: "pro",
  reference_image: "/path/to/ref.png",
  media_resolution: "high"  // low, medium, high, auto
})
```

---

## Resolution Details

### Gemini Pro

| image_size | Resolution | Cost |
|------------|-----------|------|
| small | 1K (1024px) | $0.134 |
| medium | 2K (2048px) | $0.134 |
| large | 2K (2048px) | $0.134 |
| xlarge | 4K (4096px) | $0.240 |

### Gemini Fast

All sizes produce 1024x1024. Cost: $0.039.

### OpenAI

Resolution depends on aspect ratio, not image_size:

| Aspect | Resolution | Pro cost | Fast cost |
|--------|-----------|----------|-----------|
| 1:1 | 1024x1024 | $0.167 | $0.011 |
| 16:9 | 1536x1024 | $0.248 | $0.016 |
| 9:16 | 1024x1536 | $0.250 | $0.016 |

### Together AI

Resolution depends on both aspect_ratio and image_size. Cost = width x height / 1,000,000 x $/MP.

| Aspect | small | medium/large | xlarge |
|--------|-------|-------------|--------|
| 1:1 | 512x512 | 1024x1024 | 2048x2048 |
| 16:9 | 576x320 | 1024x576 | 1920x1080 |
| 9:16 | 320x576 | 576x1024 | 1080x1920 |
| 4:3 | 512x384 | 1024x768 | 2048x1536 |
| 3:4 | 384x512 | 768x1024 | 1536x2048 |

---

## Cost Estimation

Get cost estimates without generating:

```javascript
peeperfrog-create:estimate_image_cost({
  provider: "together",
  model: "ideogram3",
  image_size: "large",
  aspect_ratio: "16:9",
  count: 5
})
```

Every `generate_image` and `add_to_batch` response includes `estimated_cost_usd`.

---

## Batch Generation

```javascript
// Queue images with different providers
peeperfrog-create:add_to_batch({
  prompt: "Hero image with dramatic lighting",
  provider: "gemini",
  quality: "pro",
  aspect_ratio: "16:9",
  filename: "hero-20260201-120000"
})

peeperfrog-create:add_to_batch({
  prompt: "Social media graphic with bold text",
  provider: "openai",
  quality: "pro",
  aspect_ratio: "1:1",
  filename: "social-20260201-120001"
})

peeperfrog-create:add_to_batch({
  prompt: "Quick thumbnail",
  model: "flux1-schnell",
  aspect_ratio: "16:9",
  filename: "thumb-20260201-120002"
})

// Review
peeperfrog-create:view_batch_queue()

// Generate all (auto WebP conversion)
peeperfrog-create:run_batch()
```

---

## Post-Generation

### Automatic WebP Conversion (Default)

Both `generate_image` and `run_batch` convert to WebP automatically (`convert_to_webp: true` by default). WebP files are saved to the configured `webp_subdir` (default: `webp` inside `images_dir`).

To disable or customize:

```javascript
// Skip WebP conversion
peeperfrog-create:generate_image({ prompt: "A sunset", convert_to_webp: false })

// Custom quality
peeperfrog-create:generate_image({ prompt: "A sunset", webp_quality: 95 })

// Same for batch
peeperfrog-create:run_batch({ convert_to_webp: false })
peeperfrog-create:run_batch({ webp_quality: 90 })
```

### Bulk WebP Conversion (Manual)

Only needed if you disabled auto conversion or have older images:

```javascript
peeperfrog-create:convert_to_webp({ quality: 85 })
```

### WordPress Upload

```javascript
peeperfrog-create:upload_to_wordpress({
  wp_url: "https://example.com"
})
```

### Get WebP Base64

```javascript
peeperfrog-create:get_generated_webp_images({ directory: "batch", limit: 10 })
```

---

## Text Rendering Guide

**Best text rendering (ranked):**
1. OpenAI (pro or fast) -- best overall
2. Ideogram3 (Together) -- best non-OpenAI option
3. Imagen4 / Imagen4-ultra (Together) -- good
4. Gemini Pro -- decent
5. Everything else -- poor to mediocre

**Tips:**
- Keep text simple and clear
- Avoid complex punctuation
- Add "Verify all text matches the prompt exactly" to prompts
- Review generated images for text accuracy
- For critical text: generate text-free image, add text in post-processing

---

## Choosing Between Providers

| Need | Best choice |
|------|------------|
| Reference images | Gemini Pro (only option) |
| Search grounding | Gemini Pro (only option) |
| Best text rendering | OpenAI Pro |
| Cheapest text rendering | OpenAI Fast ($0.011) |
| 4K resolution | Gemini Pro |
| Cheapest possible | Together: dreamshaper ($0.0006/MP) |
| Best photo quality | Together: seedream3, imagen4, flux2-pro |
| Best illustration | Together: flux2-pro/dev, imagen4-ultra |
| Fastest generation | Together: flux1-schnell (4 steps) |
