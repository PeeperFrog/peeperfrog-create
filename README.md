<p align="center">
  <img src="docs/logo.png" alt="PeeperFrog Create" width="200">
</p>

<h1 align="center">PeeperFrog Create</h1>

<p align="center">
An MCP server and Claude Skills for creative workflows.
</p>

---

## What is PeeperFrog Create?

PeeperFrog Create is an **MCP (Model Context Protocol) server** with a growing set of capabilities, paired with **Claude Skills** that teach Claude how to use them effectively. It plugs directly into Claude Code and other MCP-compatible clients.

### Capabilities

- **Image generation** -- Multi-provider AI image generation supporting Google Gemini, OpenAI, and Together AI (FLUX). Includes auto mode, batch generation, reference images, cost estimation, WebP conversion, and WordPress upload.
- **Claude Skills** -- SKILL files for auto mode selection, manual provider control, and brand guideline templates. More Skills will be added as capabilities grow.

New capabilities and integrations with other services are in active development.

## Quick Start

```bash
git clone https://github.com/PeeperFrog/peeperfrog-create.git
cd peeperfrog-create/peeperfrog-create-mcp

cp config.json.example config.json
cp .env.example .env
# Add your API keys to .env

python3 -m venv venv
source venv/bin/activate
pip install requests
```

Add the MCP server to your settings file:

| Client | OS | Path |
|---|---|---|
| **Claude Code** | All | `~/.claude/settings.json` |
| **Claude Desktop** | Linux | `~/.config/Claude/claude_desktop_config.json` |
| **Claude Desktop** | macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| **Claude Desktop** | Windows | `%APPDATA%\Claude\claude_desktop_config.json` |

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

See the full [MCP server documentation](peeperfrog-create-mcp/README.md) for provider details, auto mode, batch workflows, and pricing.

## Installing Skills

Skills teach Claude how to use the MCP tools effectively. They work in both **Claude Desktop** (the GUI app) and **Claude Code** (the CLI).

### Available skills

| Skill | Description |
|-------|-------------|
| `image-generation` | Overview of all image generation tools |
| `image-auto-mode` | Auto mode -- server picks the best model for your budget |
| `image-manual-control` | Manual provider/model selection and advanced options |
| `image-queue-management` | Manage batch queue -- add, remove, view, and run queued images |
| `cost-estimation` | Estimate costs before generating -- compare providers and batch totals |
| `webp-conversion` | Convert generated images to WebP for web optimization |
| `wordpress-upload` | Upload WebP images to WordPress (credentials from config.json) |
| `graphic-prompt-types` | Reference guide for graphic design prompt categories |
| `example-brand-image-guidelines` | Template for brand-specific image style guides |

### Claude Desktop (GUI app)

Skills are supported on Claude Desktop for Mac, Windows, and Linux (Pro plan and above).

1. Open **Settings > Capabilities**
2. Toggle on **Skills** if not already enabled
3. Click **Add > Upload a skill**
4. Upload each `SKILL.md` file from the `skills/` folder in this repo

Repeat for each skill you want to install. Skills sync between Claude Desktop and Claude.ai (web).

### Claude Code (CLI)

Copy the skill files into your Claude Code skills directory:

**Linux / macOS:**

```bash
cp -r skills/* ~/.claude/skills/
```

**Windows (PowerShell):**

```powershell
Copy-Item -Recurse -Path skills\* -Destination $env:USERPROFILE\.claude\skills\
```

**Windows (Git Bash or WSL):**

```bash
cp -r skills/* ~/.claude/skills/
```

Once installed, type `/` in Claude Code to see available skills, or Claude will auto-discover them based on context.

#### Project-level installation (alternative)

To scope skills to a single project instead of making them global:

```bash
cp -r skills/* /path/to/your/project/.claude/skills/
```

## Project Structure

```
peeperfrog-create/
├── peeperfrog-create-mcp/   # MCP server source
│   ├── src/                   # Server code
│   ├── scripts/               # Utility scripts (WebP conversion)
│   └── README.md              # Full documentation
├── skills/                    # Claude SKILL files
├── tests/                     # Test suite
└── docs/                      # Project assets
```

## License

Apache 2.0
