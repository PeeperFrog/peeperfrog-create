<p align="center">
  <img src="docs/logo.png" alt="PeeperFrog Create" width="200">
</p>

<h1 align="center">PeeperFrog Create</h1>

<p align="center">
MCP servers and Claude Skills for creative workflows.
</p>

---

## What is PeeperFrog Create?

PeeperFrog Create is a collection of **MCP (Model Context Protocol) servers** with a growing set of capabilities, paired with **Claude Skills** that teach Claude how to use them effectively. They plug directly into Claude Code and other MCP-compatible clients.

### Capabilities

- **Image generation** -- Multi-provider AI image generation supporting Google Gemini, OpenAI, and Together AI (FLUX). Includes auto mode, batch generation, reference images, cost estimation, automatic WebP conversion, and WordPress upload.
- **LinkedIn posting** -- Post to personal profiles and Company Pages via the LinkedIn Marketing API. Supports text posts, link posts with previews, image posts, drafts, comments, reactions, and analytics.
- **Claude Skills** -- SKILL files for image generation, LinkedIn posting, and brand guideline templates. More Skills will be added as capabilities grow.

New capabilities and integrations with other services are in active development.

## Prerequisites

Before you start, you'll need API keys for the services you want to use. You don't need all of them -- just the ones for your workflow.

### For Image Generation MCP

You need **at least one** of these (all are optional, use what you need):

| Provider | Where to Get It | Notes |
|----------|-----------------|-------|
| **Google Gemini** | [Google AI Studio](https://aistudio.google.com/apikey) | Click "Create API key". Free tier available. |
| **OpenAI** | [OpenAI Platform](https://platform.openai.com/api-keys) | Create a new secret key. Requires billing setup. |
| **Together AI** | [Together AI Settings](https://api.together.xyz/settings/api-keys) | Copy your API key. Free credits on signup. |

### For LinkedIn MCP

| Credential | Where to Get It | Required? |
|------------|-----------------|-----------|
| **Client ID** | [LinkedIn Developers](https://www.linkedin.com/developers/apps) | Yes - Create an app, find in Auth tab |
| **Client Secret** | [LinkedIn Developers](https://www.linkedin.com/developers/apps) | Yes - Find in Auth tab of your app |
| **Organization ID** | Your Company Page admin URL | No - Only needed for Company Page posts |

The setup script will guide you through what's needed and let you proceed even if you don't have keys ready yet.

## Quick Start

### Automated Setup (Recommended)

The setup script handles installation, updates, and configuration:

```bash
# Download and run the setup script
curl -O https://raw.githubusercontent.com/PeeperFrog/peeperfrog-create/main/setup.py
python3 setup.py
```

The script will:
- Clone the repository (or pull updates if already installed)
- Create virtual environments for each MCP server
- Install dependencies
- Copy config templates
- Install Claude Skills
- Generate MCP configuration for your settings file

**To update an existing installation:**

```bash
cd ~/peeperfrog-create
python3 setup.py
```

The script detects the existing installation and pulls updates. If dependencies changed, it reinstalls them automatically.

**To update and restart Claude Code:**

```bash
python3 setup.py --restart
```

### Manual Setup

If you prefer to set things up manually:

```bash
git clone https://github.com/PeeperFrog/peeperfrog-create.git
```

Each MCP server has its own setup. Install only the servers you need.

#### MCP Settings File Location

| Client | OS | Path |
|---|---|---|
| **Claude Code** | All | `~/.claude/settings.json` |
| **Claude Desktop** | Linux | `~/.config/Claude/claude_desktop_config.json` |
| **Claude Desktop** | macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| **Claude Desktop** | Windows | `%APPDATA%\Claude\claude_desktop_config.json` |

#### Image Generation MCP

```bash
cd peeperfrog-create/peeperfrog-create-mcp
cp config.json.example config.json
python3 -m venv venv
source venv/bin/activate
pip install requests mcp
```

Add to your MCP settings:

```json
{
  "mcpServers": {
    "peeperfrog-create": {
      "command": "/path/to/peeperfrog-create-mcp/venv/bin/python3",
      "args": ["/path/to/peeperfrog-create-mcp/src/image_server.py"],
      "env": {
        "GEMINI_API_KEY": "your-key",
        "OPENAI_API_KEY": "your-key",
        "TOGETHER_API_KEY": "your-key"
      }
    }
  }
}
```

See the full [Image MCP documentation](peeperfrog-create-mcp/README.md) for provider details, auto mode, batch workflows, and pricing.

#### LinkedIn MCP

```bash
cd peeperfrog-create/peeperfrog-linkedin-mcp
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python src/oauth_setup.py  # Complete OAuth flow in browser
```

Add to your MCP settings:

```json
{
  "mcpServers": {
    "peeperfrog-linkedin": {
      "command": "/path/to/peeperfrog-linkedin-mcp/venv/bin/python3",
      "args": ["/path/to/peeperfrog-linkedin-mcp/src/linkedin_server.py"],
      "env": {
        "LINKEDIN_CLIENT_ID": "your_client_id",
        "LINKEDIN_CLIENT_SECRET": "your_client_secret",
        "LINKEDIN_ORG_ID": "your_org_id"
      }
    }
  }
}
```

See the full [LinkedIn MCP documentation](peeperfrog-linkedin-mcp/README.md) for setup, available tools, and usage examples.

## Applying Changes After Updates

After updating PeeperFrog Create, you need to restart for changes to take effect.

### Claude Code (CLI)

MCP servers and skills are loaded when Claude Code starts. To apply updates:

```bash
# Exit your current Claude Code session (Ctrl+C or type /exit)
# Then restart:
claude
```

Or use the setup script with `--restart`:

```bash
python3 setup.py --restart
```

Skills in `~/.claude/skills/` are read fresh each session -- no extra steps needed after the setup script copies them.

### Claude Desktop (GUI app)

**For MCP server updates:**

1. Quit Claude Desktop completely (not just close the window)
   - **macOS:** Right-click the dock icon > Quit, or Cmd+Q
   - **Windows:** Right-click system tray icon > Exit
   - **Linux:** Right-click system tray icon > Quit
2. Relaunch Claude Desktop

**For skill updates:**

Skills in Claude Desktop are stored in the cloud and must be re-uploaded manually:

1. Open **Settings > Capabilities**
2. Find the skill you want to update
3. Delete the old version
4. Click **Add > Upload a skill**
5. Upload the updated `SKILL.md` file from the `skills/` folder

Skills sync automatically between Claude Desktop and Claude.ai (web) once uploaded.

## Installing Skills

Skills teach Claude how to use the MCP tools effectively. They work in both **Claude Desktop** (the GUI app) and **Claude Code** (the CLI), but are installed differently for each.

### Available skills

| Skill | Description |
|-------|-------------|
| `image-generation` | Overview of all image generation tools |
| `image-auto-mode` | Auto mode -- server picks the best model for your budget |
| `image-manual-control` | Manual provider/model selection and advanced options |
| `image-queue-management` | Manage batch queue -- add, remove, view, and run queued images |
| `cost-estimation` | Estimate costs before generating -- compare providers and batch totals |
| `webp-conversion` | Bulk convert images to WebP (auto conversion is now default) |
| `wordpress-upload` | Upload WebP images to WordPress (credentials from config.json) |
| `linkedin-posting` | Post to LinkedIn personal profiles and Company Pages |
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
├── setup.py                   # Smart installer (install + update)
├── peeperfrog-create-mcp/     # Image generation MCP server
│   ├── src/                     # Server code
│   ├── scripts/                 # Utility scripts (WebP conversion)
│   └── README.md                # Full documentation
├── peeperfrog-linkedin-mcp/   # LinkedIn MCP server
│   ├── src/                     # Server code
│   └── README.md                # Full documentation
├── skills/                    # Claude SKILL files
├── tests/                     # Test suite
└── docs/                      # Project assets
```

## License

[Apache 2.0](LICENSE)
