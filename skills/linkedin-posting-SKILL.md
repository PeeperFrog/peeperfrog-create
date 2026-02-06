---
name: linkedin-posting
description: Post text and links to LinkedIn personal profiles and Company Pages. Includes draft management, commenting, and scheduling workarounds.
---

# LinkedIn Posting

**Purpose:** Post content to your LinkedIn personal profile or Company Pages via the LinkedIn Marketing API. Supports text posts, link posts with Open Graph previews, draft management, and commenting.

**Use this skill when:** You want to publish content to LinkedIn, manage draft posts, or interact with comments.

**Prerequisites:**
- LinkedIn Developer App with "Share on LinkedIn" product enabled
- Marketing Developer Platform (optional - only for Company Page features)
- OAuth authentication completed via `oauth_setup.py`
- Valid tokens in `.linkedin_tokens.json`

---

## Quick Reference

| Tool | Description |
|------|-------------|
| `linkedin_post_text` | Publish a text post immediately |
| `linkedin_post_link` | Publish a post with link/article attachment |
| `linkedin_post_image` | Upload and post an image in one step |
| `linkedin_get_posts` | Retrieve recent posts |
| `linkedin_delete_post` | Delete a post by ID |
| `linkedin_upload_image` | Upload an image (returns URN for later use) |
| `linkedin_post_with_image` | Post with a previously uploaded image |
| `linkedin_create_draft` | Save a text post as draft |
| `linkedin_create_draft_link` | Save a link post as draft |
| `linkedin_get_drafts` | List all draft posts |
| `linkedin_publish_draft` | Publish a draft immediately |
| `linkedin_update_draft` | Edit a draft's content |
| `linkedin_delete_draft` | Delete a draft permanently |
| `linkedin_get_comments` | Retrieve comments on a post |
| `linkedin_create_comment` | Comment on a post |
| `linkedin_reply_to_comment` | Reply to an existing comment |
| `linkedin_delete_comment` | Delete a comment |
| `linkedin_like_post` | Like a post |
| `linkedin_unlike_post` | Remove a like from a post |
| `linkedin_get_reactions` | Get reactions (likes) on a post |
| `linkedin_get_posts_with_stats` | Get posts with stats, sorted by metric |
| `linkedin_get_post_impressions` | Get impressions for a post |
| `linkedin_get_organization_statistics` | Get org-wide or per-post stats |
| `linkedin_get_member_post_analytics` | Get personal post analytics |
| `linkedin_token_status` | Check and refresh OAuth token |

---

## Target Parameter

Most tools accept a `target` parameter to control where content is posted:

| Value | Description | Requires |
|-------|-------------|----------|
| `"personal"` or `"me"` | Your personal LinkedIn profile | Basic scopes only |
| `"organization"` or `"org"` | Default Company Page (from config) | Marketing Developer Platform |
| `"12345678"` | A specific organization by ID | Marketing Developer Platform |

Default is `"organization"` if not specified. **For personal-only setups, always specify `target: "personal"`.**

---

## Posting Content

### Text post to Company Page (default)

```javascript
peeperfrog-linkedin:linkedin_post_text({
  content: "Excited to announce our new product launch! #innovation #tech"
})
```

### Text post to personal profile

```javascript
peeperfrog-linkedin:linkedin_post_text({
  content: "My thoughts on the future of AI...",
  target: "personal"
})
```

### Text post to specific organization

```javascript
peeperfrog-linkedin:linkedin_post_text({
  content: "Update from our other company page",
  target: "98765432"
})
```

Maximum 3000 characters. Hashtags and mentions work normally.

### Link post with preview

```javascript
peeperfrog-linkedin:linkedin_post_link({
  content: "Check out our latest blog post on AI trends:",
  link_url: "https://example.com/blog/ai-trends-2026",
  target: "personal"  // optional
})
```

LinkedIn automatically fetches Open Graph metadata (title, description, image) from the URL.

### Get recent posts

```javascript
peeperfrog-linkedin:linkedin_get_posts({
  count: 10,  // default: 10, max: 100
  target: "personal"  // or "organization" (default), or specific org ID
})
```

Returns post IDs, text, timestamps, and engagement metrics.

### Delete a post

```javascript
peeperfrog-linkedin:linkedin_delete_post({
  post_id: "urn:li:share:7654321098765432100"
})
```

---

## Draft Management

LinkedIn's API doesn't support scheduled posts. Use drafts as a workaround: create drafts ahead of time, then publish when ready.

### Create a text draft

```javascript
peeperfrog-linkedin:linkedin_create_draft({
  content: "Upcoming webinar announcement - publish Monday morning",
  target: "organization"  // or "personal", or specific org ID
})
```

### Create a link draft

```javascript
peeperfrog-linkedin:linkedin_create_draft_link({
  content: "New case study on customer success:",
  link_url: "https://example.com/case-study",
  target: "personal"  // optional
})
```

### List all drafts

```javascript
peeperfrog-linkedin:linkedin_get_drafts({
  target: "organization"  // or "personal", or specific org ID
})
```

Returns all drafts with their IDs, content, and creation timestamps.

### Publish a draft

```javascript
peeperfrog-linkedin:linkedin_publish_draft({
  draft_id: "draft_1738700000_abc123"
})
```

### Edit a draft

```javascript
peeperfrog-linkedin:linkedin_update_draft({
  draft_id: "draft_1738700000_abc123",
  text: "Updated content for the post",
  title: "Updated Title"  // optional
})
```

### Delete a draft

```javascript
peeperfrog-linkedin:linkedin_delete_draft({
  draft_id: "draft_1738700000_abc123"
})
```

---

## Image Posts

Upload images and create posts with them.

### Post an image (one step)

```javascript
peeperfrog-linkedin:linkedin_post_image({
  content: "Check out our new office space! #newoffice",
  image_path: "/path/to/office-photo.jpg",
  alt_text: "Modern open office with natural lighting",
  target: "organization"  // optional
})
```

### Upload image separately

```javascript
// Step 1: Upload the image
peeperfrog-linkedin:linkedin_upload_image({
  image_path: "/path/to/image.png",
  target: "organization"
})
// Returns: { image_urn: "urn:li:image:123456789" }

// Step 2: Create post with the image
peeperfrog-linkedin:linkedin_post_with_image({
  content: "Here's our latest product!",
  image_urn: "urn:li:image:123456789",
  alt_text: "Product photo",
  target: "organization"
})
```

Supported image formats: PNG, JPG, JPEG, GIF, WebP.

---

## Reactions

Like and unlike posts, and view reaction counts.

### Like a post

```javascript
peeperfrog-linkedin:linkedin_like_post({
  post_id: "urn:li:share:7654321098765432100",
  actor: "organization"  // or "personal"
})
```

### Unlike a post

```javascript
peeperfrog-linkedin:linkedin_unlike_post({
  post_id: "urn:li:share:7654321098765432100",
  actor: "organization"
})
```

### Get reactions on a post

```javascript
peeperfrog-linkedin:linkedin_get_reactions({
  post_id: "urn:li:share:7654321098765432100",
  count: 50  // default: 20, max: 100
})
```

---

## Analytics

Get impressions, clicks, engagement, and other metrics for your posts.

### Get posts with stats (best/worst posts)

```javascript
// Get top 20 posts by impressions
peeperfrog-linkedin:linkedin_get_posts_with_stats({
  count: 20,
  sort_by: "impressions",  // or engagement, clicks, likes, comments, shares
  target: "organization"
})
```

Returns posts with full statistics, sorted by the specified metric (descending). Use this to find your best or worst performing posts.

### Get post impressions (convenience method)

```javascript
peeperfrog-linkedin:linkedin_get_post_impressions({
  post_id: "urn:li:share:7654321098765432100",
  target: "organization"  // or "personal" for member posts
})
```

Returns impressions, unique impressions, clicks, engagement, likes, comments, and shares.

### Get organization-wide statistics

```javascript
peeperfrog-linkedin:linkedin_get_organization_statistics({
  target: "organization"  // optional, defaults to configured org
})
```

Returns aggregate statistics for all posts from the organization.

### Get statistics for specific posts

```javascript
peeperfrog-linkedin:linkedin_get_organization_statistics({
  post_ids: ["urn:li:share:123456", "urn:li:share:789012"],
  target: "organization"
})
```

### Get member post analytics (personal profile)

```javascript
peeperfrog-linkedin:linkedin_get_member_post_analytics({
  post_id: "urn:li:share:7654321098765432100",
  metric_type: "IMPRESSION"  // or MEMBERS_REACHED, RESHARE, REACTION, COMMENT
})
```

Available metrics:
- `IMPRESSION` - Total impressions
- `MEMBERS_REACHED` - Unique viewers
- `RESHARE` - Reposts count
- `REACTION` - Reactions count
- `COMMENT` - Comments count

---

## Comments

Read, create, reply to, and delete comments on LinkedIn posts.

### Get comments on a post

```javascript
peeperfrog-linkedin:linkedin_get_comments({
  post_id: "urn:li:share:7654321098765432100",
  count: 20  // default: 20, max: 100
})
```

Returns comment IDs, authors, messages, timestamps, and reply counts.

### Create a comment

```javascript
peeperfrog-linkedin:linkedin_create_comment({
  post_id: "urn:li:share:7654321098765432100",
  message: "Great insights! Thanks for sharing.",
  actor: "personal"  // or "organization" (default), or specific org ID
})
```

### Reply to a comment

```javascript
peeperfrog-linkedin:linkedin_reply_to_comment({
  post_id: "urn:li:share:7654321098765432100",
  parent_comment_id: "123456789",
  message: "Thanks for your feedback! We really appreciate it.",
  actor: "organization"
})
```

### Delete a comment

```javascript
peeperfrog-linkedin:linkedin_delete_comment({
  post_id: "urn:li:share:7654321098765432100",
  comment_id: "123456789",
  actor: "organization"  // who created the comment
})
```

You can only delete comments that you (or your organization) created.

---

## Token Management

LinkedIn access tokens expire every 60 days. The `linkedin_token_status` tool always refreshes the token to keep it at maximum validity.

### Check and refresh token

```javascript
peeperfrog-linkedin:linkedin_token_status()
```

Response:

```json
{
  "authenticated": true,
  "expires_at": "2026-04-05T10:30:00Z",
  "expires_in_days": 60.0,
  "refreshed_at": "2026-02-05T21:45:00",
  "message": "Token refreshed. Valid for 60.0 days"
}
```

If the token is fully expired (past 60 days of inactivity), re-run `oauth_setup.py` to re-authenticate.

---

## Parameters Reference

### linkedin_post_text

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `content` | string | Yes | -- | Post content (max 3000 characters) |
| `visibility` | string | No | "PUBLIC" | PUBLIC, CONNECTIONS, or LOGGED_IN |
| `target` | string | No | "organization" | "personal", "organization", or org ID |

### linkedin_post_link

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `content` | string | Yes | -- | Post content (max 3000 characters) |
| `link_url` | string | Yes | -- | URL to attach (Open Graph metadata auto-fetched) |
| `visibility` | string | No | "PUBLIC" | PUBLIC, CONNECTIONS, or LOGGED_IN |
| `target` | string | No | "organization" | "personal", "organization", or org ID |

### linkedin_get_posts

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `count` | integer | No | 10 | Number of posts to retrieve (max 100) |
| `target` | string | No | "organization" | "personal", "organization", or org ID |

### linkedin_delete_post

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `post_id` | string | Yes | Post URN (e.g., `urn:li:share:123456`) |

### linkedin_create_draft / linkedin_create_draft_link

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `content` | string | Yes | -- | Draft content |
| `link_url` | string | Yes (link only) | -- | URL to attach |
| `visibility` | string | No | "PUBLIC" | Visibility when published |
| `target` | string | No | "organization" | "personal", "organization", or org ID |

### linkedin_get_drafts

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `count` | integer | No | 10 | Max drafts to retrieve |
| `target` | string | No | "organization" | "personal", "organization", or org ID |

### linkedin_update_draft

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `draft_id` | string | Yes | Draft ID from `linkedin_get_drafts` |
| `content` | string | Yes | New content |

### linkedin_publish_draft / linkedin_delete_draft

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `draft_id` | string | Yes | Draft ID from `linkedin_get_drafts` |

### linkedin_get_comments

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `post_id` | string | Yes | -- | Post URN or ID to get comments from |
| `count` | integer | No | 20 | Max comments to retrieve (max 100) |

### linkedin_create_comment

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `post_id` | string | Yes | -- | Post URN or ID to comment on |
| `message` | string | Yes | -- | Comment text |
| `actor` | string | No | "organization" | Who to comment as: "personal", "organization", or org ID |

### linkedin_delete_comment

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `post_id` | string | Yes | -- | Post URN or ID the comment is on |
| `comment_id` | string | Yes | -- | Comment ID to delete |
| `actor` | string | No | "organization" | Who created the comment |

### linkedin_reply_to_comment

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `post_id` | string | Yes | -- | Post URN or ID the comment is on |
| `parent_comment_id` | string | Yes | -- | Comment ID to reply to |
| `message` | string | Yes | -- | Reply text |
| `actor` | string | No | "organization" | Who to reply as |

### linkedin_like_post

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `post_id` | string | Yes | -- | Post URN or ID to like |
| `actor` | string | No | "organization" | Who to like as |

### linkedin_unlike_post

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `post_id` | string | Yes | -- | Post URN or ID to unlike |
| `actor` | string | No | "organization" | Who liked the post |

### linkedin_get_reactions

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `post_id` | string | Yes | -- | Post URN or ID to get reactions from |
| `count` | integer | No | 20 | Max reactions to retrieve (max 100) |

### linkedin_upload_image

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `image_path` | string | Yes | -- | Path to the image file |
| `target` | string | No | "organization" | Owner of the image |

### linkedin_post_image

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `content` | string | Yes | -- | Post text (max 3000 characters) |
| `image_path` | string | Yes | -- | Path to the image file |
| `visibility` | string | No | "PUBLIC" | PUBLIC, CONNECTIONS, or LOGGED_IN |
| `alt_text` | string | No | "" | Alt text for accessibility |
| `title` | string | No | "" | Image title |
| `target` | string | No | "organization" | Where to post |

### linkedin_post_with_image

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `content` | string | Yes | -- | Post text (max 3000 characters) |
| `image_urn` | string | Yes | -- | Image URN from upload_image |
| `visibility` | string | No | "PUBLIC" | PUBLIC, CONNECTIONS, or LOGGED_IN |
| `alt_text` | string | No | "" | Alt text for accessibility |
| `title` | string | No | "" | Image title |
| `target` | string | No | "organization" | Where to post |

### linkedin_get_post_impressions

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `post_id` | string | Yes | -- | Post URN or ID |
| `target` | string | No | "organization" | "personal" for member, "organization" or org ID |

### linkedin_get_organization_statistics

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `post_ids` | array | No | -- | List of post IDs for per-post stats |
| `target` | string | No | "organization" | "organization" or specific org ID |

### linkedin_get_member_post_analytics

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `post_id` | string | Yes | -- | Post URN or ID |
| `metric_type` | string | No | "IMPRESSION" | IMPRESSION, MEMBERS_REACHED, RESHARE, REACTION, COMMENT |

### linkedin_get_posts_with_stats

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `count` | integer | No | 20 | Number of posts to retrieve (max 50) |
| `sort_by` | string | No | "impressions" | impressions, engagement, clicks, likes, comments, shares |
| `target` | string | No | "organization" | "personal" or "organization" or org ID |

---

## Example Workflows

### Weekly content calendar

```javascript
// Monday: Create drafts for the week
peeperfrog-linkedin:linkedin_create_draft({
  text: "Tuesday tip: Always validate user input! #security",
  title: "Tuesday Tip"
})

peeperfrog-linkedin:linkedin_create_draft_link({
  text: "Thursday read: Our guide to microservices",
  url: "https://example.com/microservices-guide",
  title: "Thursday Article"
})

// When ready to publish:
peeperfrog-linkedin:linkedin_get_drafts()
// Find the draft ID, then:
peeperfrog-linkedin:linkedin_publish_draft({
  draft_id: "draft_..."
})
```

### Content review workflow

```javascript
// Create draft
peeperfrog-linkedin:linkedin_create_draft({
  text: "Initial draft content...",
  title: "Q1 Announcement"
})

// Review and edit
peeperfrog-linkedin:linkedin_update_draft({
  draft_id: "draft_...",
  text: "Revised content after review..."
})

// Publish when approved
peeperfrog-linkedin:linkedin_publish_draft({
  draft_id: "draft_..."
})
```

---

## API Limitations

| Limitation | Details |
|------------|---------|
| Post length | Maximum 3000 characters |
| Scheduled posts | Not supported by API (use drafts) |
| Newsletters | Not supported by API |
| Videos | Requires separate upload flow (not yet implemented) |
| Documents/PDFs | Not yet implemented |
| Rate limits | Not published, but typical usage is fine |

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| "No access token found" | Not authenticated | Run `oauth_setup.py` |
| "Token refresh failed" | Refresh token expired | Re-run `oauth_setup.py` |
| "Missing organization permissions" | App not configured | Enable Marketing Developer Platform in LinkedIn Developer Portal |
| 403 Forbidden | Not a Company Page admin | Ensure you're an admin of the target Company Page |
| Silent failures | Print statements in MCP | Check `2>/tmp/peeperfrog-linkedin-mcp.log` |

---

## Related Skills

- **wordpress-upload** -- Upload images to WordPress for use in posts
- **image-generation** -- Generate images for social media content
