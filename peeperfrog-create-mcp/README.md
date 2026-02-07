<p align="center">
  <img src="docs/logo for Image Creation.png" alt="PeeperFrog Create" width="200">
</p>

<h1 align="center">PeeperFrog Create MCP</h1>

<p align="center">
A multi-provider MCP (Model Context Protocol) server for AI image generation, compression, and upload.
</p>

<p align="center">
<strong>Part of <a href="../README.md">PeeperFrog Create</a></strong> | Version 1.0 Beta
</p>

---

> **Owned and maintained by [PeeperFrog Press](https://peeperfrog.com)** | Open source under [Apache 2.0](../LICENSE)
>
> **Not affiliated with Google, Gemini, OpenAI, Together AI, or WordPress.** All trademarks are property of their respective owners.

---

Supports Google Gemini, OpenAI (gpt-image-1), and Together AI (FLUX) with single and batch generation, reference images, cost estimation, WebP conversion, and WordPress upload.

> **Installation:** See the [main README](../README.md#quick-start) for automated setup or manual installation instructions.

## Supported Providers

| Provider | Quality Tiers | Reference Images | Max Resolution | Approx. Cost |
|---|---|---|---|---|
| **Gemini** (default) | Pro: Gemini 3 Pro, Fast: Gemini 2.5 Flash | Up to 14 (Pro only) | 4K | $0.039 - $0.24 |
| **OpenAI** | Pro: gpt-image-1 (high), Fast: gpt-image-1 (low) | Not supported | 1536x1024 | $0.011 - $0.25 |
| **Together** | Pro: FLUX.1-pro, Fast: FLUX.1-schnell | Not supported | 2048x2048 | $0.003 - $0.17 |

## Features

- **Priority-based generation** 🆕 -- `priority="high"` for immediate results or `priority="low"` for 50% cost savings via Gemini Batch API (24hr turnaround)
- **Metadata system** 🆕 -- JSON sidecar files for every image with complete metadata (title, description, alt text, caption, generation params)
- **Auto mode** -- automatically selects the best model based on cost tier, style, and constraints
- **Multi-provider** -- switch between Gemini, OpenAI, and Together AI per image
- **Two quality tiers** -- Pro (best quality) and Fast (cheaper/quicker) for each provider
- **Reference images** -- up to 14 reference images per generation (Gemini Pro only)
- **Batch generation** -- queue multiple images, review, then generate in one run
- **Google Search Grounding** -- use real-time Google Search data for factually accurate images (Gemini only)
- **Thinking levels** -- configurable reasoning depth (minimal/low/medium/high) for complex compositions (Gemini Pro only)
- **Media resolution control** -- control input processing resolution: low, medium, high, or auto (Gemini only)
- **Cost estimation** -- estimated USD cost returned with every generation
- **Auto WebP conversion** -- images are automatically converted to WebP after generation (configurable quality, output directory via `config.json`)
- **Bulk WebP conversion** -- convert older PNG/JPG to WebP for web optimization
- **WordPress upload** -- upload WebP images directly to WordPress media library with automatic metadata synchronization 🆕
- **Configurable** -- all paths, limits, and delays via `config.json`; pricing via `pricing.json`

## Tools Provided

| Tool | Description |
|------|-------------|
| `generate_image` | Generate a single image with priority="high" (immediate) or priority="low" (50% discount, 24hr wait) |
| `check_batch_status` 🆕 | Check status of async batch job (for priority="low" generations) |
| `retrieve_batch_results` 🆕 | Retrieve and save completed batch results |
| `add_to_batch` | Queue an image for batch generation |
| `remove_from_batch` | Remove from queue by index or filename |
| `view_batch_queue` | View queued images |
| `run_batch` | Generate all queued images (auto WebP conversion + optional WordPress upload) |
| `estimate_image_cost` | Get a cost estimate without generating anything |
| `get_generation_cost` | Query cost from generation logs (searches month/year stamped CSVs) |
| `convert_to_webp` | Bulk convert images to WebP (for older images or when auto conversion is disabled) |
| `upload_to_wordpress` | Upload WebP images to WordPress with automatic metadata sync |
| `list_wordpress_sites` | List configured WordPress sites (URLs only, credentials stay secure) |
| `get_generated_webp_images` | Get base64 data of WebP images |
| `get_media_id_map` | Get complete image metadata from JSON sidecar files (includes WordPress info if uploaded) |

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/PeeperFrog/peeperfrog-create.git
cd peeperfrog-create/peeperfrog-create-mcp

cp config.json.example config.json
cp .env.example .env
```

### 2. Get your API keys

You only need keys for the providers you plan to use.

| Provider | Where to get your key |
|---|---|
| **Google Gemini** | <a href="https://aistudio.google.com/apikey" target="_blank">Google AI Studio</a> -- click "Create API key". Free tier available. |
| **OpenAI** | <a href="https://platform.openai.com/api-keys" target="_blank">OpenAI Platform</a> -- create a new secret key. Requires billing setup. |
| **Together AI** | <a href="https://api.together.xyz/settings/api-keys" target="_blank">Together AI Settings</a> -- copy your API key. Free credits on signup. |

### 3. Set your API keys

Edit `.env` (only set the providers you plan to use):

```
GEMINI_API_KEY=your-gemini-api-key-here
OPENAI_API_KEY=your-openai-api-key-here
TOGETHER_API_KEY=your-together-api-key-here
```

**Security:** Keys are stored in `.env` (not in Claude's config), keeping them out of Claude's view.

### 4. Configure WordPress (optional)

Upload AI-generated images directly to your WordPress media library. No API key needed -- WordPress has built-in support.

**Prerequisites:**

| Requirement | Details |
|-------------|---------|
| **WordPress admin access** | Editor role or higher |
| **Application Password** | A special WordPress password (not your login password) |

**To create an Application Password:**

1. Log in to your WordPress admin dashboard
2. Go to **Users > Profile**
3. Scroll to **Application Passwords**
4. Enter a name (e.g., "PeeperFrog Create")
5. Click **Add New Application Password**
6. Copy the generated password -- you won't see it again

Edit `config.json` to add WordPress sites for image uploads:

```json
{
  "wordpress": {
    "https://yoursite.com": {
      "user": "your-username",
      "password": "your-application-password",
      "alt_text_prefix": "AI-generated image: "
    },
    "https://anothersite.com": {
      "user": "another-user",
      "password": "another-app-password"
    }
  }
}
```

**Security note:** Credentials stay in `config.json` (never exposed to Claude).

**Finding available sites:** Use the `list_wordpress_sites` tool to see configured WordPress URLs, or ask Claude "What WordPress sites can I upload to?"

### 5. Install dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install requests mcp
```

### 6. Add to your MCP client

#### Claude Code

Settings file: `~/.claude/settings.json` (all platforms)

For **Claude Desktop**, use `claude_desktop_config.json` instead:

| OS | Path |
|---|---|
| **Linux** | `~/.config/Claude/claude_desktop_config.json` |
| **macOS** | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| **Windows** | `%APPDATA%\Claude\claude_desktop_config.json` |

```json
{
  "mcpServers": {
    "peeperfrog-create": {
      "command": "/path/to/peeperfrog-create/peeperfrog-create-mcp/venv/bin/python3",
      "args": ["/path/to/peeperfrog-create/peeperfrog-create-mcp/src/image_server.py"]
    }
  }
}
```

**Note:** API keys and WordPress credentials are loaded from `.env` and `config.json` in the server directory (not in Claude's config).

## Project Structure

```
peeperfrog-create-mcp/
├── src/
│   ├── image_server.py            # Main MCP server
│   ├── batch_manager.py           # Batch queue management
│   ├── batch_generate.py          # Batch image generation
│   ├── metadata.py                # 🆕 Metadata management
│   └── gemini_batch.py            # 🆕 Gemini Batch API integration
├── scripts/
│   └── webp-convert.py            # PNG/JPG to WebP converter
├── docs/
│   └── systemd-service.example    # Systemd service template
├── config.json.example
├── pricing.json                   # Provider pricing for cost estimation
├── .env.example
├── .gitignore
├── LICENSE

## Generated Images Directory Structure 🆕

By default: `~/Pictures/ai-generated-images/`

```
ai-generated-images/
├── original/           # All generated PNG images
├── webp/              # All WebP conversions
└── metadata/          # All metadata and logs
    ├── json/          # JSON sidecar files (one per image)
    │   ├── image1.png.json
    │   ├── image2.png.json
    │   └── ...
    ├── batch_queue.json
    └── generation_log_february_2026.csv  # Month/year stamped logs

## Cost Savings with Priority-Based Generation 🆕

### Priority="high" (Immediate, Full Price)
- **Cost**: $0.039 per image (Gemini Pro example)
- **Speed**: 15-90 seconds
- **Use when**: Interactive workflows, immediate results needed

### Priority="low" (Batch API, 50% Discount)
- **Cost**: $0.0195 per image (Gemini Pro example) - **50% savings!**
- **Speed**: Up to 24 hours
- **Use when**: Bulk generation, scheduled content, cost optimization

### Real-World Savings

| Monthly Volume | High Priority Cost | Low Priority Cost | **Savings** |
|----------------|-------------------|-------------------|-------------|
| 50 images | $1.95 | $0.98 | **$0.97/month** |
| 100 images | $3.90 | $1.95 | **$1.95/month** |
| 500 images | $19.50 | $9.75 | **$9.75/month** |
| 1000 images | $39.00 | $19.50 | **$19.50/month** |

**Annual savings at 500 images/month: $117!**

### Usage Example

```javascript
// Immediate generation (default)
peeperfrog-create:generate_image({
  prompt: "A sunset",
  priority: "high"  // Full price, immediate
})

// Batch API (50% discount)
const result = await peeperfrog-create:generate_image({
  prompt: "A sunset",
  priority: "low",  // 50% discount!
  provider: "gemini"
})
// Returns: {batch_job_id: "...", estimated_completion: "24 hours"}

// Check status later
await peeperfrog-create:check_batch_status({
  batch_job_id: result.batch_job_id
})

// Retrieve when complete
await peeperfrog-create:retrieve_batch_results({
  batch_job_id: result.batch_job_id
})
└── README.md
```

## Usage

### Generate with different providers

All calls auto-convert to WebP by default. Use `convert_to_webp: false` to disable, or `webp_quality: N` to adjust quality (0-100, default 85).

```javascript
// Gemini (default) - returns webp_path in response
generate_image({ prompt: "A sunset", provider: "gemini", quality: "pro" })

// OpenAI
generate_image({ prompt: "A sunset", provider: "openai", quality: "pro" })

// Together AI (FLUX)
generate_image({ prompt: "A sunset", provider: "together", quality: "fast" })

// Disable auto WebP conversion
generate_image({ prompt: "A sunset", convert_to_webp: false })
```

### Generate and upload to WordPress in one call

```javascript
// Generate, convert to WebP, and upload to WordPress
generate_image({
  prompt: "Blog hero image",
  auto_mode: "balanced",
  upload_to_wordpress: true,
  wp_url: "https://yoursite.com"
})
// Returns wordpress_url and wordpress_media_id in response
```

### Batch with mixed providers

```javascript
add_to_batch({ prompt: "Hero image", provider: "gemini", quality: "pro" })
add_to_batch({ prompt: "Social post", provider: "together", quality: "fast" })
run_batch()  // auto WebP conversion, or: run_batch({ convert_to_webp: false })

// Batch with WordPress upload
run_batch({ upload_to_wordpress: true, wp_url: "https://yoursite.com" })
// Updates batch_results.json with wordpress_url and wordpress_media_id for each image
```

### Get media ID mapping (for setting featured images)

```javascript
// Get metadata without downloading image data
get_media_id_map({ directory: "batch" })
// Returns { "hero.webp": { wordpress_media_id: 1234, wordpress_url: "...", file_size: 45000, ... }, ... }
```

### Auto mode -- let the server pick the best model

Instead of choosing a provider and model manually, set `auto_mode` and optionally `style_hint`. The server filters models by your constraints (size, reference images, search grounding, available API keys) then picks the best one for the cost tier.

```javascript
// Cheapest option for a quick draft
generate_image({ prompt: "A sunset", auto_mode: "cheapest" })

// Best model for text-heavy images within a moderate budget
generate_image({ prompt: "Infographic with stats", auto_mode: "balanced", style_hint: "text" })

// Highest quality photo, no budget limit
generate_image({ prompt: "Product photo", auto_mode: "best", style_hint: "photo" })

// With reference images -- auto mode filters to models that support them
generate_image({ prompt: "Product (see ref)", auto_mode: "quality", reference_image: "/path/to/ref.png" })
```

**Cost tiers:**

| Tier | Max $/MP | Typical pick |
|------|----------|-------------|
| `cheapest` | $0.003 | dreamshaper, flux1-schnell |
| `budget` | $0.01 | hidream-fast, juggernaut-pro |
| `balanced` | $0.04 | seedream3, flux2-dev, flux2-pro |
| `quality` | $0.08 | ideogram3, imagen4-ultra |
| `best` | no limit | openai-pro, gemini-pro |

**Style hints:**

| Hint | Effect |
|------|--------|
| `general` | Balanced quality across all styles (default) |
| `photo` | Prefer photorealistic models |
| `illustration` | Prefer art/drawing models |
| `text` | Prefer models with strong text rendering |

**Constraint filtering:**
- Models that don't support the requested `image_size` are excluded (e.g. OpenAI can't do `xlarge`)
- If `reference_image`/`reference_images` are provided, only models with reference support are eligible (currently Gemini Pro)
- If `search_grounding` is enabled, only Gemini Pro is eligible
- Models whose API key is not configured are skipped

The response includes `auto_selected` (which model was chosen) and `auto_mode`/`style_hint` so you can see what was picked.

### Gemini-specific features

```javascript
// Google Search Grounding -- uses real-time data for accuracy
generate_image({ prompt: "Current weather in Tokyo as an infographic", search_grounding: true })

// Thinking level -- deeper reasoning for complex compositions
generate_image({ prompt: "Detailed architectural blueprint of a modern house", thinking_level: "high" })

// Media resolution control -- adjust input processing quality
generate_image({ prompt: "A landscape", media_resolution: "high" })
```

### Cost estimation

Every `generate_image` and `add_to_batch` response includes an `estimated_cost_usd` field. Batch results include per-image costs and a total. Pricing data is loaded from `pricing.json` and can be updated as provider rates change.

### Generation log

All image generations are logged to `generation_log.csv` in your images directory. The log records timestamp, filename, status, cost, provider, quality, and aspect ratio for every generation.

Use `get_generation_cost` to query the log:

```javascript
// Look up cost for a specific image
get_generation_cost({ filename: "hero-image" })

// Get all costs for a date range
get_generation_cost({ start_datetime: "2025-02-01", end_datetime: "2025-02-03" })

// Get costs for a specific time window
get_generation_cost({ start_datetime: "2025-02-03 09:00:00", end_datetime: "2025-02-03 17:00:00" })
```

The log file is CSV format for easy import into spreadsheets or auditing tools.

## Pricing Quick Reference

| Configuration | Approx. Cost/Image |
|---|---|
| Gemini Pro 2K | $0.135 |
| Gemini Pro 4K | $0.241 |
| Gemini Fast 1K | $0.039 |
| OpenAI High (square) | $0.168 |
| OpenAI Low (square) | $0.012 |
| Together FLUX.1-pro 1024x1024 | $0.042 |
| Together FLUX.1-schnell 1024x1024 | $0.003 |

See `pricing.json` for full details including per-resolution breakdowns.

## License

[Apache 2.0](../LICENSE) | See [DISCLAIMER](../DISCLAIMER.md) for warranty and liability terms.
