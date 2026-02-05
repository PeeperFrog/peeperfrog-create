---
name: image-auto-mode
description: Generate images using auto mode -- the server picks the best model for your budget and style
---

# Image Generation -- Auto Mode

**Purpose:** Generate AI images without worrying about providers or models. Set a cost tier and style preference, and the server picks the best model automatically based on your constraints.

**Use this skill when:** You want the best image for the job without manually choosing providers/models.

**See also:** Use **image-manual-control** skill when you need a specific provider, model, or Gemini-only features (thinking levels, media resolution).

---

## Quick Start

```javascript
// Just set auto_mode and go
peeperfrog-create:generate_image({
  prompt: "Mountain landscape at sunset, dramatic lighting, photorealistic",
  auto_mode: "balanced",
  aspect_ratio: "16:9"
})
```

That's it. The server filters available models by your constraints, picks the best one for the tier, and tells you what it chose in the response.

---

## Parameters

### auto_mode (required for auto selection)

Cost tier that caps how much the model can cost per megapixel:

| Tier | Max $/MP | Best for | Typical models |
|------|----------|----------|----------------|
| `cheapest` | $0.003 | Drafts, testing, throwaway images | dreamshaper, flux1-schnell |
| `budget` | $0.01 | Decent quality at low cost | hidream-fast, juggernaut-pro |
| `balanced` | $0.04 | Production use, good quality/cost ratio | seedream3, flux2-dev, flux2-pro, imagen4 |
| `quality` | $0.08 | Premium quality | ideogram3, imagen4-ultra, flux1-kontext-max |
| `best` | no limit | Absolute best available | gemini-pro, openai-pro |

### style_hint (optional, default: "general")

Tells the selector which quality dimension to prioritize:

| Hint | When to use | Favors |
|------|-------------|--------|
| `general` | No specific style needed | Best all-rounder at the tier |
| `photo` | Photorealistic images, product shots, real-world scenes | seedream3/4, imagen4, flux2-pro, gemini-pro |
| `illustration` | Art, drawings, stylized graphics, diagrams | flux2-pro/dev, imagen4-ultra, gemini-pro |
| `text` | Text in image matters -- signs, labels, headlines | openai (fast/pro), ideogram3, imagen4 |
| `infographic` | Charts, graphs, data visualizations, complex layouts with precise numbers | openai-pro, gemini-pro |

### Other parameters

All standard parameters still work alongside auto_mode:

- `prompt` (required): Image description
- `aspect_ratio`: Any ratio supported (e.g., "1:1", "16:9", "21:9", "2.35:1"). OpenAI uses closest match. (default: "1:1")
- `image_size`: "small", "medium", "large", "xlarge" (default: "large")
- `reference_image` / `reference_images`: Reference image paths (constrains to models with reference support)
- `search_grounding`: Enable Google Search grounding (constrains to Gemini Pro)

**Note:** `provider`, `quality`, and `model` are ignored when `auto_mode` is set -- the server overrides them.

---

## How Model Selection Works

1. **Filter by capability:**
   - Models that can't handle the requested `image_size` are excluded
   - If `reference_image` is provided, only models with reference support remain (currently: Gemini Pro)
   - If `search_grounding` is enabled, only Gemini Pro remains
   - Models whose API key is not configured are skipped

2. **Filter by cost:** Remove models above the tier's $/MP ceiling

3. **Rank by style:** Sort remaining models by the relevant quality score (text/photo/illustration/infographic/general), then by cost (cheapest first among equal quality)

4. **Pick the top result**

---

## Examples

### Quick draft -- cheapest possible

```javascript
peeperfrog-create:generate_image({
  prompt: "Abstract background pattern, blue gradient",
  auto_mode: "cheapest"
})
// Likely picks: dreamshaper ($0.0006/MP)
```

### Blog hero image -- balanced cost

```javascript
peeperfrog-create:generate_image({
  prompt: "Cloud computing visualization with interconnected nodes",
  auto_mode: "balanced",
  style_hint: "illustration",
  aspect_ratio: "16:9",
  image_size: "large"
})
// Likely picks: flux2-dev or flux2-pro (illustration_quality=3, under $0.04/MP)
```

### Infographic with text labels

```javascript
peeperfrog-create:generate_image({
  prompt: "Sales growth chart showing Q1: $2M, Q2: $3.5M, Q3: $4.1M, Q4: $5.8M",
  auto_mode: "quality",
  style_hint: "text"
})
// Likely picks: ideogram3 (text_quality=3, $0.06/MP)
```

### Product photo with reference

```javascript
peeperfrog-create:generate_image({
  prompt: "Product (see reference image) on white marble surface, studio lighting",
  auto_mode: "best",
  style_hint: "photo",
  reference_image: "/path/to/product.png"
})
// Picks: gemini-pro (only model with reference support)
```

### Budget text-heavy image

```javascript
peeperfrog-create:generate_image({
  prompt: "Motivational quote poster: 'Start before you're ready'",
  auto_mode: "budget",
  style_hint: "text"
})
// Likely picks: openai-fast (text_quality=3, $0.011/MP) if OPENAI_API_KEY set
// Falls back to: flux1-schnell (text_quality=1) if only TOGETHER_API_KEY set
```

### Infographic / Chart / Data Visualization

For infographics, **clearly separate text that should appear on the image from design instructions**:

```javascript
peeperfrog-create:generate_image({
  prompt: `Professional business infographic on clean white background.

ACTUAL TEXT TO APPEAR ON IMAGE:
- Title: "Q4 Revenue Growth"
- Bar chart labels: "Oct: $2.1M", "Nov: $2.8M", "Dec: $3.4M"
- Footer: "Source: Internal Analytics 2025"

DESIGN INSTRUCTIONS (not text on image):
Use blue/green corporate color palette. Clean sans-serif typography.
Horizontal bar chart with labeled values. Professional business presentation style.`,
  auto_mode: "best",
  style_hint: "infographic",
  aspect_ratio: "16:9"
})
// Picks: openai-pro or gemini-pro (infographic_quality=3)
// These models handle complex layouts, precise numbers, and structured data best
```

**Infographic prompt tips:**
- Use "ACTUAL TEXT TO APPEAR ON IMAGE:" section for all labels, numbers, titles
- Use "DESIGN INSTRUCTIONS:" section for colors, style, layout guidance
- Be explicit about chart types (bar, pie, line) and data values
- Most diffusion models struggle with precise data viz -- use `style_hint: "infographic"` to route to capable models

### Large format, excludes small-only models

```javascript
peeperfrog-create:generate_image({
  prompt: "Detailed cityscape panorama",
  auto_mode: "balanced",
  style_hint: "photo",
  image_size: "xlarge"
})
// Excludes: openai (max: large), gemini-fast (max: small)
// Likely picks: seedream3 or imagen4-fast
```

### Cost estimation before generating

```javascript
peeperfrog-create:estimate_image_cost({
  auto_mode: "balanced",
  style_hint: "photo",
  image_size: "large",
  count: 10
})
// Returns: which model would be picked, cost per image, total for 10
```

---

## Batch Generation with Auto Mode

Auto mode works with batch too. Each image in the batch can use different auto_mode/style_hint combinations:

```javascript
// Text-heavy header
peeperfrog-create:add_to_batch({
  prompt: "Article header: 'The Future of AI'",
  auto_mode: "balanced",
  style_hint: "text",
  aspect_ratio: "16:9",
  filename: "header-20260201-120000"
})

// Photo illustration
peeperfrog-create:add_to_batch({
  prompt: "Robot in modern office environment",
  auto_mode: "balanced",
  style_hint: "photo",
  aspect_ratio: "16:9",
  filename: "robot-office-20260201-120001"
})

// Cheap social thumbnail
peeperfrog-create:add_to_batch({
  prompt: "Abstract tech pattern",
  auto_mode: "cheapest",
  aspect_ratio: "1:1",
  filename: "social-thumb-20260201-120002"
})

// Generate all -- WebP conversion is automatic
peeperfrog-create:run_batch()

// Or with custom WebP quality
peeperfrog-create:run_batch({ webp_quality: 90 })

// Or skip WebP conversion
peeperfrog-create:run_batch({ convert_to_webp: false })
```

Each image gets routed to the best model for its specific needs. WebP files are saved to the `webp` directory by default.

---

## Response Fields

When auto_mode is used, the response includes extra fields:

```json
{
  "success": true,
  "image_path": "/path/to/image.png",
  "webp_path": "/path/to/webp/image.webp",
  "webp_size": 45000,
  "file_count": 1,
  "total_size_bytes": 45000,
  "provider": "together",
  "model": "ideogram-ai/ideogram-3.0",
  "auto_mode": "quality",
  "auto_selected": "ideogram3",
  "style_hint": "text",
  "estimated_cost_usd": 0.06288
}
```

- `auto_selected`: The model key that was chosen (matches AUTO_MODE_MODELS keys)
- `auto_mode`: The tier you requested
- `style_hint`: The style preference used for ranking
- `webp_path` / `webp_size`: Present when auto WebP conversion is enabled (default)
- `file_count` / `total_size_bytes`: Summary stats

---

## Constraint Cheat Sheet

| Constraint | Effect on model selection |
|------------|--------------------------|
| `image_size: "xlarge"` | Excludes OpenAI (max: large), Gemini Fast (max: small) |
| `image_size: "large"` | Excludes Gemini Fast (max: small) |
| `reference_image` provided | Only Gemini Pro eligible |
| `search_grounding: true` | Only Gemini Pro eligible |
| Missing `OPENAI_API_KEY` | All OpenAI models skipped |
| Missing `GEMINI_API_KEY` | All Gemini models skipped |
| Missing `TOGETHER_API_KEY` | All Together models skipped |

If no models match all constraints + cost tier, you get a clear error message explaining why.

---

## When NOT to Use Auto Mode

Use the **image-manual-control** skill instead when you:

- Need a specific model (e.g. always want Gemini 3 Pro)
- Want Gemini-specific features: `thinking_level`, `media_resolution`
- Need precise control over which provider handles each image
- Are debugging or testing a specific provider

---

## Post-Generation

### Automatic WebP Conversion (Default)

Both `generate_image` and `run_batch` convert to WebP automatically. The WebP file is saved to the configured `webp_subdir` directory (default: `webp` inside `images_dir`).

```javascript
// WebP conversion happens automatically -- just generate
peeperfrog-create:generate_image({
  prompt: "Product photo",
  auto_mode: "balanced"
})
// Response includes: webp_path, webp_size

// Disable auto conversion if you only want PNG
peeperfrog-create:generate_image({
  prompt: "Product photo",
  auto_mode: "balanced",
  convert_to_webp: false
})

// Custom WebP quality
peeperfrog-create:generate_image({
  prompt: "Product photo",
  auto_mode: "balanced",
  webp_quality: 95
})
```

### Bulk WebP Conversion (Manual)

Only needed if you disabled auto conversion or have older images:

```javascript
peeperfrog-create:convert_to_webp({ quality: 85 })
```

### WordPress Upload

Upload WebP images directly to WordPress:

```javascript
peeperfrog-create:upload_to_wordpress({
  wp_url: "https://example.com"
})
```

### Get WebP Base64

Retrieve generated WebP images as base64 data:

```javascript
peeperfrog-create:get_generated_webp_images({ directory: "batch", limit: 10 })
```
