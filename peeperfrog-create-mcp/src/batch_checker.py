#!/usr/bin/env python3
"""
Batch Job Checker - Automatically checks and retrieves completed batch jobs.

This script is designed to be run by cron to periodically check pending
batch jobs and retrieve completed results automatically.

Usage:
    python3 batch_checker.py [--verbose]

Cron example (every 30 minutes):
    */30 * * * * /usr/bin/python3 /path/to/batch_checker.py >> /path/to/batch_checker.log 2>&1
"""

import sys
import os
import json
from datetime import datetime
from pathlib import Path

# Add src directory to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

# Import required modules
from image_server import CFG, DIRS, PROVIDERS, _convert_png_to_webp
from metadata import create_metadata_dict, write_metadata_file, copy_metadata_for_webp
from gemini_batch import check_batch_status, retrieve_batch_results


def log(message, level="INFO"):
    """Log message with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")


def load_tracking_data():
    """Load batch jobs tracking file."""
    tracking_file = os.path.join(DIRS["metadata_dir"], "batch_jobs_tracking.json")
    if not os.path.exists(tracking_file):
        return {}

    with open(tracking_file, 'r') as f:
        return json.load(f)


def save_tracking_data(tracking_data):
    """Save batch jobs tracking file."""
    tracking_file = os.path.join(DIRS["metadata_dir"], "batch_jobs_tracking.json")
    with open(tracking_file, 'w') as f:
        json.dump(tracking_data, f, indent=2)


def check_and_retrieve_batch_jobs(verbose=False):
    """Check all pending batch jobs and retrieve completed ones."""
    log("Starting batch job check...")

    tracking_data = load_tracking_data()

    if not tracking_data:
        log("No batch jobs to check")
        return

    # Filter pending jobs (not yet retrieved)
    pending_jobs = {
        job_id: job_info
        for job_id, job_info in tracking_data.items()
        if not job_info.get("retrieved", False)
    }

    if not pending_jobs:
        log("No pending batch jobs found")
        return

    log(f"Found {len(pending_jobs)} pending batch job(s)")

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        log("GEMINI_API_KEY not set - skipping batch check", "ERROR")
        return

    retrieved_count = 0
    failed_count = 0

    for batch_job_id, job_info in pending_jobs.items():
        try:
            if verbose:
                log(f"Checking batch job: {batch_job_id}")

            # Check status
            status_result = check_batch_status(batch_job_id, api_key)

            if not status_result.get("success"):
                log(f"Failed to check status for {batch_job_id}: {status_result.get('error')}", "WARNING")
                job_info["check_count"] = job_info.get("check_count", 0) + 1
                job_info["last_checked"] = datetime.now().isoformat()
                failed_count += 1
                continue

            job_status = status_result.get("status", "unknown")
            job_info["status"] = job_status
            job_info["check_count"] = job_info.get("check_count", 0) + 1
            job_info["last_checked"] = datetime.now().isoformat()

            if verbose:
                log(f"  Status: {job_status}")

            # If completed, retrieve results
            if job_status in ["completed", "done", "succeeded"]:
                log(f"Retrieving completed batch job: {batch_job_id}")

                # Load batch metadata
                batch_metadata_file = os.path.join(DIRS["metadata_dir"], "batch_metadata", f"{batch_job_id}.json")
                batch_metadata = None
                if os.path.exists(batch_metadata_file):
                    with open(batch_metadata_file, 'r') as f:
                        batch_metadata = json.load(f)

                # Retrieve results
                result = retrieve_batch_results(batch_job_id, api_key, DIRS["original_dir"])

                if not result.get("success"):
                    log(f"Failed to retrieve results for {batch_job_id}: {result.get('error')}", "ERROR")
                    failed_count += 1
                    continue

                # Process each image result
                images_processed = 0
                if batch_metadata:
                    for img_result in result.get("results", []):
                        if img_result.get("status") == "success":
                            image_path = img_result.get("image_path")

                            # Determine model name
                            provider = batch_metadata.get("provider", "gemini")
                            quality = batch_metadata.get("quality", "pro")
                            model = PROVIDERS.get(provider, {}).get("models", {}).get(quality, "unknown")

                            # Create metadata JSON
                            metadata = create_metadata_dict(
                                prompt=batch_metadata.get("prompt", ""),
                                title=batch_metadata.get("title", ""),
                                description=batch_metadata.get("description", ""),
                                alternative_text=batch_metadata.get("alternative_text", ""),
                                caption=batch_metadata.get("caption", ""),
                                provider=provider,
                                model=model,
                                aspect_ratio=batch_metadata.get("aspect_ratio", "1:1"),
                                image_size=batch_metadata.get("image_size", "large"),
                                quality=100,
                                cost=batch_metadata.get("cost", 0.0),
                                reference_images=batch_metadata.get("reference_image_paths")
                            )
                            metadata_path = write_metadata_file(image_path, metadata, json_dir=DIRS["json_dir"])

                            if verbose:
                                log(f"  Created metadata: {metadata_path}")

                            # Convert to WebP if requested
                            if batch_metadata.get("convert_to_webp", False):
                                webp_quality = batch_metadata.get("webp_quality", 85)
                                webp_path, webp_size = _convert_png_to_webp(image_path, webp_quality)
                                if webp_path:
                                    copy_metadata_for_webp(image_path, webp_path, webp_quality, json_dir=DIRS["json_dir"])
                                    if verbose:
                                        log(f"  Created WebP: {webp_path}")

                            images_processed += 1

                # Mark as retrieved
                job_info["retrieved"] = True
                job_info["completed_at"] = datetime.now().isoformat()

                log(f"Successfully retrieved and processed {images_processed} image(s) from batch job {batch_job_id}")
                retrieved_count += 1

            elif job_status == "failed":
                log(f"Batch job {batch_job_id} failed", "ERROR")
                job_info["retrieved"] = True  # Mark as done so we don't keep checking
                failed_count += 1

        except Exception as e:
            log(f"Error processing batch job {batch_job_id}: {str(e)}", "ERROR")
            failed_count += 1

    # Save updated tracking data
    save_tracking_data(tracking_data)

    log(f"Batch check complete: {retrieved_count} retrieved, {failed_count} failed/errors")


def main():
    """Main entry point."""
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    try:
        check_and_retrieve_batch_jobs(verbose=verbose)
    except Exception as e:
        log(f"Fatal error in batch checker: {str(e)}", "ERROR")
        sys.exit(1)


if __name__ == "__main__":
    main()
