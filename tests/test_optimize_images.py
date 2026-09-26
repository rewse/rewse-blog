"""Tests for the image optimization script."""

import json
import signal
import tempfile
import unittest
from concurrent.futures import Future
from pathlib import Path
from threading import Event
from typing import TYPE_CHECKING, Protocol, cast
from unittest import mock

from scripts import optimize_images

if TYPE_CHECKING:
    import pyvips


class Writable(Protocol):
    def write(self, value: str) -> int: ...


class ManifestTest(unittest.TestCase):
    def test_parse_manifest_accepts_valid_data(self) -> None:
        data: object = {
            "processed": {
                "content/posts/example/image.jpg": {
                    "hash": "abc123",
                    "outputs": ["static/img/optimized/example-400w-abc123.jpg"],
                    "timestamp": "2026-09-20 17:00:00",
                }
            }
        }

        manifest = optimize_images.parse_manifest(data)

        self.assertEqual(
            manifest["processed"]["content/posts/example/image.jpg"]["hash"],
            "abc123",
        )

    def test_parse_manifest_treats_missing_version_as_legacy(self) -> None:
        data: object = {
            "processed": {
                "content/posts/example/image.jpg": {
                    "hash": "abc123",
                    "outputs": ["static/img/optimized/example-400w-abc123.jpg"],
                    "timestamp": "2026-09-20 17:00:00",
                }
            }
        }

        manifest = optimize_images.parse_manifest(data)

        self.assertEqual(
            manifest["processed"]["content/posts/example/image.jpg"]["version"],
            optimize_images.LEGACY_PROCESSING_VERSION,
        )

    def test_parse_manifest_rejects_non_integer_version(self) -> None:
        data: object = {
            "processed": {
                "content/posts/example/image.jpg": {
                    "hash": "abc123",
                    "outputs": ["static/img/optimized/example-400w-abc123.jpg"],
                    "timestamp": "2026-09-20 17:00:00",
                    "version": True,
                }
            }
        }

        with self.assertRaisesRegex(ValueError, "version"):
            _ = optimize_images.parse_manifest(data)

    def test_parse_manifest_rejects_invalid_processed_value(self) -> None:
        with self.assertRaisesRegex(ValueError, "processed"):
            _ = optimize_images.parse_manifest({"processed": []})

    def test_save_manifest_preserves_existing_file_when_write_fails(self) -> None:
        manifest: optimize_images.Manifest = {"processed": {}}
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / ".manifest.json"
            _ = manifest_path.write_text('{"processed": {}}\n', encoding="utf-8")

            def fail_dump(
                _value: object,
                file_object: object,
                **_kwargs: object,
            ) -> None:
                if not hasattr(file_object, "write"):
                    self.fail("json.dump did not receive a writable file")
                writer = cast(Writable, file_object)
                _ = writer.write("{")
                raise OSError("simulated write failure")

            with (
                mock.patch.object(optimize_images, "MANIFEST_FILE", manifest_path),
                mock.patch.object(json, "dump", side_effect=fail_dump),
                self.assertRaisesRegex(OSError, "simulated write failure"),
            ):
                optimize_images.save_manifest(manifest)

            self.assertEqual(
                manifest_path.read_text(encoding="utf-8"),
                '{"processed": {}}\n',
            )
            self.assertFalse(manifest_path.with_suffix(".tmp").exists())


class ImageDiscoveryTest(unittest.TestCase):
    def test_find_images_supports_jpeg_and_png_but_not_gif(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository_root = Path(temp_dir)
            root = repository_root / "content"
            root.mkdir()
            expected = {
                Path("content/first.JPG"),
                Path("content/second.jpeg"),
                Path("content/third.png"),
            }
            for path in (
                root / "first.JPG",
                root / "second.jpeg",
                root / "third.png",
                root / "animated.gif",
                root / "ignored.webp",
            ):
                path.touch()

            with mock.patch.object(
                optimize_images,
                "REPOSITORY_ROOT",
                repository_root,
            ):
                images = optimize_images.find_images(root)

            self.assertEqual(set(images), expected)


class OptimizationResultTest(unittest.TestCase):
    def test_dry_run_returns_typed_output_paths(self) -> None:
        source = Path("content/posts/example/photo.jpg")
        with mock.patch.object(
            optimize_images,
            "get_file_hash",
            return_value="1234567890abcdef",
        ):
            result = optimize_images.optimize_image(source, dry_run=True)

        self.assertEqual(result.source, source)
        self.assertFalse(result.errors)
        self.assertFalse(result.fatal)
        self.assertEqual(len(result.outputs), len(optimize_images.IMAGE_SIZES) * 2)
        self.assertEqual(
            result.outputs[0],
            Path("static/img/optimized/posts/example/photo-400w-12345678.jpg"),
        )


class ProcessingDecisionTest(unittest.TestCase):
    def test_matching_manifest_entry_with_existing_outputs_is_current(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository_root = Path(temp_dir)
            output = Path("static/img/optimized/output.jpg")
            output_path = repository_root / output
            output_path.parent.mkdir(parents=True)
            output_path.touch()
            source = Path("content/posts/example/photo.jpg")
            manifest: optimize_images.Manifest = {
                "processed": {
                    str(source): {
                        "hash": "abc123",
                        "outputs": [str(output)],
                        "timestamp": "2026-09-20 17:00:00",
                        "version": optimize_images.PROCESSING_VERSION,
                    }
                }
            }

            with (
                mock.patch.object(
                    optimize_images,
                    "REPOSITORY_ROOT",
                    repository_root,
                ),
                mock.patch.object(
                    optimize_images,
                    "get_file_hash",
                    return_value="abc123",
                ),
            ):
                needs_processing = optimize_images.needs_processing(
                    source,
                    manifest,
                    force=False,
                )

            self.assertFalse(needs_processing)


    def test_entry_with_older_processing_version_needs_processing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository_root = Path(temp_dir)
            output = Path("static/img/optimized/output.jpg")
            output_path = repository_root / output
            output_path.parent.mkdir(parents=True)
            output_path.touch()
            source = Path("content/posts/example/photo.jpg")
            manifest: optimize_images.Manifest = {
                "processed": {
                    str(source): {
                        "hash": "abc123",
                        "outputs": [str(output)],
                        "timestamp": "2026-09-20 17:00:00",
                        "version": optimize_images.PROCESSING_VERSION - 1,
                    }
                }
            }

            with (
                mock.patch.object(
                    optimize_images,
                    "REPOSITORY_ROOT",
                    repository_root,
                ),
                mock.patch.object(
                    optimize_images,
                    "get_file_hash",
                    return_value="abc123",
                ),
            ):
                needs_processing = optimize_images.needs_processing(
                    source,
                    manifest,
                    force=False,
                )

            self.assertTrue(needs_processing)


class InterruptingExecutor:
    """Executor fake that completes tasks inline and interrupts shutdown."""

    def __init__(self, shutdown_interrupts: int) -> None:
        self.shutdown_interrupts: int = shutdown_interrupts
        self.shutdown_calls: int = 0
        self.stop_events: list[Event] = []

    def submit(
        self,
        _function: object,
        source: Path,
        _dry_run: bool,
        stop_event: Event,
    ) -> "Future[optimize_images.OptimizationResult]":
        self.stop_events.append(stop_event)
        future: Future[optimize_images.OptimizationResult] = Future()
        future.set_result(optimize_images.OptimizationResult(source=source))
        return future

    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        del wait, cancel_futures
        self.shutdown_calls += 1
        if self.shutdown_calls <= self.shutdown_interrupts:
            raise KeyboardInterrupt


class ProgressLoggingTest(unittest.TestCase):
    def test_each_finished_image_is_logged_with_progress(self) -> None:
        images = [
            Path("content/posts/example/first.jpg"),
            Path("content/posts/example/second.jpg"),
        ]

        def fake_optimize(
            source: Path,
            _dry_run: bool,
            _stop_event: object,
        ) -> optimize_images.OptimizationResult:
            return optimize_images.OptimizationResult(source=source)

        with (
            mock.patch.object(
                optimize_images,
                "optimize_image",
                side_effect=fake_optimize,
            ),
            mock.patch.object(optimize_images, "log") as log,
        ):
            results, interrupted = optimize_images._run_optimizations(images)

        self.assertFalse(interrupted)
        self.assertEqual(len(results), 2)
        messages = [call.args[0] for call in log.call_args_list]
        self.assertEqual(
            sorted(message.split(":")[0] for message in messages),
            ["Finished 1/2", "Finished 2/2"],
        )
        self.assertEqual(
            {message.split(": ", 1)[1] for message in messages},
            {str(image) for image in images},
        )

    def test_repeated_interrupt_waits_for_workers_and_keeps_results(self) -> None:
        images = [
            Path("content/posts/example/first.jpg"),
            Path("content/posts/example/second.jpg"),
        ]
        executor = InterruptingExecutor(shutdown_interrupts=1)

        with (
            mock.patch.object(
                optimize_images,
                "ThreadPoolExecutor",
                return_value=executor,
            ),
            mock.patch.object(
                optimize_images,
                "as_completed",
                side_effect=KeyboardInterrupt,
            ),
            mock.patch.object(optimize_images, "log"),
        ):
            results, interrupted = optimize_images._run_optimizations(images)

        self.assertTrue(interrupted)
        self.assertEqual(executor.shutdown_calls, 2)
        self.assertTrue(all(event.is_set() for event in executor.stop_events))
        self.assertEqual(
            {result.source for result in results},
            set(images),
        )

    def test_interrupt_during_shutdown_is_reported(self) -> None:
        images = [Path("content/posts/example/first.jpg")]
        executor = InterruptingExecutor(shutdown_interrupts=1)

        with (
            mock.patch.object(
                optimize_images,
                "ThreadPoolExecutor",
                return_value=executor,
            ),
            mock.patch.object(optimize_images, "log"),
        ):
            results, interrupted = optimize_images._run_optimizations(images)

        self.assertTrue(interrupted)
        self.assertEqual(len(results), 1)

    def test_log_flushes_output(self) -> None:
        with mock.patch("builtins.print") as print_mock:
            optimize_images.log("message")

        self.assertTrue(print_mock.call_args.kwargs.get("flush"))


class ColorSpaceTest(unittest.TestCase):
    def test_image_with_icc_profile_is_converted_to_srgb(self) -> None:
        converted = FakeImage()
        image = FakeImage(icc_profile=True, converted=converted)

        result = optimize_images._to_srgb(cast("pyvips.Image", image))

        self.assertIs(result, converted)
        self.assertEqual(
            image.icc_transform_calls,
            [("srgb", {"embedded": True, "intent": "relative"})],
        )

    def test_image_without_icc_profile_is_unchanged(self) -> None:
        image = FakeImage()

        result = optimize_images._to_srgb(cast("pyvips.Image", image))

        self.assertIs(result, image)
        self.assertFalse(image.icc_transform_calls)


class WorkerTest(unittest.TestCase):
    def test_init_worker_ignores_sigint_and_stores_state(self) -> None:
        stop_event = Event()
        staging_root = Path("/tmp/staging")

        with (
            mock.patch.object(optimize_images, "_worker_stop_event", None),
            mock.patch.object(optimize_images, "_worker_staging_root", None),
            mock.patch.object(optimize_images.signal, "signal") as signal_mock,
        ):
            optimize_images._init_worker(stop_event, staging_root)

            self.assertIs(optimize_images._worker_stop_event, stop_event)
            self.assertEqual(optimize_images._worker_staging_root, staging_root)

        signal_mock.assert_called_once_with(signal.SIGINT, signal.SIG_IGN)

    def test_optimize_in_worker_passes_stored_state(self) -> None:
        stop_event = Event()
        staging_root = Path("/tmp/staging")
        source = Path("content/posts/example/photo.jpg")
        expected = optimize_images.OptimizationResult(source=source)

        with (
            mock.patch.object(optimize_images, "_worker_stop_event", stop_event),
            mock.patch.object(
                optimize_images,
                "_worker_staging_root",
                staging_root,
            ),
            mock.patch.object(
                optimize_images,
                "optimize_image",
                return_value=expected,
            ) as optimize,
        ):
            result = optimize_images._optimize_in_worker(source)

        self.assertIs(result, expected)
        optimize.assert_called_once_with(source, False, stop_event, staging_root)

    def test_optimize_image_stages_inside_given_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository_root = Path(temp_dir)
            source = Path("content/posts/example/photo.jpg")
            source_path = repository_root / source
            source_path.parent.mkdir(parents=True)
            _ = source_path.write_text("source", encoding="utf-8")
            staging_root = repository_root / "static/img/optimized/.run-test"

            with (
                mock.patch.object(
                    optimize_images,
                    "REPOSITORY_ROOT",
                    repository_root,
                ),
                mock.patch.object(optimize_images, "IMAGE_SIZES", (400,)),
                mock.patch.object(
                    optimize_images,
                    "get_file_hash",
                    return_value="abc123456789",
                ),
                mock.patch.object(
                    optimize_images,
                    "_hash_file",
                    return_value="abc123456789",
                ),
                mock.patch.object(
                    optimize_images.VIPS_IMAGE_CLASS,
                    "new_from_file",
                    return_value=FakeImage(),
                ),
            ):
                result = optimize_images.optimize_image(
                    source,
                    staging_root=staging_root,
                )

            self.assertFalse(result.errors)
            temporary_directory = result.temporary_directory
            assert temporary_directory is not None
            self.assertEqual(temporary_directory.parent, staging_root)
            self.assertEqual(len(result.staged_outputs), 2)
            self.assertTrue(
                all(path.is_relative_to(staging_root) for path in result.staged_outputs)
            )
            optimize_images.discard_staged_outputs(result)


class ArgumentsTest(unittest.TestCase):
    def test_parse_arguments_returns_typed_values(self) -> None:
        arguments = optimize_images.parse_arguments(
            ["--path", "content/posts/example", "--force", "--dry-run"]
        )

        self.assertEqual(arguments.path, Path("content/posts/example"))
        self.assertTrue(arguments.force)
        self.assertTrue(arguments.dry_run)


class FakeImage:
    width: int = 1000

    def __init__(
        self,
        fail_heif: bool = False,
        icc_profile: bool = False,
        converted: "FakeImage | None" = None,
    ) -> None:
        self.fail_heif: bool = fail_heif
        self.icc_profile: bool = icc_profile
        self.converted: FakeImage | None = converted
        self.icc_transform_calls: list[tuple[str, dict[str, object]]] = []

    def get_fields(self) -> list[str]:
        return ["icc-profile-data"] if self.icc_profile else []

    def icc_transform(self, output_profile: str, **options: object) -> "FakeImage":
        self.icc_transform_calls.append((output_profile, options))
        return self if self.converted is None else self.converted

    def resize(self, _scale: float) -> "FakeImage":
        return self

    def jpegsave(self, filename: str, **_options: object) -> None:
        _ = Path(filename).write_text("new image", encoding="utf-8")

    def pngsave(self, filename: str, **_options: object) -> None:
        _ = Path(filename).write_text("new image", encoding="utf-8")

    def heifsave(self, filename: str, **_options: object) -> None:
        if self.fail_heif:
            raise RuntimeError("simulated encoder failure")
        _ = Path(filename).write_text("new image", encoding="utf-8")


class PathSafetyTest(unittest.TestCase):
    def test_parse_manifest_rejects_output_outside_output_directory(self) -> None:
        data: object = {
            "processed": {
                "content/posts/example/image.jpg": {
                    "hash": "abc123",
                    "outputs": ["/tmp/unrelated-file"],
                    "timestamp": "2026-09-20 17:00:00",
                }
            }
        }

        with self.assertRaisesRegex(ValueError, "output directory"):
            _ = optimize_images.parse_manifest(data)

    def test_get_output_path_rejects_source_outside_source_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "photo.jpg"

            with self.assertRaisesRegex(ValueError, "source directories"):
                _ = optimize_images.get_output_path(
                    source,
                    400,
                    "original",
                    "abc123",
                )


class FailureSafetyTest(unittest.TestCase):
    def test_generation_failure_preserves_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository_root = Path(temp_dir)
            source = Path("content/posts/example/photo.jpg")
            source_path = repository_root / source
            source_path.parent.mkdir(parents=True)
            _ = source_path.write_text("source", encoding="utf-8")
            output_path = (
                repository_root
                / "static/img/optimized/posts/example/photo-400w-abc12345.jpg"
            )
            output_path.parent.mkdir(parents=True)
            _ = output_path.write_text("old image", encoding="utf-8")
            fake_image = FakeImage(fail_heif=True)

            with (
                mock.patch.object(
                    optimize_images,
                    "REPOSITORY_ROOT",
                    repository_root,
                ),
                mock.patch.object(optimize_images, "IMAGE_SIZES", (400,)),
                mock.patch.object(
                    optimize_images,
                    "get_file_hash",
                    return_value="abc123456789",
                ),
                mock.patch.object(
                    optimize_images,
                    "_hash_file",
                    return_value="abc123456789",
                ),
                mock.patch.object(
                    optimize_images.VIPS_IMAGE_CLASS,
                    "new_from_file",
                    return_value=fake_image,
                ),
            ):
                result = optimize_images.optimize_image(source)

            self.assertTrue(result.errors)
            self.assertEqual(output_path.read_text(encoding="utf-8"), "old image")

    def test_source_change_discards_generated_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository_root = Path(temp_dir)
            source = Path("content/posts/example/photo.jpg")
            source_path = repository_root / source
            source_path.parent.mkdir(parents=True)
            _ = source_path.write_text("source", encoding="utf-8")

            with (
                mock.patch.object(
                    optimize_images,
                    "REPOSITORY_ROOT",
                    repository_root,
                ),
                mock.patch.object(optimize_images, "IMAGE_SIZES", (400,)),
                mock.patch.object(
                    optimize_images,
                    "get_file_hash",
                    side_effect=("before123", "before123", "after456"),
                ),
                mock.patch.object(
                    optimize_images,
                    "_hash_file",
                    return_value="before123",
                ),
                mock.patch.object(
                    optimize_images.VIPS_IMAGE_CLASS,
                    "new_from_file",
                    return_value=FakeImage(),
                ),
            ):
                result = optimize_images.optimize_image(source)

            self.assertTrue(
                any("changed during optimization" in error for error in result.errors)
            )
            self.assertFalse(result.outputs)


    def test_commit_failure_restores_existing_output_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository_root = Path(temp_dir)
            source = Path("content/posts/example/photo.jpg")
            output = Path("static/img/optimized/posts/example/photo-400w-hash.jpg")
            final_path = repository_root / output
            final_path.parent.mkdir(parents=True)
            _ = final_path.write_text("old image", encoding="utf-8")
            staging_directory = repository_root / "static/img/optimized/.staging"
            staged_path = staging_directory / "output.jpg"
            staged_path.parent.mkdir(parents=True)
            _ = staged_path.write_text("new image", encoding="utf-8")
            old_entry: optimize_images.ManifestEntry = {
                "hash": "old-hash",
                "outputs": [str(output)],
                "timestamp": "2026-09-20 17:00:00",

                "version": optimize_images.PROCESSING_VERSION,
            }
            manifest: optimize_images.Manifest = {
                "processed": {str(source): old_entry.copy()}
            }
            result = optimize_images.OptimizationResult(
                source=source,
                source_hash="new-hash",
                outputs=[output],
                staged_outputs=[staged_path],
                temporary_directory=staging_directory,
            )

            with (
                mock.patch.object(
                    optimize_images,
                    "REPOSITORY_ROOT",
                    repository_root,
                ),
                mock.patch.object(
                    optimize_images,
                    "get_file_hash",
                    return_value="new-hash",
                ),
                mock.patch.object(
                    optimize_images,
                    "save_manifest",
                    side_effect=OSError("disk full"),
                ),
                self.assertRaisesRegex(OSError, "disk full"),
            ):
                _ = optimize_images.commit_result(result, manifest)

            self.assertEqual(final_path.read_text(encoding="utf-8"), "old image")
            self.assertEqual(manifest["processed"][str(source)], old_entry)

    def test_interrupt_after_backup_move_restores_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository_root = Path(temp_dir)
            source = Path("content/posts/example/photo.jpg")
            output = Path("static/img/optimized/posts/example/photo-400w-hash.jpg")
            final_path = repository_root / output
            final_path.parent.mkdir(parents=True)
            _ = final_path.write_text("old image", encoding="utf-8")
            staging_directory = repository_root / "static/img/optimized/.staging"
            staged_path = staging_directory / "output.jpg"
            staged_path.parent.mkdir(parents=True)
            _ = staged_path.write_text("new image", encoding="utf-8")
            manifest: optimize_images.Manifest = {"processed": {}}
            result = optimize_images.OptimizationResult(
                source=source,
                source_hash="new-hash",
                outputs=[output],
                staged_outputs=[staged_path],
                temporary_directory=staging_directory,
            )
            original_replace = Path.replace

            def interrupt_after_move(path: Path, target: Path) -> Path:
                moved_path = original_replace(path, target)
                if path.resolve() == final_path.resolve():
                    raise KeyboardInterrupt
                return moved_path

            with (
                mock.patch.object(
                    optimize_images,
                    "REPOSITORY_ROOT",
                    repository_root,
                ),
                mock.patch.object(
                    optimize_images,
                    "get_file_hash",
                    return_value="new-hash",
                ),
                mock.patch.object(Path, "replace", new=interrupt_after_move),
                self.assertRaises(KeyboardInterrupt),
            ):
                _ = optimize_images.commit_result(result, manifest)

            self.assertEqual(final_path.read_text(encoding="utf-8"), "old image")
            self.assertFalse(staging_directory.exists())

    def test_keyboard_interrupt_during_commit_restores_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository_root = Path(temp_dir)
            source = Path("content/posts/example/photo.jpg")
            output = Path("static/img/optimized/posts/example/photo-400w-hash.jpg")
            final_path = repository_root / output
            final_path.parent.mkdir(parents=True)
            _ = final_path.write_text("old image", encoding="utf-8")
            staging_directory = repository_root / "static/img/optimized/.staging"
            staged_path = staging_directory / "output.jpg"
            staged_path.parent.mkdir(parents=True)
            _ = staged_path.write_text("new image", encoding="utf-8")
            old_entry: optimize_images.ManifestEntry = {
                "hash": "old-hash",
                "outputs": [str(output)],
                "timestamp": "2026-09-20 17:00:00",

                "version": optimize_images.PROCESSING_VERSION,
            }
            manifest: optimize_images.Manifest = {
                "processed": {str(source): old_entry.copy()}
            }
            result = optimize_images.OptimizationResult(
                source=source,
                source_hash="new-hash",
                outputs=[output],
                staged_outputs=[staged_path],
                temporary_directory=staging_directory,
            )

            with (
                mock.patch.object(
                    optimize_images,
                    "REPOSITORY_ROOT",
                    repository_root,
                ),
                mock.patch.object(
                    optimize_images,
                    "get_file_hash",
                    return_value="new-hash",
                ),
                mock.patch.object(
                    optimize_images,
                    "save_manifest",
                    side_effect=KeyboardInterrupt,
                ),
                self.assertRaises(KeyboardInterrupt),
            ):
                _ = optimize_images.commit_result(result, manifest)

            self.assertEqual(final_path.read_text(encoding="utf-8"), "old image")
            self.assertEqual(manifest["processed"][str(source)], old_entry)
            self.assertFalse(staging_directory.exists())

    def test_source_change_during_commit_restores_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository_root = Path(temp_dir)
            source = Path("content/posts/example/photo.jpg")
            output = Path("static/img/optimized/posts/example/photo-400w-hash.jpg")
            final_path = repository_root / output
            final_path.parent.mkdir(parents=True)
            _ = final_path.write_text("old image", encoding="utf-8")
            staging_directory = repository_root / "static/img/optimized/.staging"
            staged_path = staging_directory / "output.jpg"
            staged_path.parent.mkdir(parents=True)
            _ = staged_path.write_text("new image", encoding="utf-8")
            manifest: optimize_images.Manifest = {"processed": {}}
            result = optimize_images.OptimizationResult(
                source=source,
                source_hash="source-hash",
                outputs=[output],
                staged_outputs=[staged_path],
                temporary_directory=staging_directory,
            )

            with (
                mock.patch.object(
                    optimize_images,
                    "REPOSITORY_ROOT",
                    repository_root,
                ),
                mock.patch.object(
                    optimize_images,
                    "get_file_hash",
                    side_effect=("source-hash", "changed-hash"),
                ),
            ):
                committed = optimize_images.commit_result(result, manifest)

            self.assertFalse(committed)
            self.assertEqual(final_path.read_text(encoding="utf-8"), "old image")
            self.assertNotIn(str(source), manifest["processed"])


    def test_successful_commit_records_processing_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository_root = Path(temp_dir)
            source = Path("content/posts/example/photo.jpg")
            output = Path("static/img/optimized/posts/example/photo-400w-hash.jpg")
            staging_directory = repository_root / "static/img/optimized/.staging"
            staged_path = staging_directory / "output.jpg"
            staged_path.parent.mkdir(parents=True)
            _ = staged_path.write_text("new image", encoding="utf-8")
            manifest: optimize_images.Manifest = {"processed": {}}
            result = optimize_images.OptimizationResult(
                source=source,
                source_hash="source-hash",
                outputs=[output],
                staged_outputs=[staged_path],
                temporary_directory=staging_directory,
            )

            with (
                mock.patch.object(
                    optimize_images,
                    "REPOSITORY_ROOT",
                    repository_root,
                ),
                mock.patch.object(
                    optimize_images,
                    "get_file_hash",
                    return_value="source-hash",
                ),
            ):
                committed = optimize_images.commit_result(result, manifest)

            self.assertTrue(committed)
            self.assertEqual(
                manifest["processed"][str(source)]["version"],
                optimize_images.PROCESSING_VERSION,
            )

if __name__ == "__main__":
    _ = unittest.main()
