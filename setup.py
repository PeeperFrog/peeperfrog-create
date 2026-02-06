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
    python3 setup.py --repair     # Force repair of broken installations
    python3 setup.py --health     # Run health check only (no updates)
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
    """Pull latest changes from remote and restore any deleted tracked files."""
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

    # Check for local modifications that would block pull
    modified_files = run_command("git diff --name-only", cwd=install_dir, capture=True)
    if modified_files:
        modified_list = [f for f in modified_files.strip().split('\n') if f]
        if modified_list:
            print(f"  Local modifications detected in {len(modified_list)} file(s):")
            for f in modified_list[:5]:  # Show first 5
                print(f"    • {f}")
            if len(modified_list) > 5:
                print(f"    • ... and {len(modified_list) - 5} more")
            print("  Resetting to match remote (local changes will be lost)...")
            run_command("git checkout -- .", cwd=install_dir)

    # Check for deleted tracked files and restore them
    deleted_files = run_command("git diff --name-only --diff-filter=D", cwd=install_dir, capture=True)
    if deleted_files:
        deleted_list = [f for f in deleted_files.strip().split('\n') if f]
        if deleted_list:
            print(f"  Restoring {len(deleted_list)} deleted file(s)...")
            run_command("git checkout -- .", cwd=install_dir)

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
        # Check if directory only contains setup.py (curl'd in)
        contents = list(install_dir.iterdir())
        setup_only = len(contents) == 1 and contents[0].name == "setup.py"

        if setup_only:
            # Directory has only the curl'd setup.py - use git init + pull
            print("  Initializing repository...")
            if not run_command("git init", cwd=install_dir):
                return False
            if not run_command(f"git remote add origin {REPO_URL}", cwd=install_dir):
                return False
            if not run_command("git fetch origin", cwd=install_dir):
                return False
            # Remove the curl'd setup.py so checkout doesn't conflict
            (install_dir / "setup.py").unlink()
            if not run_command("git checkout origin/main -b main", cwd=install_dir):
                return False
            return True
        else:
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


def check_venv_health(mcp_dir):
    """Check if virtual environment is functional.

    Returns:
        dict with keys:
            - healthy: bool - overall health status
            - issues: list of strings describing problems
            - can_repair: bool - whether issues can be auto-repaired
    """
    venv_dir = mcp_dir / "venv"
    issues = []

    # Check venv directory exists
    if not venv_dir.exists():
        return {"healthy": False, "issues": ["Virtual environment missing"], "can_repair": True}

    # Check python binary exists and is executable
    python_bin = venv_dir / "bin" / "python"
    if not python_bin.exists():
        issues.append("Python binary missing from venv")
    elif not os.access(python_bin, os.X_OK):
        issues.append("Python binary not executable")
    else:
        # Try to run python
        try:
            result = subprocess.run(
                [str(python_bin), "-c", "import sys; print(sys.version)"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                issues.append(f"Python not working: {result.stderr.strip()}")
        except subprocess.TimeoutExpired:
            issues.append("Python binary hangs/times out")
        except Exception as e:
            issues.append(f"Python error: {e}")

    # Check pip exists and works
    pip_bin = venv_dir / "bin" / "pip"
    if not pip_bin.exists():
        issues.append("pip missing from venv")
    else:
        try:
            result = subprocess.run(
                [str(pip_bin), "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                issues.append("pip not working properly")
        except Exception:
            issues.append("pip error")

    return {
        "healthy": len(issues) == 0,
        "issues": issues,
        "can_repair": True  # venv issues can always be repaired by recreating
    }


def check_dependencies_installed(mcp_dir, server_config):
    """Check if key dependencies are importable.

    Returns:
        dict with keys:
            - healthy: bool
            - issues: list of strings
            - can_repair: bool
    """
    venv_python = mcp_dir / "venv" / "bin" / "python"
    if not venv_python.exists():
        return {"healthy": False, "issues": ["venv python missing"], "can_repair": True}

    issues = []

    # Get list of packages to check
    packages_to_check = []

    if "dependencies" in server_config:
        packages_to_check.extend(server_config["dependencies"])

    if "requirements_file" in server_config:
        req_file = mcp_dir / server_config["requirements_file"]
        if req_file.exists():
            for line in req_file.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    # Extract package name (remove version specifiers)
                    pkg = line.split(">=")[0].split("==")[0].split("<")[0].split(">")[0].strip()
                    if pkg:
                        packages_to_check.append(pkg)

    # Always check mcp is importable for MCP servers
    if "mcp" not in packages_to_check:
        packages_to_check.append("mcp")

    for pkg in packages_to_check:
        try:
            result = subprocess.run(
                [str(venv_python), "-c", f"import {pkg}"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                issues.append(f"Package '{pkg}' not importable")
        except Exception:
            issues.append(f"Error checking package '{pkg}'")

    return {
        "healthy": len(issues) == 0,
        "issues": issues,
        "can_repair": True
    }


def check_config_health(mcp_dir, server_config):
    """Check if config file exists and has valid structure.

    Returns:
        dict with keys:
            - healthy: bool
            - issues: list of strings
            - can_repair: bool
    """
    if "config_file" not in server_config:
        return {"healthy": True, "issues": [], "can_repair": True}

    config_file = mcp_dir / server_config["config_file"]
    issues = []

    if not config_file.exists():
        # Check if example exists - if so, we can repair
        config_example = mcp_dir / server_config.get("config_example", "")
        can_repair = config_example.exists() if config_example else False
        return {
            "healthy": False,
            "issues": [f"Config file missing: {server_config['config_file']}"],
            "can_repair": can_repair
        }

    # Try to parse as JSON
    try:
        with open(config_file) as f:
            config_data = json.load(f)
    except json.JSONDecodeError as e:
        return {
            "healthy": False,
            "issues": [f"Config file has invalid JSON: {e}"],
            "can_repair": False  # Can't auto-fix corrupted JSON
        }
    except Exception as e:
        return {
            "healthy": False,
            "issues": [f"Error reading config: {e}"],
            "can_repair": False
        }

    return {"healthy": True, "issues": [], "can_repair": True}


def check_server_script_exists(mcp_dir, server_config):
    """Check if the main server script exists.

    Returns:
        dict with keys:
            - healthy: bool
            - issues: list of strings
            - can_repair: bool
    """
    server_script = mcp_dir / server_config["server_script"]

    if not server_script.exists():
        return {
            "healthy": False,
            "issues": [f"Server script missing: {server_config['server_script']}"],
            "can_repair": True  # git checkout can restore it
        }

    return {"healthy": True, "issues": [], "can_repair": True}


def run_health_check(install_dir, verbose=True):
    """Run comprehensive health check on all installed servers.

    Returns:
        dict with server_id keys, each containing:
            - healthy: bool
            - issues: list of all issues
            - can_repair: bool
            - checks: dict of individual check results
    """
    results = {}

    for server_id, server_config in MCP_SERVERS.items():
        mcp_dir = install_dir / server_id

        if not mcp_dir.exists():
            results[server_id] = {
                "healthy": False,
                "issues": ["Server directory missing"],
                "can_repair": True,
                "checks": {},
                "exists": False
            }
            continue

        checks = {
            "venv": check_venv_health(mcp_dir),
            "dependencies": check_dependencies_installed(mcp_dir, server_config),
            "config": check_config_health(mcp_dir, server_config),
            "server_script": check_server_script_exists(mcp_dir, server_config),
        }

        all_issues = []
        can_repair_all = True

        for check_name, check_result in checks.items():
            all_issues.extend(check_result["issues"])
            if not check_result["can_repair"]:
                can_repair_all = False

        results[server_id] = {
            "healthy": len(all_issues) == 0,
            "issues": all_issues,
            "can_repair": can_repair_all,
            "checks": checks,
            "exists": True
        }

    return results


def print_health_report(health_results):
    """Print a formatted health report."""
    all_healthy = all(r["healthy"] for r in health_results.values())

    if all_healthy:
        print("\n✅ All servers are healthy")
        return

    print("\n" + "=" * 60)
    print("🏥 Health Check Report")
    print("=" * 60)

    for server_id, result in health_results.items():
        server_name = MCP_SERVERS[server_id]["name"]

        if result["healthy"]:
            print(f"\n  ✅ {server_name}: Healthy")
        else:
            status = "⚠️" if result["can_repair"] else "❌"
            print(f"\n  {status} {server_name}:")
            for issue in result["issues"]:
                print(f"      • {issue}")
            if result["can_repair"]:
                print("      → Can be auto-repaired")
            else:
                print("      → Manual intervention required")


def repair_server(install_dir, server_id, health_result):
    """Attempt to repair a broken server installation.

    Returns True if repair was successful.
    """
    server_config = MCP_SERVERS[server_id]
    mcp_dir = install_dir / server_id

    print(f"\n🔧 Repairing {server_config['name']}...")

    # If directory is missing, we can't repair without fresh install
    if not health_result.get("exists", True):
        print("  Server directory missing - will be restored via git")
        # Try git checkout to restore the directory
        result = run_command(f"git checkout HEAD -- {server_id}", cwd=install_dir, capture=True)
        if result is None:
            print("  ❌ Could not restore server directory")
            return False
        print("  ✅ Server directory restored")

    checks = health_result.get("checks", {})
    venv_recreated = False

    # Repair venv if needed
    venv_check = checks.get("venv", {})
    if not venv_check.get("healthy", True):
        print("  Recreating virtual environment...")
        venv_dir = mcp_dir / "venv"
        if venv_dir.exists():
            shutil.rmtree(venv_dir)
        if not setup_venv(mcp_dir):
            print("  ❌ Failed to create virtual environment")
            return False
        print("  ✅ Virtual environment recreated")
        venv_recreated = True

    # Reinstall dependencies if needed (always reinstall if venv was recreated)
    deps_check = checks.get("dependencies", {})
    if not deps_check.get("healthy", True) or venv_recreated:
        print("  Reinstalling dependencies...")
        if not install_dependencies(mcp_dir, server_config):
            print("  ❌ Failed to install dependencies")
            return False
        print("  ✅ Dependencies installed")

    # Restore config if needed
    config_check = checks.get("config", {})
    if not config_check.get("healthy", True) and config_check.get("can_repair", False):
        print("  Restoring config file...")
        setup_config(mcp_dir, server_config)
        print("  ✅ Config file restored from example")

    # Restore server script if needed
    script_check = checks.get("server_script", {})
    if not script_check.get("healthy", True):
        print("  Restoring server script...")
        result = run_command(
            f"git checkout HEAD -- {server_id}/{server_config['server_script']}",
            cwd=install_dir,
            capture=True
        )
        if result is None:
            print("  ❌ Could not restore server script")
            return False
        print("  ✅ Server script restored")

    print(f"  ✅ {server_config['name']} repaired!")
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

    # Simple question based on server type
    if server_id == "peeperfrog-create-mcp":
        question = "Do you have any image generation API keys (Gemini, OpenAI, or Together)?"
    elif server_id == "peeperfrog-linkedin-mcp":
        question = "Do you have LinkedIn Developer App credentials?"
    else:
        question = "Do you have the required API keys ready?"

    print()
    has_keys = prompt_yes_no(question, default=True)

    if not has_keys:
        print_api_key_instructions(env_vars)
        print("\n" + "-" * 60)
        print("You can still proceed. Add your keys to the config file later.")
        print("-" * 60)

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

        # Build env vars - use empty string for missing keys
        # Empty strings let the server give clear "missing key" errors
        env_dict = {}
        for var in server_config.get("env_vars", []):
            if var in collected_keys and collected_keys[var]:
                env_dict[var] = collected_keys[var]
            else:
                env_dict[var] = ""

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


def is_claude_code_installed():
    """Check if Claude Code CLI is installed."""
    result = run_command("which claude", capture=True)
    return result is not None and len(result.strip()) > 0


def get_os_type():
    """Detect the operating system."""
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    elif system == "windows":
        return "windows"
    else:
        return "linux"


def get_claude_desktop_config_path():
    """Get the Claude Desktop config file path based on OS."""
    os_type = get_os_type()
    if os_type == "macos":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    elif os_type == "windows":
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            return Path(appdata) / "Claude" / "claude_desktop_config.json"
        return None
    else:  # linux
        return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def get_claude_code_config_path():
    """Get the Claude Code settings file path."""
    return Path.home() / ".claude" / "settings.json"


def read_config_file(config_path):
    """Read and parse a JSON config file."""
    if not config_path or not config_path.exists():
        return None
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def write_config_file(config_path, config):
    """Write config to JSON file, creating parent directories if needed."""
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except IOError:
        return False


def prompt_api_key(key_name):
    """Prompt user for an API key with info about where to get it."""
    info = API_KEY_INFO.get(key_name, {})
    required = info.get("required", False)

    print(f"\n  {info.get('name', key_name)}:")
    print(f"    {info.get('description', '')}")
    print(f"    Get it here: {info.get('url', 'N/A')}")
    print(f"    {info.get('instructions', '')}")

    if required:
        prompt = f"  Enter {key_name}: "
    else:
        prompt = f"  Enter {key_name} (or press Enter to skip): "

    try:
        value = input(prompt).strip()
        return value if value else None
    except EOFError:
        return None


def collect_api_keys(server_id):
    """Collect API keys for a specific server."""
    server_config = MCP_SERVERS.get(server_id, {})
    env_vars = server_config.get("env_vars", [])
    collected = {}

    if not env_vars:
        return collected

    print(f"\n  Configure API keys for {server_config.get('name', server_id)}:")

    for var in env_vars:
        value = prompt_api_key(var)
        if value:
            collected[var] = value

    return collected


def add_servers_to_config(config_path, mcp_config, config_type="desktop"):
    """Add MCP server configs to an existing config file."""
    existing = read_config_file(config_path)

    if existing is None:
        # Create new config
        if config_type == "desktop":
            existing = {"mcpServers": {}}
        else:
            existing = {}

    # Ensure mcpServers exists
    if "mcpServers" not in existing:
        existing["mcpServers"] = {}

    # Merge in new servers, preserving existing env vars (API keys)
    for server_name, server_config in mcp_config.get("mcpServers", {}).items():
        if server_name in existing["mcpServers"]:
            # Server already exists - preserve existing env vars that have values
            existing_env = existing["mcpServers"][server_name].get("env", {})
            new_env = server_config.get("env", {})

            # Start with new env vars
            merged_env = dict(new_env)

            # Preserve existing values that are non-empty
            for key, value in existing_env.items():
                if value:
                    merged_env[key] = value

            # Update server config with merged env
            server_config = dict(server_config)
            server_config["env"] = merged_env

        existing["mcpServers"][server_name] = server_config

    return write_config_file(config_path, existing)


def offer_config_setup(install_dir, selected_servers, collected_keys=None):
    """Offer to automatically add servers to config files."""
    if collected_keys is None:
        collected_keys = {}

    print("\n" + "=" * 60)
    print("📝 Configure MCP Servers")
    print("=" * 60)

    # Check for Claude Desktop config
    desktop_path = get_claude_desktop_config_path()
    code_path = get_claude_code_config_path()

    # Ask about API keys first
    if prompt_yes_no("\nWould you like to enter your API keys now?"):
        for server_id in selected_servers:
            keys = collect_api_keys(server_id)
            collected_keys.update(keys)
    else:
        print("\n  You can add API keys later by editing the config file.")

    # Generate config with collected keys
    mcp_config = generate_mcp_config(install_dir, selected_servers, collected_keys)

    # Offer to add to Claude Desktop config
    if desktop_path:
        desktop_exists = desktop_path.exists()
        if desktop_exists:
            action = "Update"
            print(f"\n  Found Claude Desktop config: {desktop_path}")
        else:
            action = "Create"
            print(f"\n  Claude Desktop config will be created at: {desktop_path}")

        if prompt_yes_no(f"  {action} Claude Desktop config with these servers?"):
            if add_servers_to_config(desktop_path, mcp_config, "desktop"):
                print(f"  ✅ Claude Desktop config {'updated' if desktop_exists else 'created'}!")
            else:
                print(f"  ❌ Failed to write config file")
        else:
            print("\n  Manual setup required. Add this to your config file:")
            print_mcp_config(mcp_config, selected_servers)
            return

    # Show success message
    print("\n" + "-" * 60)
    print("  Servers added to config:")
    for server_id in selected_servers:
        config_name = server_id.replace("-mcp", "").replace("peeperfrog-", "peeperfrog-")
        if server_id == "peeperfrog-create-mcp":
            config_name = "peeperfrog-create"
        elif server_id == "peeperfrog-linkedin-mcp":
            config_name = "peeperfrog-linkedin"
        print(f"    • {config_name}")

    # Show any keys that still need to be added
    missing_keys = []
    for server_id in selected_servers:
        server_config = MCP_SERVERS.get(server_id, {})
        for var in server_config.get("env_vars", []):
            if var not in collected_keys or not collected_keys[var]:
                info = API_KEY_INFO.get(var, {})
                if info.get("required", False):
                    missing_keys.append((var, info))

    if missing_keys:
        print("\n  ⚠️  Required keys still need to be added:")
        for var, info in missing_keys:
            print(f"    • {var}: {info.get('url', '')}")
    print("-" * 60)


def install_skills(install_dir):
    """Copy skills to Claude Code skills directory."""
    skills_src = install_dir / "skills"
    skills_dest = Path.home() / ".claude" / "skills"

    if not skills_src.exists():
        return 0

    # Check if Claude Code CLI is installed
    if not is_claude_code_installed():
        print("\n📝 Skipping Claude Code skills (CLI not installed)")
        print("   Skills are available in: {}/skills/".format(install_dir))
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


def run_linkedin_oauth_setup(install_dir):
    """Run the LinkedIn OAuth setup script interactively."""
    linkedin_dir = install_dir / "peeperfrog-linkedin-mcp"
    oauth_script = linkedin_dir / "src" / "oauth_setup.py"
    venv_python = linkedin_dir / "venv" / "bin" / "python3"

    if not oauth_script.exists():
        print("  OAuth setup script not found")
        return False

    if not venv_python.exists():
        print("  Virtual environment not found")
        return False

    # Try to get LinkedIn credentials from Claude Desktop config
    desktop_config_path = get_claude_desktop_config_path()
    linkedin_env = {}

    if desktop_config_path:
        config = read_config_file(desktop_config_path)
        if config:
            linkedin_cfg = config.get("mcpServers", {}).get("peeperfrog-linkedin", {})
            env_vars = linkedin_cfg.get("env", {})
            if env_vars.get("LINKEDIN_CLIENT_ID"):
                linkedin_env["LINKEDIN_CLIENT_ID"] = env_vars["LINKEDIN_CLIENT_ID"]
            if env_vars.get("LINKEDIN_CLIENT_SECRET"):
                linkedin_env["LINKEDIN_CLIENT_SECRET"] = env_vars["LINKEDIN_CLIENT_SECRET"]

    # Check if we have credentials
    if not linkedin_env.get("LINKEDIN_CLIENT_ID") or not linkedin_env.get("LINKEDIN_CLIENT_SECRET"):
        print("\n⚠️  LinkedIn credentials not found in config.")
        print("   Please add LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET to your")
        print("   Claude Desktop config file first, then run OAuth setup manually:")
        print(f"\n     cd {linkedin_dir}")
        print("     source venv/bin/activate")
        print("     python src/oauth_setup.py")
        return False

    print("\n" + "=" * 60)
    print("🔗 LinkedIn OAuth Setup")
    print("=" * 60)
    print("\nThis will open a browser for LinkedIn authorization.")
    print("Make sure your LinkedIn app's redirect URI is set to:")
    print("  http://localhost:8585/callback")
    print()

    if not prompt_yes_no("Run OAuth setup now?", default=True):
        print("\n  You can run it later with:")
        print(f"    cd {linkedin_dir}")
        print("    source venv/bin/activate")
        print("    python src/oauth_setup.py")
        return False

    print("\nStarting OAuth setup...")
    try:
        # Run the OAuth setup script with credentials in environment
        env = os.environ.copy()
        env.update(linkedin_env)
        subprocess.run([str(venv_python), str(oauth_script)], cwd=str(linkedin_dir), env=env)
        return True
    except Exception as e:
        print(f"  Error running OAuth setup: {e}")
        return False


def print_claude_desktop_skills_instructions(install_dir, is_update=False):
    """Print instructions for installing/updating skills in Claude Desktop."""
    skills_src = install_dir / "skills"
    if not skills_src.exists():
        return

    skill_files = list(skills_src.glob("*.md"))
    if not skill_files:
        return

    print("\n" + "-" * 60)
    print("📱 For Claude Desktop (GUI app):")
    print("-" * 60)

    if is_update:
        print("To update skills, you must re-upload them manually:")
        print("  1. Open Claude Desktop")
        print("  2. Go to Settings > Capabilities")
        print("  3. Delete the old version of each skill you want to update")
        print("  4. Click 'Add' > 'Upload a skill'")
        print(f"  5. Upload the updated files from: {skills_src}")
    else:
        print("Skills must be uploaded manually through the app:")
        print("  1. Open Claude Desktop")
        print("  2. Go to Settings > Capabilities")
        print("  3. Toggle on 'Skills' if not already enabled")
        print("  4. Click 'Add' > 'Upload a skill'")
        print(f"  5. Upload files from: {skills_src}")

    print()
    print("Skills sync between Claude Desktop and Claude.ai (web).")
    print("-" * 60)


def print_restart_instructions(mcp_updated=False, skills_updated=False, install_dir=None):
    """Print context-aware restart instructions based on OS and what changed."""
    os_type = get_os_type()

    if not mcp_updated and not skills_updated:
        return

    print("\n" + "=" * 60)
    print("🔄 To Apply Changes")
    print("=" * 60)

    # Claude Code instructions
    print("\n📟 Claude Code (CLI):")
    if mcp_updated:
        print("  MCP servers were updated. You must restart Claude Code:")
        print("    1. Exit your current session (Ctrl+C or type /exit)")
        print("    2. Run: claude")
    if skills_updated and not mcp_updated:
        print("  Skills are loaded fresh each session - just start a new session.")

    # Claude Desktop instructions (only if MCP was updated or skills need uploading)
    if mcp_updated:
        print("\n📱 Claude Desktop (GUI app):")
        print("  MCP servers were updated. You must restart Claude Desktop:")

        if os_type == "macos":
            print("    1. Quit completely: Cmd+Q or right-click dock icon > Quit")
            print("    2. Relaunch Claude Desktop")
        elif os_type == "windows":
            print("    1. Quit completely: Right-click system tray icon > Exit")
            print("    2. Relaunch Claude Desktop")
        else:  # Linux
            print("    1. Quit completely: Right-click system tray icon > Quit")
            print("    2. Relaunch Claude Desktop")

    if skills_updated and install_dir:
        skills_src = install_dir / "skills"
        print("\n  To update skills in Claude Desktop:")
        print("    1. Open Settings > Capabilities")
        print("    2. Delete old versions of updated skills")
        print("    3. Click 'Add' > 'Upload a skill'")
        print(f"    4. Upload from: {skills_src}")

    print()
    print("=" * 60)


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
    do_repair = "--repair" in sys.argv
    health_only = "--health" in sys.argv

    # Determine install directory
    install_dir = DEFAULT_INSTALL_DIR

    # Check if running from within an existing repo installation
    script_dir = Path(__file__).resolve().parent
    if (script_dir / ".git").exists() and (script_dir / "peeperfrog-create-mcp").exists():
        install_dir = script_dir
        print(f"\n📍 Running from existing installation: {install_dir}")
    elif script_dir != DEFAULT_INSTALL_DIR and not (script_dir / ".git").exists():
        # Script was curl'd into a custom directory - use that as install location
        install_dir = script_dir
        print(f"\n📍 Installing to: {install_dir}")

    # Check installation status
    already_installed = is_installed(install_dir)

    # Track if we need to suggest restart
    needs_restart = False
    skills_installed = 0

    # Track what changed for context-aware instructions
    mcp_updated = False
    skills_updated = False

    if already_installed:
        print(f"\n✅ Existing installation detected at: {install_dir}")

        # Run comprehensive health check
        print("\n🔍 Running health check...")
        health_results = run_health_check(install_dir)

        # Check if any servers have issues
        unhealthy_servers = {sid: r for sid, r in health_results.items() if not r["healthy"]}

        if unhealthy_servers:
            print_health_report(health_results)

            # Check if all issues are repairable
            all_repairable = all(r["can_repair"] for r in unhealthy_servers.values())

            if do_repair or (not update_only and not health_only):
                if do_repair:
                    do_repairs = True
                elif all_repairable:
                    do_repairs = prompt_yes_no("\nAttempt to repair these issues?", default=True)
                else:
                    print("\n⚠️  Some issues cannot be auto-repaired.")
                    do_repairs = prompt_yes_no("Attempt to repair what we can?", default=True)

                if do_repairs:
                    for server_id, result in unhealthy_servers.items():
                        if result["can_repair"]:
                            if repair_server(install_dir, server_id, result):
                                mcp_updated = True
                        else:
                            print(f"\n⚠️  {MCP_SERVERS[server_id]['name']}: Manual repair needed")
                            for issue in result["issues"]:
                                print(f"      • {issue}")
        else:
            print("  ✅ All servers healthy")

        # If health check only, exit here
        if health_only:
            print("\n✅ Health check complete!")
            return 0

        # Store hashes of files before pull to detect changes
        req_hashes_before = {}
        for server_id, config in MCP_SERVERS.items():
            if "requirements_file" in config:
                req_file = install_dir / server_id / config["requirements_file"]
                req_hashes_before[server_id] = get_file_hash(req_file)

        # Store hashes of MCP server scripts
        server_hashes_before = {}
        for server_id, config in MCP_SERVERS.items():
            server_script = install_dir / server_id / config["server_script"]
            server_hashes_before[server_id] = get_file_hash(server_script)

        # Store hashes of skill files
        skills_src = install_dir / "skills"
        skill_hashes_before = {}
        if skills_src.exists():
            for skill_file in skills_src.glob("*.md"):
                skill_hashes_before[skill_file.name] = get_file_hash(skill_file)

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
                mcp_updated = True
                print(f"\n📦 Dependencies changed for {config['name']}")

        # Check if server scripts changed
        for server_id, hash_before in server_hashes_before.items():
            config = MCP_SERVERS[server_id]
            server_script = install_dir / server_id / config["server_script"]
            if get_file_hash(server_script) != hash_before:
                mcp_updated = True
                print(f"\n📝 Server code changed for {config['name']}")

        # Check if skills changed
        if skills_src.exists():
            for skill_file in skills_src.glob("*.md"):
                old_hash = skill_hashes_before.get(skill_file.name)
                new_hash = get_file_hash(skill_file)
                if old_hash != new_hash:
                    skills_updated = True
                    if old_hash is None:
                        print(f"\n🆕 New skill: {skill_file.name}")
                    else:
                        print(f"\n📝 Skill updated: {skill_file.name}")

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
        if skills_installed > 0:
            skills_updated = True

        print("\n✅ Update complete!")

        # Check if servers are missing from Claude Desktop config
        if not update_only:
            desktop_config_path = get_claude_desktop_config_path()
            if desktop_config_path:
                config = read_config_file(desktop_config_path)
                mcp_servers = config.get("mcpServers", {}) if config else {}

                # Check which installed servers are missing from config
                missing_servers = []
                for server_id in MCP_SERVERS:
                    mcp_dir = install_dir / server_id
                    if mcp_dir.exists():
                        # Map server_id to config name
                        if server_id == "peeperfrog-create-mcp":
                            config_name = "peeperfrog-create"
                        elif server_id == "peeperfrog-linkedin-mcp":
                            config_name = "peeperfrog-linkedin"
                        else:
                            config_name = server_id.replace("-mcp", "")

                        if config_name not in mcp_servers:
                            missing_servers.append(server_id)

                if missing_servers:
                    print(f"\n⚠️  {len(missing_servers)} server(s) not in Claude Desktop config:")
                    for sid in missing_servers:
                        print(f"    • {MCP_SERVERS[sid]['name']}")

                    if prompt_yes_no("\nAdd missing servers to config?", default=True):
                        offer_config_setup(install_dir, missing_servers)
                        mcp_updated = True

        # Show context-aware instructions based on what changed
        if mcp_updated or skills_updated:
            print_restart_instructions(
                mcp_updated=mcp_updated,
                skills_updated=skills_updated,
                install_dir=install_dir
            )

            # Handle restart for Claude Code
            if mcp_updated:
                if do_restart:
                    restart_claude_code()
                elif not update_only:
                    if prompt_yes_no("\nRestart Claude Code now?", default=False):
                        restart_claude_code()
        else:
            print("\n  No changes detected. Everything is up to date.")

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

        # Offer to configure MCP servers in config file
        if not update_only:
            offer_config_setup(install_dir, servers_to_setup)

        # Install skills
        if not update_only:
            if is_claude_code_installed():
                if prompt_yes_no("\nInstall Claude Code Skills?"):
                    skills_installed = install_skills(install_dir)
                    skills_updated = True
                    print_claude_desktop_skills_instructions(install_dir, is_update=False)
                    # Pause so user can read the info
                    input("\nPress Enter to continue...")

        print("\n✅ Installation complete!")

        # Show next steps with OS-specific instructions
        os_type = get_os_type()
        print("\n" + "=" * 60)
        print("📋 Next Steps")
        print("=" * 60)

        # LinkedIn OAuth setup
        if "peeperfrog-linkedin-mcp" in servers_to_setup:
            run_linkedin_oauth_setup(install_dir)

        print("\n1. Restart to load the new MCP servers:")
        print("\n   Claude Code (CLI):")
        print("     Just run: claude")

        print("\n   Claude Desktop (GUI app):")
        if os_type == "macos":
            print("     Quit completely (Cmd+Q), then relaunch")
        elif os_type == "windows":
            print("     Right-click system tray > Exit, then relaunch")
        else:
            print("     Quit completely from system tray, then relaunch")

        print()
        print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
