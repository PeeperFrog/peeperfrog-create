---
name: image-queue-management
description: Manage the batch image generation queue -- add, remove, view, and run queued images
---

# Image Queue Management

**Purpose:** Queue multiple images for batch generation instead of generating one at a time. Useful for producing sets of images efficiently, managing costs, and reviewing prompts before committing to generation.

**Use this skill when:** You need to generate multiple images and want to queue them first, review the queue, or run batch generation.

---

## Quick Start

```javascript
// Add images to the queue
peeperfrog-create:add_to_batch({
  prompt: "Hero image for blog post about productivity",
  auto_mode: "balanced",
  aspect_ratio: "16:9",
  filename: "productivity-hero"
})

peeperfrog-create:add_to_batch({
  prompt: "Social media thumbnail, productivity theme",
  auto_mode: "budget",
  aspect_ratio: "1:1",
  filename: "productivity-social"
})

// Review the queue
peeperfrog-create:view_batch_queue()

// Generate all queued images
peeperfrog-create:run_batch()
```

---

## Tools

### add_to_batch

Add an image to the queue for later generation.

```javascript
peeperfrog-create:add_to_batch({
  prompt: "Image description",
  filename: "optional-custom-name",
  auto_mode: "balanced",
  style_hint: "photo",
  aspect_ratio: "16:9",
  image_size: "large",
  description: "Internal note about this image"
})
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `prompt` | string | Yes | -- | Image generation prompt |
| `filename` | string | No | auto-generated | Custom filename (without extension) |
| `auto_mode` | string | No | none | Cost tier: "cheapest", "budget", "balanced", "quality", "best" |
| `style_hint` | string | No | "general" | Style hint for auto_mode: "general", "photo", "illustration", "text" |
| `provider` | string | No | "gemini" | Manual provider: "gemini", "openai", "together" |
| `quality` | string | No | "pro" | Manual quality: "pro" or "fast" |
| `model` | string | No | none | Specific Together AI model alias |
| `aspect_ratio` | string | No | "16:9" | Any ratio (e.g., "1:1", "16:9", "21:9", "2.35:1"). OpenAI uses closest match. |
| `image_size` | string | No | "large" | "small", "medium", "large", "xlarge" |
| `reference_image` | string | No | none | Path to a single reference image |
| `reference_images` | array | No | none | Array of reference image paths (max 14) |
| `description` | string | No | "" | Internal note (not sent to the model) |
| `search_grounding` | boolean | No | false | Enable Google Search grounding (Gemini only) |
| `thinking_level` | string | No | none | Gemini thinking: "minimal", "low", "medium", "high" |
| `media_resolution` | string | No | none | Gemini media resolution: "low", "medium", "high" |

**Response:**

```json
{
  "success": true,
  "added": {
    "prompt": "Hero image for blog post about productivity",
    "filename": "productivity-hero",
    "aspect_ratio": "16:9",
    "auto_mode": "balanced",
    "style_hint": "photo"
  },
  "queue_size": 1,
  "estimated_cost_usd": 0.04
}
```

---

### view_batch_queue

View all images currently in the queue.

```javascript
peeperfrog-create:view_batch_queue()
```

No parameters required.

**Response:**

```json
{
  "total": 2,
  "prompts": [
    {
      "prompt": "Hero image for blog post about productivity",
      "filename": "productivity-hero",
      "aspect_ratio": "16:9",
      "auto_mode": "balanced",
      "style_hint": "photo",
      "added_at": "2026-02-03T10:30:00"
    },
    {
      "prompt": "Social media thumbnail, productivity theme",
      "filename": "productivity-social",
      "aspect_ratio": "1:1",
      "auto_mode": "budget",
      "added_at": "2026-02-03T10:31:00"
    }
  ]
}
```

---

### remove_from_batch

Remove an image from the queue by index (0-based) or filename.

```javascript
// Remove by index (first item = 0)
peeperfrog-create:remove_from_batch({ identifier: "0" })

// Remove by filename
peeperfrog-create:remove_from_batch({ identifier: "productivity-social" })
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `identifier` | string | Yes | Queue index (e.g. "0", "1") or filename |

**Response:**

```json
{
  "success": true,
  "removed": ["productivity-social"],
  "queue_size": 1,
  "message": "Removed 1 item(s) from queue"
}
```

---

### run_batch

Generate all queued images. Images are generated sequentially with a delay between each to respect API rate limits.

```javascript
peeperfrog-create:run_batch()
```

No parameters required. Uses the queue file and batch output directory from `config.json`.

**Response:**

```json
{
  "success": true,
  "output": "Generated 2 images:\n  productivity-hero.png (balanced/flux2-pro)\n  productivity-social.png (budget/hidream-fast)\n",
  "error": null
}
```

Generated images are saved to the `batch` subdirectory within your configured `images_dir`.

---

## Workflows

### Basic batch workflow

```javascript
// 1. Queue images
peeperfrog-create:add_to_batch({
  prompt: "Product photo, white background",
  auto_mode: "quality",
  style_hint: "photo",
  filename: "product-main"
})

peeperfrog-create:add_to_batch({
  prompt: "Product lifestyle shot, kitchen setting",
  auto_mode: "quality",
  style_hint: "photo",
  filename: "product-lifestyle"
})

// 2. Review queue
peeperfrog-create:view_batch_queue()

// 3. Generate all
peeperfrog-create:run_batch()
```

### Review and edit before generating

```javascript
// Add several images
peeperfrog-create:add_to_batch({ prompt: "Image A", filename: "a" })
peeperfrog-create:add_to_batch({ prompt: "Image B", filename: "b" })
peeperfrog-create:add_to_batch({ prompt: "Image C - wrong prompt", filename: "c" })

// Review
peeperfrog-create:view_batch_queue()

// Remove the one with the wrong prompt
peeperfrog-create:remove_from_batch({ identifier: "c" })

// Add corrected version
peeperfrog-create:add_to_batch({ prompt: "Image C - corrected", filename: "c" })

// Generate
peeperfrog-create:run_batch()
```

### Full pipeline: queue, generate, convert, upload

```javascript
// Queue images
peeperfrog-create:add_to_batch({
  prompt: "Blog hero image",
  auto_mode: "balanced",
  aspect_ratio: "16:9",
  filename: "blog-hero"
})

peeperfrog-create:add_to_batch({
  prompt: "Blog thumbnail",
  auto_mode: "budget",
  aspect_ratio: "1:1",
  filename: "blog-thumb"
})

// Generate
peeperfrog-create:run_batch()

// Convert to WebP
peeperfrog-create:convert_to_webp({ quality: 85 })

// Upload to WordPress
peeperfrog-create:upload_to_wordpress({ wp_url: "https://yoursite.com" })
```

### Estimate batch cost before generating

```javascript
// Add images to queue
peeperfrog-create:add_to_batch({ prompt: "Image 1", auto_mode: "balanced" })
peeperfrog-create:add_to_batch({ prompt: "Image 2", auto_mode: "balanced" })
peeperfrog-create:add_to_batch({ prompt: "Image 3", auto_mode: "balanced" })

// Check queue to see count
peeperfrog-create:view_batch_queue()
// → total: 3

// Estimate total cost
peeperfrog-create:estimate_image_cost({
  auto_mode: "balanced",
  count: 3
})
// → estimated_total_cost_usd: ~$0.12

// If acceptable, generate
peeperfrog-create:run_batch()
```

---

## Tips

- **Filenames are optional** -- if not provided, a timestamp-based name is generated
- **The queue persists** -- items stay in the queue until generated or removed, even across sessions
- **Each add shows cost** -- the `add_to_batch` response includes `estimated_cost_usd` for that image
- **Mixed providers work** -- you can queue images with different `auto_mode` or `provider` settings
- **Failed images don't block** -- if one image fails, the batch continues with the rest

---

## Queue File Location

The queue is stored in `batch_queue.json` within your configured `images_dir` (default: `~/Pictures/ai-generated-images/batch_queue.json`). You can inspect or manually edit this file if needed.

---

## Related Skills

- **image-generation** -- Overview of all image generation tools and approaches
- **image-auto-mode** -- Auto mode with cost tiers and style hints
- **image-manual-control** -- Manual provider and model selection
- **cost-estimation** -- Estimate costs before generating
- **webp-conversion** -- Convert generated images to WebP
- **wordpress-upload** -- Upload images to WordPress
