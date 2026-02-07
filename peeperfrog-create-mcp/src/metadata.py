"""
Metadata management for generated images.

This module handles creation, reading, and updating of JSON sidecar files
that store metadata for generated images.
"""

import os
import json
from datetime import datetime


def create_metadata_dict(
    prompt,
    title,
    description,
    alternative_text,
    caption,
    provider,
    model,
    aspect_ratio,
    image_size,
    quality=100,
    cost=0.0
):
    """
    Build metadata dictionary for JSON sidecar file.

    Args:
        prompt: Generation prompt
        title: Image title
        description: Detailed description
        alternative_text: Alt text for accessibility
        caption: Brief caption
        provider: Provider name (gemini, openai, etc)
        model: Model name
        aspect_ratio: Aspect ratio (e.g., "16:9")
        image_size: Image size (small, medium, large)
        quality: Image quality (0-100)
        cost: Generation cost in USD

    Returns:
        Dictionary with complete metadata
    """
    return {
        "date_time_created": datetime.now().isoformat(),
        "prompt": prompt,
        "title": title,
        "description": description,
        "alternative_text": alternative_text,
        "caption": caption,
        "provider": provider,
        "model": model,
        "aspect_ratio": aspect_ratio,
        "image_size": image_size,
        "quality": quality,
        "cost": cost
    }


def write_metadata_file(image_path, metadata_dict):
    """
    Write JSON sidecar file for image.

    Args:
        image_path: Full path to image file (e.g., /path/to/original/image.png)
        metadata_dict: Dictionary from create_metadata_dict()

    Returns:
        Path to created JSON file

    Creates: /path/to/metadata/json/image.png.json
    """
    # Get the base directory (parent of original/ or webp/)
    image_dir = os.path.dirname(image_path)
    base_dir = os.path.dirname(image_dir)

    json_dir = os.path.join(base_dir, "metadata", "json")
    os.makedirs(json_dir, exist_ok=True)

    basename = os.path.basename(image_path)
    json_path = os.path.join(json_dir, f"{basename}.json")

    with open(json_path, 'w') as f:
        json.dump(metadata_dict, f, indent=2)

    return json_path


def read_metadata_file(image_path):
    """
    Read JSON sidecar file for image.

    Args:
        image_path: Path to image file

    Returns:
        Metadata dict or None if not found
    """
    # Get the base directory (parent of original/ or webp/)
    image_dir = os.path.dirname(image_path)
    base_dir = os.path.dirname(image_dir)

    json_dir = os.path.join(base_dir, "metadata", "json")
    basename = os.path.basename(image_path)
    json_path = os.path.join(json_dir, f"{basename}.json")

    if not os.path.exists(json_path):
        return None

    with open(json_path, 'r') as f:
        return json.load(f)


def copy_metadata_for_webp(original_image_path, webp_image_path, webp_quality):
    """
    Copy metadata from original PNG to WebP, updating date_time_created and quality.

    Args:
        original_image_path: Path to original PNG
        webp_image_path: Path to converted WebP
        webp_quality: WebP quality setting (0-100)

    Returns:
        Path to created WebP metadata JSON file, or None if original metadata not found
    """
    # Read original metadata
    metadata = read_metadata_file(original_image_path)
    if not metadata:
        return None

    # Update for WebP
    metadata["date_time_created"] = datetime.now().isoformat()
    metadata["quality"] = webp_quality

    # Write WebP metadata
    return write_metadata_file(webp_image_path, metadata)


def update_wordpress_info(image_path, media_id, media_url):
    """
    Add WordPress upload info to existing metadata JSON.

    Args:
        image_path: Path to image file
        media_id: WordPress media ID
        media_url: WordPress media URL

    Returns:
        True if successful, False if metadata file not found
    """
    metadata = read_metadata_file(image_path)
    if not metadata:
        return False

    metadata["wordpress_media_id"] = media_id
    metadata["wordpress_url"] = media_url
    metadata["wordpress_uploaded_at"] = datetime.now().isoformat()

    write_metadata_file(image_path, metadata)
    return True
