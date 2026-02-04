---
name: image-generation
description: Generate high-quality AI images using PeeperFrog Create MCP Server
---

# Image Generation

**Purpose:** Generate high-quality AI images for any use case -- articles, social media, marketing, presentations, or creative projects. Supports multiple providers: Google Gemini (default), OpenAI (gpt-image-1), and Together AI (FLUX + 20 models).

**Use this skill when:** You need to generate AI images programmatically.

---

## Two Approaches

### Auto Mode (Recommended) -- use **image-auto-mode** skill

Set a cost tier and optional style hint. The server picks the best model automatically.

```javascript
peeperfrog-create:generate_image({
  prompt: "Product photo in studio lighting",
  auto_mode: "balanced",
  style_hint: "photo",
  aspect_ratio: "16:9"
})
```

- `auto_mode`: "cheapest", "budget", "balanced", "quality", "best"
- `style_hint`: "general", "photo", "illustration", "text", "infographic"
- Automatically filters by constraints (size, references, grounding, API keys)
- Best for most use cases

### Manual Control -- use **image-manual-control** skill

Pick a specific provider, model, and configure all parameters yourself.

```javascript
peeperfrog-create:generate_image({
  prompt: "Product photo in studio lighting",
  provider: "gemini",
  quality: "pro",
  thinking_level: "high",
  search_grounding: true
})
```

- Full access to all provider-specific features
- Required for Gemini thinking levels, media resolution
- Best when you know exactly which model you want

---

## Available MCP Tools

| Tool | Description |
|------|-------------|
| `generate_image` | Generate a single image immediately (any provider, auto or manual) |
| `add_to_batch` | Queue an image for batch generation |
| `remove_from_batch` | Remove from queue by index or filename |
| `view_batch_queue` | View queued images |
| `run_batch` | Generate all queued images |
| `estimate_image_cost` | Get a cost estimate without generating |
| `convert_to_webp` | Convert generated images to WebP |
| `upload_to_wordpress` | Upload WebP images to WordPress (credentials from config.json) |
| `get_generated_webp_images` | Get base64 data of WebP images |

---

## Quick Decision Guide

| Situation | Use |
|-----------|-----|
| Don't care which model, want good results | Auto mode: `auto_mode: "balanced"` |
| Need cheapest possible | Auto mode: `auto_mode: "cheapest"` |
| Text in image matters | Auto mode: `auto_mode: "balanced", style_hint: "text"` |
| Charts/graphs/infographics | Auto mode: `auto_mode: "best", style_hint: "infographic"` |
| Need reference images | Auto mode: `auto_mode: "quality"` + reference_image (routes to Gemini Pro) |
| Need search grounding | Manual: `provider: "gemini", search_grounding: true` |
| Need thinking levels | Manual: `provider: "gemini", thinking_level: "high"` |
| Want a specific model | Manual: `model: "ideogram3"` or `provider: "openai"` |
| Testing/iterating quickly | Auto mode: `auto_mode: "cheapest"` |
| Final production image | Auto mode: `auto_mode: "best", style_hint: "photo"` |

---

## Prompt Engineering

### Standard Template

```
[Main subject/concept] in [style], [lighting], [setting], [quality/composition]
```

### Examples

```
Modern smartphone on minimalist white surface, professional product photography, soft diffused lighting, clean composition, photorealistic

Abstract representation of cloud computing with interconnected nodes, modern digital art, vibrant blue and purple gradient, balanced composition

Bold text design with quote "Start before you're ready", modern typography, vibrant gradient background, high contrast
```

### Tips

- Be specific about subject and style
- Specify lighting conditions
- Include composition guidance
- For text: keep it simple, add "Verify all text matches the prompt exactly"
- With reference images: cite them ("Product (see reference image) in setting"), don't describe product details

---

## Aspect Ratio Guide

Any aspect ratio is supported (e.g., `21:9`, `2.35:1`, `3:2`). OpenAI picks the closest match from its fixed sizes.

| Ratio | Use for |
|-------|---------|
| 16:9 | Website heroes, blog headers, video thumbnails |
| 1:1 | Instagram, social thumbnails, profile images |
| 9:16 | Stories, mobile graphics, vertical video |
| 4:3 | Presentations, traditional photography |
| 3:4 | Portrait photography, print materials |
| 21:9 | Ultrawide banners, cinematic headers |
| 2.35:1 | Cinemascope, film-style compositions |
| 3:2 | Classic photography, DSLR native ratio |
| 1.91:1 | Facebook/LinkedIn link previews |

---

## Cost Quick Reference

| Configuration | Approx. Cost |
|---|---|
| Auto cheapest (dreamshaper 1MP) | $0.0006 |
| Auto budget (hidream-fast 1MP) | $0.003 |
| Auto balanced (flux2-pro 1MP) | $0.04 |
| Auto quality (ideogram3 1MP) | $0.06 |
| Gemini Pro 2K | $0.135 |
| Gemini Pro 4K | $0.241 |
| Gemini Fast 1K | $0.039 |
| OpenAI Pro (square) | $0.168 |
| OpenAI Fast (square) | $0.012 |

Use `estimate_image_cost` for precise estimates before generating.

---

## Related Skills

- **image-auto-mode** -- Full auto mode documentation with all tiers, style hints, constraint filtering
- **image-manual-control** -- Full manual control documentation with all providers, models, Gemini features
- **cost-estimation** -- Estimate costs before generating, compare providers and batch totals
- **webp-conversion** -- Convert generated images to WebP for web optimization
- **wordpress-upload** -- Upload WebP images to WordPress media library
- **example-brand-image-guidelines** -- Template for brand-specific visual identity extensions
