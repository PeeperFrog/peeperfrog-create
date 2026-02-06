#!/usr/bin/env python3
"""
PeeperFrog Create - Smart Setup Script

This script handles both installation and updates:
- First run: Clones repo, creates venvs, installs dependencies
- Subsequent runs: Pulls updates, reinstalls dependencies if changed

Usage:
    python3 setup.py              # Interactive setup
    python3 setup.py --update     # Update only (skip prompts)
    python3 setup.py --restart    # Restart Claude Code after setup
"""

import os
import sys
import subprocess
import shutil
import json
import hashlib
import platform
import signal
from pathlib import Path

# Configuration
REPO_URL = "https://github.com/PeeperFrog/peeperfrog-create.git"
DEFAULT_INSTALL_DIR = Path.home() / "peeperfrog-create"

# API key information with where to get them
API_KEY_INFO = {
    "GEMINI_API_KEY": {
        "name": "Google Gemini API Key",
        "required": False,
        "description": "For AI image generation with Google Gemini models",
        "url": "https://aistudio.google.com/apikey",
        "instructions": "Click 'Create API key'. Free tier available.",
    },
    "OPENAI_API_KEY": {
        "name": "OpenAI API Key",
        "required": False,
        "description": "For AI image generation with gpt-image-1",
        "url": "https://platform.openai.com/api-keys",
        "instructions": "Create a new secret key. Requires billing setup.",
    },
    "TOGETHER_API_KEY": {
        "name": "Together AI API Key",
        "required": False,
        "description": "For AI image generation with FLUX models",
        "url": "https://api.together.xyz/settings/api-keys",
        "instructions": "Copy your API key. Free credits on signup.",
    },
    "LINKEDIN_CLIENT_ID": {
        "name": "LinkedIn Client ID",
        "required": True,
        "description": "OAuth app client ID for LinkedIn API access",
        "url": "https://www.linkedin.com/developers/apps",
        "instructions": "Create an app, then find Client ID in the Auth tab.",
    },
    "LINKEDIN_CLIENT_SECRET": {
        "name": "LinkedIn Client Secret",
        "required": True,
        "description": "OAuth app client secret for LinkedIn API access",
        "url": "https://www.linkedin.com/developers/apps",
        "instructions": "Find Client Secret in the Auth tab of your app.",
    },
    "LINKEDIN_ORG_ID": {
        "name": "LinkedIn Organization ID",
        "required": False,
        "description": "For posting to Company Pages (optional, personal posts work without it)",
        "url": "https://www.linkedin.com/company/YOUR_COMPANY/admin",
        "instructions": "Find in your Company Page admin URL, or leave empty for personal posts only.",
    },
}

# MCP servers to set up
MCP_SERVERS = {
    "peeperfrog-create-mcp": {
        "name": "Image Generation MCP",
        "description": "Multi-provider AI image generation (Gemini, OpenAI, Together/FLUX)",
        "dependencies": ["requests", "mcp"],
        "server_script": "src/image_server.py",
        "config_example": "config.json.example",
        "config_file": "config.json",
        "env_vars": ["GEMINI_API_KEY", "OPENAI_API_KEY", "TOGETHER_API_KEY"],
        "min_keys_required": 1,  # Need at least one provider
        "prereq_note": "You need at least ONE API key (Gemini, OpenAI, or Together AI) to use this server.",
    },
    "peeperfrog-linkedin-mcp": {
        "name": "LinkedIn MCP",
        "description": "Post to LinkedIn personal profiles and Company Pages",
        "requirements_file": "requirements.txt",
        "server_script": "src/linkedin_server.py",
        "env_vars": ["LINKEDIN_CLIENT_ID", "LINKEDIN_CLIENT_SECRET", "LINKEDIN_ORG_ID"],
        "min_keys_required": 2,  # Need client ID and secret at minimum
        "prereq_note": "You need a LinkedIn Developer App with Client ID and Secret. Organization ID is optional.",
        "post_setup": "oauth_setup",
    },
}


def run_command(cmd, cwd=None, capture=False):
    """Run a shell command."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=capture,
            text=True,
            check=True,
        )
        return result.stdout.strip() if capture else True
    except subprocess.CalledProcessError as e:
        if capture:
            return None
        print(f"  Error: {e}")
        return False


def get_file_hash(filepath):
    """Get MD5 hash of a file for change detection."""
    if not filepath.exists():
        return None
    return hashlib.md5(filepath.read_bytes()).hexdigest()


def is_installed(install_dir):
    """Check if PeeperFrog Create is already installed."""
    return (install_dir / ".git").exists()


def git_pull(install_dir):
    """Pull latest changes from remote."""
    print("\n📥 Pulling latest updates...")

    # Check if setup.py is untracked (curl'd in) and would conflict
    script_path = install_dir / "setup.py"
    if script_path.exists():
        # Check if it's untracked
        status = run_command("git status --porcelain setup.py", cwd=install_dir, capture=True)
        if status and status.startswith("??"):
            # It's untracked - remove it so git pull can bring in the tracked version
            print("  Removing downloaded setup.py (will be replaced by tracked version)...")
            script_path.unlink()

    result = run_command("git pull", cwd=install_dir, capture=True)
    if result is None:
        # Try to get more info about the error
        error_check = run_command("git pull 2>&1", cwd=install_dir, capture=True)
        if error_check and "untracked working tree files would be overwritten" in error_check:
            print("  Error: Untracked files would be overwritten by update.")
            print("  Please commit or remove these files, then run setup.py again:")
            # Show which files
            run_command("git status --short", cwd=install_dir)
        else:
            print("  Failed to pull updates")
        return False
    print(f"  {result}")
    return True


def clone_repo(install_dir):
    """Clone the repository."""
    print(f"\n📦 Cloning repository to {install_dir}...")
    if install_dir.exists():
        print(f"  Directory exists but is not a git repo. Remove it first.")
        return False
    return run_command(f"git clone {REPO_URL} {install_dir}")


def setup_venv(mcp_dir):
    """Create or update virtual environment."""
    venv_dir = mcp_dir / "venv"
    if venv_dir.exists():
        print("  Virtual environment exists")
        return True
    print("  Creating virtual environment...")
    return run_command(f"python3 -m venv {venv_dir}")


def install_dependencies(mcp_dir, server_config):
    """Install Python dependencies."""
    venv_pip = mcp_dir / "venv" / "bin" / "pip"

    if "requirements_file" in server_config:
        req_file = mcp_dir / server_config["requirements_file"]
        if req_file.exists():
            print(f"  Installing from {server_config['requirements_file']}...")
            return run_command(f"{venv_pip} install -r {req_file}")

    if "dependencies" in server_config:
        deps = " ".join(server_config["dependencies"])
        print(f"  Installing: {deps}...")
        return run_command(f"{venv_pip} install {deps}")

    return True


def setup_config(mcp_dir, server_config):
    """Copy config example if config doesn't exist."""
    if "config_example" not in server_config:
        return True

    config_example = mcp_dir / server_config["config_example"]
    config_file = mcp_dir / server_config["config_file"]

    if config_file.exists():
        print(f"  Config file already exists: {server_config['config_file']}")
        return True

    if config_example.exists():
        print(f"  Creating {server_config['config_file']} from example...")
        shutil.copy(config_example, config_file)
        return True

    return True


def print_api_key_instructions(env_vars):
    """Print instructions for obtaining API keys."""
    print("\n" + "=" * 60)
    print("🔑 API Keys Required")
    print("=" * 60)

    for var in env_vars:
        info = API_KEY_INFO.get(var, {})
        required_str = "(Required)" if info.get("required", False) else "(Optional)"
        print(f"\n  {info.get('name', var)} {required_str}")
        print(f"    {info.get('description', '')}")
        print(f"    Get it here: {info.get('url', 'N/A')}")
        print(f"    {info.get('instructions', '')}")


def check_api_key_readiness(server_id):
    """Ask user if they have the required API keys, provide guidance if not."""
    server_config = MCP_SERVERS[server_id]
    env_vars = server_config.get("env_vars", [])

    if not env_vars:
        return True

    print(f"\n{'=' * 60}")
    print(f"📋 Prerequisites for {server_config['name']}")
    print("=" * 60)
    print(f"\n  {server_config.get('prereq_note', '')}")
    print("\n  This server uses the following API keys/credentials:\n")

    for var in env_vars:
        info = API_KEY_INFO.get(var, {})
        required_str = "REQUIRED" if info.get("required", False) else "optional"
        print(f"    • {info.get('name', var)} ({required_str})")

    print()
    has_keys = prompt_yes_no("Do you have the required API keys/credentials ready?", default=False)

    if not has_keys:
        print_api_key_instructions(env_vars)
        print("\n" + "-" * 60)
        print("You can still proceed with installation. The MCP server will be")
        print("set up, but you'll need to add your API keys to the MCP settings")
        print("file before using it.")
        print("-" * 60)

        proceed = prompt_yes_no("\nProceed with installation anyway?", default=True)
        if not proceed:
            return False

    return True


def generate_mcp_config(install_dir, selected_servers, collected_keys=None):
    """Generate MCP configuration snippet with comments for optional keys."""
    if collected_keys is None:
        collected_keys = {}

    config = {"mcpServers": {}}

    for server_id in selected_servers:
        server_config = MCP_SERVERS[server_id]
        mcp_dir = install_dir / server_id
        venv_python = mcp_dir / "venv" / "bin" / "python3"
        server_script = mcp_dir / server_config["server_script"]

        # Server name for config
        if server_id == "peeperfrog-create-mcp":
            config_name = "peeperfrog-create"
        elif server_id == "peeperfrog-linkedin-mcp":
            config_name = "peeperfrog-linkedin"
        else:
            config_name = server_id.replace("-mcp", "")

        # Build env vars with helpful placeholders
        env_dict = {}
        for var in server_config.get("env_vars", []):
            info = API_KEY_INFO.get(var, {})
            if var in collected_keys and collected_keys[var]:
                env_dict[var] = collected_keys[var]
            elif info.get("required", False):
                env_dict[var] = f"YOUR_{var}_HERE"
            else:
                # For optional keys, use a descriptive placeholder
                env_dict[var] = f"OPTIONAL_{var}_OR_REMOVE_THIS_LINE"

        config["mcpServers"][config_name] = {
            "command": str(venv_python),
            "args": [str(server_script)],
            "env": env_dict,
        }

    return config


def print_mcp_config(config, selected_servers):
    """Pretty print MCP configuration with notes about optional keys."""
    print("\n" + "=" * 60)
    print("📋 Add this to your MCP settings file:")
    print("=" * 60)

    # Print notes about optional keys
    has_optional = False
    for server_id in selected_servers:
        server_config = MCP_SERVERS[server_id]
        for var in server_config.get("env_vars", []):
            info = API_KEY_INFO.get(var, {})
            if not info.get("required", False):
                has_optional = True
                break

    if has_optional:
        print("\nNote: Lines with 'OPTIONAL_...' can be removed if you don't")
        print("need that provider. You only need keys for providers you'll use.")
        print()

    print(json.dumps(config, indent=2))
    print()
    print("=" * 60)
    print()
    print("MCP Settings file locations:")
    print("  Claude Code:    ~/.claude/settings.json")
    print("  Claude Desktop:")
    print("    Linux:        ~/.config/Claude/claude_desktop_config.json")
    print("    macOS:        ~/Library/Application Support/Claude/claude_desktop_config.json")
    print("    Windows:      %APPDATA%\\Claude\\claude_desktop_config.json")


def install_skills(install_dir):
    """Copy skills to Claude Code skills directory."""
    skills_src = install_dir / "skills"
    skills_dest = Path.home() / ".claude" / "skills"

    if not skills_src.exists():
        return 0

    print("\n🎯 Installing Claude Code Skills...")
    print("   (This installs skills for Claude Code CLI only)")
    skills_dest.mkdir(parents=True, exist_ok=True)

    count = 0
    for skill_file in skills_src.glob("*.md"):
        dest_file = skills_dest / skill_file.name
        shutil.copy(skill_file, dest_file)
        print(f"  Installed: {skill_file.name}")
        count += 1

    return count


def print_claude_desktop_skills_instructions(install_dir):
    """Print instructions for installing skills in Claude Desktop."""
    skills_src = install_dir / "skills"
    if not skills_src.exists():
        return

    skill_files = list(skills_src.glob("*.md"))
    if not skill_files:
        return

    print("\n" + "-" * 60)
    print("📱 For Claude Desktop (GUI app):")
    print("-" * 60)
    print("Skills must be uploaded manually through the app:")
    print("  1. Open Claude Desktop")
    print("  2. Go to Settings > Capabilities")
    print("  3. Toggle on 'Skills' if not already enabled")
    print("  4. Click 'Add' > 'Upload a skill'")
    print(f"  5. Upload files from: {skills_src}")
    print()
    print("Skills sync between Claude Desktop and Claude.ai (web).")
    print("-" * 60)


def find_claude_processes():
    """Find running Claude Code processes."""
    processes = []
    try:
        # Try pgrep first (Linux/macOS)
        result = subprocess.run(
            ["pgrep", "-f", "claude"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            for pid in result.stdout.strip().split("\n"):
                if pid:
                    processes.append(int(pid))
    except FileNotFoundError:
        # pgrep not available, try ps
        try:
            result = subprocess.run(
                ["ps", "aux"],
                capture_output=True,
                text=True
            )
            for line in result.stdout.split("\n"):
                if "claude" in line.lower() and "python" not in line.lower():
                    parts = line.split()
                    if len(parts) > 1:
                        try:
                            processes.append(int(parts[1]))
                        except ValueError:
                            pass
        except Exception:
            pass

    return processes


def restart_claude_code():
    """Attempt to restart Claude Code."""
    print("\n🔄 Restarting Claude Code...")

    # Find Claude processes
    processes = find_claude_processes()

    if not processes:
        print("  No running Claude Code processes found.")
        print("  Start Claude Code manually when ready.")
        return False

    # Kill existing processes
    killed = 0
    for pid in processes:
        try:
            os.kill(pid, signal.SIGTERM)
            killed += 1
            print(f"  Stopped process {pid}")
        except (OSError, ProcessLookupError):
            pass

    if killed > 0:
        print(f"  Stopped {killed} Claude process(es).")
        print()
        print("  To restart Claude Code, run:")
        print("    claude")
        print()
        print("  Or if using Claude Desktop, relaunch the application.")
        return True

    return False


def prompt_yes_no(question, default=True):
    """Prompt user for yes/no answer."""
    default_str = "Y/n" if default else "y/N"
    response = input(f"{question} [{default_str}]: ").strip().lower()
    if not response:
        return default
    return response in ("y", "yes")


def prompt_selection(options, prompt_text):
    """Prompt user to select from options."""
    print(f"\n{prompt_text}")
    for i, (key, config) in enumerate(options.items(), 1):
        print(f"  {i}. {config['name']} - {config.get('description', '')}")
    print(f"  A. All of the above")

    while True:
        response = input("\nSelect options (comma-separated, e.g., 1,2 or A for all): ").strip().upper()
        if response == "A":
            return list(options.keys())

        try:
            indices = [int(x.strip()) for x in response.split(",")]
            selected = []
            for i in indices:
                if 1 <= i <= len(options):
                    selected.append(list(options.keys())[i - 1])
            if selected:
                return selected
        except ValueError:
            pass

        print("Invalid selection. Please try again.")


def print_prerequisites_summary():
    """Print a summary of all prerequisites before starting."""
    print("\n" + "=" * 60)
    print("📋 Before You Start")
    print("=" * 60)
    print("""
This installer will set up MCP servers for Claude Code/Desktop.
Here's what you might need:

For Image Generation MCP:
  • At least ONE of: Gemini, OpenAI, or Together AI API key
  • All providers are optional - use only what you need
  • Free tiers available for Gemini and Together AI

For LinkedIn MCP:
  • LinkedIn Developer App (Client ID + Secret) - required
  • Organization ID - optional, only for Company Page posts

You can proceed without keys and add them later to your
MCP settings file.
""")


def main():
    print()
    print("=" * 60)
    print("  PeeperFrog Create - Setup Script")
    print("=" * 60)

    # Parse arguments
    update_only = "--update" in sys.argv
    do_restart = "--restart" in sys.argv

    # Determine install directory
    install_dir = DEFAULT_INSTALL_DIR

    # Check if running from within the repo
    script_dir = Path(__file__).resolve().parent
    if (script_dir / ".git").exists() and (script_dir / "peeperfrog-create-mcp").exists():
        install_dir = script_dir
        print(f"\n📍 Running from existing installation: {install_dir}")

    # Check installation status
    already_installed = is_installed(install_dir)

    # Track if we need to suggest restart
    needs_restart = False
    skills_installed = 0

    if already_installed:
        print(f"\n✅ Existing installation detected at: {install_dir}")

        # Store hashes of requirements files before pull
        req_hashes_before = {}
        for server_id, config in MCP_SERVERS.items():
            if "requirements_file" in config:
                req_file = install_dir / server_id / config["requirements_file"]
                req_hashes_before[server_id] = get_file_hash(req_file)

        # Pull updates
        if not git_pull(install_dir):
            print("\n❌ Failed to update. Please check your git configuration.")
            return 1

        # Check if requirements changed
        deps_changed = False
        for server_id, hash_before in req_hashes_before.items():
            config = MCP_SERVERS[server_id]
            req_file = install_dir / server_id / config["requirements_file"]
            if get_file_hash(req_file) != hash_before:
                deps_changed = True
                needs_restart = True
                print(f"\n📦 Dependencies changed for {config['name']}")

        # Update dependencies if changed
        if deps_changed:
            print("\n🔄 Updating dependencies...")
            for server_id in MCP_SERVERS:
                mcp_dir = install_dir / server_id
                if mcp_dir.exists():
                    print(f"\n  {MCP_SERVERS[server_id]['name']}:")
                    install_dependencies(mcp_dir, MCP_SERVERS[server_id])

        # Update skills
        skills_installed = install_skills(install_dir)

        print("\n✅ Update complete!")

        # Show Claude Desktop instructions
        print_claude_desktop_skills_instructions(install_dir)

        # Handle restart
        if needs_restart:
            print("\n⚠️  MCP server code was updated. Restart required for changes to take effect.")
            if do_restart:
                restart_claude_code()
            elif not update_only:
                if prompt_yes_no("\nRestart Claude Code now?", default=False):
                    restart_claude_code()
                else:
                    print("\n  Remember to restart Claude Code to apply changes.")

    else:
        # Fresh installation
        print(f"\n🆕 Fresh installation to: {install_dir}")

        if not update_only:
            print_prerequisites_summary()

            if not prompt_yes_no("Proceed with installation?"):
                print("\nInstallation cancelled.")
                return 0

        # Clone repository
        if not clone_repo(install_dir):
            print("\n❌ Failed to clone repository.")
            return 1

        # Select which MCPs to install
        if update_only:
            selected_servers = list(MCP_SERVERS.keys())
        else:
            selected_servers = prompt_selection(MCP_SERVERS, "Which MCP servers do you want to set up?")

        # Check API key readiness for each selected server
        servers_to_setup = []
        for server_id in selected_servers:
            if update_only or check_api_key_readiness(server_id):
                servers_to_setup.append(server_id)

        if not servers_to_setup:
            print("\nNo servers selected for setup.")
            print(f"The repository has been cloned to: {install_dir}")
            print("Run this script again when you're ready to set up the servers.")
            return 0

        # Set up each selected MCP
        for server_id in servers_to_setup:
            server_config = MCP_SERVERS[server_id]
            mcp_dir = install_dir / server_id

            print(f"\n🔧 Setting up {server_config['name']}...")

            if not mcp_dir.exists():
                print(f"  Warning: {server_id} directory not found")
                continue

            # Create venv
            if not setup_venv(mcp_dir):
                print(f"  Failed to create virtual environment")
                continue

            # Install dependencies
            if not install_dependencies(mcp_dir, server_config):
                print(f"  Failed to install dependencies")
                continue

            # Set up config
            setup_config(mcp_dir, server_config)

            print(f"  ✅ {server_config['name']} ready!")

        # Install skills
        if not update_only and prompt_yes_no("\nInstall Claude Code Skills?"):
            skills_installed = install_skills(install_dir)
            print_claude_desktop_skills_instructions(install_dir)

        # Generate and display MCP config
        mcp_config = generate_mcp_config(install_dir, servers_to_setup)
        print_mcp_config(mcp_config, servers_to_setup)

        print("\n✅ Installation complete!")
        print("\nNext steps:")
        print("  1. Add the MCP configuration above to your settings file")
        print("  2. Replace the placeholder values with your actual API keys")
        print("     (Remove lines for providers you don't need)")
        print("  3. Restart Claude Code or Claude Desktop")

        # LinkedIn-specific instructions
        if "peeperfrog-linkedin-mcp" in servers_to_setup:
            print("\n  For LinkedIn MCP (additional step):")
            print(f"    cd {install_dir / 'peeperfrog-linkedin-mcp'}")
            print("    source venv/bin/activate")
            print("    python src/oauth_setup.py  # Complete OAuth flow in browser")

    return 0


if __name__ == "__main__":
    sys.exit(main())
