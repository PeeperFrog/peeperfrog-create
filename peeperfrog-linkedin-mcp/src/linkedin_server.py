#!/usr/bin/env python3
# Copyright (c) 2025 PeeperFrog Press
# Licensed under the Apache License, Version 2.0. See LICENSE file for details.
#
# Not affiliated with LinkedIn, Microsoft, or any other third-party service.
# All trademarks are property of their respective owners.
# THIS SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.
"""
PeeperFrog LinkedIn MCP Server - Version 1.0 Beta

Provides tools for posting to LinkedIn personal profiles and Company Pages
via the LinkedIn Marketing API. Uses 3-legged OAuth with automatic token refresh.

Part of PeeperFrog Create: https://github.com/PeeperFrog/peeperfrog-create
"""

import os
import sys
import json
import time
import httpx
from pathlib import Path
from datetime import datetime, timedelta

# MCP SDK imports
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CONFIG_DIR = Path(__file__).parent.parent
CONFIG_FILE = CONFIG_DIR / "config.json"
TOKENS_FILE = CONFIG_DIR / ".linkedin_tokens.json"
ENV_FILE = CONFIG_DIR / ".env"

LINKEDIN_API_VERSION = "202601"
LINKEDIN_API_BASE = "https://api.linkedin.com"

def debug_log(msg: str, level: str = "INFO"):
    """Log to stderr (stdout breaks MCP protocol)."""
    print(f"[{level}] {msg}", file=sys.stderr)

def load_config():
    """Load config.json with LinkedIn settings."""
    if not CONFIG_FILE.exists():
        debug_log(f"Config file not found: {CONFIG_FILE}", "ERROR")
        return {}
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def load_env():
    """Load .env file if present."""
    if ENV_FILE.exists():
        with open(ENV_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())

# Load environment on import
load_env()
CFG = load_config()

# ---------------------------------------------------------------------------
# Token Management
# ---------------------------------------------------------------------------

def load_tokens() -> dict:
    """Load stored OAuth tokens from file."""
    if not TOKENS_FILE.exists():
        return {}
    try:
        with open(TOKENS_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        debug_log(f"Failed to load tokens: {e}", "ERROR")
        return {}

def save_tokens(tokens: dict):
    """Save OAuth tokens to file."""
    # Ensure we don't accidentally expose tokens
    TOKENS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TOKENS_FILE, "w") as f:
        json.dump(tokens, f, indent=2)
    # Set restrictive permissions
    os.chmod(TOKENS_FILE, 0o600)
    debug_log("Tokens saved successfully")

def is_token_expired(tokens: dict) -> bool:
    """Check if access token is expired or about to expire (within 7 days)."""
    expires_at = tokens.get("expires_at", 0)
    # Refresh 7 days early to avoid last-minute failures
    seven_days = 7 * 24 * 60 * 60  # 604800 seconds
    return time.time() >= (expires_at - seven_days)

def refresh_access_token(tokens: dict) -> dict:
    """Refresh the access token using the refresh token."""
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        raise Exception("No refresh token available. Please re-authenticate.")

    client_id = os.environ.get("LINKEDIN_CLIENT_ID") or CFG.get("linkedin", {}).get("client_id")
    client_secret = os.environ.get("LINKEDIN_CLIENT_SECRET") or CFG.get("linkedin", {}).get("client_secret")

    if not client_id or not client_secret:
        raise Exception("Missing LINKEDIN_CLIENT_ID or LINKEDIN_CLIENT_SECRET")

    debug_log("Refreshing access token...")

    response = httpx.post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    if response.status_code != 200:
        raise Exception(f"Token refresh failed: {response.status_code} - {response.text}")

    data = response.json()
    new_tokens = {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token", refresh_token),  # May or may not be returned
        "expires_at": time.time() + data.get("expires_in", 5184000),  # Default 60 days
        "refreshed_at": datetime.now().isoformat(),
    }
    save_tokens(new_tokens)
    debug_log("Access token refreshed successfully")
    return new_tokens

def get_valid_token() -> str:
    """Get a valid access token, refreshing if necessary."""
    tokens = load_tokens()

    if not tokens.get("access_token"):
        raise Exception("No access token found. Run the OAuth setup script first.")

    if is_token_expired(tokens):
        tokens = refresh_access_token(tokens)

    return tokens["access_token"]

# ---------------------------------------------------------------------------
# LinkedIn API Functions
# ---------------------------------------------------------------------------

def get_linkedin_headers(access_token: str) -> dict:
    """Build standard LinkedIn API headers."""
    return {
        "Authorization": f"Bearer {access_token}",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": LINKEDIN_API_VERSION,
        "Content-Type": "application/json",
    }

def get_organization_id() -> str | None:
    """Get the default configured organization ID, or None if not configured."""
    org_id = os.environ.get("LINKEDIN_ORG_ID") or CFG.get("linkedin", {}).get("organization_id")
    return str(org_id) if org_id else None

def get_person_urn() -> str:
    """Get the authenticated user's person URN from stored tokens."""
    tokens = load_tokens()
    user_info = tokens.get("user_info", {})
    sub = user_info.get("sub")
    if not sub:
        raise Exception("No user info found in tokens. Re-run oauth_setup.py to capture user identity.")
    return f"urn:li:person:{sub}"

def get_author_urn(target: str = "organization") -> str:
    """
    Resolve the target to a LinkedIn author URN.

    Args:
        target: One of:
            - "personal" or "me": Post to authenticated user's personal profile
            - "organization" or "org": Post to default configured organization
            - A numeric org ID (e.g., "12345678"): Post to that specific organization

    Returns:
        LinkedIn author URN (e.g., "urn:li:organization:12345" or "urn:li:person:abc123")
    """
    target = target.lower().strip() if target else "organization"

    if target in ("personal", "me"):
        return get_person_urn()
    elif target in ("organization", "org"):
        org_id = get_organization_id()
        if not org_id:
            # Fall back to personal if no org ID configured
            debug_log("No LINKEDIN_ORG_ID configured, using personal profile")
            return get_person_urn()
        return f"urn:li:organization:{org_id}"
    elif target.isdigit():
        # Specific organization ID provided
        return f"urn:li:organization:{target}"
    else:
        # Assume it's an org ID even if not purely numeric (some may have letters)
        return f"urn:li:organization:{target}"

async def create_text_post(content: str, visibility: str = "PUBLIC", as_draft: bool = False, target: str = "organization") -> dict:
    """Create a text-only post on the specified target (personal profile or company page)."""
    access_token = get_valid_token()
    author_urn = get_author_urn(target)

    url = f"{LINKEDIN_API_BASE}/rest/posts"
    headers = get_linkedin_headers(access_token)

    lifecycle_state = "DRAFT" if as_draft else "PUBLISHED"

    payload = {
        "author": author_urn,
        "commentary": content,
        "visibility": visibility,
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": []
        },
        "lifecycleState": lifecycle_state,
        "isReshareDisabledByAuthor": False
    }

    action = "draft" if as_draft else "post"
    debug_log(f"Creating {action} as {author_urn}")

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)

        if response.status_code == 201:
            post_id = response.headers.get("x-restli-id", "unknown")
            if as_draft:
                return {
                    "success": True,
                    "draft_id": post_id,
                    "message": f"Draft saved successfully. Draft ID: {post_id}"
                }
            else:
                return {
                    "success": True,
                    "post_id": post_id,
                    "message": f"Successfully posted to LinkedIn. Post ID: {post_id}"
                }
        else:
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text,
                "message": f"Failed to create {action}: {response.status_code}"
            }

async def create_link_post(content: str, link_url: str, visibility: str = "PUBLIC", as_draft: bool = False, target: str = "organization") -> dict:
    """Create a post with a link/article attachment."""
    access_token = get_valid_token()
    author_urn = get_author_urn(target)

    url = f"{LINKEDIN_API_BASE}/rest/posts"
    headers = get_linkedin_headers(access_token)

    lifecycle_state = "DRAFT" if as_draft else "PUBLISHED"

    payload = {
        "author": author_urn,
        "commentary": content,
        "visibility": visibility,
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": []
        },
        "content": {
            "article": {
                "source": link_url,
                "title": "",  # LinkedIn will auto-fetch from Open Graph
                "description": ""
            }
        },
        "lifecycleState": lifecycle_state,
        "isReshareDisabledByAuthor": False
    }

    action = "draft" if as_draft else "post"
    debug_log(f"Creating link {action} as {author_urn} with URL: {link_url}")

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)

        if response.status_code == 201:
            post_id = response.headers.get("x-restli-id", "unknown")
            if as_draft:
                return {
                    "success": True,
                    "draft_id": post_id,
                    "message": f"Draft with link saved successfully. Draft ID: {post_id}"
                }
            else:
                return {
                    "success": True,
                    "post_id": post_id,
                    "message": f"Successfully posted to LinkedIn with link. Post ID: {post_id}"
                }
        else:
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text,
                "message": f"Failed to create {action}: {response.status_code}"
            }

async def get_posts(count: int = 10, include_drafts: bool = False, target: str = "organization") -> dict:
    """Retrieve recent posts from the specified target (personal profile or company page)."""
    access_token = get_valid_token()
    author_urn = get_author_urn(target)

    # URL-encode the URN
    encoded_urn = author_urn.replace(":", "%3A")

    url = f"{LINKEDIN_API_BASE}/rest/posts?author={encoded_urn}&q=author&count={count}&sortBy=LAST_MODIFIED"
    headers = get_linkedin_headers(access_token)

    debug_log(f"Fetching posts for {author_urn}")

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            posts = []
            for element in data.get("elements", []):
                lifecycle = element.get("lifecycleState")
                # Filter out drafts unless requested
                if not include_drafts and lifecycle == "DRAFT":
                    continue
                posts.append({
                    "id": element.get("id"),
                    "commentary": element.get("commentary", ""),
                    "visibility": element.get("visibility"),
                    "created_at": element.get("createdAt"),
                    "lifecycle_state": lifecycle,
                    "content": element.get("content"),
                })
            return {
                "success": True,
                "count": len(posts),
                "posts": posts
            }
        else:
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text
            }

async def get_drafts(count: int = 10, target: str = "organization") -> dict:
    """Retrieve draft posts from the specified target (personal profile or company page)."""
    access_token = get_valid_token()
    author_urn = get_author_urn(target)

    # URL-encode the URN
    encoded_urn = author_urn.replace(":", "%3A")

    # Fetch posts and filter for drafts
    url = f"{LINKEDIN_API_BASE}/rest/posts?author={encoded_urn}&q=author&count=100&sortBy=LAST_MODIFIED"
    headers = get_linkedin_headers(access_token)

    debug_log(f"Fetching drafts for {author_urn}")

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            drafts = []
            for element in data.get("elements", []):
                if element.get("lifecycleState") == "DRAFT":
                    draft_info = {
                        "id": element.get("id"),
                        "commentary": element.get("commentary", ""),
                        "visibility": element.get("visibility"),
                        "created_at": element.get("createdAt"),
                    }
                    # Include link URL if present
                    content = element.get("content", {})
                    if content and "article" in content:
                        draft_info["link_url"] = content["article"].get("source")
                    drafts.append(draft_info)
                    if len(drafts) >= count:
                        break
            return {
                "success": True,
                "count": len(drafts),
                "drafts": drafts
            }
        else:
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text
            }

async def publish_draft(draft_id: str) -> dict:
    """Publish a draft post by changing its lifecycle state to PUBLISHED."""
    access_token = get_valid_token()

    # Handle both full URN and just the ID
    if not draft_id.startswith("urn:"):
        # Try share first, then ugcPost
        draft_id = f"urn:li:share:{draft_id}"

    encoded_id = draft_id.replace(":", "%3A")
    url = f"{LINKEDIN_API_BASE}/rest/posts/{encoded_id}"
    headers = get_linkedin_headers(access_token)
    headers["X-RestLi-Method"] = "PARTIAL_UPDATE"

    payload = {
        "patch": {
            "$set": {
                "lifecycleState": "PUBLISHED"
            }
        }
    }

    debug_log(f"Publishing draft: {draft_id}")

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)

        if response.status_code == 204:
            return {
                "success": True,
                "post_id": draft_id,
                "message": f"Draft published successfully. Post ID: {draft_id}"
            }
        else:
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text,
                "message": f"Failed to publish draft: {response.status_code}"
            }

async def update_draft(draft_id: str, content: str = None, link_url: str = None) -> dict:
    """Update a draft post's content or link."""
    access_token = get_valid_token()

    # Handle both full URN and just the ID
    if not draft_id.startswith("urn:"):
        draft_id = f"urn:li:share:{draft_id}"

    encoded_id = draft_id.replace(":", "%3A")
    url = f"{LINKEDIN_API_BASE}/rest/posts/{encoded_id}"
    headers = get_linkedin_headers(access_token)
    headers["X-RestLi-Method"] = "PARTIAL_UPDATE"

    # Build the patch payload
    set_fields = {}
    if content is not None:
        set_fields["commentary"] = content

    if not set_fields:
        return {
            "success": False,
            "message": "No fields to update. Provide content to update."
        }

    payload = {
        "patch": {
            "$set": set_fields
        }
    }

    debug_log(f"Updating draft: {draft_id}")

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)

        if response.status_code == 204:
            return {
                "success": True,
                "draft_id": draft_id,
                "message": f"Draft updated successfully."
            }
        else:
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text,
                "message": f"Failed to update draft: {response.status_code}"
            }

async def delete_post(post_id: str) -> dict:
    """Delete a post by its ID/URN."""
    access_token = get_valid_token()

    # Handle both full URN and just the ID
    if not post_id.startswith("urn:"):
        post_id = f"urn:li:share:{post_id}"

    encoded_id = post_id.replace(":", "%3A")
    url = f"{LINKEDIN_API_BASE}/rest/posts/{encoded_id}"
    headers = get_linkedin_headers(access_token)

    debug_log(f"Deleting post: {post_id}")

    async with httpx.AsyncClient() as client:
        response = await client.delete(url, headers=headers)

        if response.status_code == 204:
            return {
                "success": True,
                "message": f"Successfully deleted post: {post_id}"
            }
        else:
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text
            }

# ---------------------------------------------------------------------------
# Comment Functions
# ---------------------------------------------------------------------------

def normalize_post_urn(post_id: str) -> str:
    """Normalize a post ID to a full URN format."""
    if post_id.startswith("urn:"):
        return post_id
    # Default to share URN format
    return f"urn:li:share:{post_id}"

async def get_comments(post_id: str, count: int = 20) -> dict:
    """Retrieve comments on a post."""
    access_token = get_valid_token()
    post_urn = normalize_post_urn(post_id)
    encoded_urn = post_urn.replace(":", "%3A")

    url = f"{LINKEDIN_API_BASE}/rest/socialActions/{encoded_urn}/comments?count={count}"
    headers = get_linkedin_headers(access_token)

    debug_log(f"Fetching comments for {post_urn}")

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            comments = []
            for element in data.get("elements", []):
                comment_info = {
                    "id": element.get("id"),
                    "actor": element.get("actor"),
                    "message": element.get("message", {}).get("text", ""),
                    "created_at": element.get("created", {}).get("time"),
                    "last_modified_at": element.get("lastModified", {}).get("time"),
                }
                # Include nested comment count if available
                if "commentsSummary" in element:
                    comment_info["reply_count"] = element["commentsSummary"].get("totalFirstLevelComments", 0)
                comments.append(comment_info)
            return {
                "success": True,
                "post_id": post_urn,
                "count": len(comments),
                "comments": comments
            }
        else:
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text
            }

async def create_comment(post_id: str, message: str, actor: str = "organization") -> dict:
    """Create a comment on a post."""
    access_token = get_valid_token()
    post_urn = normalize_post_urn(post_id)
    encoded_urn = post_urn.replace(":", "%3A")
    actor_urn = get_author_urn(actor)

    url = f"{LINKEDIN_API_BASE}/rest/socialActions/{encoded_urn}/comments"
    headers = get_linkedin_headers(access_token)

    payload = {
        "actor": actor_urn,
        "message": {
            "text": message
        }
    }

    debug_log(f"Creating comment on {post_urn} as {actor_urn}")

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)

        if response.status_code == 201:
            comment_id = response.headers.get("x-restli-id", "unknown")
            return {
                "success": True,
                "comment_id": comment_id,
                "post_id": post_urn,
                "actor": actor_urn,
                "message": f"Comment created successfully"
            }
        else:
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text,
                "message": f"Failed to create comment: {response.status_code}"
            }

async def delete_comment(post_id: str, comment_id: str, actor: str = "organization") -> dict:
    """Delete a comment from a post."""
    access_token = get_valid_token()
    post_urn = normalize_post_urn(post_id)
    encoded_post_urn = post_urn.replace(":", "%3A")
    actor_urn = get_author_urn(actor)
    encoded_actor = actor_urn.replace(":", "%3A")

    # Extract just the comment ID if a full URN was provided
    if comment_id.startswith("urn:"):
        # Extract the ID portion from the URN
        comment_id = comment_id.split(":")[-1]

    url = f"{LINKEDIN_API_BASE}/rest/socialActions/{encoded_post_urn}/comments/{comment_id}?actor={encoded_actor}"
    headers = get_linkedin_headers(access_token)

    debug_log(f"Deleting comment {comment_id} from {post_urn} as {actor_urn}")

    async with httpx.AsyncClient() as client:
        response = await client.delete(url, headers=headers)

        if response.status_code == 204:
            return {
                "success": True,
                "message": f"Comment deleted successfully"
            }
        else:
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text,
                "message": f"Failed to delete comment: {response.status_code}"
            }

async def reply_to_comment(post_id: str, parent_comment_id: str, message: str, actor: str = "organization") -> dict:
    """Reply to an existing comment on a post (nested comment)."""
    access_token = get_valid_token()
    post_urn = normalize_post_urn(post_id)
    encoded_urn = post_urn.replace(":", "%3A")
    actor_urn = get_author_urn(actor)

    # Format parent comment URN if needed
    if not parent_comment_id.startswith("urn:"):
        parent_comment_urn = f"urn:li:comment:(urn:li:activity:{post_id},{parent_comment_id})"
    else:
        parent_comment_urn = parent_comment_id

    url = f"{LINKEDIN_API_BASE}/rest/socialActions/{encoded_urn}/comments"
    headers = get_linkedin_headers(access_token)

    payload = {
        "actor": actor_urn,
        "message": {
            "text": message
        },
        "parentComment": parent_comment_urn
    }

    debug_log(f"Replying to comment {parent_comment_id} on {post_urn} as {actor_urn}")

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)

        if response.status_code == 201:
            comment_id = response.headers.get("x-restli-id", "unknown")
            return {
                "success": True,
                "comment_id": comment_id,
                "parent_comment_id": parent_comment_id,
                "post_id": post_urn,
                "actor": actor_urn,
                "message": "Reply created successfully"
            }
        else:
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text,
                "message": f"Failed to create reply: {response.status_code}"
            }

# ---------------------------------------------------------------------------
# Reactions/Likes Functions
# ---------------------------------------------------------------------------

async def like_post(post_id: str, actor: str = "organization") -> dict:
    """Like a post as yourself or an organization."""
    access_token = get_valid_token()
    post_urn = normalize_post_urn(post_id)
    encoded_urn = post_urn.replace(":", "%3A")
    actor_urn = get_author_urn(actor)

    url = f"{LINKEDIN_API_BASE}/rest/socialActions/{encoded_urn}/likes"
    headers = get_linkedin_headers(access_token)

    payload = {
        "actor": actor_urn
    }

    debug_log(f"Liking post {post_urn} as {actor_urn}")

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)

        if response.status_code == 201:
            return {
                "success": True,
                "post_id": post_urn,
                "actor": actor_urn,
                "message": "Post liked successfully"
            }
        elif response.status_code == 409:
            return {
                "success": True,
                "post_id": post_urn,
                "actor": actor_urn,
                "message": "Post was already liked"
            }
        else:
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text,
                "message": f"Failed to like post: {response.status_code}"
            }

async def unlike_post(post_id: str, actor: str = "organization") -> dict:
    """Remove a like from a post."""
    access_token = get_valid_token()
    post_urn = normalize_post_urn(post_id)
    encoded_urn = post_urn.replace(":", "%3A")
    actor_urn = get_author_urn(actor)
    encoded_actor = actor_urn.replace(":", "%3A")

    url = f"{LINKEDIN_API_BASE}/rest/socialActions/{encoded_urn}/likes/{encoded_actor}"
    headers = get_linkedin_headers(access_token)

    debug_log(f"Unliking post {post_urn} as {actor_urn}")

    async with httpx.AsyncClient() as client:
        response = await client.delete(url, headers=headers)

        if response.status_code == 204:
            return {
                "success": True,
                "post_id": post_urn,
                "actor": actor_urn,
                "message": "Like removed successfully"
            }
        elif response.status_code == 404:
            return {
                "success": True,
                "post_id": post_urn,
                "actor": actor_urn,
                "message": "Post was not liked"
            }
        else:
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text,
                "message": f"Failed to unlike post: {response.status_code}"
            }

async def get_reactions(post_id: str, count: int = 20) -> dict:
    """Get reactions (likes) on a post."""
    access_token = get_valid_token()
    post_urn = normalize_post_urn(post_id)
    encoded_urn = post_urn.replace(":", "%3A")

    url = f"{LINKEDIN_API_BASE}/rest/socialActions/{encoded_urn}/likes?count={count}"
    headers = get_linkedin_headers(access_token)

    debug_log(f"Fetching reactions for {post_urn}")

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            reactions = []
            for element in data.get("elements", []):
                reactions.append({
                    "actor": element.get("actor"),
                    "created_at": element.get("created", {}).get("time"),
                })
            return {
                "success": True,
                "post_id": post_urn,
                "count": len(reactions),
                "reactions": reactions,
                "paging": data.get("paging", {})
            }
        else:
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text
            }

# ---------------------------------------------------------------------------
# Image Upload Functions
# ---------------------------------------------------------------------------

async def initialize_image_upload(actor: str = "organization") -> dict:
    """Initialize an image upload and get the upload URL."""
    access_token = get_valid_token()
    actor_urn = get_author_urn(actor)

    url = f"{LINKEDIN_API_BASE}/rest/images?action=initializeUpload"
    headers = get_linkedin_headers(access_token)

    payload = {
        "initializeUploadRequest": {
            "owner": actor_urn
        }
    }

    debug_log(f"Initializing image upload for {actor_urn}")

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)

        if response.status_code == 200:
            data = response.json()
            value = data.get("value", {})
            return {
                "success": True,
                "upload_url": value.get("uploadUrl"),
                "image_urn": value.get("image"),
                "expires_at": value.get("uploadUrlExpiresAt")
            }
        else:
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text,
                "message": f"Failed to initialize upload: {response.status_code}"
            }

async def upload_image_binary(upload_url: str, image_data: bytes, content_type: str = "image/png") -> dict:
    """Upload image binary data to the provided upload URL."""
    headers = {
        "Content-Type": content_type,
    }

    debug_log(f"Uploading image ({len(image_data)} bytes) to LinkedIn")

    async with httpx.AsyncClient() as client:
        response = await client.put(upload_url, content=image_data, headers=headers)

        if response.status_code in (200, 201):
            return {
                "success": True,
                "message": "Image uploaded successfully"
            }
        else:
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text,
                "message": f"Failed to upload image: {response.status_code}"
            }

async def upload_image_from_path(image_path: str, actor: str = "organization") -> dict:
    """Upload an image from a file path to LinkedIn."""
    from pathlib import Path
    import mimetypes

    path = Path(image_path).expanduser()
    if not path.exists():
        return {
            "success": False,
            "error": f"File not found: {image_path}"
        }

    # Determine content type
    content_type, _ = mimetypes.guess_type(str(path))
    if not content_type:
        content_type = "image/png"

    # Initialize upload
    init_result = await initialize_image_upload(actor)
    if not init_result.get("success"):
        return init_result

    # Read and upload image
    image_data = path.read_bytes()
    upload_result = await upload_image_binary(
        upload_url=init_result["upload_url"],
        image_data=image_data,
        content_type=content_type
    )

    if not upload_result.get("success"):
        return upload_result

    return {
        "success": True,
        "image_urn": init_result["image_urn"],
        "file_path": str(path),
        "file_size": len(image_data),
        "content_type": content_type,
        "message": "Image uploaded successfully"
    }

async def create_image_post(content: str, image_urn: str, visibility: str = "PUBLIC",
                            alt_text: str = "", title: str = "", as_draft: bool = False,
                            target: str = "organization") -> dict:
    """Create a post with an uploaded image."""
    access_token = get_valid_token()
    author_urn = get_author_urn(target)

    url = f"{LINKEDIN_API_BASE}/rest/posts"
    headers = get_linkedin_headers(access_token)

    lifecycle_state = "DRAFT" if as_draft else "PUBLISHED"

    payload = {
        "author": author_urn,
        "commentary": content,
        "visibility": visibility,
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": []
        },
        "content": {
            "media": {
                "id": image_urn,
                "title": title,
                "altText": alt_text
            }
        },
        "lifecycleState": lifecycle_state,
        "isReshareDisabledByAuthor": False
    }

    action = "draft" if as_draft else "post"
    debug_log(f"Creating image {action} as {author_urn}")

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)

        if response.status_code == 201:
            post_id = response.headers.get("x-restli-id", "unknown")
            if as_draft:
                return {
                    "success": True,
                    "draft_id": post_id,
                    "image_urn": image_urn,
                    "message": f"Image draft saved successfully. Draft ID: {post_id}"
                }
            else:
                return {
                    "success": True,
                    "post_id": post_id,
                    "image_urn": image_urn,
                    "message": f"Successfully posted image to LinkedIn. Post ID: {post_id}"
                }
        else:
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text,
                "message": f"Failed to create image {action}: {response.status_code}"
            }

async def post_image(content: str, image_path: str, visibility: str = "PUBLIC",
                     alt_text: str = "", title: str = "", as_draft: bool = False,
                     target: str = "organization") -> dict:
    """Upload an image and create a post with it in one operation."""
    # Step 1: Upload the image
    upload_result = await upload_image_from_path(image_path, target)
    if not upload_result.get("success"):
        return upload_result

    # Step 2: Create the post with the image
    post_result = await create_image_post(
        content=content,
        image_urn=upload_result["image_urn"],
        visibility=visibility,
        alt_text=alt_text,
        title=title,
        as_draft=as_draft,
        target=target
    )

    # Include upload info in result
    if post_result.get("success"):
        post_result["file_path"] = upload_result.get("file_path")
        post_result["file_size"] = upload_result.get("file_size")

    return post_result

def get_token_status() -> dict:
    """
    Get current token status and refresh the token.

    This function will:
    - Report if no token exists
    - Automatically refresh the token to extend validity
    - Report if token is fully expired and needs re-authentication
    """
    tokens = load_tokens()

    if not tokens.get("access_token"):
        return {
            "authenticated": False,
            "message": "No access token found. Run `python src/oauth_setup.py` to authenticate."
        }

    expires_at = tokens.get("expires_at", 0)
    expires_in_seconds = expires_at - time.time()

    # Check if token is fully expired (past expiration date)
    if expires_in_seconds <= 0:
        return {
            "authenticated": False,
            "expired": True,
            "expires_at": datetime.fromtimestamp(expires_at).isoformat() if expires_at else None,
            "message": "Token has expired. Run `python src/oauth_setup.py` to re-authenticate."
        }

    # Always refresh to keep token fresh
    try:
        tokens = refresh_access_token(tokens)
        expires_at = tokens.get("expires_at", 0)
        expires_in_days = (expires_at - time.time()) / 86400
        return {
            "authenticated": True,
            "expires_in_days": round(expires_in_days, 1),
            "expires_at": datetime.fromtimestamp(expires_at).isoformat(),
            "refreshed_at": tokens.get("refreshed_at"),
            "message": f"Token refreshed. Valid for {round(expires_in_days, 1)} days"
        }
    except Exception as e:
        expires_in_days = expires_in_seconds / 86400
        return {
            "authenticated": True,
            "expires_in_days": round(expires_in_days, 1),
            "expires_at": datetime.fromtimestamp(expires_at).isoformat() if expires_at else None,
            "refresh_failed": True,
            "refresh_error": str(e),
            "message": f"Token valid for {round(expires_in_days, 1)} days. Refresh failed: {e}"
        }

# ---------------------------------------------------------------------------
# Analytics Functions
# ---------------------------------------------------------------------------

async def get_organization_post_statistics(post_ids: list = None, target: str = "organization") -> dict:
    """
    Get statistics (impressions, clicks, engagement) for organization posts.

    Args:
        post_ids: List of post IDs/URNs to get stats for. If None, returns aggregate stats.
        target: Organization to query ("organization" for default, or specific org ID)

    Returns:
        Post statistics including impressionCount, clickCount, engagement, etc.
    """
    access_token = get_valid_token()

    # Get the organization URN
    if target in ("organization", "org"):
        org_id = get_organization_id()
        if not org_id:
            return {
                "success": False,
                "error": "No organization ID configured. Set LINKEDIN_ORG_ID or use linkedin_get_member_post_analytics for personal posts.",
                "message": "Organization statistics require Marketing Developer Platform and a configured org ID."
            }
    else:
        org_id = target

    org_urn = f"urn:li:organization:{org_id}"
    encoded_org = org_urn.replace(":", "%3A")

    # Build the URL
    url = f"{LINKEDIN_API_BASE}/rest/organizationalEntityShareStatistics?q=organizationalEntity&organizationalEntity={encoded_org}"

    # Add specific post IDs if provided
    if post_ids:
        share_urns = []
        for pid in post_ids:
            if pid.startswith("urn:"):
                share_urns.append(pid.replace(":", "%3A"))
            else:
                share_urns.append(f"urn%3Ali%3Ashare%3A{pid}")
        url += f"&shares=List({','.join(share_urns)})"

    headers = get_linkedin_headers(access_token)

    debug_log(f"Fetching organization post statistics for {org_urn}")

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            elements = data.get("elements", [])

            result = {
                "success": True,
                "organization": org_urn,
            }

            if elements:
                element = elements[0]
                # Aggregate stats for the org
                if "totalShareStatistics" in element:
                    result["total_statistics"] = element["totalShareStatistics"]

                # Per-share stats if queried
                if "shareStatistics" in element:
                    result["post_statistics"] = []
                    for share_stat in element.get("shareStatistics", []):
                        result["post_statistics"].append({
                            "post_id": share_stat.get("share"),
                            "impressions": share_stat.get("totalShareStatistics", {}).get("impressionCount", 0),
                            "unique_impressions": share_stat.get("totalShareStatistics", {}).get("uniqueImpressionsCount", 0),
                            "clicks": share_stat.get("totalShareStatistics", {}).get("clickCount", 0),
                            "likes": share_stat.get("totalShareStatistics", {}).get("likeCount", 0),
                            "comments": share_stat.get("totalShareStatistics", {}).get("commentCount", 0),
                            "shares": share_stat.get("totalShareStatistics", {}).get("shareCount", 0),
                            "engagement": share_stat.get("totalShareStatistics", {}).get("engagement", 0),
                        })

            return result
        else:
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text,
                "message": f"Failed to get statistics: {response.status_code}"
            }

async def get_member_post_analytics(post_id: str, metric_type: str = "IMPRESSION") -> dict:
    """
    Get analytics for a personal profile post.

    Args:
        post_id: The post ID/URN to get analytics for
        metric_type: Type of metric - IMPRESSION, MEMBERS_REACHED, RESHARE, REACTION, COMMENT

    Returns:
        Post analytics for the specified metric
    """
    access_token = get_valid_token()

    # Normalize post URN
    post_urn = normalize_post_urn(post_id)
    encoded_post = post_urn.replace(":", "%3A")

    # Determine entity format based on URN type
    if "ugcPost" in post_urn:
        entity_param = f"(ugcPost:{encoded_post})"
    else:
        entity_param = f"(share:{encoded_post})"

    url = f"{LINKEDIN_API_BASE}/rest/memberCreatorPostAnalytics?q=entity&entity={entity_param}&queryType={metric_type}&aggregation=TOTAL"
    headers = get_linkedin_headers(access_token)

    debug_log(f"Fetching member post analytics for {post_urn}, metric: {metric_type}")

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            elements = data.get("elements", [])

            result = {
                "success": True,
                "post_id": post_urn,
                "metric_type": metric_type,
            }

            if elements:
                element = elements[0]
                result["count"] = element.get("count", 0)
                result["date_range"] = element.get("dateRange", {})
            else:
                result["count"] = 0
                result["message"] = "No analytics data available for this post"

            return result
        elif response.status_code == 403:
            return {
                "success": False,
                "status_code": 403,
                "error": "Permission denied. Member post analytics requires the r_member_postAnalytics scope.",
                "message": "You may need to re-authenticate with the r_member_postAnalytics permission."
            }
        else:
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text,
                "message": f"Failed to get analytics: {response.status_code}"
            }

async def get_post_impressions(post_id: str, target: str = "organization") -> dict:
    """
    Convenience function to get impressions for a post.
    Automatically uses the right API based on target (organization vs personal).

    Args:
        post_id: The post ID/URN
        target: "personal" for member posts, "organization" or org ID for company page posts

    Returns:
        Impressions count and related statistics
    """
    target_lower = target.lower().strip() if target else "organization"

    if target_lower in ("personal", "me"):
        # Use member analytics API
        result = await get_member_post_analytics(post_id, "IMPRESSION")
        if result.get("success"):
            # Also get unique reach
            reach_result = await get_member_post_analytics(post_id, "MEMBERS_REACHED")
            if reach_result.get("success"):
                result["unique_impressions"] = reach_result.get("count", 0)
            result["impressions"] = result.pop("count", 0)
        return result
    else:
        # Use organization statistics API
        result = await get_organization_post_statistics([post_id], target)
        if result.get("success") and result.get("post_statistics"):
            stats = result["post_statistics"][0]
            return {
                "success": True,
                "post_id": stats.get("post_id"),
                "impressions": stats.get("impressions", 0),
                "unique_impressions": stats.get("unique_impressions", 0),
                "clicks": stats.get("clicks", 0),
                "engagement": stats.get("engagement", 0),
                "likes": stats.get("likes", 0),
                "comments": stats.get("comments", 0),
                "shares": stats.get("shares", 0),
            }
        return result

async def get_posts_with_stats(count: int = 20, sort_by: str = "impressions", target: str = "organization") -> dict:
    """
    Get recent posts with their statistics, sorted by a metric.

    Args:
        count: Number of posts to retrieve (max 50)
        sort_by: Metric to sort by - impressions, engagement, clicks, likes, comments, shares
        target: "organization" for company page posts, "personal" for member posts

    Returns:
        Posts with statistics, sorted by the specified metric
    """
    target_lower = target.lower().strip() if target else "organization"

    # First get the posts
    posts_result = await get_posts(count=min(count, 50), target=target)

    if not posts_result.get("success"):
        return posts_result

    posts = posts_result.get("posts", [])
    if not posts:
        return {
            "success": True,
            "posts": [],
            "message": "No posts found"
        }

    # Extract post IDs
    post_ids = [p.get("id") for p in posts if p.get("id")]

    if not post_ids:
        return {
            "success": True,
            "posts": posts,
            "message": "Posts found but no IDs available for statistics"
        }

    # Get statistics for the posts
    if target_lower in ("personal", "me"):
        # For personal posts, we need to fetch stats one by one
        posts_with_stats = []
        for post in posts:
            post_id = post.get("id")
            if post_id:
                stats = await get_post_impressions(post_id, "personal")
                post_with_stats = {**post}
                if stats.get("success"):
                    post_with_stats["stats"] = {
                        "impressions": stats.get("impressions", 0),
                        "unique_impressions": stats.get("unique_impressions", 0),
                    }
                else:
                    post_with_stats["stats"] = {"impressions": 0, "unique_impressions": 0}
                posts_with_stats.append(post_with_stats)
    else:
        # For organization posts, we can batch the request
        stats_result = await get_organization_post_statistics(post_ids, target)

        # Create a lookup map for stats
        stats_map = {}
        if stats_result.get("success") and stats_result.get("post_statistics"):
            for stat in stats_result["post_statistics"]:
                stats_map[stat.get("post_id")] = stat

        # Merge posts with their stats
        posts_with_stats = []
        for post in posts:
            post_id = post.get("id")
            post_with_stats = {**post}

            if post_id in stats_map:
                post_with_stats["stats"] = stats_map[post_id]
            else:
                # No stats available (maybe no impressions yet)
                post_with_stats["stats"] = {
                    "impressions": 0,
                    "unique_impressions": 0,
                    "clicks": 0,
                    "engagement": 0,
                    "likes": 0,
                    "comments": 0,
                    "shares": 0,
                }
            posts_with_stats.append(post_with_stats)

    # Sort by the specified metric
    sort_key = sort_by.lower()
    valid_sort_keys = ["impressions", "engagement", "clicks", "likes", "comments", "shares", "unique_impressions"]
    if sort_key not in valid_sort_keys:
        sort_key = "impressions"

    posts_with_stats.sort(key=lambda p: p.get("stats", {}).get(sort_key, 0), reverse=True)

    return {
        "success": True,
        "posts": posts_with_stats,
        "count": len(posts_with_stats),
        "sorted_by": sort_key,
        "target": target
    }

# ---------------------------------------------------------------------------
# MCP Server Setup
# ---------------------------------------------------------------------------

server = Server("peeperfrog-linkedin-mcp")

@server.list_tools()
async def handle_list_tools():
    """List available LinkedIn tools."""
    return [
        Tool(
            name="linkedin_post_text",
            description="Create a text post on LinkedIn. Posts to the default Company Page unless target is specified. Maximum 3000 characters.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The text content of the post (max 3000 characters)",
                        "maxLength": 3000
                    },
                    "visibility": {
                        "type": "string",
                        "description": "Post visibility: PUBLIC, CONNECTIONS, or LOGGED_IN",
                        "enum": ["PUBLIC", "CONNECTIONS", "LOGGED_IN"],
                        "default": "PUBLIC"
                    },
                    "target": {
                        "type": "string",
                        "description": "Where to post: 'personal' for your profile, 'organization' for default company page, or a specific org ID",
                        "default": "organization"
                    }
                },
                "required": ["content"]
            }
        ),
        Tool(
            name="linkedin_post_link",
            description="Create a post with a link/article attachment on LinkedIn. LinkedIn will auto-fetch the link preview from Open Graph tags.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The text content of the post",
                        "maxLength": 3000
                    },
                    "link_url": {
                        "type": "string",
                        "description": "URL of the article/link to attach",
                        "format": "uri"
                    },
                    "visibility": {
                        "type": "string",
                        "description": "Post visibility",
                        "enum": ["PUBLIC", "CONNECTIONS", "LOGGED_IN"],
                        "default": "PUBLIC"
                    },
                    "target": {
                        "type": "string",
                        "description": "Where to post: 'personal' for your profile, 'organization' for default company page, or a specific org ID",
                        "default": "organization"
                    }
                },
                "required": ["content", "link_url"]
            }
        ),
        Tool(
            name="linkedin_get_posts",
            description="Retrieve recent posts from LinkedIn (personal profile or Company Page).",
            inputSchema={
                "type": "object",
                "properties": {
                    "count": {
                        "type": "integer",
                        "description": "Number of posts to retrieve (max 100)",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 100
                    },
                    "target": {
                        "type": "string",
                        "description": "Where to fetch posts from: 'personal', 'organization', or a specific org ID",
                        "default": "organization"
                    }
                }
            }
        ),
        Tool(
            name="linkedin_delete_post",
            description="Delete a post from the LinkedIn Company Page by its ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "post_id": {
                        "type": "string",
                        "description": "The post ID or URN (e.g., 'urn:li:share:123456' or just '123456')"
                    }
                },
                "required": ["post_id"]
            }
        ),
        Tool(
            name="linkedin_token_status",
            description="Check and refresh the LinkedIn OAuth token. Always refreshes to extend validity. Reports if the token has expired and needs re-authentication.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        # Draft tools
        Tool(
            name="linkedin_create_draft",
            description="Save a text post as a draft on LinkedIn. Drafts can be edited and published later.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The text content of the draft (max 3000 characters)",
                        "maxLength": 3000
                    },
                    "visibility": {
                        "type": "string",
                        "description": "Post visibility when published",
                        "enum": ["PUBLIC", "CONNECTIONS", "LOGGED_IN"],
                        "default": "PUBLIC"
                    },
                    "target": {
                        "type": "string",
                        "description": "Where to save draft: 'personal', 'organization', or a specific org ID",
                        "default": "organization"
                    }
                },
                "required": ["content"]
            }
        ),
        Tool(
            name="linkedin_create_draft_link",
            description="Save a post with a link attachment as a draft on LinkedIn. Drafts can be edited and published later.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The text content of the draft",
                        "maxLength": 3000
                    },
                    "link_url": {
                        "type": "string",
                        "description": "URL of the article/link to attach",
                        "format": "uri"
                    },
                    "visibility": {
                        "type": "string",
                        "description": "Post visibility when published",
                        "enum": ["PUBLIC", "CONNECTIONS", "LOGGED_IN"],
                        "default": "PUBLIC"
                    },
                    "target": {
                        "type": "string",
                        "description": "Where to save draft: 'personal', 'organization', or a specific org ID",
                        "default": "organization"
                    }
                },
                "required": ["content", "link_url"]
            }
        ),
        Tool(
            name="linkedin_get_drafts",
            description="List all draft posts on LinkedIn (personal profile or Company Page).",
            inputSchema={
                "type": "object",
                "properties": {
                    "count": {
                        "type": "integer",
                        "description": "Maximum number of drafts to retrieve",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50
                    },
                    "target": {
                        "type": "string",
                        "description": "Where to fetch drafts from: 'personal', 'organization', or a specific org ID",
                        "default": "organization"
                    }
                }
            }
        ),
        Tool(
            name="linkedin_publish_draft",
            description="Publish a draft post immediately. The draft becomes a live post visible to the selected audience.",
            inputSchema={
                "type": "object",
                "properties": {
                    "draft_id": {
                        "type": "string",
                        "description": "The draft ID or URN to publish"
                    }
                },
                "required": ["draft_id"]
            }
        ),
        Tool(
            name="linkedin_update_draft",
            description="Update the content of an existing draft post.",
            inputSchema={
                "type": "object",
                "properties": {
                    "draft_id": {
                        "type": "string",
                        "description": "The draft ID or URN to update"
                    },
                    "content": {
                        "type": "string",
                        "description": "New text content for the draft",
                        "maxLength": 3000
                    }
                },
                "required": ["draft_id", "content"]
            }
        ),
        Tool(
            name="linkedin_delete_draft",
            description="Delete a draft post permanently.",
            inputSchema={
                "type": "object",
                "properties": {
                    "draft_id": {
                        "type": "string",
                        "description": "The draft ID or URN to delete"
                    }
                },
                "required": ["draft_id"]
            }
        ),
        # Comment tools
        Tool(
            name="linkedin_get_comments",
            description="Retrieve comments on a LinkedIn post. Works with your own posts or organization posts you have access to.",
            inputSchema={
                "type": "object",
                "properties": {
                    "post_id": {
                        "type": "string",
                        "description": "The post ID or URN to get comments from (e.g., 'urn:li:share:123456' or just '123456')"
                    },
                    "count": {
                        "type": "integer",
                        "description": "Maximum number of comments to retrieve",
                        "default": 20,
                        "minimum": 1,
                        "maximum": 100
                    }
                },
                "required": ["post_id"]
            }
        ),
        Tool(
            name="linkedin_create_comment",
            description="Create a comment on a LinkedIn post. Can comment as yourself or as an organization you manage.",
            inputSchema={
                "type": "object",
                "properties": {
                    "post_id": {
                        "type": "string",
                        "description": "The post ID or URN to comment on"
                    },
                    "message": {
                        "type": "string",
                        "description": "The comment text"
                    },
                    "actor": {
                        "type": "string",
                        "description": "Who to comment as: 'personal' for your profile, 'organization' for default company page, or a specific org ID",
                        "default": "organization"
                    }
                },
                "required": ["post_id", "message"]
            }
        ),
        Tool(
            name="linkedin_delete_comment",
            description="Delete a comment from a LinkedIn post. You can only delete comments you created.",
            inputSchema={
                "type": "object",
                "properties": {
                    "post_id": {
                        "type": "string",
                        "description": "The post ID or URN the comment is on"
                    },
                    "comment_id": {
                        "type": "string",
                        "description": "The comment ID to delete"
                    },
                    "actor": {
                        "type": "string",
                        "description": "Who created the comment: 'personal', 'organization', or a specific org ID",
                        "default": "organization"
                    }
                },
                "required": ["post_id", "comment_id"]
            }
        ),
        Tool(
            name="linkedin_reply_to_comment",
            description="Reply to an existing comment on a LinkedIn post. Creates a nested comment under the parent comment.",
            inputSchema={
                "type": "object",
                "properties": {
                    "post_id": {
                        "type": "string",
                        "description": "The post ID or URN the comment is on"
                    },
                    "parent_comment_id": {
                        "type": "string",
                        "description": "The comment ID to reply to"
                    },
                    "message": {
                        "type": "string",
                        "description": "The reply text"
                    },
                    "actor": {
                        "type": "string",
                        "description": "Who to reply as: 'personal', 'organization', or a specific org ID",
                        "default": "organization"
                    }
                },
                "required": ["post_id", "parent_comment_id", "message"]
            }
        ),
        # Reactions/Likes tools
        Tool(
            name="linkedin_like_post",
            description="Like a LinkedIn post as yourself or an organization.",
            inputSchema={
                "type": "object",
                "properties": {
                    "post_id": {
                        "type": "string",
                        "description": "The post ID or URN to like"
                    },
                    "actor": {
                        "type": "string",
                        "description": "Who to like as: 'personal', 'organization', or a specific org ID",
                        "default": "organization"
                    }
                },
                "required": ["post_id"]
            }
        ),
        Tool(
            name="linkedin_unlike_post",
            description="Remove a like from a LinkedIn post.",
            inputSchema={
                "type": "object",
                "properties": {
                    "post_id": {
                        "type": "string",
                        "description": "The post ID or URN to unlike"
                    },
                    "actor": {
                        "type": "string",
                        "description": "Who liked the post: 'personal', 'organization', or a specific org ID",
                        "default": "organization"
                    }
                },
                "required": ["post_id"]
            }
        ),
        Tool(
            name="linkedin_get_reactions",
            description="Get reactions (likes) on a LinkedIn post.",
            inputSchema={
                "type": "object",
                "properties": {
                    "post_id": {
                        "type": "string",
                        "description": "The post ID or URN to get reactions from"
                    },
                    "count": {
                        "type": "integer",
                        "description": "Maximum number of reactions to retrieve",
                        "default": 20,
                        "minimum": 1,
                        "maximum": 100
                    }
                },
                "required": ["post_id"]
            }
        ),
        # Image tools
        Tool(
            name="linkedin_upload_image",
            description="Upload an image to LinkedIn for use in posts. Returns an image URN that can be used with linkedin_post_with_image.",
            inputSchema={
                "type": "object",
                "properties": {
                    "image_path": {
                        "type": "string",
                        "description": "Path to the image file to upload"
                    },
                    "target": {
                        "type": "string",
                        "description": "Owner of the image: 'personal', 'organization', or a specific org ID",
                        "default": "organization"
                    }
                },
                "required": ["image_path"]
            }
        ),
        Tool(
            name="linkedin_post_image",
            description="Upload an image and create a post with it in one operation. Combines upload and posting for convenience.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The text content of the post",
                        "maxLength": 3000
                    },
                    "image_path": {
                        "type": "string",
                        "description": "Path to the image file to upload"
                    },
                    "visibility": {
                        "type": "string",
                        "description": "Post visibility",
                        "enum": ["PUBLIC", "CONNECTIONS", "LOGGED_IN"],
                        "default": "PUBLIC"
                    },
                    "alt_text": {
                        "type": "string",
                        "description": "Alt text for the image (accessibility)",
                        "default": ""
                    },
                    "title": {
                        "type": "string",
                        "description": "Title for the image",
                        "default": ""
                    },
                    "target": {
                        "type": "string",
                        "description": "Where to post: 'personal', 'organization', or a specific org ID",
                        "default": "organization"
                    }
                },
                "required": ["content", "image_path"]
            }
        ),
        Tool(
            name="linkedin_post_with_image",
            description="Create a post with a previously uploaded image. Use this if you already have an image URN from linkedin_upload_image.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The text content of the post",
                        "maxLength": 3000
                    },
                    "image_urn": {
                        "type": "string",
                        "description": "The image URN from linkedin_upload_image (e.g., 'urn:li:image:123456')"
                    },
                    "visibility": {
                        "type": "string",
                        "description": "Post visibility",
                        "enum": ["PUBLIC", "CONNECTIONS", "LOGGED_IN"],
                        "default": "PUBLIC"
                    },
                    "alt_text": {
                        "type": "string",
                        "description": "Alt text for the image (accessibility)",
                        "default": ""
                    },
                    "title": {
                        "type": "string",
                        "description": "Title for the image",
                        "default": ""
                    },
                    "target": {
                        "type": "string",
                        "description": "Where to post: 'personal', 'organization', or a specific org ID",
                        "default": "organization"
                    }
                },
                "required": ["content", "image_urn"]
            }
        ),
        # Analytics tools
        Tool(
            name="linkedin_get_post_impressions",
            description="Get impressions and engagement statistics for a LinkedIn post. Works with both personal and organization posts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "post_id": {
                        "type": "string",
                        "description": "The post ID or URN to get impressions for"
                    },
                    "target": {
                        "type": "string",
                        "description": "Who owns the post: 'personal' for your profile, 'organization' for default company page, or a specific org ID",
                        "default": "organization"
                    }
                },
                "required": ["post_id"]
            }
        ),
        Tool(
            name="linkedin_get_organization_statistics",
            description="Get aggregate statistics for all posts from an organization, or statistics for specific posts. Returns impressions, clicks, engagement, likes, comments, and shares.",
            inputSchema={
                "type": "object",
                "properties": {
                    "post_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of post IDs/URNs to get stats for. If omitted, returns aggregate stats for all organization posts."
                    },
                    "target": {
                        "type": "string",
                        "description": "Organization to query: 'organization' for default, or a specific org ID",
                        "default": "organization"
                    }
                }
            }
        ),
        Tool(
            name="linkedin_get_member_post_analytics",
            description="Get analytics for a personal profile post. Returns counts for a specific metric type.",
            inputSchema={
                "type": "object",
                "properties": {
                    "post_id": {
                        "type": "string",
                        "description": "The post ID or URN to get analytics for"
                    },
                    "metric_type": {
                        "type": "string",
                        "description": "Type of metric to retrieve",
                        "enum": ["IMPRESSION", "MEMBERS_REACHED", "RESHARE", "REACTION", "COMMENT"],
                        "default": "IMPRESSION"
                    }
                },
                "required": ["post_id"]
            }
        ),
        Tool(
            name="linkedin_get_posts_with_stats",
            description="Get recent posts with their statistics (impressions, clicks, engagement, etc.), sorted by a metric. Use this to find your best or worst performing posts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "count": {
                        "type": "integer",
                        "description": "Number of posts to retrieve (max 50)",
                        "default": 20,
                        "minimum": 1,
                        "maximum": 50
                    },
                    "sort_by": {
                        "type": "string",
                        "description": "Metric to sort by (descending)",
                        "enum": ["impressions", "engagement", "clicks", "likes", "comments", "shares"],
                        "default": "impressions"
                    },
                    "target": {
                        "type": "string",
                        "description": "Where to get posts from: 'organization' for company page, 'personal' for your profile",
                        "default": "organization"
                    }
                }
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict):
    """Handle tool calls."""
    try:
        if name == "linkedin_post_text":
            result = await create_text_post(
                content=arguments["content"],
                visibility=arguments.get("visibility", "PUBLIC"),
                target=arguments.get("target", "organization")
            )
        elif name == "linkedin_post_link":
            result = await create_link_post(
                content=arguments["content"],
                link_url=arguments["link_url"],
                visibility=arguments.get("visibility", "PUBLIC"),
                target=arguments.get("target", "organization")
            )
        elif name == "linkedin_get_posts":
            result = await get_posts(
                count=arguments.get("count", 10),
                target=arguments.get("target", "organization")
            )
        elif name == "linkedin_delete_post":
            result = await delete_post(arguments["post_id"])
        elif name == "linkedin_token_status":
            result = get_token_status()
        # Draft tools
        elif name == "linkedin_create_draft":
            result = await create_text_post(
                content=arguments["content"],
                visibility=arguments.get("visibility", "PUBLIC"),
                as_draft=True,
                target=arguments.get("target", "organization")
            )
        elif name == "linkedin_create_draft_link":
            result = await create_link_post(
                content=arguments["content"],
                link_url=arguments["link_url"],
                visibility=arguments.get("visibility", "PUBLIC"),
                as_draft=True,
                target=arguments.get("target", "organization")
            )
        elif name == "linkedin_get_drafts":
            result = await get_drafts(
                count=arguments.get("count", 10),
                target=arguments.get("target", "organization")
            )
        elif name == "linkedin_publish_draft":
            result = await publish_draft(arguments["draft_id"])
        elif name == "linkedin_update_draft":
            result = await update_draft(
                draft_id=arguments["draft_id"],
                content=arguments.get("content")
            )
        elif name == "linkedin_delete_draft":
            result = await delete_post(arguments["draft_id"])  # Same as delete_post
        # Comment tools
        elif name == "linkedin_get_comments":
            result = await get_comments(
                post_id=arguments["post_id"],
                count=arguments.get("count", 20)
            )
        elif name == "linkedin_create_comment":
            result = await create_comment(
                post_id=arguments["post_id"],
                message=arguments["message"],
                actor=arguments.get("actor", "organization")
            )
        elif name == "linkedin_delete_comment":
            result = await delete_comment(
                post_id=arguments["post_id"],
                comment_id=arguments["comment_id"],
                actor=arguments.get("actor", "organization")
            )
        elif name == "linkedin_reply_to_comment":
            result = await reply_to_comment(
                post_id=arguments["post_id"],
                parent_comment_id=arguments["parent_comment_id"],
                message=arguments["message"],
                actor=arguments.get("actor", "organization")
            )
        # Reactions/Likes tools
        elif name == "linkedin_like_post":
            result = await like_post(
                post_id=arguments["post_id"],
                actor=arguments.get("actor", "organization")
            )
        elif name == "linkedin_unlike_post":
            result = await unlike_post(
                post_id=arguments["post_id"],
                actor=arguments.get("actor", "organization")
            )
        elif name == "linkedin_get_reactions":
            result = await get_reactions(
                post_id=arguments["post_id"],
                count=arguments.get("count", 20)
            )
        # Image tools
        elif name == "linkedin_upload_image":
            result = await upload_image_from_path(
                image_path=arguments["image_path"],
                actor=arguments.get("target", "organization")
            )
        elif name == "linkedin_post_image":
            result = await post_image(
                content=arguments["content"],
                image_path=arguments["image_path"],
                visibility=arguments.get("visibility", "PUBLIC"),
                alt_text=arguments.get("alt_text", ""),
                title=arguments.get("title", ""),
                target=arguments.get("target", "organization")
            )
        elif name == "linkedin_post_with_image":
            result = await create_image_post(
                content=arguments["content"],
                image_urn=arguments["image_urn"],
                visibility=arguments.get("visibility", "PUBLIC"),
                alt_text=arguments.get("alt_text", ""),
                title=arguments.get("title", ""),
                target=arguments.get("target", "organization")
            )
        # Analytics tools
        elif name == "linkedin_get_post_impressions":
            result = await get_post_impressions(
                post_id=arguments["post_id"],
                target=arguments.get("target", "organization")
            )
        elif name == "linkedin_get_organization_statistics":
            result = await get_organization_post_statistics(
                post_ids=arguments.get("post_ids"),
                target=arguments.get("target", "organization")
            )
        elif name == "linkedin_get_member_post_analytics":
            result = await get_member_post_analytics(
                post_id=arguments["post_id"],
                metric_type=arguments.get("metric_type", "IMPRESSION")
            )
        elif name == "linkedin_get_posts_with_stats":
            result = await get_posts_with_stats(
                count=arguments.get("count", 20),
                sort_by=arguments.get("sort_by", "impressions"),
                target=arguments.get("target", "organization")
            )
        else:
            result = {"error": f"Unknown tool: {name}"}

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        debug_log(f"Tool error: {e}", "ERROR")
        return [TextContent(type="text", text=json.dumps({
            "success": False,
            "error": str(e)
        }, indent=2))]

# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

async def main():
    """Run the MCP server."""
    debug_log("Starting PeeperFrog LinkedIn MCP Server...")
    debug_log(f"Config file: {CONFIG_FILE}")
    debug_log(f"Tokens file: {TOKENS_FILE}")

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
