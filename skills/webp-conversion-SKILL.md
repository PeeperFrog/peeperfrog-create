---
name: webp-conversion
description: Convert generated PNG/JPG images to WebP format for web optimization and WordPress upload
---

# WebP Conversion

**Purpose:** Convert AI-generated PNG and JPG images to WebP format for smaller file sizes (typically 70-80% reduction) optimized for web use and WordPress publishing.

**Use this skill when:** You disabled automatic WebP conversion (`convert_to_webp: false`) on `generate_image` or `run_batch`, or you have older images that weren't auto-converted.

**Note:** As of the latest update, **`generate_image` and `run_batch` convert to WebP automatically** (`convert_to_webp: true`, `webp_quality: 85` by default). WebP files are saved to the `webp` subdirectory inside `images_dir` (configurable via `webp_subdir` in `config.json`). You typically don't need this bulk tool unless you disabled auto conversion.

---

## Quick Start

```javascript
// Bulk convert all images with default quality (85)
peeperfrog-create:convert_to_webp()
```

This tool scans your images directory recursively, finds all PNG and JPG files, and creates `.webp` versions alongside them.

---

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `quality` | integer | No | 85 | WebP quality (0-100). Higher = better quality, larger files. |
| `force` | boolean | No | false | Force reconversion even if `.webp` files already exist. |

---

## Usage

### Default conversion

```javascript
peeperfrog-create:convert_to_webp()
// Converts all PNG/JPG in images_dir, skips files that already have a .webp version
```

### Custom quality

```javascript
// Higher quality for hero images
peeperfrog-create:convert_to_webp({ quality: 95 })

// Lower quality for thumbnails (smaller files)
peeperfrog-create:convert_to_webp({ quality: 70 })
```

### Force reconversion

If you previously converted at one quality and want to redo at a different quality:

```javascript
peeperfrog-create:convert_to_webp({ quality: 90, force: true })
```

---

## Quality Guide

| Quality | File size vs PNG | Best for |
|---------|-----------------|----------|
| 95-100 | ~40-50% smaller | High-detail photography, hero images |
| 85 (default) | ~70-80% smaller | General web use, blog images |
| 70-80 | ~80-85% smaller | Thumbnails, social previews |
| 50-65 | ~85-90% smaller | Drafts, low-priority images |

The default of 85 is a good balance for most web use cases. You rarely need to change it.

---

## How It Works

1. Scans the configured `images_dir` directory recursively
2. Finds all `.png` and `.jpg`/`.jpeg` files
3. Creates a `.webp` version next to each original (e.g. `image.png` → `image.webp`)
4. Skips files that already have a `.webp` version (unless `force: true`)
5. Original files are preserved -- not deleted

The conversion uses the `webp-convert.py` script configured in `config.json`.

---

## Common Workflows

### Generate → Upload (auto WebP)

With auto conversion, the pipeline is simpler:

```javascript
// Generate (WebP conversion is automatic)
peeperfrog-create:generate_image({
  prompt: "Product photo, studio lighting",
  auto_mode: "balanced",
  style_hint: "photo"
})
// Response includes webp_path

// Upload to WordPress
peeperfrog-create:upload_to_wordpress({ wp_url: "https://yoursite.com" })
```

### Batch → Upload (auto WebP)

```javascript
peeperfrog-create:add_to_batch({ prompt: "Image 1", auto_mode: "balanced", filename: "img1" })
peeperfrog-create:add_to_batch({ prompt: "Image 2", auto_mode: "balanced", filename: "img2" })
peeperfrog-create:run_batch()
// Response includes files list with WebP paths

peeperfrog-create:upload_to_wordpress({ wp_url: "https://yoursite.com" })
```

### Bulk convert older images

If you have PNG/JPG images generated before auto conversion was added:

```javascript
peeperfrog-create:convert_to_webp({ quality: 85 })
```

### Get base64 data instead of uploading

If you need the WebP image data directly (e.g. for embedding or other APIs):

```javascript
peeperfrog-create:get_generated_webp_images({
  directory: "batch",
  limit: 10
})
// Returns base64-encoded WebP data for each image
```

---

## Response

```json
{
  "success": true,
  "output": "Converted 3 images to WebP\n  image1.png → image1.webp (245KB → 62KB)\n  ...",
  "error": null
}
```

---

## Related Skills

- **wordpress-upload** -- Upload converted WebP images to WordPress
- **image-generation** -- Overview of all image generation tools
- **cost-estimation** -- Estimate generation costs before producing images
