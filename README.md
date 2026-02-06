<p align="center">
  <img src="docs/logo for PF Create.png" alt="PeeperFrog Create" width="200">
</p>

<h1 align="center">PeeperFrog Create</h1>

<h2 align="center">Like Bluetooth for AI</h2>
</p>

<p align="center">
<strong>Version 1.0 Beta</strong> | MCP servers and Claude Skills for creative workflows | Designed for Creators
</p>

---

> **Owned and maintained by [PeeperFrog Press](https://peeperfrog.com)**
>
> Open source under the [Apache 2.0 License](LICENSE)
>
> **Not affiliated with Anthropic, Claude, LinkedIn, Microsoft, Google, Gemini, OpenAI, ChatGPT, Automattic, WordPress, or any other third-party service.** All product names, trademarks, and registered trademarks are the property of their respective owners. This project simply provides integrations to connect these services.[Full Disclaimer](DISCLAIMER.md)

---

## Status

**Version 1.0 features are complete.** The project is currently in the testing phase with a beta test program starting soon.

**Platform support:** Linux, macOS, and Windows

**Designed to complement:** Claude Desktop and Claude Code CLI

---

## Like Bluetooth for AI

Think of how Bluetooth connects your phone to your headphones -- you don't manage audio encoding, you just play music.

**PeeperFrog Create works the same way for AI:**

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  AI Assistant   │     │   MCP Server    │     │  External APIs  │
│  (Claude)       │────▶│   (Local)       │────▶│  (Cloud)        │
│                 │     │                 │     │                 │
│  "Generate a    │     │  Handles all    │     │  Gemini, OpenAI │
│   hero image    │     │  data movement, │     │  LinkedIn, etc. │
│   and post it   │     │  API calls,     │     │                 │
│   to LinkedIn"  │     │  credentials    │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
     Conceptual              Technical              Secure APIs
```

- **The AI stays conceptual** -- it describes what it wants ("generate an image," "post to LinkedIn") without handling raw data
- **The MCP runs locally** -- all API keys and secrets stay on your machine, never exposed to the AI
- **Skills teach in plain language** -- they tell the AI how to use available tools, turning it into an agent with extended capabilities
- **Secure APIs handle the rest** -- proven, secure connections to external services

The result: your AI assistant orchestrates complex creative workflows while the technical details stay safely abstracted away.

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

### For WordPress Upload (Optional)

Upload AI-generated images directly to your WordPress media library. No API key needed -- WordPress has built-in support.

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
- Collect and securely store your API keys (in local `.env` files)
- Configure WordPress sites for image uploads (optional)
- Install Claude Skills
- Generate MCP configuration for your settings file

**Security:** API keys are stored in `.env` files within the codebase, not in Claude's settings. This keeps your credentials out of Claude's view.

**To update an existing installation:**

```bash
update-pfc
```

The script detects the existing installation and pulls updates. If dependencies changed, it reinstalls them automatically.

**To update and restart Claude Code:**

```bash
update-pfc --restart
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
cp .env.example .env
# Edit .env with your API keys (Gemini, OpenAI, and/or Together AI)
# Edit config.json to add WordPress sites (optional, requires Application Password -- see Prerequisites)
python3 -m venv venv
source venv/bin/activate
pip install requests mcp
```

Add to your MCP settings (no secrets needed - they're in .env and config.json):

```json
{
  "mcpServers": {
    "peeperfrog-create": {
      "command": "/path/to/peeperfrog-create-mcp/venv/bin/python3",
      "args": ["/path/to/peeperfrog-create-mcp/src/image_server.py"]
    }
  }
}
```

See the full [Image MCP documentation](peeperfrog-create-mcp/README.md) for provider details, auto mode, batch workflows, and pricing.

#### LinkedIn MCP

```bash
cd peeperfrog-create/peeperfrog-linkedin-mcp
cp .env.example .env
# Edit .env with your LinkedIn Client ID and Secret
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python src/oauth_setup.py  # Complete OAuth flow in browser
```

Add to your MCP settings (no secrets needed - they're in .env):

```json
{
  "mcpServers": {
    "peeperfrog-linkedin": {
      "command": "/path/to/peeperfrog-linkedin-mcp/venv/bin/python3",
      "args": ["/path/to/peeperfrog-linkedin-mcp/src/linkedin_server.py"]
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
| `webp-conversion` | Bulk convert images to WebP (auto conversion is the default) |
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
├── update-pfc.sh              # Quick update script (symlinked to PATH by setup.py)
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

[Apache 2.0](LICENSE) | [Full Disclaimer](DISCLAIMER.md)

---

<p align="center">
<em>Made with care by <a href="https://peeperfrog.com">PeeperFrog Press</a></em>
</p>
