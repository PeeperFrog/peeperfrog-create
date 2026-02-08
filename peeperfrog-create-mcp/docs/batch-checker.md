# Automated Batch Job Checker

Automatically checks pending batch jobs and retrieves completed images in the background.

## Features

- **Automatic checking**: Runs every N minutes (configurable 5-1440)
- **Log rotation**: Max 10MB per file, 10 backup files (100MB total)
- **Cron persistence**: Survives system restarts
- **Full automation**: Downloads images, creates metadata, converts to WebP
- **Error handling**: Gracefully handles failures and retries

## Configuration

Edit `config.json`:

```json
{
  "batch_check_enabled": true,
  "batch_check_interval_minutes": 30,
  "batch_checker_script": "./src/batch_checker.py"
}
```

**Settings:**
- `batch_check_enabled`: Set to `false` to disable
- `batch_check_interval_minutes`: 5-1440 minutes (5 min to 24 hours)
- `batch_checker_script`: Path to batch_checker.py

## How It Works

### 1. Submit Batch Job
```python
result = generate_image(
    prompt="...",
    priority="low",  # Batch API - 50% cost savings
    # ... other params
)
# Returns: {"batch_job_id": "batch_20260207_210000"}
```

### 2. Automatic Processing
Every N minutes, the cron job:
1. Loads pending jobs from `metadata/batch_jobs_tracking.json`
2. Checks status with Gemini Batch API
3. Downloads completed images
4. Creates metadata JSON files
5. Converts to WebP (if enabled)
6. Creates WebP metadata JSON
7. Updates tracking file
8. Logs everything

### 3. Results Ready
Images appear in your directories with full metadata and WebP conversions!

## File Locations

```
~/Pictures/ai-generated-images/
├── original/
│   └── req_0.png                           # Generated image
├── webp/
│   └── req_0.webp                          # WebP conversion
├── json/
│   ├── req_0.png.json                      # Original metadata
│   └── req_0.webp.json                     # WebP metadata
└── metadata/
    ├── logs/
    │   ├── batch_checker.log               # Current log
    │   ├── batch_checker.log.1             # Rotated logs
    │   └── batch_checker.log.2-10          # (up to 10 backups)
    ├── batch_metadata/
    │   └── batch_20260207_210000.json      # Batch request metadata
    └── batch_jobs_tracking.json            # Job status tracking
```

## Log Files

**Log rotation:**
- Max 10MB per file
- Keeps 10 backup files
- 100MB total maximum
- Automatic rotation when size limit reached

**View logs:**
```bash
# Tail current log
tail -f ~/Pictures/ai-generated-images/metadata/logs/batch_checker.log

# View all logs
ls -lh ~/Pictures/ai-generated-images/metadata/logs/

# Search for errors
grep ERROR ~/Pictures/ai-generated-images/metadata/logs/batch_checker.log
```

**Sample log:**
```
[2026-02-08 09:30:00] [INFO] Batch checker started
[2026-02-08 09:30:00] [INFO] Starting batch job check...
[2026-02-08 09:30:00] [INFO] Found 1 pending batch job(s)
[2026-02-08 09:30:05] [INFO] Retrieving completed batch job: batch_20260207_210000
[2026-02-08 09:30:10] [INFO] Successfully retrieved and processed 1 image(s)
[2026-02-08 09:30:15] [INFO] Batch check complete: 1 retrieved, 0 failed/errors
```

## Cron Job

**Persistence:**
- Cron jobs **persist after system restart**
- Stored in system crontab (survives reboots)
- Runs automatically on boot

**View cron entry:**
```bash
crontab -l | grep batch_checker
```

**Example entry:**
```cron
# PeeperFrog Create batch checker
*/30 * * * * /path/to/venv/bin/python3 /path/to/batch_checker.py 2>&1
```

**Schedules:**
- `*/5 * * * *` = Every 5 minutes
- `*/15 * * * *` = Every 15 minutes
- `*/30 * * * *` = Every 30 minutes (default)
- `0 * * * *` = Every hour
- `0 0 * * *` = Once daily at midnight

## Manual Operations

**Run manually (for testing):**
```bash
cd ~/peeperfrog-create/peeperfrog-create-mcp/src
python3 batch_checker.py --verbose
```

**Check specific job:**
```python
from gemini_batch import check_batch_status
status = check_batch_status("batch_20260207_210000", api_key)
```

**Retrieve specific job:**
```python
from gemini_batch import retrieve_batch_results
result = retrieve_batch_results("batch_20260207_210000", api_key, save_dir)
```

## Enable/Disable

**Disable:**
1. Edit `config.json`: `"batch_check_enabled": false`
2. Run: `python3 setup.py --update`

Or remove cron job directly:
```bash
crontab -e
# Delete lines with "PeeperFrog Create batch checker"
```

**Re-enable:**
1. Edit `config.json`: `"batch_check_enabled": true`
2. Run: `python3 setup.py --update`

## Change Check Interval

Edit `config.json`:
```json
{
  "batch_check_interval_minutes": 60
}
```

Then update:
```bash
python3 setup.py --update
```

## Troubleshooting

**Check if cron is running:**
```bash
crontab -l | grep batch_checker
```

**Test manually:**
```bash
cd ~/peeperfrog-create/peeperfrog-create-mcp/src
python3 batch_checker.py --verbose
```

**Check logs:**
```bash
tail -50 ~/Pictures/ai-generated-images/metadata/logs/batch_checker.log
```

**Common issues:**
1. **GEMINI_API_KEY not set**: Cron doesn't inherit environment variables
   - Solution: Set in `.env` file (batch_checker loads from image_server.py)

2. **Python path wrong**: Cron uses system Python, not venv
   - Solution: setup.py uses full venv path in cron command

3. **Permission denied**: Script not executable
   - Solution: `chmod +x src/batch_checker.py`

## First Time Setup

When you run `update-pfc` or `python3 setup.py --update` for the first time after this update:

1. Setup detects missing batch checker config
2. Prompts: "Enable automated batch job checker?"
3. If yes:
   - Asks for check interval (default 30 minutes)
   - Saves to config.json
   - Creates cron job
   - Shows log path
4. If no:
   - Saves disabled config
   - Can enable later

**This prompt only appears once** - on first update after the batch checker feature was added.

## System Requirements

- **Linux/macOS**: Cron available by default
- **Windows**: Not supported (no cron), use Task Scheduler instead
- **Python 3.10+**: Required
- **Disk space**: Max 100MB for logs (with rotation)

## Benefits

1. **Save 50% on API costs** with batch processing
2. **No manual checking** - fully automated
3. **Submit before bed, ready in the morning**
4. **Automatic metadata and WebP** conversion
5. **Log rotation prevents disk issues**
6. **Survives restarts** - cron persists
