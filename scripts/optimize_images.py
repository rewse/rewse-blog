#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
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
from concurrent.futures import Executor, Future, ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import shutil
import signal
import tempfile
import time
import traceback
from typing import Literal, Protocol, TypedDict, cast

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
# Worker processes exit after this many images, which returns memory leaked
# by native encoders to the system.
TASKS_PER_WORKER = 10
PNG_COMPRESSION = 9

# Increment when a change alters generated pixels so cached outputs are rebuilt.
PROCESSING_VERSION = 1
# Version assumed for manifest entries written before versions were recorded.
LEGACY_PROCESSING_VERSION = 1

OutputFormat = Literal["original", "avif"]
OUTPUT_FORMATS: tuple[OutputFormat, ...] = ("original", "avif")


class ManifestEntry(TypedDict):
    """Metadata for one processed source image."""

    hash: str
    outputs: list[str]
    timestamp: str
    version: int


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


class StopSignal(Protocol):
    """Cancellation flag shared by the parent and its workers."""

    def is_set(self) -> bool: ...

    def set(self) -> None: ...


def log(message: str) -> None:
    """Print a timestamped message immediately, even when stdout is a pipe."""
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


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


def _parse_manifest_entry(source: str, raw_entry: object) -> ManifestEntry:
    """Validate one manifest entry for a normalized source path."""
    entry_data = _as_object_dict(raw_entry, f"entry for {source!r}")
    file_hash = entry_data.get("hash")
    raw_outputs = entry_data.get("outputs")
    timestamp = entry_data.get("timestamp", "")
    version = entry_data.get("version", LEGACY_PROCESSING_VERSION)

    if not isinstance(file_hash, str):
        raise ValueError(f"Manifest hash for {source!r} must be a string")
    if not isinstance(raw_outputs, list) or not raw_outputs:
        raise ValueError(f"Manifest outputs for {source!r} must be a non-empty array")
    output_values = cast(list[object], raw_outputs)
    if not all(isinstance(output, str) for output in output_values):
        raise ValueError(f"Manifest outputs for {source!r} must contain only strings")
    outputs = [output for output in output_values if isinstance(output, str)]
    for output in outputs:
        _ = resolve_output_path(Path(output))
    if not isinstance(timestamp, str):
        raise ValueError(f"Manifest timestamp for {source!r} must be a string")
    if not isinstance(version, int) or isinstance(version, bool):
        raise ValueError(f"Manifest version for {source!r} must be an integer")

    return {
        "hash": file_hash,
        "outputs": outputs,
        "timestamp": timestamp,
        "version": version,
    }


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
        processed[source] = _parse_manifest_entry(source, raw_entry)

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


def _has_supported_extension(path: Path) -> bool:
    """Return whether path has a supported image extension."""
    return path.suffix.lower() in SUPPORTED_EXTENSIONS


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
            if _has_supported_extension(search_dir):
                images.add(normalize_source_path(search_dir))
            continue
        if not search_dir.exists():
            continue
        images.update(
            normalize_source_path(path)
            for path in search_dir.rglob("*")
            if path.is_file() and _has_supported_extension(path)
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
    if entry["version"] != PROCESSING_VERSION:
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


def _discard_result(result: OptimizationResult) -> None:
    """Drop every staged and planned output of an uncommitted result."""
    discard_staged_outputs(result)
    result.outputs.clear()


def _fail(result: OptimizationResult, message: str) -> None:
    """Record an error and drop the result's outputs."""
    result.errors.append(message)
    _discard_result(result)


def _raise_if_cancelled(stop_event: StopSignal | None) -> None:
    """Abort optimization when another task has requested a stop."""
    if stop_event is not None and stop_event.is_set():
        raise RuntimeError("Optimization cancelled")


def _planned_outputs(source: Path, source_hash: str) -> list[Path]:
    """Return every output path for a source, ordered by width then format."""
    return [
        get_output_path(source, width, output_format, source_hash)
        for width in IMAGE_SIZES
        for output_format in OUTPUT_FORMATS
    ]


def _create_snapshot(
    result: OptimizationResult,
    temporary_directory: Path,
) -> Path | None:
    """Copy the source aside and verify it still matches the recorded hash."""
    snapshot_path = temporary_directory / f"source{result.source.suffix.lower()}"
    try:
        _ = shutil.copyfile(_repository_path(result.source), snapshot_path)
        snapshot_hash = _hash_file(snapshot_path)
        if (
            result.source_hash != snapshot_hash
            or get_file_hash(result.source) != snapshot_hash
        ):
            _fail(result, f"Source changed while creating snapshot: {result.source}")
            return None
    except OSError as error:
        _fail(result, f"Failed to create source snapshot: {error}")
        return None
    return snapshot_path


def _to_srgb(image: pyvips.Image) -> pyvips.Image:
    """Convert an image with an embedded ICC profile to sRGB.

    Saving strips the profile, so browsers read the pixels as sRGB. Leaving
    wide-gamut pixels unconverted would shift their colors.
    """
    if "icc-profile-data" not in image.get_fields():
        return image
    return image.icc_transform("srgb", embedded=True, intent="relative")


def _save_variant(
    image: pyvips.Image,
    path: Path,
    output_format: OutputFormat,
    is_png: bool,
) -> None:
    """Encode one resized image in the requested output format."""
    if output_format == "avif":
        image.heifsave(str(path), Q=AVIF_QUALITY, compression="av1", strip=True)
    elif is_png:
        image.pngsave(str(path), compression=PNG_COMPRESSION, strip=True)
    else:
        image.jpegsave(str(path), Q=JPEG_QUALITY, strip=True)


def optimize_image(
    source_path: Path,
    dry_run: bool = False,
    stop_event: StopSignal | None = None,
    staging_root: Path | None = None,
) -> OptimizationResult:
    """Optimize one image without replacing currently published outputs.

    Staged files go into a new directory under staging_root, which defaults
    to the output directory.
    """
    source = normalize_source_path(source_path)
    source_hash = get_file_hash(source)
    result = OptimizationResult(source=source, source_hash=source_hash)

    if dry_run:
        result.outputs.extend(_planned_outputs(source, source_hash))
        return result

    if staging_root is None:
        staging_root = _repository_path(OUTPUT_DIR)
    staging_root.mkdir(parents=True, exist_ok=True)
    temporary_directory = Path(tempfile.mkdtemp(prefix=".image-", dir=staging_root))
    result.temporary_directory = temporary_directory
    snapshot_path = _create_snapshot(result, temporary_directory)
    if snapshot_path is None:
        return result

    current_width: int | None = None
    try:
        image = _to_srgb(VIPS_IMAGE_CLASS.new_from_file(str(snapshot_path)))
        original_width = image.width
        is_png = source.suffix.lower() == ".png"
        for width in IMAGE_SIZES:
            current_width = width
            _raise_if_cancelled(stop_event)
            resized = (
                image if width > original_width else image.resize(width / original_width)
            )

            for output_format in OUTPUT_FORMATS:
                _raise_if_cancelled(stop_event)
                output_path = get_output_path(source, width, output_format, source_hash)
                staged_path = temporary_directory / output_path.relative_to(OUTPUT_DIR)
                staged_path.parent.mkdir(parents=True, exist_ok=True)
                _save_variant(resized, staged_path, output_format, is_png)
                result.outputs.append(output_path)
                result.staged_outputs.append(staged_path)

        _raise_if_cancelled(stop_event)
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
        _discard_result(result)
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


def _ensure_source_unchanged(result: OptimizationResult) -> None:
    """Raise SourceChangedError when the source no longer matches the result."""
    if get_file_hash(result.source) != result.source_hash:
        raise SourceChangedError


def _publish_staged_outputs(
    result: OptimizationResult,
    backup_directory: Path,
    published: list[tuple[Path, Path | None]],
) -> None:
    """Move staged files into place, recording each move before making it."""
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


def _rollback_commit(
    result: OptimizationResult,
    manifest: Manifest,
    old_entry: ManifestEntry | None,
    published: list[tuple[Path, Path | None]],
    manifest_saved: bool,
) -> None:
    """Restore the manifest entry and published files from before a commit."""
    source_key = str(result.source)
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
    _discard_result(result)


def commit_result(result: OptimizationResult, manifest: Manifest) -> bool:
    """Publish a complete result and roll back every partial update on failure."""
    if result.errors or result.temporary_directory is None:
        return False
    if get_file_hash(result.source) != result.source_hash:
        _fail(result, f"Source changed before commit: {result.source}")
        return False

    source_key = str(result.source)
    old_entry = manifest["processed"].get(source_key)
    old_outputs = [] if old_entry is None else old_entry["outputs"].copy()
    published: list[tuple[Path, Path | None]] = []
    manifest_saved = False
    try:
        _publish_staged_outputs(
            result,
            result.temporary_directory / ".backups",
            published,
        )
        _ensure_source_unchanged(result)

        manifest["processed"][source_key] = {
            "hash": result.source_hash,
            "outputs": [str(output) for output in result.outputs],
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "version": PROCESSING_VERSION,
        }
        save_manifest(manifest)
        manifest_saved = True
        _ensure_source_unchanged(result)

    except BaseException as error:
        _rollback_commit(result, manifest, old_entry, published, manifest_saved)
        if isinstance(error, SourceChangedError):
            result.errors.append(f"Source changed during commit: {result.source}")
            return False
        raise

    discard_staged_outputs(result)
    remove_old_outputs(old_outputs, result.outputs)
    return True


_worker_stop_event: StopSignal | None = None
_worker_staging_root: Path | None = None


def _init_worker(stop_event: StopSignal, staging_root: Path) -> None:
    """Prepare a worker process; the parent alone handles SIGINT."""
    global _worker_stop_event, _worker_staging_root
    _ = signal.signal(signal.SIGINT, signal.SIG_IGN)
    _worker_stop_event = stop_event
    _worker_staging_root = staging_root


def _optimize_in_worker(source: Path) -> OptimizationResult:
    """Optimize one image with the state stored by _init_worker."""
    return optimize_image(source, False, _worker_stop_event, _worker_staging_root)


def _cancel_pending(futures: Sequence[Future[OptimizationResult]]) -> None:
    """Cancel tasks that have not started."""
    for future in futures:
        _ = future.cancel()


def _shutdown_executor(executor: Executor, stop_event: StopSignal) -> bool:
    """Wait for every worker to stop and report whether an interrupt arrived.

    Interrupts during the wait are absorbed so workers can discard their own
    staged files; the stop event makes them finish at the next checkpoint.
    """
    interrupted = False
    while True:
        try:
            executor.shutdown(wait=True, cancel_futures=True)
        except KeyboardInterrupt:
            interrupted = True
            stop_event.set()
        else:
            return interrupted


def _run_optimizations(
    images: Sequence[Path],
    staging_root: Path,
) -> tuple[list[OptimizationResult], bool]:
    """Optimize images in parallel and report whether the run was interrupted.

    Each finished image is logged so long runs keep producing output; CI
    runners may kill a build that stays silent for too long. Every completed
    result is returned, including ones finished after an interrupt, so the
    caller can discard their staged files.
    """
    # libvips runs its own threads, so forking a process that has used it is
    # unsafe.
    context = multiprocessing.get_context("spawn")
    stop_event = context.Event()
    results: list[OptimizationResult] = []
    collected: set[Future[OptimizationResult]] = set()
    future_to_path: dict[Future[OptimizationResult], Path] = {}
    interrupted = False
    executor = ProcessPoolExecutor(
        max_workers=MAX_WORKERS,
        mp_context=context,
        max_tasks_per_child=TASKS_PER_WORKER,
        initializer=_init_worker,
        initargs=(stop_event, staging_root),
    )
    try:
        for image in images:
            future_to_path[executor.submit(_optimize_in_worker, image)] = image
        for future in as_completed(future_to_path):
            collected.add(future)
            image_path = future_to_path[future]
            try:
                result = future.result()
            except Exception as error:
                result = OptimizationResult(source=image_path)
                result.errors.append(str(error))
            results.append(result)
            log(f"Finished {len(results)}/{len(images)}: {result.source}")
            if result.fatal:
                stop_event.set()
                _cancel_pending(tuple(future_to_path))
    except KeyboardInterrupt:
        interrupted = True
        stop_event.set()
        log("Interrupted. Waiting for running tasks to stop...")
    finally:
        if _shutdown_executor(executor, stop_event):
            interrupted = True

    for future in future_to_path:
        if future in collected or future.cancelled() or future.exception():
            continue
        results.append(future.result())
    return results, interrupted


def _create_run_staging() -> Path:
    """Create the directory that holds every staged file of one run."""
    output_root = _repository_path(OUTPUT_DIR)
    output_root.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=".run-", dir=output_root))


def _discard_all(results: Sequence[OptimizationResult]) -> None:
    """Remove staged outputs for every result."""
    for result in results:
        discard_staged_outputs(result)


def _log_failure(result: OptimizationResult) -> None:
    """Log a failed source and each of its errors."""
    log(f"✗ {result.source}")
    for error in result.errors:
        log(f"  {error}")


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

    staging_root = _create_run_staging()
    try:
        results, interrupted = _run_optimizations(to_process, staging_root)
        if interrupted:
            _discard_all(results)
            log("Interrupted. Cancelled remaining tasks.")
            return 1

        if any(result.fatal for result in results):
            _discard_all(results)
            for result in results:
                if result.errors:
                    _log_failure(result)
            log("FATAL: AVIF encoder not available. Stopped all image updates.")
            return 1

        error_count = 0
        processed_count = 0
        for result in results:
            if result.errors or not commit_result(result, manifest):
                _log_failure(result)
                error_count += 1
                continue
            log(f"✓ {result.source} ({len(result.outputs)} files)")
            processed_count += 1
    finally:
        # Removing the run directory also clears files staged by workers that
        # died before returning a result.
        shutil.rmtree(staging_root, ignore_errors=True)

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
