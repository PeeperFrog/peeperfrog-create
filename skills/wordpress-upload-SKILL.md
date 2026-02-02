---
name: wordpress-upload
description: Upload generated WebP images to WordPress media library. Credentials are stored in config.json.
---

# WordPress Upload

**Purpose:** Upload AI-generated WebP images directly to your WordPress site's media library via the REST API. Credentials are stored in `config.json` so you only need to provide the site URL.

**Use this skill when:** You want to publish generated images to WordPress.

**Prerequisites:**
- Images must be converted to WebP first (use **webp-conversion** skill)
- WordPress credentials must be configured in `config.json`

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
      "password": "xxxx xxxx xxxx xxxx xxxx xxxx"
    }
  }
}
```

You can configure multiple sites:

```json
{
  "wordpress": {
    "https://site-one.com": {
      "user": "admin",
      "password": "app-password-for-site-one"
    },
    "https://site-two.com": {
      "user": "editor",
      "password": "app-password-for-site-two"
    }
  }
}
```

The URL must match exactly what you pass to the tool (trailing slashes are normalized automatically).

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

### Full workflow: generate, convert, upload

```javascript
// 1. Generate images
peeperfrog-create:generate_image({
  prompt: "Blog hero image, mountain landscape at golden hour",
  auto_mode: "balanced",
  style_hint: "photo",
  aspect_ratio: "16:9"
})

// 2. Convert to WebP
peeperfrog-create:convert_to_webp({ quality: 85 })

// 3. Upload to WordPress
peeperfrog-create:upload_to_wordpress({
  wp_url: "https://yoursite.com"
})
```

### Batch workflow

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

// Generate all
peeperfrog-create:run_batch()

// Convert to WebP
peeperfrog-create:convert_to_webp({ quality: 85 })

// Upload all to WordPress
peeperfrog-create:upload_to_wordpress({
  wp_url: "https://yoursite.com"
})
```

---

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `wp_url` | string | Yes | -- | WordPress site URL. Must match a key in config.json `wordpress` section. |
| `directory` | string | No | "batch" | Subdirectory within `images_dir` to scan for WebP files. |
| `limit` | integer | No | 10 | Maximum number of images to upload. |

---

## Response

```json
{
  "success": true,
  "uploaded": [
    {
      "filename": "hero-20260202-120000.webp",
      "media_id": 1234,
      "url": "https://yoursite.com/wp-content/uploads/2026/02/hero-20260202-120000.webp",
      "title": "hero-20260202-120000"
    }
  ],
  "failed": [],
  "total": 1
}
```

- `media_id`: WordPress media library ID -- use this to set featured images on posts
- `url`: Public URL of the uploaded image
- Images are uploaded in order of most recently modified first

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| "No WordPress credentials found in config.json" | URL doesn't match any entry | Check the URL matches exactly (including https://) |
| "missing 'user' or 'password'" | Incomplete config entry | Add both `user` and `password` to the config |
| HTTP 401 | Bad credentials | Regenerate the application password in WordPress |
| HTTP 403 | Insufficient permissions | User needs `upload_files` capability (Editor or Admin role) |
| HTTP 413 | File too large | Increase `upload_max_filesize` in WordPress PHP config |
| No .webp files found | Images not converted | Run `convert_to_webp` first |

---

## Related Skills

- **webp-conversion** -- Convert generated images to WebP before uploading
- **image-generation** -- Overview of all image generation tools
- **image-auto-mode** -- Auto mode image generation
- **cost-estimation** -- Estimate generation costs before producing images
