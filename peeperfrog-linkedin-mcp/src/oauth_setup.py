#!/usr/bin/env python3
"""
LinkedIn OAuth Setup Script

This script handles the 3-legged OAuth flow for LinkedIn:
1. Opens a browser for user authentication
2. Captures the authorization code from the redirect
3. Exchanges the code for access/refresh tokens
4. Saves tokens to .linkedin_tokens.json

Run this script once to set up authentication, then again whenever
tokens need to be refreshed manually.
"""

import os
import sys
import json
import time
import webbrowser
import urllib.parse
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

import httpx

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CONFIG_DIR = Path(__file__).parent.parent
CONFIG_FILE = CONFIG_DIR / "config.json"
TOKENS_FILE = CONFIG_DIR / ".linkedin_tokens.json"
ENV_FILE = CONFIG_DIR / ".env"

# LinkedIn OAuth endpoints
AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"

# Default redirect URI - must match what's configured in LinkedIn Developer Portal
DEFAULT_REDIRECT_URI = "http://localhost:8585/callback"

# Scopes for personal profile (always available with "Share on LinkedIn" product)
PERSONAL_SCOPES = [
    "openid",
    "profile",
    "email",
    "w_member_social",
]

# Additional scopes for Company Page (requires Marketing Developer Platform)
ORGANIZATION_SCOPES = [
    "w_organization_social",
    "r_organization_social",
]

# Global to capture the auth code
auth_code = None
auth_error = None

def load_env():
    """Load .env file if present."""
    if ENV_FILE.exists():
        with open(ENV_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())

def load_config():
    """Load config.json."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}

def save_tokens(tokens: dict):
    """Save tokens to file with restrictive permissions."""
    with open(TOKENS_FILE, "w") as f:
        json.dump(tokens, f, indent=2)
    os.chmod(TOKENS_FILE, 0o600)
    print(f"Tokens saved to: {TOKENS_FILE}")

# ---------------------------------------------------------------------------
# OAuth Callback Server
# ---------------------------------------------------------------------------

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Handle the OAuth callback from LinkedIn."""

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass

    def do_GET(self):
        global auth_code, auth_error

        # Parse query parameters
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "code" in params:
            auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
                <html>
                <head><title>LinkedIn OAuth Success</title></head>
                <body style="font-family: system-ui; text-align: center; padding: 50px;">
                    <h1 style="color: #0077B5;">Authorization Successful!</h1>
                    <p>You can close this window and return to the terminal.</p>
                </body>
                </html>
            """)
        elif "error" in params:
            auth_error = params.get("error_description", params["error"])[0]
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(f"""
                <html>
                <head><title>LinkedIn OAuth Error</title></head>
                <body style="font-family: system-ui; text-align: center; padding: 50px;">
                    <h1 style="color: #cc0000;">Authorization Failed</h1>
                    <p>{auth_error}</p>
                    <p>Please try again.</p>
                </body>
                </html>
            """.encode())
        else:
            self.send_response(400)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Invalid callback request")

def start_callback_server(port: int = 8585) -> HTTPServer:
    """Start a local server to receive the OAuth callback."""
    server = HTTPServer(("localhost", port), OAuthCallbackHandler)
    thread = threading.Thread(target=server.handle_request)
    thread.daemon = True
    thread.start()
    return server

# ---------------------------------------------------------------------------
# OAuth Flow
# ---------------------------------------------------------------------------

def get_authorization_url(client_id: str, redirect_uri: str, scopes: list, state: str = "linkedin_oauth") -> str:
    """Build the LinkedIn authorization URL."""
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "scope": " ".join(scopes),
    }
    return f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

def exchange_code_for_tokens(code: str, client_id: str, client_secret: str, redirect_uri: str) -> dict:
    """Exchange authorization code for access tokens."""
    response = httpx.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    if response.status_code != 200:
        raise Exception(f"Token exchange failed: {response.status_code} - {response.text}")

    data = response.json()
    return {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token"),
        "expires_in": data.get("expires_in", 5184000),
        "expires_at": time.time() + data.get("expires_in", 5184000),
        "scope": data.get("scope"),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

def verify_token(access_token: str) -> dict:
    """Verify the token by fetching user info."""
    response = httpx.get(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if response.status_code == 200:
        return response.json()
    return None

# ---------------------------------------------------------------------------
# Main Flow
# ---------------------------------------------------------------------------

def main():
    global auth_code, auth_error

    print("=" * 60)
    print("LinkedIn OAuth Setup")
    print("=" * 60)
    print()

    # Load configuration
    load_env()
    config = load_config()
    linkedin_cfg = config.get("linkedin", {})

    # Get credentials
    client_id = os.environ.get("LINKEDIN_CLIENT_ID") or linkedin_cfg.get("client_id")
    client_secret = os.environ.get("LINKEDIN_CLIENT_SECRET") or linkedin_cfg.get("client_secret")
    redirect_uri = os.environ.get("LINKEDIN_REDIRECT_URI") or linkedin_cfg.get("redirect_uri") or DEFAULT_REDIRECT_URI

    if not client_id:
        print("ERROR: LINKEDIN_CLIENT_ID not found in environment or config.json")
        print()
        print("Please set up your LinkedIn Developer App first:")
        print("  1. Go to https://www.linkedin.com/developers/apps/new")
        print("  2. Create an app and get your Client ID and Client Secret")
        print("  3. Add them to .env or config.json")
        sys.exit(1)

    if not client_secret:
        print("ERROR: LINKEDIN_CLIENT_SECRET not found")
        sys.exit(1)

    # Parse port from redirect URI
    parsed_uri = urllib.parse.urlparse(redirect_uri)
    port = parsed_uri.port or 8585

    print(f"Client ID: {client_id[:8]}...{client_id[-4:]}")
    print(f"Redirect URI: {redirect_uri}")
    print()

    # Ask whether to include organization scopes
    print("Do you have Marketing Developer Platform access for Company Pages?")
    print("  [y] Yes - include organization scopes (for Company Page posting)")
    print("  [n] No  - personal profile only (default)")
    print()
    include_org = input("Include organization scopes? [y/N]: ").strip().lower()

    if include_org == 'y':
        scopes = PERSONAL_SCOPES + ORGANIZATION_SCOPES
        print()
        print("Including organization scopes for Company Page access.")
    else:
        scopes = PERSONAL_SCOPES
        print()
        print("Using personal profile scopes only.")

    print(f"Scopes: {', '.join(scopes)}")
    print()

    # Check if redirect URI matches expected format
    if "localhost" not in redirect_uri:
        print("WARNING: Redirect URI should use localhost for this script.")
        print("Make sure this exact URI is configured in your LinkedIn app.")
        print()

    # Start callback server
    print(f"Starting local callback server on port {port}...")
    try:
        server = start_callback_server(port)
    except OSError as e:
        print(f"ERROR: Could not start server on port {port}: {e}")
        print("Make sure the port is not in use by another application.")
        sys.exit(1)

    # Build and open authorization URL
    auth_url = get_authorization_url(client_id, redirect_uri, scopes)
    print()
    print("Opening browser for LinkedIn authorization...")
    print()
    print("If the browser doesn't open, visit this URL manually:")
    print(auth_url)
    print()

    webbrowser.open(auth_url)

    # Wait for callback
    print("Waiting for authorization callback...")
    timeout = 300  # 5 minutes
    start = time.time()

    while auth_code is None and auth_error is None:
        if time.time() - start > timeout:
            print("ERROR: Authorization timed out after 5 minutes.")
            sys.exit(1)
        time.sleep(0.5)

    server.server_close()

    if auth_error:
        print(f"ERROR: Authorization failed: {auth_error}")
        sys.exit(1)

    print("Authorization code received!")
    print()

    # Exchange code for tokens
    print("Exchanging code for access token...")
    try:
        tokens = exchange_code_for_tokens(code=auth_code, client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    # Verify token
    print("Verifying token...")
    user_info = verify_token(tokens["access_token"])
    if user_info:
        print(f"Authenticated as: {user_info.get('name', 'Unknown')} ({user_info.get('email', 'no email')})")
        tokens["user_info"] = {
            "name": user_info.get("name"),
            "email": user_info.get("email"),
            "sub": user_info.get("sub"),  # This is the person URN ID
        }
    else:
        print("WARNING: Could not verify token, but it may still work.")

    # Save tokens
    save_tokens(tokens)

    # Calculate expiration
    expires_in_days = tokens["expires_in"] / 86400

    print()
    print("=" * 60)
    print("SUCCESS! LinkedIn OAuth setup complete.")
    print("=" * 60)
    print()
    print(f"Access token expires in: {expires_in_days:.1f} days")
    print(f"Tokens saved to: {TOKENS_FILE}")
    print()
    print("You can now use the LinkedIn MCP server.")
    print()

    if not tokens.get("refresh_token"):
        print("NOTE: No refresh token was returned. You may need to re-authenticate")
        print("when the access token expires. To get refresh tokens, ensure your")
        print("LinkedIn app has the 'refresh_token' product enabled.")

if __name__ == "__main__":
    main()
