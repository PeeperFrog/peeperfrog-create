<p align="center">
  <img src="docs/logo for LinkedIn.webp" alt="PeeperFrog" width="200">
</p>

<h1 align="center">PeeperFrog LinkedIn MCP</h1>

<p align="center">
An MCP server for connecting to LinkedIn personal profiles and Company Pages.
</p>

<p align="center">
<strong>Part of <a href="../README.md">PeeperFrog Create</a></strong> | Version 1.0 Beta
</p>

---

> **Owned and maintained by [PeeperFrog Press](https://peeperfrog.com)** | Open source under [Apache 2.0](../LICENSE)
>
> **Not affiliated with LinkedIn, Microsoft, or any other third-party service.** All trademarks are property of their respective owners.

---

> **Installation:** See the [main README](../README.md#quick-start) for automated setup or manual installation instructions.

## Features

- **Post to personal profile or Company Pages** - choose where to publish
- **Multiple organization support** - manage posts across different Company Pages
- **Post text updates** with up to 3000 characters
- **Post links with previews** (auto-fetches Open Graph metadata)
- **Post images** - upload and share images with your posts
- **Draft support** - save posts as drafts, edit, and publish later
- **Comments** - read, create, delete, and reply to comments
- **Reactions** - like/unlike posts and view reaction counts
- **Analytics** - get impressions, clicks, engagement for your posts
- **Read recent posts** from any target (personal or organization)
- **Delete posts** by ID
- **Automatic token refresh** when tokens are about to expire
- **Token status check** to monitor authentication validity

## Prerequisites

1. **LinkedIn Developer App** - Create one at [LinkedIn Developer Portal](https://www.linkedin.com/developers/apps/new)
2. **Python 3.10+** with pip

## Quick Start

### 1. Create LinkedIn Developer App

1. Go to [LinkedIn Developer Portal](https://www.linkedin.com/developers/apps/new)
2. Create a new app (you'll need a Company Page to associate it with)
3. Once created, go to the **Products** tab and request access to:
   - **Share on LinkedIn** (required)
   - **Sign In with LinkedIn using OpenID Connect** (required)
   - **Marketing Developer Platform** (optional - for Company Page features)
4. Go to the **Auth** tab to find your **Client ID** and **Client Secret**
5. Add `http://localhost:8585/callback` to **Authorized redirect URLs**
6. Under **OAuth 2.0 scopes**, ensure you have:
   - `openid` (required)
   - `profile` (required)
   - `email` (required)
   - `w_member_social` (required - for personal posts)
   - `w_organization_social` (optional - for Company Page posts)
   - `r_organization_social` (optional - for reading Company Page posts)

> **Note:** Marketing Developer Platform requires LinkedIn approval and is only needed for Company Page features. All personal profile features work without it.

### 2. Clone and Setup

```bash
cd peeperfrog-linkedin-mcp
cp .env.example .env
# Edit .env with your LinkedIn Client ID and Secret
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure credentials

Edit `.env` with your LinkedIn app credentials:

```
LINKEDIN_CLIENT_ID=your-client-id
LINKEDIN_CLIENT_SECRET=your-client-secret
LINKEDIN_ORG_ID=your-organization-id-optional
```

**Security:** Keys are stored in `.env` (not in Claude's config), keeping them out of Claude's view.

> **Note:** `LINKEDIN_ORG_ID` is optional - only needed for Company Page features. To find your Organization ID, go to your Company Page admin URL: `https://www.linkedin.com/company/12345678/admin/` → the ID is `12345678`

### 4. Add to your MCP client

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
    "peeperfrog-linkedin": {
      "command": "/path/to/peeperfrog-linkedin-mcp/venv/bin/python3",
      "args": ["/path/to/peeperfrog-linkedin-mcp/src/linkedin_server.py"]
    }
  }
}
```

**Note:** No `env` block needed -- credentials are loaded from `.env` in the server directory.

### 5. Run OAuth Setup

```bash
cd peeperfrog-linkedin-mcp
source venv/bin/activate
python src/oauth_setup.py
```

This will:
1. Open your browser to LinkedIn's authorization page
2. After you approve, capture the authorization code
3. Exchange it for access/refresh tokens
4. Save tokens to `.linkedin_tokens.json`

## Available Tools

### Publishing

| Tool | Description |
|------|-------------|
| `linkedin_post_text` | Create a text post (personal or Company Page) |
| `linkedin_post_link` | Create a post with a link/article attachment |
| `linkedin_post_image` | Upload an image and create a post with it |
| `linkedin_get_posts` | Retrieve recent posts from personal or Company Page |
| `linkedin_delete_post` | Delete a post by its ID |

### Images

| Tool | Description |
|------|-------------|
| `linkedin_upload_image` | Upload an image to LinkedIn (returns image URN) |
| `linkedin_post_image` | Upload and post an image in one step |
| `linkedin_post_with_image` | Create a post with a previously uploaded image |

### Drafts

| Tool | Description |
|------|-------------|
| `linkedin_create_draft` | Save a text post as a draft |
| `linkedin_create_draft_link` | Save a post with link as a draft |
| `linkedin_get_drafts` | List all draft posts |
| `linkedin_publish_draft` | Publish a draft immediately |
| `linkedin_update_draft` | Edit a draft's content |
| `linkedin_delete_draft` | Delete a draft permanently |

### Comments

| Tool | Description |
|------|-------------|
| `linkedin_get_comments` | Retrieve comments on a post |
| `linkedin_create_comment` | Comment on a post (as personal or organization) |
| `linkedin_reply_to_comment` | Reply to an existing comment (nested comments) |
| `linkedin_delete_comment` | Delete a comment you created |

### Reactions

| Tool | Description |
|------|-------------|
| `linkedin_like_post` | Like a post as yourself or organization |
| `linkedin_unlike_post` | Remove a like from a post |
| `linkedin_get_reactions` | Get reactions (likes) on a post |

### Analytics

| Tool | Description |
|------|-------------|
| `linkedin_get_posts_with_stats` | Get posts with stats, sorted by metric (best/worst) |
| `linkedin_get_post_impressions` | Get impressions and engagement stats for a post |
| `linkedin_get_organization_statistics` | Get aggregate or per-post stats for an organization |
| `linkedin_get_member_post_analytics` | Get analytics for personal profile posts |

### Utility

| Tool | Description |
|------|-------------|
| `linkedin_token_status` | Check and refresh OAuth token (always refreshes to extend validity) |

## Target Parameter

Most tools accept a `target` parameter to specify where to post:

| Value | Description | Requires |
|-------|-------------|----------|
| `"personal"` or `"me"` | Post to your personal LinkedIn profile | Basic scopes only |
| `"organization"` or `"org"` | Post to default Company Page (from config) | Marketing Developer Platform |
| `"12345678"` | Post to a specific organization by ID | Marketing Developer Platform |

**Default behavior:** If `target` is omitted, it defaults to `"organization"`. However, if `LINKEDIN_ORG_ID` is not configured, the server automatically falls back to your personal profile.

## Usage Examples

### Post to personal profile

```
Post to my personal LinkedIn: "Excited to share my thoughts on AI! #AI"
```

### Post to LinkedIn (uses Company Page if configured, otherwise personal)

```
Post to LinkedIn: "Excited to announce our new product launch! #innovation"
```

### Post to specific organization

```
Post to LinkedIn org 12345678: "Company update for our other page"
```

### Post with a link

```
Share this blog post on LinkedIn with a brief intro: https://example.com/blog/new-feature
```

### Check token status

```
What's the status of my LinkedIn authentication?
```

### Working with drafts

```
Create a draft LinkedIn post about our upcoming webinar on AI trends
```

```
Show me my LinkedIn drafts
```

```
Publish the draft about the webinar
```

Since LinkedIn doesn't support scheduled posts via API, drafts provide a workaround:
1. Create drafts ahead of time
2. Review and edit as needed
3. Publish when ready (manually or ask Claude)

### Post an image

```
Post this image to LinkedIn with caption "Check out our new office!": /path/to/office.jpg
```

### Like a post

```
Like the latest post on our Company Page
```

### Reply to a comment

```
Reply to that comment thanking them for their feedback
```

### Get post impressions

```
How many impressions did our latest LinkedIn post get?
```

### Get best performing posts

```
Show me our top 10 LinkedIn posts by impressions
```

### Get posts sorted by engagement

```
Which of our posts got the most engagement?
```

## Token Management

LinkedIn access tokens expire every **60 days**. The server automatically:

1. Checks token expiration before each API call
2. Refreshes tokens automatically if they're within **7 days** of expiring
3. Saves refreshed tokens to `.linkedin_tokens.json`

> **Important:** Auto-refresh only happens when you use the tool. If you don't use the LinkedIn MCP for more than 60 days, the token will expire and you'll need to re-run `oauth_setup.py` to re-authenticate.

If automatic refresh fails, re-run `python src/oauth_setup.py` to re-authenticate.

### Check Token Status

Use the `linkedin_token_status` tool to:
- Refresh the token (extends validity to 60 days)
- See days until expiration
- Confirm the token is valid

The tool always attempts a refresh to keep your token at maximum validity.

## API Limitations

- **Post length**: Maximum 3000 characters
- **Rate limits**: LinkedIn doesn't publish exact limits, but typical usage is fine
- **Company Page access**: Requires Marketing Developer Platform product (optional)
- **Personal post analytics**: May require `r_member_postAnalytics` scope
- **Scheduled posts**: Not supported by LinkedIn API (use drafts as a workaround)
- **Newsletters**: Not supported via API (manual creation only)
- **Videos**: Requires separate upload flow (not yet implemented)
- **Documents/PDFs**: Not yet implemented

## Personal Profile vs Company Page

| Feature | Personal Profile | Company Page |
|---------|------------------|--------------|
| Post text/links/images | Yes | Yes (requires Marketing Developer Platform) |
| Drafts | Yes | Yes (requires Marketing Developer Platform) |
| Comments | Yes | Yes |
| Reactions | Yes | Yes |
| Analytics | Requires `r_member_postAnalytics` | Requires Marketing Developer Platform |
| Required products | Share on LinkedIn | Marketing Developer Platform |

## Troubleshooting

### "No access token found"

Run `python src/oauth_setup.py` to authenticate.

### "Token refresh failed"

Your refresh token may have expired. Re-run `oauth_setup.py`.

### "Missing organization permissions"

Ensure your LinkedIn app has the Marketing Developer Platform product enabled and you're an admin of the Company Page.

### Silent failures in Claude

The MCP protocol uses stdio, so print statements break the connection. Check stderr output or run with:

```bash
python src/linkedin_server.py 2>/tmp/peeperfrog-linkedin-mcp.log
```

## File Structure

```
peeperfrog-linkedin-mcp/
├── src/
│   ├── linkedin_server.py    # Main MCP server
│   └── oauth_setup.py        # OAuth authentication script
├── .linkedin_tokens.json     # OAuth tokens (created by oauth_setup.py)
├── .gitignore
├── requirements.txt
└── README.md
```

## Security Notes

- Never commit `.linkedin_tokens.json` to version control
- Credentials are stored in Claude's config file (not in the project directory)
- Token files are created with restricted permissions (600)
- The OAuth callback server only runs during initial setup
- Access tokens are never logged or exposed in tool responses

## LinkedIn API Resources

- [LinkedIn Developer Portal](https://developer.linkedin.com/)
- [Posts API Documentation](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api)
- [OAuth 2.0 Guide](https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow)

## License

[Apache 2.0](../LICENSE) | See [DISCLAIMER](../DISCLAIMER.md) for warranty and liability terms.
