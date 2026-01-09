#!/usr/bin/env python3
"""
Image optimization script using ShortPixel API.

Usage:
    python scripts/optimize_images.py              # Process unprocessed images
    python scripts/optimize_images.py --path content/posts/new-article/  # Specific path
    python scripts/optimize_images.py --force      # Force reprocess all
    python scripts/optimize_images.py --dry-run    # Preview without changes
"""

import argparse
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import requests

# API Configuration
SHORTPIXEL_API_KEY = os.environ.get("SHORTPIXEL_API_KEY", "")
SHORTPIXEL_API_URL = "https://api.shortpixel.com/v2/post-reducer.php"

# Target widths for responsive images (in pixels)
IMAGE_SIZES = [400, 800, 1200, 1600, 2400]

# Supported input formats
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif"}

# Output paths
OUTPUT_DIR = Path("static/img/optimized")

# Manifest for tracking processed files
MANIFEST_FILE = OUTPUT_DIR / ".manifest.json"

# Source directories
SOURCE_DIRS = [Path("content"), Path("assets/img")]


def log(message: str) -> None:
    """Print message with timestamp."""
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")


def get_file_hash(filepath: Path) -> str:
    """Calculate MD5 hash of a file."""
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def load_manifest() -> dict:
    """Load the manifest file tracking processed images."""
    if MANIFEST_FILE.exists():
        with open(MANIFEST_FILE, "r") as f:
            return json.load(f)
    return {"processed": {}}


def save_manifest(manifest: dict) -> None:
    """Save the manifest file."""
    MANIFEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_FILE, "w") as f:
        json.dump(manifest, f, indent=2)


def find_images(base_path: Optional[Path] = None) -> list[Path]:
    """Find all images in source directories."""
    images = []
    search_dirs = [base_path] if base_path else SOURCE_DIRS

    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for ext in SUPPORTED_EXTENSIONS:
            images.extend(search_dir.rglob(f"*{ext}"))
            images.extend(search_dir.rglob(f"*{ext.upper()}"))

    return sorted(set(images))


def get_output_path(source_path: Path, width: int, fmt: str) -> Path:
    """Generate output path for optimized image."""
    # Convert source path to output path
    # content/posts/my-post/image.jpg -> posts/my-post/image-800w.webp
    rel_path = source_path
    for prefix in ["content/", "assets/img/", "assets/"]:
        if str(source_path).startswith(prefix):
            rel_path = Path(str(source_path)[len(prefix) :])
            break

    stem = rel_path.stem
    parent = rel_path.parent

    if fmt == "original":
        ext = source_path.suffix.lower()
    else:
        ext = f".{fmt}"

    return OUTPUT_DIR / parent / f"{stem}-{width}w{ext}"


def needs_processing(source_path: Path, manifest: dict, force: bool) -> bool:
    """Check if an image needs to be processed."""
    if force:
        return True

    str_path = str(source_path)
    if str_path not in manifest["processed"]:
        return True

    current_hash = get_file_hash(source_path)
    return manifest["processed"][str_path]["hash"] != current_hash


def optimize_image(source_path: Path, dry_run: bool = False) -> dict:
    """
    Optimize a single image using ShortPixel API.

    Returns dict with processing results.
    """
    results = {"source": str(source_path), "outputs": [], "errors": []}

    if dry_run:
        for width in IMAGE_SIZES:
            for fmt in ["original", "webp", "avif"]:
                output_path = get_output_path(source_path, width, fmt)
                results["outputs"].append(str(output_path))
        return results

    # Process all sizes in parallel
    with ThreadPoolExecutor(max_workers=len(IMAGE_SIZES)) as executor:
        futures = {
            executor.submit(process_single_size, source_path, width): width
            for width in IMAGE_SIZES
        }

        for future in as_completed(futures):
            width = futures[future]
            try:
                output_files = future.result()
                results["outputs"].extend(output_files)
            except Exception as e:
                results["errors"].append(f"Width {width}: {str(e)}")

    return results


def process_single_size(source_path: Path, width: int) -> list[str]:
    """Process image at a specific width, returning list of output paths."""
    output_files = []

    with open(source_path, "rb") as f:
        file_content = f.read()

    file_key = f"file1"
    file_paths = {file_key: str(source_path)}

    # API request with resize and format conversion
    response = requests.post(
        SHORTPIXEL_API_URL,
        files={file_key: (source_path.name, file_content, "application/octet-stream")},
        data={
            "key": SHORTPIXEL_API_KEY,
            "plugin_version": "HUGO1",
            "lossy": 2,  # Glossy compression
            "wait": 30,
            "resize": 3,  # Inner resize (fit within dimensions)
            "resize_width": width,
            "resize_height": 100000,  # Large value to constrain by width only
            "convertto": "+webp|+avif",
            "file_paths": json.dumps(file_paths),
        },
    )

    if response.status_code != 200:
        raise Exception(f"API error: {response.status_code}")

    result = response.json()
    if not result or len(result) == 0:
        raise Exception("Empty API response")

    item = result[0]
    status_code = int(item.get("Status", {}).get("Code", -1))

    # Handle pending status (Code 1) - image still processing
    if status_code == 1:
        # Wait and retry with OriginalURL
        time.sleep(5)
        return retry_optimization(source_path, item.get("OriginalURL", ""), width)

    if status_code != 2:
        msg = item.get("Status", {}).get("Message", "Unknown error")
        raise Exception(f"API error: {msg}")

    # Download and save optimized images
    output_files.extend(download_optimized_images(source_path, item, width))

    return output_files


def retry_optimization(
    source_path: Path, original_url: str, width: int, max_retries: int = 10
) -> list[str]:
    """Retry getting optimization results for pending image with exponential backoff."""
    base_delay = 1.0
    max_delay = 60.0

    for attempt in range(max_retries):
        delay = min(base_delay * (2**attempt), max_delay)

        response = requests.post(
            SHORTPIXEL_API_URL,
            data={
                "key": SHORTPIXEL_API_KEY,
                "plugin_version": "HUGO1",
                "lossy": 1,
                "wait": 30,
                "resize": 3,
                "resize_width": width,
                "resize_height": 9999,
                "convertto": "+webp|+avif",
                "file_urls": json.dumps([original_url]),
            },
        )

        if response.status_code != 200:
            time.sleep(delay)
            continue

        result = response.json()
        if not result:
            time.sleep(delay)
            continue

        item = result[0]
        status_code = int(item.get("Status", {}).get("Code", -1))

        if status_code == 2:
            return download_optimized_images(source_path, item, width)
        elif status_code == 1:
            time.sleep(delay)
            continue
        else:
            msg = item.get("Status", {}).get("Message", "Unknown error")
            raise Exception(f"API error after retry: {msg}")

    raise Exception(f"Timeout waiting for optimization after {max_retries} retries")


def download_optimized_images(source_path: Path, api_result: dict, width: int) -> list[str]:
    """Download optimized images from API result."""
    output_files = []

    # Format-to-URL mapping from API response
    format_urls = {
        "original": api_result.get("LossyURL"),
        "webp": api_result.get("WebPLossyURL"),
        "avif": api_result.get("AVIFLossyURL"),
    }

    for fmt, url in format_urls.items():
        if not url or url == "NA":
            continue

        output_path = get_output_path(source_path, width, fmt)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Download the file
        img_response = requests.get(url)
        if img_response.status_code == 200:
            with open(output_path, "wb") as f:
                f.write(img_response.content)
            output_files.append(str(output_path))
            log(f"  ✓ {output_path}")
        else:
            log(f"  ✗ Failed to download {fmt} for width {width}")

    return output_files


def process_images(
    path: Optional[Path] = None, force: bool = False, dry_run: bool = False
) -> None:
    """Main function to process images."""
    manifest = load_manifest()
    images = find_images(path)

    # Filter images needing processing
    to_process = [img for img in images if needs_processing(img, manifest, force)]

    if not to_process:
        log("No images need processing.")
        return

    log(f"Found {len(to_process)} images to process")
    if dry_run:
        log("[DRY RUN] Would process:")

    processed_count = 0
    error_count = 0

    for i, img_path in enumerate(to_process, 1):
        log(f"[{i}/{len(to_process)}] {img_path}")

        try:
            result = optimize_image(img_path, dry_run)

            if dry_run:
                for output in result["outputs"]:
                    log(f"  → {output}")
            else:
                if result["errors"]:
                    for err in result["errors"]:
                        log(f"  ✗ {err}")
                    error_count += 1
                else:
                    # Update manifest on success
                    manifest["processed"][str(img_path)] = {
                        "hash": get_file_hash(img_path),
                        "outputs": result["outputs"],
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                    save_manifest(manifest)
                    processed_count += 1

        except Exception as e:
            log(f"  ✗ Error: {e}")
            error_count += 1

        # Rate limiting between API calls
        if not dry_run:
            time.sleep(1)

    log(f"{'[DRY RUN] ' if dry_run else ''}Summary:")
    log(f"  Processed: {processed_count}")
    log(f"  Errors: {error_count}")
    log(f"  Skipped: {len(images) - len(to_process)}")


def main():
    parser = argparse.ArgumentParser(
        description="Optimize images using ShortPixel API"
    )
    parser.add_argument(
        "--path",
        type=Path,
        help="Specific path to process (default: all source directories)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force reprocessing of all images",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without making changes",
    )

    args = parser.parse_args()

    if not SHORTPIXEL_API_KEY and not args.dry_run:
        log("Error: SHORTPIXEL_API_KEY environment variable is not set")
        log("Set it with: export SHORTPIXEL_API_KEY='your-api-key'")
        sys.exit(1)

    process_images(path=args.path, force=args.force, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
