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
cd peeperfrog-create/peeperfrog-create-image

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
      "command": "/path/to/peeperfrog-create/peeperfrog-create-image/venv/bin/python3",
      "args": ["/path/to/peeperfrog-create/peeperfrog-create-image/src/image_server.py"],
      "env": {
        "GEMINI_API_KEY": "your-key",
        "OPENAI_API_KEY": "your-key",
        "TOGETHER_API_KEY": "your-key"
      }
    }
  }
}
```

See the full [image server documentation](peeperfrog-create-image/README.md) for provider details, auto mode, batch workflows, and pricing.

## Project Structure

```
peeperfrog-create/
├── peeperfrog-create-image/   # MCP server source
│   ├── src/                   # Server code
│   ├── skills/                # Claude SKILL files
│   ├── scripts/               # Utility scripts (WebP conversion)
│   └── README.md              # Full documentation
├── tools/                     # Workflow guides
├── tests/                     # Test suite
└── docs/                      # Project assets
```

## License

Apache 2.0
