# Remaining Implementation Work

## Quick Reference: What's Done vs What's Left

**Core Infrastructure**: ✅ 100% Complete
**Batch API**: ✅ 90% Complete (module created, needs MCP tool wiring)
**Metadata System**: ✅ 100% Complete
**Priority Flag**: ✅ 100% Complete
**WordPress Integration**: ⚠️ 50% Complete (needs metadata setting)
**Tests**: ❌ 0% Complete
**Documentation**: ❌ 0% Complete

---

## 1. Add Batch Status MCP Tools (HIGH PRIORITY)

### File: `/home/peeperfrog/peeperfrog-create/peeperfrog-create-mcp/src/image_server.py`

### Step 1.1: Add to tools list (around line 1651, before closing `]`)

```python
                },
                {
                    "name": "check_batch_status",
                    "description": "Check status of async batch job submitted with priority='low' or run_batch. Returns job status, progress, and results if complete.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "batch_job_id": {
                                "type": "string",
                                "description": "Batch job ID returned from generate_image with priority='low'"
                            }
                        },
                        "required": ["batch_job_id"]
                    }
                },
                {
                    "name": "retrieve_batch_results",
                    "description": "Retrieve and save completed batch results to disk. Downloads images from completed batch job and creates metadata files.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "batch_job_id": {
                                "type": "string",
                                "description": "Batch job ID returned from generate_image with priority='low'"
                            }
                        },
                        "required": ["batch_job_id"]
                    }
                }
            ]
```

### Step 1.2: Add tool call handlers (around line 1700, after other tool handlers)

```python
        elif tool_name == "check_batch_status":
            from gemini_batch import check_batch_status
            result = check_batch_status(
                arguments.get("batch_job_id"),
                os.environ.get("GEMINI_API_KEY")
            )
        elif tool_name == "retrieve_batch_results":
            from gemini_batch import retrieve_batch_results
            result = retrieve_batch_results(
                arguments.get("batch_job_id"),
                os.environ.get("GEMINI_API_KEY"),
                DIRS["original_dir"]
            )
```

### Step 1.3: Update generate_image tool call handler (around line 1660)

Add the new parameters to the tool call:

```python
        if tool_name == "generate_image":
            result = generate_image(
                arguments.get("prompt"),
                arguments.get("aspect_ratio", "1:1"),
                arguments.get("image_size", "large"),
                arguments.get("reference_image"),
                arguments.get("reference_images"),
                arguments.get("quality", "pro"),
                arguments.get("provider"),
                arguments.get("search_grounding", False),
                arguments.get("thinking_level"),
                arguments.get("media_resolution"),
                arguments.get("model"),
                arguments.get("auto_mode"),
                arguments.get("style_hint", "general"),
                arguments.get("convert_to_webp", True),
                arguments.get("webp_quality", 85),
                arguments.get("upload_to_wordpress", False),
                arguments.get("wp_url"),
                arguments.get("priority", "high"),  # NEW
                arguments.get("title", ""),  # NEW
                arguments.get("description", ""),  # NEW
                arguments.get("alternative_text", ""),  # NEW
                arguments.get("caption", "")  # NEW
            )
```

### Step 1.4: Update generate_image tool schema (around line 1493)

Add to properties section:

```python
                            "priority": {
                                "type": "string",
                                "enum": ["high", "low"],
                                "default": "high",
                                "description": "high: immediate generation (full price), low: batch API (50% discount, 24hr wait, Gemini only)"
                            },
                            "title": {
                                "type": "string",
                                "description": "Image title for metadata (auto-generated if not provided)"
                            },
                            "description": {
                                "type": "string",
                                "description": "Image description for metadata (uses prompt if not provided)"
                            },
                            "alternative_text": {
                                "type": "string",
                                "description": "Alt text for accessibility (auto-generated if not provided)"
                            },
                            "caption": {
                                "type": "string",
                                "description": "Image caption for metadata (uses title if not provided)"
                            }
```

---

## 2. WordPress Metadata Enhancement (MEDIUM PRIORITY)

### File: `/home/peeperfrog/peeperfrog-create/peeperfrog-create-mcp/src/image_server.py`

### Step 2.1: Create _update_wordpress_metadata function (add around line 1100)

```python
def _update_wordpress_metadata(media_id, wp_url, metadata_dict):
    """
    Update WordPress media item with metadata from JSON file.

    Args:
        media_id: WordPress media ID (integer)
        wp_url: WordPress site URL
        metadata_dict: Metadata from read_metadata_file()

    Returns:
        {"success": True/False, "media_id": 123, "error": "..."}
    """
    normalized_url, wp_user, wp_password, _ = _get_wordpress_config(wp_url)

    update_url = f"{normalized_url}/wp-json/wp/v2/media/{media_id}"

    payload = {
        "title": metadata_dict.get("title", ""),
        "alt_text": metadata_dict.get("alternative_text", ""),
        "caption": metadata_dict.get("caption", ""),
        "description": metadata_dict.get("description", "")
    }

    try:
        response = requests.post(
            update_url,
            json=payload,
            auth=(wp_user, wp_password),
            headers={'Content-Type': 'application/json'}
        )

        if response.status_code in [200, 201]:
            return {"success": True, "media_id": media_id}
        else:
            return {
                "success": False,
                "media_id": media_id,
                "error": f"HTTP {response.status_code}: {response.text}"
            }
    except Exception as e:
        return {"success": False, "media_id": media_id, "error": str(e)}
```

### Step 2.2: Update _upload_single_to_wordpress function (around line 1011)

Find this section (after successful upload):

```python
    if response.status_code in [201, 200]:
        media_data = response.json()
        media_id = media_data.get("id")

        # ADD THIS:
        # Read metadata and update WordPress
        from metadata import read_metadata_file, update_wordpress_info
        metadata = read_metadata_file(file_path)
        if metadata:
            metadata_result = _update_wordpress_metadata(media_id, wp_url, metadata)
            if not metadata_result["success"]:
                debug_log(f"Warning: Failed to update metadata for media_id {media_id}: {metadata_result.get('error')}")

            # Store WordPress info back to metadata
            update_wordpress_info(file_path, media_id, media_data.get("source_url"))

        return {
            "success": True,
            "filename": filename,
            "media_id": media_id,
            "url": media_data.get("source_url"),
            "title": metadata.get("title", filename) if metadata else filename,
            "alt_text": metadata.get("alternative_text", "") if metadata else "",
            "caption": metadata.get("caption", "") if metadata else "",
            "description": metadata.get("description", "") if metadata else "",
            "metadata_updated": metadata_result["success"] if metadata else False
        }
```

---

## 3. Update get_media_id_map() (MEDIUM PRIORITY)

### File: `/home/peeperfrog/peeperfrog-create/peeperfrog-create-mcp/src/image_server.py`

### Replace entire function (around line 1106):

```python
def get_media_id_map(directory="original", output_format="json"):
    """
    Get metadata mapping for images by scanning metadata/json/ files.

    Args:
        directory: "original" or "webp" (for backwards compatibility)
        output_format: "json", "yaml", or "python_dict"

    Returns:
        {
            "success": True,
            "media_map": {
                "image1.png": {
                    "title": "...",
                    "description": "...",
                    "alternative_text": "...",
                    "caption": "...",
                    "wordpress_media_id": 123,  // if uploaded
                    "wordpress_url": "https://..."  // if uploaded
                }
            }
        }
    """
    json_dir = DIRS.get("json_dir")
    if not json_dir or not os.path.exists(json_dir):
        return {
            "success": False,
            "error": "Metadata directory not found",
            "media_map": {}
        }

    media_map = {}

    try:
        for json_file in os.listdir(json_dir):
            if not json_file.endswith('.json'):
                continue

            json_path = os.path.join(json_dir, json_file)
            with open(json_path, 'r') as f:
                metadata = json.load(f)

            # Remove .json extension to get image filename
            image_filename = json_file[:-5]
            media_map[image_filename] = metadata
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "media_map": {}
        }

    # Format output
    if output_format == "yaml":
        import yaml
        formatted = yaml.dump(media_map, default_flow_style=False, sort_keys=False)
    elif output_format == "python_dict":
        formatted = str(media_map)
    else:  # json
        formatted = json.dumps(media_map, indent=2)

    return {
        "success": True,
        "media_map": formatted if output_format != "json" else media_map,
        "count": len(media_map),
        "format": output_format
    }
```

---

## 4. Tests (LOW PRIORITY - can be done later)

### Create: `/home/peeperfrog/peeperfrog-create/peeperfrog-create-mcp/tests/test_metadata.py`

```python
import unittest
import os
import json
import tempfile
from datetime import datetime
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from metadata import (
    create_metadata_dict,
    write_metadata_file,
    read_metadata_file,
    copy_metadata_for_webp,
    update_wordpress_info
)

class TestMetadata(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_create_metadata_dict(self):
        metadata = create_metadata_dict(
            prompt="A sunset",
            title="Beautiful Sunset",
            description="A vibrant sunset over mountains",
            alternative_text="Orange and pink sunset",
            caption="Sunset in the mountains",
            provider="gemini",
            model="gemini-2.5-flash-image",
            aspect_ratio="16:9",
            image_size="large",
            quality=100,
            cost=0.039
        )

        self.assertEqual(metadata["prompt"], "A sunset")
        self.assertEqual(metadata["title"], "Beautiful Sunset")
        self.assertEqual(metadata["provider"], "gemini")
        self.assertEqual(metadata["quality"], 100)
        self.assertIn("date_time_created", metadata)

    def test_write_and_read_metadata(self):
        # Create test structure
        original_dir = os.path.join(self.test_dir, "original")
        os.makedirs(original_dir)

        image_path = os.path.join(original_dir, "test_image.png")
        with open(image_path, 'w') as f:
            f.write("fake image data")

        metadata = create_metadata_dict(
            prompt="Test",
            title="Test Image",
            description="Test description",
            alternative_text="Test alt",
            caption="Test caption",
            provider="gemini",
            model="test-model",
            aspect_ratio="1:1",
            image_size="large",
            quality=100,
            cost=0.01
        )

        # Write metadata
        json_path = write_metadata_file(image_path, metadata)
        self.assertTrue(os.path.exists(json_path))

        # Read metadata
        read_meta = read_metadata_file(image_path)
        self.assertEqual(read_meta["title"], "Test Image")
        self.assertEqual(read_meta["prompt"], "Test")

if __name__ == '__main__':
    unittest.main()
```

### Create: `/home/peeperfrog/peeperfrog-create/peeperfrog-create-mcp/tests/test_gemini_batch.py`

```python
import unittest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from gemini_batch import submit_batch_job, check_batch_status

class TestGeminiBatch(unittest.TestCase):
    @patch('gemini_batch.requests.post')
    def test_submit_batch_job(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "test-job-123",
            "status": "pending"
        }
        mock_post.return_value = mock_response

        result = submit_batch_job([{"prompt": "test"}], "fake-api-key")

        self.assertTrue(result["success"])
        self.assertIn("batch_job_id", result)

if __name__ == '__main__':
    unittest.main()
```

---

## 5. Documentation Updates (LOW PRIORITY)

### Update all skill files in root directory

Files to update:
- `image-generation-SKILL.md`
- `image-batch-SKILL.md`
- Any other *-SKILL.md files

Add sections for:
1. **Required Metadata Fields** - Document title, description, alternative_text, caption
2. **Priority Flag** - Document priority="high" vs priority="low"
3. **Batch API Usage** - Example workflow with check_batch_status
4. **File Structure** - Document original/, webp/, metadata/ structure
5. **Generation Logs** - Update batch_results.json references to generation_log CSVs

### Update README.md

Add sections:
1. **Directory Structure**
2. **Batch API Cost Savings**
3. **Metadata System**
4. **WordPress Integration**

---

## Testing Checklist

After implementing the above:

1. **Test immediate generation** (priority="high")
   ```python
   result = generate_image(
       prompt="A sunset",
       priority="high",
       title="Sunset Test",
       description="Test sunset image",
       alternative_text="Orange sunset",
       caption="Test caption"
   )
   ```
   - ✅ Image saved to original/
   - ✅ Metadata JSON created
   - ✅ WebP created with metadata
   - ✅ Generation log entry created

2. **Test batch API** (priority="low")
   ```python
   result = generate_image(
       prompt="A sunset",
       priority="low",
       provider="gemini",
       title="Sunset Test"
   )
   batch_id = result["batch_job_id"]

   status = check_batch_status(batch_job_id=batch_id)
   # When complete:
   results = retrieve_batch_results(batch_job_id=batch_id)
   ```
   - ✅ Returns batch_job_id immediately
   - ✅ check_batch_status works
   - ✅ retrieve_batch_results downloads images

3. **Test WordPress upload**
   - ✅ Metadata fields set on WordPress
   - ✅ WordPress info stored in metadata JSON

4. **Test get_media_id_map**
   - ✅ Reads from metadata JSON files
   - ✅ Returns WordPress info if available

5. **Run unit tests**
   ```bash
   cd /home/peeperfrog/peeperfrog-create/peeperfrog-create-mcp
   python -m pytest tests/ -v
   ```

---

## Priority Order

1. **CRITICAL**: Add batch status MCP tools (#1) - Required for batch API workflow
2. **HIGH**: WordPress metadata enhancement (#2) - Completes metadata round-trip
3. **MEDIUM**: Update get_media_id_map (#3) - Removes last batch_results.json dependency
4. **LOW**: Tests (#4) - Important but not blocking
5. **LOW**: Documentation (#5) - Can be done incrementally

---

## Estimated Time

- MCP Tools: 30 minutes
- WordPress: 30 minutes
- get_media_id_map: 15 minutes
- Tests: 1-2 hours
- Documentation: 1-2 hours

**Total**: 3-5 hours to completion
