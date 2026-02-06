---
name: wordpress-upload
description: Upload generated WebP images to WordPress media library. Credentials are stored in config.json.
---

# WordPress Upload

**Purpose:** Upload AI-generated WebP images directly to your WordPress site's media library via the REST API. Credentials are stored in `config.json` so you only need to provide the site URL.

**Use this skill when:** You want to publish generated images to WordPress.

**Prerequisites:**
- WordPress credentials must be configured in `config.json`
- Images are auto-converted to WebP during generation (default behavior)

---

## Setup

### 1. Create a WordPress Application Password

WordPress application passwords allow API access without exposing your main account password.

1. Log in to your WordPress admin panel
2. Go to **Users > Profile**
3. Scroll to **Application Passwords**
4. Enter a name (e.g. "PeeperFrog Create") and click **Add New Application Password**
5. Copy the generated password -- you won't see it again

### 2. Add credentials to config.json

Add a `wordpress` section to your `config.json` (in the `peeperfrog-create-mcp/` directory):

```json
{
  "images_dir": "~/Pictures/ai-generated-images",
  "wordpress": {
    "https://yoursite.com": {
      "user": "your-wordpress-username",
      "password": "xxxx xxxx xxxx xxxx xxxx xxxx",
      "alt_text_prefix": "AI-generated image: "
    }
  }
}
```

You can configure multiple sites with different alt text prefixes:

```json
{
  "wordpress": {
    "https://site-one.com": {
      "user": "admin",
      "password": "app-password-for-site-one",
      "alt_text_prefix": "Site One: "
    },
    "https://site-two.com": {
      "user": "editor",
      "password": "app-password-for-site-two",
      "alt_text_prefix": ""
    }
  }
}
```

The URL must match exactly what you pass to the tool (trailing slashes are normalized automatically).

**Alt text:** When uploading, the alt text is automatically generated from the filename (replacing `-` and `_` with spaces) and prefixed with `alt_text_prefix` if configured. For example, a file `hero-mountain-sunset.webp` with prefix `"AI-generated: "` becomes alt text `"AI-generated: hero mountain sunset"`.

---

## Finding Available WordPress Sites

Call `list_wordpress_sites` once to discover configured sites, then use those URLs in subsequent calls:

```javascript
peeperfrog-create:list_wordpress_sites()
```

Response:
```json
{
  "success": true,
  "sites": ["https://site-one.com", "https://site-two.com"],
  "count": 2,
  "note": "Use these URLs with upload_to_wordpress or generate_image with upload_to_wordpress=true"
}
```

**Note:** You only need to call this once per session. After that, use one of the returned URLs in your `wp_url` parameter for uploads.

---

## Usage

### Basic upload

Upload the most recent WebP images from the batch directory:

```javascript
peeperfrog-create:upload_to_wordpress({
  wp_url: "https://yoursite.com"
})
```

### Upload with options

```javascript
peeperfrog-create:upload_to_wordpress({
  wp_url: "https://yoursite.com",
  directory: "batch",  // subdirectory within images_dir (default: "batch")
  limit: 5             // max images to upload (default: 10)
})
```

### Generate and upload in one call

The easiest way -- generate, convert to WebP, and upload all in one step:

```javascript
peeperfrog-create:generate_image({
  prompt: "Blog hero image, mountain landscape at golden hour",
  auto_mode: "balanced",
  style_hint: "photo",
  aspect_ratio: "16:9",
  upload_to_wordpress: true,
  wp_url: "https://yoursite.com"
})
```

Response includes `wordpress_url` and `wordpress_media_id` for immediate use.

### Batch workflow with auto-upload

```javascript
// Queue multiple images
peeperfrog-create:add_to_batch({
  prompt: "Hero image",
  auto_mode: "balanced",
  aspect_ratio: "16:9",
  filename: "hero-20260202-120000"
})

peeperfrog-create:add_to_batch({
  prompt: "Social thumbnail",
  auto_mode: "budget",
  aspect_ratio: "1:1",
  filename: "social-20260202-120001"
})

// Generate all and upload to WordPress
peeperfrog-create:run_batch({
  upload_to_wordpress: true,
  wp_url: "https://yoursite.com"
})
```

The `batch_results.json` file is updated with `wordpress_url` and `wordpress_media_id` for each image.

### Upload existing images separately

If you generated images earlier without uploading:

```javascript
peeperfrog-create:upload_to_wordpress({
  wp_url: "https://yoursite.com",
  directory: "batch",
  limit: 10
})
```

---

## Parameters

### For `generate_image` and `run_batch`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `upload_to_wordpress` | boolean | No | false | Upload image(s) to WordPress after generation |
| `wp_url` | string | If uploading | -- | WordPress site URL. Must match a key in config.json `wordpress` section. |

### For `upload_to_wordpress` (standalone tool)

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `wp_url` | string | Yes | -- | WordPress site URL. Must match a key in config.json `wordpress` section. |
| `directory` | string | No | "batch" | Subdirectory within `images_dir` to scan for WebP files. |
| `limit` | integer | No | 10 | Maximum number of images to upload. |

### For `get_media_id_map`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `directory` | string | No | "batch" | Subdirectory to scan for metadata. |
| `output_format` | string | No | "json" | Output format: "json", "yaml", or "python_dict". |

---

## Response Examples

### generate_image with upload

```json
{
  "success": true,
  "image_path": "/path/to/generated_image.png",
  "webp_path": "/path/to/webp/generated_image.webp",
  "wordpress_url": "https://yoursite.com/wp-content/uploads/2026/02/generated_image.webp",
  "wordpress_media_id": 1234,
  "wordpress_upload": {
    "success": true,
    "filename": "generated_image.webp",
    "media_id": 1234,
    "url": "https://yoursite.com/wp-content/uploads/2026/02/generated_image.webp",
    "title": "generated_image",
    "alt_text": "AI-generated image: generated image"
  }
}
```

### run_batch with upload

```json
{
  "success": true,
  "files": ["/path/to/webp/hero.webp", "/path/to/webp/social.webp"],
  "summary": {"count": 2, "total_size_bytes": 90000, "webp_converted": 2},
  "wordpress_upload": {
    "uploaded": [
      {"filename": "hero.webp", "media_id": 1234, "url": "https://...", "alt_text": "AI-generated image: hero"},
      {"filename": "social.webp", "media_id": 1235, "url": "https://...", "alt_text": "AI-generated image: social"}
    ],
    "failed": [],
    "total_uploaded": 2,
    "total_failed": 0
  }
}
```

The `batch_results.json` file is also updated with `wordpress_url` and `wordpress_media_id` for each image.

### get_media_id_map

Get metadata without downloading image data -- useful for setting featured images:

```javascript
peeperfrog-create:get_media_id_map({
  directory: "batch",
  output_format: "json"
})
```

Response:

```json
{
  "success": true,
  "format": "json",
  "count": 2,
  "media_map": {
    "hero.webp": {
      "file_path": "/path/to/webp/hero.webp",
      "file_size": 45000,
      "modified_time": "2026-02-05 10:30:00",
      "wordpress_media_id": 1234,
      "wordpress_url": "https://yoursite.com/wp-content/uploads/2026/02/hero.webp",
      "provider": "gemini",
      "aspect_ratio": "16:9"
    },
    "social.webp": {
      "file_path": "/path/to/webp/social.webp",
      "file_size": 25000,
      "modified_time": "2026-02-05 10:31:00",
      "wordpress_media_id": 1235,
      "wordpress_url": "https://yoursite.com/wp-content/uploads/2026/02/social.webp"
    }
  }
}
```

- `media_id`: WordPress media library ID -- use this to set featured images on posts
- `url`: Public URL of the uploaded image

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| "No WordPress credentials found in config.json" | URL doesn't match any entry | Check the URL matches exactly (including https://) |
| "missing 'user' or 'password'" | Incomplete config entry | Add both `user` and `password` to the config |
| HTTP 401 | Bad credentials | Regenerate the application password in WordPress |
| HTTP 403 | Insufficient permissions | User needs `upload_files` capability (Editor or Admin role) |
| HTTP 413 | File too large | Increase `upload_max_filesize` in WordPress PHP config |
| No .webp files found | Images not converted | Ensure `convert_to_webp: true` (default) when generating |

---

## Related Skills

- **webp-conversion** -- Convert generated images to WebP before uploading
- **image-generation** -- Overview of all image generation tools
- **image-auto-mode** -- Auto mode image generation
- **cost-estimation** -- Estimate generation costs before producing images
