<p align="center">
  <img src="docs/logo.png" alt="PeeperFrog Create" width="200">
</p>

<h1 align="center">PeeperFrog Create MCP</h1>

A multi-provider MCP (Model Context Protocol) server for AI image generation. Supports Google Gemini, OpenAI (gpt-image-1), and Together AI (FLUX) with single and batch generation, reference images, cost estimation, WebP conversion, and WordPress upload.

## Supported Providers

| Provider | Quality Tiers | Reference Images | Max Resolution | Approx. Cost |
|---|---|---|---|---|
| **Gemini** (default) | Pro: Gemini 3 Pro, Fast: Gemini 2.5 Flash | Up to 14 (Pro only) | 4K | $0.039 - $0.24 |
| **OpenAI** | Pro: gpt-image-1 (high), Fast: gpt-image-1 (low) | Not supported | 1536x1024 | $0.011 - $0.25 |
| **Together** | Pro: FLUX.1-pro, Fast: FLUX.1-schnell | Not supported | 2048x2048 | $0.003 - $0.17 |

## Features

- **Auto mode** -- automatically selects the best model based on cost tier, style, and constraints
- **Multi-provider** -- switch between Gemini, OpenAI, and Together AI per image
- **Two quality tiers** -- Pro (best quality) and Fast (cheaper/quicker) for each provider
- **Reference images** -- up to 14 reference images per generation (Gemini Pro only)
- **Batch generation** -- queue multiple images, review, then generate in one run
- **Google Search Grounding** -- use real-time Google Search data for factually accurate images (Gemini only)
- **Thinking levels** -- configurable reasoning depth (minimal/low/medium/high) for complex compositions (Gemini Pro only)
- **Media resolution control** -- control input processing resolution: low, medium, high, or auto (Gemini only)
- **Cost estimation** -- estimated USD cost returned with every generation
- **WebP conversion** -- convert PNG/JPG to WebP for web optimization
- **WordPress upload** -- upload WebP images directly to WordPress media library
- **Configurable** -- all paths, limits, and delays via `config.json`; pricing via `pricing.json`

## Tools Provided

| Tool | Description |
|------|-------------|
| `generate_image` | Generate a single image immediately (any provider) |
| `add_to_batch` | Queue an image for batch generation |
| `remove_from_batch` | Remove from queue by index or filename |
| `view_batch_queue` | View queued images |
| `run_batch` | Generate all queued images |
| `estimate_image_cost` | Get a cost estimate without generating anything |
| `get_generation_cost` | Query cost from generation log by filename or date range |
| `convert_to_webp` | Convert generated images to WebP |
| `upload_to_wordpress` | Upload WebP images to WordPress (credentials from config.json) |
| `get_generated_webp_images` | Get base64 data of WebP images |

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

### 4. Install dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install requests
```

### 5. Add to your MCP client

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
      "args": ["/path/to/peeperfrog-create/peeperfrog-create-mcp/src/image_server.py"],
      "env": {
        "GEMINI_API_KEY": "your-key",
        "OPENAI_API_KEY": "your-key",
        "TOGETHER_API_KEY": "your-key"
      }
    }
  }
}
```

## Project Structure

```
peeperfrog-create-mcp/
├── src/
│   ├── image_server.py            # Main MCP server
│   ├── batch_manager.py           # Batch queue management
│   └── batch_generate.py          # Batch image generation
├── scripts/
│   └── webp-convert.py            # PNG/JPG to WebP converter
├── docs/
│   └── systemd-service.example    # Systemd service template
├── config.json.example
├── pricing.json                   # Provider pricing for cost estimation
├── .env.example
├── .gitignore
├── LICENSE
└── README.md
```

## Usage

### Generate with different providers

```javascript
// Gemini (default)
generate_image({ prompt: "A sunset", provider: "gemini", quality: "pro" })

// OpenAI
generate_image({ prompt: "A sunset", provider: "openai", quality: "pro" })

// Together AI (FLUX)
generate_image({ prompt: "A sunset", provider: "together", quality: "fast" })
```

### Batch with mixed providers

```javascript
add_to_batch({ prompt: "Hero image", provider: "gemini", quality: "pro" })
add_to_batch({ prompt: "Social post", provider: "together", quality: "fast" })
run_batch()
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

Apache 2.0
