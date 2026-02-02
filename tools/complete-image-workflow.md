# Complete Image Workflow with WebP Conversion

## Updated Image Skill

✅ **Catalyst Brief Images skill now includes WebP conversion instructions**

Location: `/mnt/skills/user/catalyst-brief-images/SKILL.md`

## Smart WebP Converter Features

### 🎯 Intelligent Skipping
- **Automatically skips** files that already have .webp versions
- Safe to run repeatedly without reconverting
- Only processes new/unconverted images

### 📊 Conversion Statistics
```
Processing 10 images...

✓ Converted: quantum-ai-header.png
  Original: 847,392 bytes
  WebP: 187,234 bytes
  Saved: 77.9%
  
⊘ Skipped (already exists): previous-image.png

✓ Converted: 3
⊘ Skipped (already exist): 7
Total processed: 10/10
```

### 🔄 Non-Blocking Workflow

**The conversion is separate from generation** - no blocking during batch processing.

## Complete Daily Workflow

### Step 1: Generate Images (Batch)

```python
# Queue images during daily production
add_to_batch(
  prompt="...",
  filename="quantum-ai-header.png",
  aspect_ratio="16:9"
)

# Later, run batch
run_batch()
# Images save to ~/Pictures/ai-generated-images/batch/
```

### Step 2: Convert to WebP (After Generation)

```bash
# Run once after batch completes
uv run ~/peeperfrog-create/tools/webp-convert.py \
  ~/Pictures/ai-generated-images/ \
  --batch \
  --recursive \
  --quality 85
```

**This command:**
- ✅ Scans all directories recursively
- ✅ Finds PNG/JPG files
- ✅ Skips files that already have .webp versions
- ✅ Converts only new images
- ✅ Reports statistics

### Step 3: Upload to WordPress

Upload the `.webp` files (not the `.png` originals) via:
- WordPress MCP server
- WordPress REST API
- Manual upload through media library

## Installation

Save `webp-convert.py` to `~/peeperfrog-create/tools/webp-convert.py`:

```bash
# Make executable
chmod +x ~/peeperfrog-create/tools/webp-convert.py

# Test it
uv run ~/peeperfrog-create/tools/webp-convert.py --help
```

## Command Reference

### Basic Usage
```bash
# Convert single image (skips if .webp exists)
uv run ~/peeperfrog-create/tools/webp-convert.py image.png

# Batch directory (skips converted)
uv run ~/peeperfrog-create/tools/webp-convert.py ~/Pictures/ai-generated-images/ --batch

# Include subdirectories (recommended for daily workflow)
uv run ~/peeperfrog-create/tools/webp-convert.py ~/Pictures/ai-generated-images/ --batch --recursive
```

### Advanced Options
```bash
# Force reconversion (ignore existing .webp)
uv run ~/peeperfrog-create/tools/webp-convert.py ~/Pictures/ai-generated-images/ --batch --force

# Custom quality
uv run ~/peeperfrog-create/tools/webp-convert.py ~/Pictures/ai-generated-images/ --batch --quality 90

# Specify output filename
uv run ~/peeperfrog-create/tools/webp-convert.py input.png output.webp
```

## Quality Presets

### Featured Images (1920x1080)
```bash
--quality 90  # High quality, ~180KB target
```

### Social Media (1080x1080, 1200x630)
```bash
--quality 85  # Standard quality, ~120KB target
```

### Infographics
```bash
--quality 85  # Balance quality/size, ~200KB target
```

## Optional: Create Alias

Add to `~/.bashrc` or `~/.zshrc`:

```bash
alias webp='uv run ~/peeperfrog-create/tools/webp-convert.py'
alias webp-batch='uv run ~/peeperfrog-create/tools/webp-convert.py ~/Pictures/ai-generated-images/ --batch --recursive --quality 85'
```

Then just:
```bash
webp image.png
webp-batch  # Converts all unconverted images
```

## Integration with Daily Production

The image skill now includes WebP conversion as a documented post-processing step:

1. **During production:** Queue images with `add_to_batch`
2. **Generate batch:** Run `run_batch()` when ready
3. **Convert to WebP:** Run conversion command
4. **Upload optimized:** Use .webp files for WordPress

**No blocking, no manual tracking** - the converter handles everything intelligently.

## File Size Expectations

**Typical reduction: 70-80%**

| Original (PNG) | WebP | Savings |
|---------------|------|---------|
| 847KB | 187KB | 77.9% |
| 1.2MB | 280KB | 76.7% |
| 450KB | 98KB | 78.2% |

## Troubleshooting

### First run is slow
`uv` downloads Pillow on first run (~5 seconds). Subsequent runs are instant.

### "No images found"
Check the directory path:
```bash
ls ~/Pictures/ai-generated-images/batch/
```

### Everything shows "Skipped"
Good! It means all images already have .webp versions. Use `--force` to reconvert if needed.

### Need to reconvert everything
```bash
uv run ~/peeperfrog-create/tools/webp-convert.py ~/Pictures/ai-generated-images/ --batch --recursive --force
```

---

🧠 SAPIEN FUSION
Complete Image Production Pipeline
