#!/usr/bin/env python3
"""
Image optimization script using pyvips for local processing.

Usage:
    python scripts/optimize_images.py              # Process unprocessed images
    python scripts/optimize_images.py --path content/posts/new-article/  # Specific path
    python scripts/optimize_images.py --force      # Force reprocess all
    python scripts/optimize_images.py --dry-run    # Preview without changes
"""

import argparse
import hashlib
import json
import time
import pyvips
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

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

# Compression quality settings
JPEG_QUALITY = 85
PNG_COMPRESSION = 9
WEBP_QUALITY = 85
AVIF_QUALITY = 65

# Parallel processing (Recommend: # of logical CPU / 3)
MAX_WORKERS = 4


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
    rel_path = source_path
    for prefix in ["content/", "assets/img/", "assets/"]:
        if str(source_path).startswith(prefix):
            rel_path = Path(str(source_path)[len(prefix):])
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
    Optimize a single image using pyvips.

    Returns dict with processing results.
    """
    results = {"source": str(source_path), "outputs": [], "errors": []}

    if dry_run:
        for width in IMAGE_SIZES:
            for fmt in ["original", "webp", "avif"]:
                output_path = get_output_path(source_path, width, fmt)
                results["outputs"].append(str(output_path))
        return results

    try:
        # Load image into memory to avoid sequential access issues
        image = pyvips.Image.new_from_file(str(source_path))
        original_width = image.width

        for width in IMAGE_SIZES:
            try:
                # Skip resize if target width is larger than original
                if width > original_width:
                    resized = image
                else:
                    scale = width / original_width
                    resized = image.resize(scale)

                # Determine original format
                source_ext = source_path.suffix.lower()
                is_png = source_ext == ".png"

                # Save in each format
                for fmt in ["original", "webp", "avif"]:
                    output_path = get_output_path(source_path, width, fmt)
                    output_path.parent.mkdir(parents=True, exist_ok=True)

                    if fmt == "original":
                        if is_png:
                            resized.pngsave(str(output_path), compression=PNG_COMPRESSION, strip=True)
                        else:
                            resized.jpegsave(str(output_path), Q=JPEG_QUALITY, strip=True)
                    elif fmt == "webp":
                        resized.webpsave(str(output_path), Q=WEBP_QUALITY, strip=True)
                    elif fmt == "avif":
                        resized.heifsave(str(output_path), Q=AVIF_QUALITY, compression="av1", strip=True)

                    results["outputs"].append(str(output_path))

            except Exception as e:
                import traceback
                results["errors"].append(f"Width {width}: {str(e)}\n{traceback.format_exc()}")

    except Exception as e:
        import traceback
        results["errors"].append(f"Load error: {str(e)}\n{traceback.format_exc()}")

    return results


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

    log(f"Found {len(to_process)} images to process (workers: {MAX_WORKERS})")
    if dry_run:
        log("[DRY RUN] Would process:")
        for img_path in to_process:
            result = optimize_image(img_path, dry_run)
            log(f"  {img_path}")
            for output in result["outputs"]:
                log(f"    → {output}")
        return

    processed_count = 0
    error_count = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_path = {
            executor.submit(optimize_image, img_path, False): img_path
            for img_path in to_process
        }

        try:
            for future in as_completed(future_to_path):
                img_path = future_to_path[future]
                try:
                    result = future.result()

                    if result["errors"]:
                        log(f"✗ {img_path}")
                        for err in result["errors"]:
                            log(f"  {err}")
                        error_count += 1
                    else:
                        log(f"✓ {img_path} ({len(result['outputs'])} files)")
                        manifest["processed"][str(img_path)] = {
                            "hash": get_file_hash(img_path),
                            "outputs": result["outputs"],
                            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                        }
                        save_manifest(manifest)
                        processed_count += 1

                except Exception as e:
                    log(f"✗ {img_path}: {e}")
                    error_count += 1
        except KeyboardInterrupt:
            log("Interrupted. Cancelling remaining tasks...")
            executor.shutdown(wait=False, cancel_futures=True)
            return

    log(f"Summary:")
    log(f"  Processed: {processed_count}")
    log(f"  Errors: {error_count}")
    log(f"  Skipped: {len(images) - len(to_process)}")


def main():
    parser = argparse.ArgumentParser(
        description="Optimize images using pyvips"
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

    process_images(path=args.path, force=args.force, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
