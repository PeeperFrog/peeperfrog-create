"""
Gemini Batch API integration for cost-effective image generation.

This module provides functions to submit batch jobs to Gemini's Batch API
(50% discount vs immediate API), check status, and retrieve results.
"""

import requests
import json
import os
import base64
from datetime import datetime


def submit_batch_job(requests_list, api_key, model=None):
    """
    Submit batch job to Gemini Batch API for 50% cost savings.

    Args:
        requests_list: List of dicts with generation parameters:
            {
                "prompt": str,
                "aspect_ratio": str,
                "image_size": str,
                "quality": str,
                "reference_images": list,
                "gemini_opts": dict (optional),
                "filename": str (optional, for tracking)
            }
        api_key: GEMINI_API_KEY
        model: Model to use (defaults based on quality)

    Returns:
        {
            "success": True,
            "batch_job_id": "...",
            "request_count": 5,
            "estimated_completion_time": "24 hours",
            "status": "pending"
        }

    Note: Gemini Batch API uses :batchGenerateContent endpoint
    """
    # Build batch request payload
    batch_requests = []

    for idx, req in enumerate(requests_list):
        # Determine model based on quality
        quality = req.get("quality", "fast")
        if not model:
            # Match the model selection from batch_generate.py
            models = {
                "pro": "gemini-3-flash-thinking-image-2",
                "fast": "gemini-2.5-flash-image-exp"
            }
            req_model = models.get(quality, models["fast"])
        else:
            req_model = model

        # Build parts with reference images + prompt
        parts = []
        if req.get("reference_images"):
            for ref_img in req["reference_images"]:
                if isinstance(ref_img, str):
                    # Base64 encoded image
                    parts.append({
                        "inlineData": {
                            "mimeType": "image/png",
                            "data": ref_img
                        }
                    })
        parts.append({"text": req["prompt"]})

        # Build image config
        size_map = {"small": "1K", "medium": "2K", "large": "2K", "xlarge": "4K"}
        gemini_size = size_map.get(req.get("image_size", "large"), "2K")

        image_config = {"aspectRatio": req.get("aspect_ratio", "16:9")}
        if quality == "pro":
            image_config["imageSize"] = gemini_size

        # Build generation config
        generation_config = {
            "responseModalities": ["TEXT", "IMAGE"],
            "imageConfig": image_config
        }

        # Add optional gemini settings
        gemini_opts = req.get("gemini_opts", {})
        if gemini_opts.get("media_resolution"):
            generation_config["mediaResolution"] = f"MEDIA_RESOLUTION_{gemini_opts['media_resolution'].upper()}"
        if gemini_opts.get("thinking_level") and quality == "pro":
            generation_config["thinkingConfig"] = {"thinkingLevel": gemini_opts["thinking_level"].lower()}

        # Build request
        request_payload = {
            "contents": [{"parts": parts}],
            "generationConfig": generation_config
        }

        if gemini_opts.get("search_grounding"):
            request_payload["tools"] = [{"google_search": {}}]

        # Add to batch with request ID
        batch_requests.append({
            "request_id": req.get("filename", f"req_{idx}"),
            "request": request_payload
        })

    # Submit batch job
    # Note: Using inline requests format (for <20MB batches)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{req_model}:batchGenerateContent?key={api_key}"

    batch_payload = {
        "requests": batch_requests
    }

    try:
        response = requests.post(
            url,
            json=batch_payload,
            headers={'Content-Type': 'application/json'}
        )

        if response.status_code not in [200, 201]:
            return {
                "success": False,
                "error": f"Batch API error: {response.status_code} - {response.text}"
            }

        # Parse response
        data = response.json()

        # Gemini Batch API might return job ID or immediate results depending on batch size
        # For now, assume it returns a job tracking structure
        batch_job_id = data.get("name", data.get("batch_job_id", f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"))

        return {
            "success": True,
            "batch_job_id": batch_job_id,
            "request_count": len(requests_list),
            "estimated_completion_time": "24 hours",
            "status": data.get("status", "pending"),
            "raw_response": data  # Store for debugging
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def check_batch_status(batch_job_id, api_key):
    """
    Check status of submitted batch job.

    Args:
        batch_job_id: Job ID returned from submit_batch_job()
        api_key: GEMINI_API_KEY

    Returns:
        {
            "batch_job_id": "...",
            "status": "pending|processing|completed|failed",
            "progress": "3/5 completed",
            "results": [...] if completed, else None
        }
    """
    # Construct status check URL
    # Note: Actual Gemini Batch API endpoint may differ
    url = f"https://generativelanguage.googleapis.com/v1beta/jobs/{batch_job_id}?key={api_key}"

    try:
        response = requests.get(url, headers={'Content-Type': 'application/json'})

        if response.status_code == 404:
            return {
                "success": False,
                "batch_job_id": batch_job_id,
                "error": "Batch job not found"
            }

        if response.status_code != 200:
            return {
                "success": False,
                "batch_job_id": batch_job_id,
                "error": f"Status check error: {response.status_code} - {response.text}"
            }

        data = response.json()
        status = data.get("state", data.get("status", "unknown"))

        # Calculate progress if available
        total = data.get("totalTasks", data.get("request_count", 0))
        completed = data.get("completedTasks", 0)
        progress = f"{completed}/{total} completed" if total > 0 else "unknown"

        result = {
            "success": True,
            "batch_job_id": batch_job_id,
            "status": status.lower(),
            "progress": progress
        }

        # Include results if completed
        if status.lower() in ["completed", "done", "succeeded"]:
            result["results"] = data.get("results", [])

        return result

    except Exception as e:
        return {
            "success": False,
            "batch_job_id": batch_job_id,
            "error": str(e)
        }


def retrieve_batch_results(batch_job_id, api_key, save_directory):
    """
    Retrieve completed batch results and save images to disk.

    Args:
        batch_job_id: Job ID returned from submit_batch_job()
        api_key: GEMINI_API_KEY
        save_directory: Directory to save images (e.g., original/ folder)

    Returns:
        {
            "success": True,
            "images_saved": 5,
            "results": [
                {
                    "request_id": "img_1",
                    "status": "success",
                    "image_path": "/path/to/original/image.png",
                    "filename": "image.png"
                }
            ]
        }
    """
    # First check if job is complete
    status_result = check_batch_status(batch_job_id, api_key)

    if not status_result.get("success"):
        return status_result

    if status_result["status"] not in ["completed", "done", "succeeded"]:
        return {
            "success": False,
            "batch_job_id": batch_job_id,
            "error": f"Batch job not completed yet. Status: {status_result['status']}"
        }

    # Get results
    results = status_result.get("results", [])
    if not results:
        # Try fetching results directly
        url = f"https://generativelanguage.googleapis.com/v1beta/jobs/{batch_job_id}/results?key={api_key}"
        try:
            response = requests.get(url, headers={'Content-Type': 'application/json'})
            if response.status_code == 200:
                results = response.json().get("results", [])
        except Exception as e:
            return {
                "success": False,
                "batch_job_id": batch_job_id,
                "error": f"Failed to fetch results: {str(e)}"
            }

    if not results:
        return {
            "success": False,
            "batch_job_id": batch_job_id,
            "error": "No results available"
        }

    # Process and save results
    saved_results = []
    os.makedirs(save_directory, exist_ok=True)

    for result in results:
        request_id = result.get("request_id", "unknown")

        try:
            # Extract image data from response
            response_data = result.get("response", {})
            image_data = None

            # Navigate through Gemini response structure
            for candidate in response_data.get("candidates", []):
                for part in candidate.get("content", {}).get("parts", []):
                    if "inlineData" in part:
                        image_data = part["inlineData"]["data"]
                        break
                if image_data:
                    break

            if not image_data:
                saved_results.append({
                    "request_id": request_id,
                    "status": "failed",
                    "error": "No image data in response"
                })
                continue

            # Decode and save image
            filename = f"{request_id}.png" if not request_id.endswith(".png") else request_id
            image_path = os.path.join(save_directory, filename)

            with open(image_path, 'wb') as f:
                f.write(base64.b64decode(image_data))

            saved_results.append({
                "request_id": request_id,
                "status": "success",
                "image_path": image_path,
                "filename": filename
            })

        except Exception as e:
            saved_results.append({
                "request_id": request_id,
                "status": "failed",
                "error": str(e)
            })

    successful_saves = sum(1 for r in saved_results if r["status"] == "success")

    return {
        "success": True,
        "batch_job_id": batch_job_id,
        "images_saved": successful_saves,
        "results": saved_results
    }
