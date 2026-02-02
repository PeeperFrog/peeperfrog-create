# WebP Converter - Installation Instructions

## Install to ~/peeperfrog-create/tools

```bash
# Create tools directory if it doesn't exist
mkdir -p ~/peeperfrog-create/tools

# Save the webp-convert.py file to ~/peeperfrog-create/tools/webp-convert.py

# Make it executable
chmod +x ~/peeperfrog-create/tools/webp-convert.py
```

## Usage (No Installation Required)

The script uses inline dependency declarations, so `uv` handles everything automatically.

**Smart skipping:** By default, the script skips files that already have .webp versions. This means you can run it repeatedly and it will only convert new images.

### Single Image
```bash
uv run ~/peeperfrog-create/tools/webp-convert.py image.png --quality 85
```

### Batch Convert Directory (Skips Already-Converted)
```bash
uv run ~/peeperfrog-create/tools/webp-convert.py ~/Downloads/sapien-images/ --batch --quality 85
```

### Recursive (Include Subdirectories)
```bash
uv run ~/peeperfrog-create/tools/webp-convert.py ~/Downloads/sapien-images/ --batch --recursive --quality 85
```

### Force Reconversion (Ignore Existing .webp Files)
```bash
uv run ~/peeperfrog-create/tools/webp-convert.py ~/Downloads/sapien-images/ --batch --force --quality 85
```

## Quality Presets

**Featured Images (1920x1080)**: `--quality 90`
- High quality for hero images
- Target: < 200KB

**Social Media (1200x630, 1080x1080)**: `--quality 85`
- Standard quality for social
- Target: < 150KB

**Infographics**: `--quality 85`
- Balance quality and file size
- Target: < 250KB

## Typical Workflow

After generating images:

```bash
# 1. Generate batch images (via PeeperFrog Create MCP or manual)
#    Images save to ~/Pictures/ai-generated-images/batch/

# 2. Convert all unconverted images to WebP
uv run ~/peeperfrog-create/tools/webp-convert.py \
  ~/Pictures/ai-generated-images/ \
  --batch \
  --recursive \
  --quality 85

# Output example:
# Processing 10 images...
# 
# ✓ Converted: quantum-ai-header.png
#   Original: 847,392 bytes
#   WebP: 187,234 bytes
#   Saved: 77.9%
#   Output: quantum-ai-header.webp
# 
# ⊘ Skipped (already exists): previous-article.png
# 
# ✓ Converted: 3
# ⊘ Skipped (already exist): 7
# Total processed: 10/10

# 3. Upload .webp files to WordPress (not .png originals)
```

**Key benefit:** Run this command anytime after batch generation. It only converts new images, so you can run it repeatedly without wasting time reconverting existing files.

## Create Alias (Optional)

Add to ~/.bashrc or ~/.zshrc:

```bash
alias webp='uv run ~/peeperfrog-create/tools/webp-convert.py'
```

Then just use:
```bash
webp image.png --quality 85
webp ~/Downloads/sapien-images/ --batch
```

## Expected Results

**Typical file size reduction: 70-80%**

Example:
```
✓ Converted: quantum-ai-header.png
  Original: 847,392 bytes
  WebP: 187,234 bytes
  Saved: 77.9%
  Output: quantum-ai-header.webp
```

## Troubleshooting

### First run is slow
`uv` downloads and caches Pillow on first run. Subsequent runs are instant.

### "No such file or directory"
Check the input path exists:
```bash
ls ~/Downloads/sapien-fusion-images/
```

### Permission denied
Make sure script is executable:
```bash
chmod +x ~/peeperfrog-create/tools/webp-convert.py
```

---

🧠 SAPIEN FUSION Tools
WebP Conversion for WordPress Optimization
