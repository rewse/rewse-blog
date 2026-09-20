#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pyvips==3.2.0",
# ]
# ///
"""Optimize source images for responsive delivery.

Usage:
    uv run scripts/optimize_images.py
    uv run scripts/optimize_images.py --path content/posts/new-article/
    uv run scripts/optimize_images.py --force
    uv run scripts/optimize_images.py --dry-run
"""

import argparse
from collections.abc import Sequence
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from threading import Event
import time
import traceback
from typing import Literal, TypedDict, cast

import pyvips

VIPS_IMAGE_CLASS = pyvips.Image
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
IMAGE_SIZES = (400, 800, 1200, 1600, 2400)
SUPPORTED_EXTENSIONS = frozenset({".jpeg", ".jpg", ".png"})
OUTPUT_DIR = Path("static/img/optimized")
MANIFEST_FILE = OUTPUT_DIR / ".manifest.json"
SOURCE_DIRS = (Path("content"), Path("assets/img"))

AVIF_QUALITY = 65
JPEG_QUALITY = 85
MAX_WORKERS = 3
PNG_COMPRESSION = 9

OutputFormat = Literal["original", "avif"]
OUTPUT_FORMATS: tuple[OutputFormat, ...] = ("original", "avif")


class ManifestEntry(TypedDict):
    """Metadata for one processed source image."""

    hash: str
    outputs: list[str]
    timestamp: str


class Manifest(TypedDict):
    """Persistent state for processed source images."""

    processed: dict[str, ManifestEntry]


@dataclass
class OptimizationResult:
    """Result of optimizing one source image."""

    source: Path
    source_hash: str = ""
    errors: list[str] = field(default_factory=list)
    fatal: bool = False
    outputs: list[Path] = field(default_factory=list)
    staged_outputs: list[Path] = field(default_factory=list, repr=False)
    temporary_directory: Path | None = field(default=None, repr=False)


class Arguments(argparse.Namespace):
    """Typed command-line arguments."""

    dry_run: bool = False
    force: bool = False
    path: Path | None = None


class SourceChangedError(RuntimeError):
    """Signal that a source changed while its outputs were being published."""


def log(message: str) -> None:
    """Print a timestamped message."""
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")


def _repository_path(path: Path) -> Path:
    """Resolve a repository-relative path without requiring it to exist."""
    return path.resolve() if path.is_absolute() else (REPOSITORY_ROOT / path).resolve()


def _is_within(path: Path, directory: Path) -> bool:
    """Return whether path is inside directory after resolution."""
    try:
        _ = path.relative_to(directory)
    except ValueError:
        return False
    return True


def normalize_source_path(source_path: Path) -> Path:
    """Return a repository-relative source path inside an allowed source root."""
    absolute_path = _repository_path(source_path)
    allowed_roots = tuple(_repository_path(root) for root in SOURCE_DIRS)
    if not any(_is_within(absolute_path, root) for root in allowed_roots):
        raise ValueError(f"Source path must be inside source directories: {source_path}")
    return absolute_path.relative_to(REPOSITORY_ROOT.resolve())


def resolve_output_path(output_path: Path) -> Path:
    """Resolve and validate a path inside the generated output directory."""
    if output_path.is_absolute():
        raise ValueError(f"Path must be inside the output directory: {output_path}")
    absolute_path = _repository_path(output_path)
    output_root = _repository_path(OUTPUT_DIR)
    if not _is_within(absolute_path, output_root):
        raise ValueError(f"Path must be inside the output directory: {output_path}")
    return absolute_path


def _hash_file(filepath: Path) -> str:
    """Calculate an MD5 content hash for an arbitrary file."""
    hasher = hashlib.md5()
    with filepath.open("rb") as file_object:
        for chunk in iter(lambda: file_object.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def get_file_hash(filepath: Path) -> str:
    """Calculate the content hash used in generated filenames."""
    source_path = _repository_path(normalize_source_path(filepath))
    return _hash_file(source_path)


def _as_object_dict(value: object, context: str) -> dict[object, object]:
    """Return a JSON object with a useful validation error."""
    if not isinstance(value, dict):
        raise ValueError(f"Manifest {context} must be an object")
    return cast(dict[object, object], value)


def parse_manifest(data: object) -> Manifest:
    """Validate and normalize data loaded from the manifest file."""
    root = _as_object_dict(data, "root")
    processed_data = _as_object_dict(root.get("processed"), "processed")
    processed: dict[str, ManifestEntry] = {}

    for source, raw_entry in processed_data.items():
        if not isinstance(source, str):
            raise ValueError("Manifest processed keys must be strings")
        normalized_source = normalize_source_path(Path(source))
        if str(normalized_source) != source:
            raise ValueError(f"Manifest source path is not normalized: {source!r}")

        entry_data = _as_object_dict(raw_entry, f"entry for {source!r}")
        file_hash = entry_data.get("hash")
        raw_outputs = entry_data.get("outputs")
        timestamp = entry_data.get("timestamp", "")

        if not isinstance(file_hash, str):
            raise ValueError(f"Manifest hash for {source!r} must be a string")
        if not isinstance(raw_outputs, list) or not raw_outputs:
            raise ValueError(
                f"Manifest outputs for {source!r} must be a non-empty array"
            )
        output_values = cast(list[object], raw_outputs)
        if not all(isinstance(output, str) for output in output_values):
            raise ValueError(
                f"Manifest outputs for {source!r} must contain only strings"
            )
        outputs = [output for output in output_values if isinstance(output, str)]
        for output in outputs:
            _ = resolve_output_path(Path(output))
        if not isinstance(timestamp, str):
            raise ValueError(f"Manifest timestamp for {source!r} must be a string")

        processed[source] = {
            "hash": file_hash,
            "outputs": outputs,
            "timestamp": timestamp,
        }

    return {"processed": processed}


def load_manifest() -> Manifest:
    """Load and validate the manifest that tracks processed images."""
    manifest_path = _repository_path(MANIFEST_FILE)
    if not manifest_path.exists():
        log(f"No manifest found at {MANIFEST_FILE}, starting fresh")
        return {"processed": {}}

    log(f"Found existing manifest: {MANIFEST_FILE}")
    with manifest_path.open("r", encoding="utf-8") as file_object:
        raw_manifest = cast(object, json.load(file_object))
    manifest = parse_manifest(raw_manifest)
    log(f"Loaded {len(manifest['processed'])} processed images from manifest")
    return manifest


def save_manifest(manifest: Manifest) -> None:
    """Atomically save the manifest through a unique temporary file."""
    manifest_path = _repository_path(MANIFEST_FILE)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=manifest_path.parent,
            prefix=f".{manifest_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as file_object:
            temporary_path = Path(file_object.name)
            json.dump(manifest, file_object, indent=2)
            _ = file_object.write("\n")
            file_object.flush()
            os.fsync(file_object.fileno())
        os.replace(temporary_path, manifest_path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def find_images(base_path: Path | None = None) -> list[Path]:
    """Find supported images and return normalized repository-relative paths."""
    if base_path is None:
        search_dirs = tuple(_repository_path(path) for path in SOURCE_DIRS)
    else:
        normalized_base = normalize_source_path(base_path)
        search_dirs = (_repository_path(normalized_base),)

    images: set[Path] = set()
    for search_dir in search_dirs:
        if search_dir.is_file():
            if search_dir.suffix.lower() in SUPPORTED_EXTENSIONS:
                images.add(normalize_source_path(search_dir))
            continue
        if not search_dir.exists():
            continue
        images.update(
            normalize_source_path(path)
            for path in search_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
        )
    return sorted(images)


def get_output_path(
    source_path: Path,
    width: int,
    output_format: OutputFormat,
    file_hash: str,
) -> Path:
    """Generate an output path that matches the Hugo template convention."""
    normalized_source = normalize_source_path(source_path)
    if normalized_source.parts[:2] == ("assets", "img"):
        relative_path = Path(*normalized_source.parts[2:])
    else:
        relative_path = Path(*normalized_source.parts[1:])

    extension = (
        normalized_source.suffix.lower()
        if output_format == "original"
        else f".{output_format}"
    )
    hash_short = file_hash[:8]
    filename = f"{relative_path.stem}-{width}w-{hash_short}{extension}"
    output_path = OUTPUT_DIR / relative_path.parent / filename
    _ = resolve_output_path(output_path)
    return output_path


def needs_processing(source_path: Path, manifest: Manifest, force: bool) -> bool:
    """Return whether a source image needs to be processed."""
    normalized_source = normalize_source_path(source_path)
    if force:
        return True

    entry = manifest["processed"].get(str(normalized_source))
    if entry is None or entry["hash"] != get_file_hash(normalized_source):
        return True
    for output_path in entry["outputs"]:
        if not resolve_output_path(Path(output_path)).exists():
            log(f"Output file missing: {output_path}")
            return True
    return False


def discard_staged_outputs(result: OptimizationResult) -> None:
    """Remove temporary output files for an uncommitted result."""
    if result.temporary_directory is not None:
        shutil.rmtree(result.temporary_directory, ignore_errors=True)
        result.temporary_directory = None
    result.staged_outputs.clear()


def optimize_image(
    source_path: Path,
    dry_run: bool = False,
    stop_event: Event | None = None,
) -> OptimizationResult:
    """Optimize one image without replacing currently published outputs."""
    source = normalize_source_path(source_path)
    source_hash = get_file_hash(source)
    result = OptimizationResult(source=source, source_hash=source_hash)

    if dry_run:
        for width in IMAGE_SIZES:
            for output_format in OUTPUT_FORMATS:
                result.outputs.append(
                    get_output_path(source, width, output_format, source_hash)
                )
        return result

    output_root = _repository_path(OUTPUT_DIR)
    output_root.mkdir(parents=True, exist_ok=True)
    result.temporary_directory = Path(
        tempfile.mkdtemp(prefix=".image-", dir=output_root)
    )
    snapshot_path = result.temporary_directory / f"source{source.suffix.lower()}"
    try:
        _ = shutil.copyfile(_repository_path(source), snapshot_path)
        snapshot_hash = _hash_file(snapshot_path)
        if source_hash != snapshot_hash or get_file_hash(source) != snapshot_hash:
            result.errors.append(f"Source changed while creating snapshot: {source}")
            discard_staged_outputs(result)
            return result
    except OSError as error:
        result.errors.append(f"Failed to create source snapshot: {error}")
        discard_staged_outputs(result)
        return result
    source_hash = snapshot_hash
    result.source_hash = snapshot_hash

    current_width: int | None = None
    try:
        image = VIPS_IMAGE_CLASS.new_from_file(str(snapshot_path))
        original_width = image.width
        for width in IMAGE_SIZES:
            current_width = width
            if stop_event is not None and stop_event.is_set():
                raise RuntimeError("Optimization cancelled")
            resized = (
                image if width > original_width else image.resize(width / original_width)
            )
            is_png = source.suffix.lower() == ".png"

            for output_format in OUTPUT_FORMATS:
                if stop_event is not None and stop_event.is_set():
                    raise RuntimeError("Optimization cancelled")
                output_path = get_output_path(
                    source,
                    width,
                    output_format,
                    source_hash,
                )
                staged_path = result.temporary_directory / output_path.relative_to(
                    OUTPUT_DIR
                )
                staged_path.parent.mkdir(parents=True, exist_ok=True)

                if output_format == "original" and is_png:
                    image_to_save = resized
                    image_to_save.pngsave(
                        str(staged_path),
                        compression=PNG_COMPRESSION,
                        strip=True,
                    )
                elif output_format == "original":
                    resized.jpegsave(
                        str(staged_path),
                        Q=JPEG_QUALITY,
                        strip=True,
                    )
                else:
                    resized.heifsave(
                        str(staged_path),
                        Q=AVIF_QUALITY,
                        compression="av1",
                        strip=True,
                    )
                result.outputs.append(output_path)
                result.staged_outputs.append(staged_path)

        if stop_event is not None and stop_event.is_set():
            raise RuntimeError("Optimization cancelled")
        if get_file_hash(source) != source_hash:
            result.errors.append(f"Source changed during optimization: {source}")

    except Exception as error:
        context = "Load error" if current_width is None else f"Width {current_width}"
        result.errors.append(f"{context}: {error}\n{traceback.format_exc()}")
        if "Unsupported compression" in str(error):
            result.fatal = True
            if stop_event is not None:
                stop_event.set()

    if result.errors:
        discard_staged_outputs(result)
        result.outputs.clear()
    return result


def remove_old_outputs(old_outputs: list[str], current_outputs: list[Path]) -> None:
    """Remove obsolete generated files after a new manifest entry is committed."""
    current = {str(path) for path in current_outputs}
    for output in old_outputs:
        if output in current:
            continue
        old_path = resolve_output_path(Path(output))
        if not old_path.exists():
            continue
        try:
            old_path.unlink()
            log(f"  Removed old file: {output}")
        except OSError as error:
            log(f"  Failed to remove {output}: {error}")


def commit_result(result: OptimizationResult, manifest: Manifest) -> bool:
    """Publish a complete result and roll back every partial update on failure."""
    if result.errors or result.temporary_directory is None:
        return False
    if get_file_hash(result.source) != result.source_hash:
        result.errors.append(f"Source changed before commit: {result.source}")
        discard_staged_outputs(result)
        result.outputs.clear()
        return False

    source_key = str(result.source)
    old_entry = manifest["processed"].get(source_key)
    old_outputs = [] if old_entry is None else old_entry["outputs"].copy()
    published: list[tuple[Path, Path | None]] = []
    manifest_saved = False
    try:
        backup_directory = result.temporary_directory / ".backups"
        for index, (staged_path, output_path) in enumerate(
            zip(result.staged_outputs, result.outputs, strict=True)
        ):
            final_path = resolve_output_path(output_path)
            final_path.parent.mkdir(parents=True, exist_ok=True)
            backup_path: Path | None = None
            if final_path.exists():
                backup_directory.mkdir(parents=True, exist_ok=True)
                backup_path = backup_directory / str(index)
            published.append((final_path, backup_path))
            if backup_path is not None:
                _ = final_path.replace(backup_path)
            _ = staged_path.replace(final_path)

        if get_file_hash(result.source) != result.source_hash:
            raise SourceChangedError

        manifest["processed"][source_key] = {
            "hash": result.source_hash,
            "outputs": [str(output) for output in result.outputs],
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        save_manifest(manifest)
        manifest_saved = True
        if get_file_hash(result.source) != result.source_hash:
            raise SourceChangedError

    except BaseException as error:
        if old_entry is None:
            _ = manifest["processed"].pop(source_key, None)
        else:
            manifest["processed"][source_key] = old_entry

        for final_path, backup_path in reversed(published):
            if backup_path is None:
                final_path.unlink(missing_ok=True)
            elif backup_path.exists():
                final_path.unlink(missing_ok=True)
                _ = backup_path.replace(final_path)

        if manifest_saved:
            save_manifest(manifest)
        discard_staged_outputs(result)
        result.outputs.clear()
        if isinstance(error, SourceChangedError):
            result.errors.append(f"Source changed during commit: {result.source}")
            return False
        raise

    discard_staged_outputs(result)
    remove_old_outputs(old_outputs, result.outputs)
    return True


def _cancel_pending(futures: Sequence[Future[OptimizationResult]]) -> None:
    """Cancel tasks that have not started."""
    for future in futures:
        _ = future.cancel()


def process_images(
    path: Path | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> int:
    """Process images and return a process exit code."""
    manifest = load_manifest()
    images = find_images(path)
    to_process = [
        image for image in images if needs_processing(image, manifest, force)
    ]

    if not to_process:
        log("No images need processing.")
        return 0

    log(f"Found {len(to_process)} images to process (workers: {MAX_WORKERS})")
    if dry_run:
        log("[DRY RUN] Would process:")
        for image_path in to_process:
            result = optimize_image(image_path, dry_run=True)
            log(f"  {image_path}")
            for output_path in result.outputs:
                log(f"    → {output_path}")
        return 0

    stop_event = Event()
    results: list[OptimizationResult] = []
    interrupted = False
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_path = {
            executor.submit(optimize_image, image, False, stop_event): image
            for image in to_process
        }
        try:
            for future in as_completed(future_to_path):
                image_path = future_to_path[future]
                try:
                    result = future.result()
                except Exception as error:
                    result = OptimizationResult(source=image_path)
                    result.errors.append(str(error))
                results.append(result)
                if result.fatal:
                    stop_event.set()
                    _cancel_pending(tuple(future_to_path))
        except KeyboardInterrupt:
            interrupted = True
            stop_event.set()
            _cancel_pending(tuple(future_to_path))

    if interrupted:
        for result in results:
            discard_staged_outputs(result)
        log("Interrupted. Cancelled remaining tasks.")
        return 1

    if any(result.fatal for result in results):
        for result in results:
            discard_staged_outputs(result)
            if result.errors:
                log(f"✗ {result.source}")
                for error in result.errors:
                    log(f"  {error}")
        log("FATAL: AVIF encoder not available. Stopped all image updates.")
        return 1

    error_count = 0
    processed_count = 0
    for result in results:
        if result.errors or not commit_result(result, manifest):
            log(f"✗ {result.source}")
            for error in result.errors:
                log(f"  {error}")
            error_count += 1
            continue
        log(f"✓ {result.source} ({len(result.outputs)} files)")
        processed_count += 1

    log("Summary:")
    log(f"  Processed: {processed_count}")
    log(f"  Errors: {error_count}")
    log(f"  Skipped: {len(images) - len(to_process)}")
    return 1 if error_count else 0


def parse_arguments(argv: Sequence[str] | None = None) -> Arguments:
    """Parse typed command-line arguments."""
    parser = argparse.ArgumentParser(description="Optimize images using pyvips")
    _ = parser.add_argument(
        "--path",
        type=Path,
        help="Specific path to process (default: all source directories)",
    )
    _ = parser.add_argument(
        "--force",
        action="store_true",
        help="Force reprocessing of all images",
    )
    _ = parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without making changes",
    )
    arguments = Arguments()
    _ = parser.parse_args(argv, namespace=arguments)
    return arguments


def main(argv: Sequence[str] | None = None) -> int:
    """Run the image optimizer CLI."""
    arguments = parse_arguments(argv)
    try:
        return process_images(
            path=arguments.path,
            force=arguments.force,
            dry_run=arguments.dry_run,
        )
    except ValueError as error:
        log(f"ERROR: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
