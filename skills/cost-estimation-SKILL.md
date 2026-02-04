---
name: cost-estimation
description: Estimate image generation costs before producing images -- compare providers, models, and batch totals
---

# Cost Estimation

**Purpose:** Get accurate cost estimates for image generation without actually generating anything. Compare providers, models, quality tiers, and calculate batch totals to stay within budget.

**Use this skill when:** You want to know what an image will cost before generating it, or need to compare pricing across providers and models.

---

## Quick Start

```javascript
// How much will a default Gemini Pro image cost?
peeperfrog-create:estimate_image_cost()

// How much for 10 images with auto mode?
peeperfrog-create:estimate_image_cost({
  auto_mode: "balanced",
  style_hint: "photo",
  count: 10
})
```

---

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `provider` | string | No | "gemini" | Provider: "gemini", "openai", "together" |
| `quality` | string | No | "pro" | Quality tier: "pro" or "fast" |
| `aspect_ratio` | string | No | "1:1" | Any ratio (e.g., "1:1", "16:9", "21:9", "2.35:1"). OpenAI uses closest match. |
| `image_size` | string | No | "large" | "small", "medium", "large", "xlarge" |
| `num_reference_images` | integer | No | 0 | Number of reference images (Gemini Pro only, max 14) |
| `search_grounding` | boolean | No | false | Whether Google Search grounding will be used |
| `thinking_level` | string | No | none | Gemini Pro thinking level: "minimal", "low", "medium", "high" |
| `count` | integer | No | 1 | Number of images to estimate (multiplies per-image cost) |
| `model` | string | No | none | Together AI model alias (overrides provider/quality) |
| `auto_mode` | string | No | none | Auto-select model: "cheapest", "budget", "balanced", "quality", "best" |
| `style_hint` | string | No | "general" | Style for auto_mode: "general", "photo", "illustration", "text", "infographic" |

---

## Examples

### Compare providers for a single image

```javascript
// Gemini Pro (default)
peeperfrog-create:estimate_image_cost({
  provider: "gemini", quality: "pro"
})
// → ~$0.134

// OpenAI Pro
peeperfrog-create:estimate_image_cost({
  provider: "openai", quality: "pro"
})
// → ~$0.167

// Together FLUX.1-pro
peeperfrog-create:estimate_image_cost({
  provider: "together", quality: "pro"
})
// → ~$0.042
```

### Compare auto mode tiers

```javascript
peeperfrog-create:estimate_image_cost({ auto_mode: "cheapest" })
// → ~$0.0006 (dreamshaper)

peeperfrog-create:estimate_image_cost({ auto_mode: "budget", style_hint: "photo" })
// → ~$0.003-0.01

peeperfrog-create:estimate_image_cost({ auto_mode: "balanced", style_hint: "photo" })
// → ~$0.02-0.04

peeperfrog-create:estimate_image_cost({ auto_mode: "best", style_hint: "photo" })
// → ~$0.134-0.167
```

### Estimate a batch

```javascript
// 10 balanced photo images
peeperfrog-create:estimate_image_cost({
  auto_mode: "balanced",
  style_hint: "photo",
  count: 10
})
// Returns per-image cost AND total for 10
```

### Specific Together model

```javascript
peeperfrog-create:estimate_image_cost({
  model: "ideogram3",
  image_size: "large",
  aspect_ratio: "16:9",
  count: 5
})
```

### Gemini Pro with all extras

```javascript
peeperfrog-create:estimate_image_cost({
  provider: "gemini",
  quality: "pro",
  image_size: "xlarge",
  num_reference_images: 3,
  search_grounding: true,
  thinking_level: "high"
})
// Includes: base cost + reference images + grounding + thinking overhead
```

---

## Response

```json
{
  "success": true,
  "provider": "together",
  "quality": "pro",
  "image_size": "large",
  "aspect_ratio": "1:1",
  "reference_images": 0,
  "search_grounding": false,
  "thinking_level": null,
  "estimated_cost_per_image_usd": 0.042,
  "count": 10,
  "estimated_total_cost_usd": 0.42,
  "auto_mode": "balanced",
  "auto_selected": "flux2-pro",
  "style_hint": "photo"
}
```

When `auto_mode` is used, `auto_selected` tells you which model would be chosen.

---

## Pricing Quick Reference

### Auto Mode Tiers

| Tier | Max $/MP | Typical cost/image (1MP) |
|------|----------|--------------------------|
| `cheapest` | $0.003 | $0.0006 - $0.003 |
| `budget` | $0.01 | $0.003 - $0.01 |
| `balanced` | $0.04 | $0.018 - $0.04 |
| `quality` | $0.08 | $0.04 - $0.08 |
| `best` | no limit | $0.06 - $0.17 |

### Manual Provider Costs

| Configuration | Approx. Cost/Image |
|---|---|
| Gemini Pro 2K | $0.134 |
| Gemini Pro 4K | $0.241 |
| Gemini Fast 1K | $0.039 |
| OpenAI Pro (square) | $0.167 |
| OpenAI Fast (square) | $0.011 |
| Together FLUX.1-pro 1MP | $0.042 |
| Together FLUX.1-schnell 1MP | $0.003 |

### Cost Add-ons (Gemini Pro only)

| Feature | Additional Cost |
|---------|----------------|
| Each reference image | +$0.0011 |
| Search grounding | +$0.014 |
| Thinking: minimal | +$0.00 |
| Thinking: low | +$0.003 |
| Thinking: medium | +$0.006 |
| Thinking: high | +$0.012 |

---

## Tips

- **Always estimate before large batches** -- a 50-image batch at "quality" tier costs very differently than at "cheapest"
- **auto_mode estimates show which model would be picked** -- useful for verifying the selection before committing
- **Every `generate_image` and `add_to_batch` response also includes `estimated_cost_usd`** -- you get cost info even without using this tool
- **Pricing comes from `pricing.json`** -- update it if provider rates change

---

## Generation Log & Cost Lookup

Every image generation (single or batch) is logged to `generation_log.csv` in your images directory. Use `get_generation_cost` to query historical costs.

### Query by Filename

```javascript
// Look up cost for a specific image
peeperfrog-create:get_generation_cost({
  filename: "generated_image_20250203_141523"
})
// Works with or without .png extension
```

### Query by Date Range

```javascript
// Get all costs for today
peeperfrog-create:get_generation_cost({
  start_datetime: "2025-02-03",
  end_datetime: "2025-02-03"
})

// Get costs for a specific time range
peeperfrog-create:get_generation_cost({
  start_datetime: "2025-02-01 09:00:00",
  end_datetime: "2025-02-03 17:00:00"
})
```

### Response

```json
{
  "records": [
    {
      "datetime": "2025-02-03 14:15:23",
      "filename": "generated_image_20250203_141523.png",
      "status": "success",
      "cost_usd": "0.042000",
      "provider": "together",
      "quality": "pro",
      "aspect_ratio": "16:9"
    }
  ],
  "count": 1,
  "total_cost": 0.042,
  "log_file": "/home/user/Pictures/ai-generated-images/generation_log.csv"
}
```

### Log File Format

The CSV log (`generation_log.csv`) contains:

| Column | Description |
|--------|-------------|
| datetime | Generation timestamp (YYYY-MM-DD HH:MM:SS) |
| filename | Image filename |
| status | "success" or error message |
| cost_usd | Estimated cost (6 decimal places) |
| provider | gemini, openai, or together |
| quality | pro or fast |
| aspect_ratio | Image aspect ratio |

Use this for auditing, expense tracking, or importing into spreadsheets.

---

## Related Skills

- **image-auto-mode** -- Auto mode generation with cost tiers
- **image-manual-control** -- Manual provider/model selection
- **image-generation** -- Overview of all image generation tools
- **webp-conversion** -- Convert images to WebP after generation
- **wordpress-upload** -- Upload images to WordPress after conversion
