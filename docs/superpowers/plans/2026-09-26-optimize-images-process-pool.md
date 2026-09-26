# optimize_images ワーカーのプロセス化 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** AVIF 保存時のネイティブなメモリリークがあっても、全 530 枚の作り直しが Amplify の 16 GiB 環境で完了するようにし、最後に `PROCESSING_VERSION` を 2 に上げて全出力を sRGB 変換済みにする。

**Architecture:** `_run_optimizations` の `ThreadPoolExecutor` を、`spawn` で起動し `max_tasks_per_child=1` で入れ替わる `ProcessPoolExecutor` に置き換える。ワーカーは初期化関数で共有の停止フラグと実行ごとのステージング先を受け取り、SIGINT を無視する。親プロセスは実行ごとに `OUTPUT_DIR/.run-<random>/` を作り、公開と破棄を終えた後に必ず削除する。

**Tech Stack:** Python 3.11 以上（標準ライブラリの `concurrent.futures`、`multiprocessing`、`signal`）、pyvips 3.2.0、unittest、pyright、Amplify Hosting。

**Spec:** `docs/superpowers/specs/2026-09-26-optimize-images-process-pool-design.md`

## Global Constraints

- スクリプトの `requires-python` は `>=3.11`、`pyrightconfig.json` の `pythonVersion` は `"3.11"`。
- 依存の追加はしない。使うのは標準ライブラリと既存の `pyvips==3.2.0` だけ。
- `MAX_WORKERS = 3`、`TASKS_PER_WORKER = 1`（python/cpython#115634 のため。当初の計画では 10）、起動方式は `spawn`。
- ステージングは実行ごとに `OUTPUT_DIR/.run-<random>/`、画像ごとの一時ディレクトリはその中の `.image-*`。
- `process_images` の戻り値、ログの文言、`commit_result`、マニフェスト形式は変えない。
- 成功条件: `v4` イメージの amd64 コンテナ（8 CPU、16 GB）で全 530 枚を処理したピーク使用メモリが 6 GB 以下。Amplify の作り直しが 60 分のタイムアウト内に成功する。
- コードコメントは英語で、変更の経緯ではなく今のコードについて書く。コミットメッセージは英語の Conventional Commits。
- テスト: `uv run -q --with pyvips==3.2.0 python -m unittest tests.test_optimize_images`。型チェック: `uvx -q pyright`。どちらもリポジトリのルートで実行する。
- GitHub への push は、この端末からは `github-push-via-fox` スキルの手順で fox 経由で行う。
- AWS は `--profile hugo --region ap-northeast-1`、Amplify のアプリ ID は `d8gzy6xdskncg`、ブランチは `main`。

## Review Focus

1. `uv run scripts/optimize_images.py` で起動するとモジュールは `__main__` になる。`spawn` のワーカーがワーカー関数を import し直せず、全画像が失敗したりハングしたりしてはならない。Task 3 のエンドツーエンドテストで、実際に CLI として起動して確かめる。
2. `max_tasks_per_child` でワーカーが入れ替わるときに、結果を取りこぼしたりハングしたりしてはならない。Task 3 で `TASKS_PER_WORKER = 1`、ワーカー 2 つ、画像 3 枚にして、入れ替わりを必ず起こす。タイムアウトは 300 秒にする。
3. ワーカーが OOM などで強制終了されたとき、ステージングが残ってはならない。残りの画像はエラーとして報告し、終了コード 1 で終わる。Task 2 の `BrokenProcessPool` テストと、`.run-*` 削除のテストで確かめる。
4. ターミナルの Ctrl-C はワーカーにも SIGINT として届く。ワーカーはそれを無視し、親が片付けを担う。Task 1 の `_init_worker` テストと、Task 4 の SIGINT 2 回の実地確認で確かめる。
5. 公開中の例外（`commit_result` から `KeyboardInterrupt` が伝わる場合など）で `process_images` を抜けても、`.run-*` は削除される。Task 2 の例外経路のテストで確かめる。

---

### Task 1: ワーカーの入口、停止フラグの型、ステージング先の引数

**Files:**
- Modify: `scripts/optimize_images.py`（import、`SourceChangedError` の後に型を追加、`_raise_if_cancelled`、`optimize_image`、`_cancel_pending` の前にワーカー関数を追加）
- Test: `tests/test_optimize_images.py`

**Interfaces:**
- Consumes: なし
- Produces:
  - `class StopSignal(Protocol)`: `is_set(self) -> bool` と `set(self) -> None`
  - `optimize_image(source_path: Path, dry_run: bool = False, stop_event: StopSignal | None = None, staging_root: Path | None = None) -> OptimizationResult`
  - `_init_worker(stop_event: StopSignal, staging_root: Path) -> None`
  - `_optimize_in_worker(source: Path) -> OptimizationResult`
  - モジュール変数 `_worker_stop_event: StopSignal | None`、`_worker_staging_root: Path | None`

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_optimize_images.py` の import に `import signal` を追加する（`import json` の直後）。`class ArgumentsTest(unittest.TestCase):` の直前に次のクラスを追加する。

```python
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
```

- [ ] **Step 2: テストが失敗することを確かめる**

Run: `uv run -q --with pyvips==3.2.0 python -m unittest tests.test_optimize_images.WorkerTest 2>&1 | tail -5`
Expected: FAIL（`AttributeError: ... has no attribute '_worker_stop_event'` と、`staging_root` が予期しない引数だという `TypeError`）

- [ ] **Step 3: 最小限の実装を書く**

`scripts/optimize_images.py` の import を次のように変える。

```python
import argparse
from collections.abc import Sequence
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import tempfile
from threading import Event
import time
import traceback
from typing import Literal, Protocol, TypedDict, cast
```

`class SourceChangedError(RuntimeError):` のクラス定義の直後に追加する。

```python
class StopSignal(Protocol):
    """Cancellation flag shared by the parent and its workers."""

    def is_set(self) -> bool: ...

    def set(self) -> None: ...
```

`_raise_if_cancelled` の引数の型を `stop_event: StopSignal | None` に変える。

`optimize_image` のシグネチャと、一時ディレクトリを作る部分を次のように変える。

```python
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
```

（`snapshot_path = _create_snapshot(...)` 以降は変えない。）

`def _cancel_pending(` の直前に追加する。

```python
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
```

- [ ] **Step 4: テストが通ることを確かめる**

Run: `uv run -q --with pyvips==3.2.0 python -m unittest tests.test_optimize_images 2>&1 | tail -3 && uvx -q pyright 2>&1 | tail -1`
Expected: `OK`（28 件）と `0 errors, 0 warnings, 0 informations`

- [ ] **Step 5: コミットする**

```bash
git add scripts/optimize_images.py tests/test_optimize_images.py
git commit -m "refactor: add worker entry points and per-run staging for image optimization"
```

---

### Task 2: プロセスプールへの切り替えと実行ごとのステージング

**Files:**
- Modify: `scripts/optimize_images.py`（ヘッダーの `requires-python`、import、定数、`_shutdown_executor`、`_run_optimizations`、`process_images`、新しい `_create_run_staging`）
- Modify: `pyrightconfig.json`
- Test: `tests/test_optimize_images.py`（`InterruptingExecutor` と `ProgressLoggingTest` を置き換え、`RunStagingTest` を追加）

**Interfaces:**
- Consumes: Task 1 の `StopSignal`、`_init_worker(stop_event, staging_root)`、`_optimize_in_worker(source)`
- Produces:
  - 定数 `TASKS_PER_WORKER = 10`
  - `_create_run_staging() -> Path`
  - `_run_optimizations(images: Sequence[Path], staging_root: Path) -> tuple[list[OptimizationResult], bool]`
  - `_shutdown_executor(executor: Executor, stop_event: StopSignal) -> bool`

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_optimize_images.py` の import を次のように変える（`multiprocessing.context` と `BrokenProcessPool` を追加）。

```python
import json
import multiprocessing.context
import signal
import tempfile
import unittest
from concurrent.futures import Future
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path
from threading import Event
from typing import TYPE_CHECKING, Protocol, cast
from unittest import mock
```

`class InterruptingExecutor:` から `class ProgressLoggingTest` の `test_interrupt_during_shutdown_is_reported` の終わりまでを、次のコードで置き換える（`test_log_flushes_output` は残す）。

```python
class FakeProcessPool:
    """Process pool fake that completes tasks inline and interrupts shutdown."""

    def __init__(
        self,
        shutdown_interrupts: int = 0,
        error: Exception | None = None,
    ) -> None:
        self.shutdown_interrupts: int = shutdown_interrupts
        self.error: Exception | None = error
        self.shutdown_calls: int = 0
        self.options: dict[str, object] = {}

    def create(self, **options: object) -> "FakeProcessPool":
        self.options = options
        return self

    @property
    def stop_event(self) -> optimize_images.StopSignal:
        initargs = cast(
            tuple[optimize_images.StopSignal, Path],
            self.options["initargs"],
        )
        return initargs[0]

    def submit(
        self,
        _function: object,
        source: Path,
    ) -> "Future[optimize_images.OptimizationResult]":
        future: Future[optimize_images.OptimizationResult] = Future()
        if self.error is None:
            future.set_result(optimize_images.OptimizationResult(source=source))
        else:
            future.set_exception(self.error)
        return future

    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        del wait, cancel_futures
        self.shutdown_calls += 1
        if self.shutdown_calls <= self.shutdown_interrupts:
            raise KeyboardInterrupt


STAGING_ROOT = Path("/tmp/staging")
IMAGES = [
    Path("content/posts/example/first.jpg"),
    Path("content/posts/example/second.jpg"),
]


class ProgressLoggingTest(unittest.TestCase):
    def test_each_finished_image_is_logged_with_progress(self) -> None:
        pool = FakeProcessPool()

        with (
            mock.patch.object(
                optimize_images,
                "ProcessPoolExecutor",
                side_effect=pool.create,
            ),
            mock.patch.object(optimize_images, "log") as log,
        ):
            results, interrupted = optimize_images._run_optimizations(
                IMAGES,
                STAGING_ROOT,
            )

        self.assertFalse(interrupted)
        self.assertEqual(len(results), 2)
        messages = [call.args[0] for call in log.call_args_list]
        self.assertEqual(
            sorted(message.split(":")[0] for message in messages),
            ["Finished 1/2", "Finished 2/2"],
        )
        self.assertEqual(
            {message.split(": ", 1)[1] for message in messages},
            {str(image) for image in IMAGES},
        )

    def test_pool_uses_recycled_spawned_workers(self) -> None:
        pool = FakeProcessPool()

        with (
            mock.patch.object(
                optimize_images,
                "ProcessPoolExecutor",
                side_effect=pool.create,
            ),
            mock.patch.object(optimize_images, "log"),
        ):
            _ = optimize_images._run_optimizations(IMAGES, STAGING_ROOT)

        context = cast(
            multiprocessing.context.BaseContext,
            pool.options["mp_context"],
        )
        self.assertEqual(context.get_start_method(), "spawn")
        self.assertEqual(pool.options["max_workers"], optimize_images.MAX_WORKERS)
        self.assertEqual(
            pool.options["max_tasks_per_child"],
            optimize_images.TASKS_PER_WORKER,
        )
        self.assertIs(pool.options["initializer"], optimize_images._init_worker)
        initargs = cast(tuple[object, Path], pool.options["initargs"])
        self.assertEqual(initargs[1], STAGING_ROOT)

    def test_repeated_interrupt_waits_for_workers_and_keeps_results(self) -> None:
        pool = FakeProcessPool(shutdown_interrupts=1)

        with (
            mock.patch.object(
                optimize_images,
                "ProcessPoolExecutor",
                side_effect=pool.create,
            ),
            mock.patch.object(
                optimize_images,
                "as_completed",
                side_effect=KeyboardInterrupt,
            ),
            mock.patch.object(optimize_images, "log"),
        ):
            results, interrupted = optimize_images._run_optimizations(
                IMAGES,
                STAGING_ROOT,
            )

        self.assertTrue(interrupted)
        self.assertEqual(pool.shutdown_calls, 2)
        self.assertTrue(pool.stop_event.is_set())
        self.assertEqual({result.source for result in results}, set(IMAGES))

    def test_interrupt_during_shutdown_is_reported(self) -> None:
        pool = FakeProcessPool(shutdown_interrupts=1)

        with (
            mock.patch.object(
                optimize_images,
                "ProcessPoolExecutor",
                side_effect=pool.create,
            ),
            mock.patch.object(optimize_images, "log"),
        ):
            results, interrupted = optimize_images._run_optimizations(
                IMAGES[:1],
                STAGING_ROOT,
            )

        self.assertTrue(interrupted)
        self.assertEqual(len(results), 1)

    def test_broken_pool_turns_into_error_results(self) -> None:
        pool = FakeProcessPool(error=BrokenProcessPool("worker died"))

        with (
            mock.patch.object(
                optimize_images,
                "ProcessPoolExecutor",
                side_effect=pool.create,
            ),
            mock.patch.object(optimize_images, "log"),
        ):
            results, interrupted = optimize_images._run_optimizations(
                IMAGES,
                STAGING_ROOT,
            )

        self.assertFalse(interrupted)
        self.assertEqual({result.source for result in results}, set(IMAGES))
        self.assertTrue(all(result.errors == ["worker died"] for result in results))
```

同じファイルの `class ColorSpaceTest(unittest.TestCase):` の直前に追加する。

```python
class RunStagingTest(unittest.TestCase):
    def _process_with(
        self,
        repository_root: Path,
        fake_run: object,
    ) -> int:
        with (
            mock.patch.object(optimize_images, "REPOSITORY_ROOT", repository_root),
            mock.patch.object(
                optimize_images,
                "load_manifest",
                return_value={"processed": {}},
            ),
            mock.patch.object(
                optimize_images,
                "find_images",
                return_value=[IMAGES[0]],
            ),
            mock.patch.object(
                optimize_images,
                "needs_processing",
                return_value=True,
            ),
            mock.patch.object(
                optimize_images,
                "_run_optimizations",
                side_effect=fake_run,
            ),
            mock.patch.object(optimize_images, "log"),
        ):
            return optimize_images.process_images()

    def test_run_staging_is_removed_after_success(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository_root = Path(temp_dir)
            seen: list[Path] = []

            def fake_run(
                _images: list[Path],
                staging_root: Path,
            ) -> tuple[list[optimize_images.OptimizationResult], bool]:
                self.assertTrue(staging_root.is_dir())
                seen.append(staging_root)
                return [], False

            exit_code = self._process_with(repository_root, fake_run)

            self.assertEqual(exit_code, 0)
            self.assertEqual(len(seen), 1)
            self.assertEqual(
                seen[0].parent,
                repository_root / "static/img/optimized",
            )
            self.assertTrue(seen[0].name.startswith(".run-"))
            self.assertFalse(seen[0].exists())

    def test_run_staging_is_removed_when_processing_raises(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository_root = Path(temp_dir)
            seen: list[Path] = []

            def fake_run(
                _images: list[Path],
                staging_root: Path,
            ) -> tuple[list[optimize_images.OptimizationResult], bool]:
                seen.append(staging_root)
                raise KeyboardInterrupt

            with self.assertRaises(KeyboardInterrupt):
                _ = self._process_with(repository_root, fake_run)

            self.assertEqual(len(seen), 1)
            self.assertFalse(seen[0].exists())
```

- [ ] **Step 2: テストが失敗することを確かめる**

Run: `uv run -q --with pyvips==3.2.0 python -m unittest tests.test_optimize_images 2>&1 | rg "^(FAIL|ERROR):|^Ran|FAILED|^OK"`
Expected: `ProgressLoggingTest` と `RunStagingTest` の各テストが ERROR（`ProcessPoolExecutor` 属性がない、`_run_optimizations` の引数の数が違う、など）

- [ ] **Step 3: 実装する**

`scripts/optimize_images.py` の 3 行目を `# requires-python = ">=3.11"` に変える。`pyrightconfig.json` の `"pythonVersion": "3.10"` を `"pythonVersion": "3.11"` に変える。

import を次のように変える（`ThreadPoolExecutor` と `threading.Event` はもう使わない）。

```python
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
```

`MAX_WORKERS = 3` の直後に追加する。

```python
# Worker processes exit after this many images, which returns memory leaked
# by native encoders to the system.
TASKS_PER_WORKER = 10
```

`_shutdown_executor` のシグネチャを次に変える（本体は変えない）。

```python
def _shutdown_executor(executor: Executor, stop_event: StopSignal) -> bool:
```

`_run_optimizations` を丸ごと次のコードに置き換える。

```python
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
```

`def _discard_all(` の直前に追加する。

```python
def _create_run_staging() -> Path:
    """Create the directory that holds every staged file of one run."""
    output_root = _repository_path(OUTPUT_DIR)
    output_root.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=".run-", dir=output_root))
```

`process_images` の `results, interrupted = _run_optimizations(to_process)` から関数の終わりまでを次のコードに置き換える。

```python
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
```

README や AGENTS.md に Python 3.10 の記述がないことを確かめる。

Run: `rg -n "3\.10" README.md AGENTS.md amplify.yml`
Expected: 出力なし（ある場合は 3.11 に直す）

- [ ] **Step 4: テストと型チェックが通ることを確かめる**

Run: `uv run -q --with pyvips==3.2.0 python -m unittest tests.test_optimize_images 2>&1 | tail -3 && uvx -q pyright 2>&1 | tail -1`
Expected: `OK`（32 件）と `0 errors, 0 warnings, 0 informations`

- [ ] **Step 5: dry-run の出力が変わらないことを確かめる**

dry-run は並列実行を使わないので、出力は変わらないはず。

Run: `uv run -q scripts/optimize_images.py --dry-run --force 2>&1 | grep '^\[' | cut -c12- | tail -3`
Expected: `→ static/img/optimized/uses/home-assistant-2400w-eae8bb72.avif` などの計画出力が並び、エラーがない

- [ ] **Step 6: コミットする**

```bash
git add scripts/optimize_images.py tests/test_optimize_images.py pyrightconfig.json
git commit -m "fix: isolate image optimization workers in recycled processes

AVIF saves through libvips 8.18.0 and libheif 1.21.2 leak about 130 MB
each, which exhausted the 16 GiB Amplify build after roughly 150 images.
Run workers in spawned processes that exit after TASKS_PER_WORKER images
so leaked memory returns to the system. Workers ignore SIGINT and stage
files under a per-run directory that the parent always removes."
```

---

### Task 3: CLI として起動するエンドツーエンドテスト

**Files:**
- Modify: `typings/pyvips/__init__.pyi`（`black` を追加）
- Test: `tests/test_optimize_images.py`（`EndToEndTest` を追加）

**Interfaces:**
- Consumes: Task 2 までの `scripts/optimize_images.py` 全体。定数の行 `MAX_WORKERS = 3` と `TASKS_PER_WORKER = 10` がそのままの文字列で存在すること。
- Produces: なし

- [ ] **Step 1: テストを書く**

`typings/pyvips/__init__.pyi` の `class Image:` の中、`new_from_file` の直前に追加する。

```python
    @classmethod
    def black(cls, width: int, height: int, **kwargs: object) -> "Image": ...

```

`tests/test_optimize_images.py` の import に `import subprocess` と `import sys` を追加する（`import signal` の直後にアルファベット順で）。ファイル末尾の `if __name__ == "__main__":` の直前に追加する。

```python
class EndToEndTest(unittest.TestCase):
    def test_cli_run_recycles_worker_processes_and_cleans_up(self) -> None:
        import pyvips

        with tempfile.TemporaryDirectory() as temp_dir:
            repository_root = Path(temp_dir)
            script_text = Path(optimize_images.__file__).read_text(encoding="utf-8")
            self.assertIn("TASKS_PER_WORKER = 10", script_text)
            self.assertIn("MAX_WORKERS = 3", script_text)
            script_text = script_text.replace(
                "TASKS_PER_WORKER = 10",
                "TASKS_PER_WORKER = 1",
            ).replace("MAX_WORKERS = 3", "MAX_WORKERS = 2")
            script_path = repository_root / "scripts/optimize_images.py"
            script_path.parent.mkdir()
            _ = script_path.write_text(script_text, encoding="utf-8")
            post = repository_root / "content/posts/example"
            post.mkdir(parents=True)
            for index in range(3):
                pyvips.Image.black(64, 48, bands=3).pngsave(
                    str(post / f"image-{index}.png"),
                    compression=0,
                    strip=True,
                )

            completed = subprocess.run(
                [sys.executable, str(script_path)],
                cwd=repository_root,
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )

            self.assertEqual(
                completed.returncode,
                0,
                completed.stdout + completed.stderr,
            )
            output_root = repository_root / "static/img/optimized"
            manifest = cast(
                dict[str, dict[str, dict[str, object]]],
                json.loads((output_root / ".manifest.json").read_text("utf-8")),
            )
            self.assertEqual(len(manifest["processed"]), 3)
            for entry in manifest["processed"].values():
                outputs = cast(list[str], entry["outputs"])
                self.assertEqual(len(outputs), 10)
                for output in outputs:
                    self.assertTrue((repository_root / output).is_file(), output)
            leftovers = [
                path.name
                for path in output_root.iterdir()
                if path.is_dir() and path.name.startswith(".")
            ]
            self.assertEqual(leftovers, [])
```

- [ ] **Step 2: テストを実行する**

このテストは Task 2 の実装の検証なので、書いた時点で通るはず。失敗した場合は、`completed.stdout + completed.stderr` に出るトレースバックで原因を調べる（`__main__` の関数を import できない、ハングして 300 秒でタイムアウトする、など）。

Run: `uv run -q --with pyvips==3.2.0 python -m unittest tests.test_optimize_images.EndToEndTest 2>&1 | tail -3`
Expected: `OK`

- [ ] **Step 3: 実装を壊すとテストが失敗することを確かめる**

`scripts/optimize_images.py` の `_optimize_in_worker` の本体を一時的に `raise RuntimeError("broken worker")` に変えて、テストを実行する。

Run: `uv run -q --with pyvips==3.2.0 python -m unittest tests.test_optimize_images.EndToEndTest 2>&1 | tail -3`
Expected: FAIL（終了コードが 1）

変更を元に戻す。

Run: `git -P diff --stat scripts/optimize_images.py`
Expected: 出力なし

- [ ] **Step 4: 全テストと型チェック**

Run: `uv run -q --with pyvips==3.2.0 python -m unittest tests.test_optimize_images 2>&1 | tail -3 && uvx -q pyright 2>&1 | tail -1`
Expected: `OK`（33 件）と `0 errors, 0 warnings, 0 informations`

- [ ] **Step 5: コミットする**

```bash
git add tests/test_optimize_images.py typings/pyvips/__init__.pyi
git commit -m "test: run the optimizer CLI end to end with recycled workers"
```

---

### Task 4: 実地検証と、プロセス化の展開

**Files:**
- 変更なし（検証と push だけ）

**Interfaces:**
- Consumes: Task 1〜3 のコミット
- Produces: `origin/main` に push されたプロセス化のコミットと、成功した Amplify ジョブ

- [ ] **Step 1: macOS で全 530 枚を処理して時間を測る**

`static/img/optimized/` は gitignore されたビルド成果物で、このリポジトリの手元の出力は上書きしてよい。

Run: `cd /Users/shibtats/git/rewse-blog && /usr/bin/time -p uv run -q scripts/optimize_images.py --force > /tmp/full_process.log 2>&1; tail -4 /tmp/full_process.log; rg "^real" /tmp/full_process.log`
Expected: `Processed: 530`、`Errors: 0`。`real` がスレッド版の 527 秒（8 分 47 秒）から大きく遅くなっていない（目安として 700 秒以下）。

Run: `ls -A static/img/optimized | rg "^\.(run|image)-" || echo "no staging left"`
Expected: `no staging left`

- [ ] **Step 2: SIGINT を 2 回送る**

Run:

```bash
cd /Users/shibtats/git/rewse-blog
( uv run -q scripts/optimize_images.py --force > /tmp/sigint.log 2>&1; echo "exit=$?" >> /tmp/sigint.log ) &
sleep 20; pkill -INT -f "scripts/optimize_images.py --force"; sleep 1; pkill -INT -f "scripts/optimize_images.py --force"; sleep 20
pgrep -f "optimize_images.py" || echo "no process left"
tail -3 /tmp/sigint.log; rg -c Traceback /tmp/sigint.log || echo "no traceback"
ls -A static/img/optimized | rg "^\.(run|image)-" || echo "no staging left"
```

Expected: `no process left`、`Interrupted. Cancelled remaining tasks.`、`exit=1`、`no traceback`、`no staging left`。`pkill -f` はワーカープロセスにも SIGINT を送るので、ワーカーが SIGINT を無視していることの確認にもなる。

- [ ] **Step 3: `v4` イメージのコンテナでメモリを測る**

コンテナからは PyPI に接続できないので、依存を先にダウンロードしてオフラインで入れる。

Run:

```bash
container system start
command rm -rf /tmp/rb-copy && mkdir -p /tmp/rb-copy/wheels
cd /Users/shibtats/git/rewse-blog && rsync -a --exclude static/img/optimized --exclude public --exclude resources --exclude themes --exclude .git ./ /tmp/rb-copy/
cd /tmp/rb-copy/wheels
uvx -q pip download --no-deps --no-binary pyvips pyvips==3.2.0 -d .
uvx -q pip download --only-binary=:all: --platform manylinux_2_28_x86_64 --platform manylinux2014_x86_64 --python-version 3.14 --implementation cp cffi pycparser setuptools wheel pkgconfig -d .
cat > /tmp/rb-copy/run_monitor.sh <<'EOF'
#!/bin/bash
cd /work
( while true; do
    used=$(awk '/MemTotal/{t=$2}/MemAvailable/{a=$2}END{print (t-a)}' /proc/meminfo)
    echo "$(date +%T) used_kb=$used done=$(grep -c Finished /work/run.log 2>/dev/null)" >> /work/mem.log
    sleep 10
  done ) &
uv run --offline --no-index --find-links /work/wheels scripts/optimize_images.py > /work/run.log 2>&1
echo "exit=$?" >> /work/run.log
EOF
chmod +x /tmp/rb-copy/run_monitor.sh
container run --rm --name rb-mem --arch amd64 --cpus 8 --memory 16g -v /tmp/rb-copy:/work public.ecr.aws/v5r5z4u0/amplify-hugo-vips:v4 /work/run_monitor.sh > /tmp/rb-container.out 2>&1
tail -5 /tmp/rb-copy/run.log
sort -t= -k2 -n /tmp/rb-copy/mem.log | awk -F'used_kb=' '{print $2}' | awk '{print $1}' | tail -1
```

イメージの取得で `429 Too Many Requests` が出たら、45 秒待って `container image pull --arch amd64 public.ecr.aws/v5r5z4u0/amplify-hugo-vips:v4` をやり直す。

Expected: `Processed: 530`、`Errors: 0`、`exit=0`。最後の行（コンテナ全体の最大使用メモリ、KB）が 6000000 以下。全体で 1 時間以上かかることがあるので、`run_in_background` で実行する。

Run: `command rm -rf /tmp/rb-copy; container system stop`
Expected: 後片付けが終わる

- [ ] **Step 4: push する**

`github-push-via-fox` スキルの「Local commits already made」の手順で、`origin/main..HEAD` のコミット（spec、plan、Task 1〜3）を fox に送り、push する。push 後はこの端末で `git fetch origin` をしてから `git -P diff HEAD origin/main` が空であることを確かめ、`git reset --hard origin/main` でそろえる。

- [ ] **Step 5: Amplify のビルドを確認する**

Run: `aws amplify list-jobs --profile hugo --region ap-northeast-1 --app-id d8gzy6xdskncg --branch-name main --max-items 1 --query 'jobSummaries[0].[jobId,status,commitId]' --output text | cat`
Expected: 最新のコミットのジョブが `SUCCEED` になる（`RUNNING` の間は 30 秒ごとに確かめる）。ビルドログの `logUrl` を `aws amplify get-job ... --query 'job.steps[?stepName==\`BUILD\`].logUrl'` で取り、`curl -s` で取得すると `No images need processing.` が出ている。

---

### Task 5: 全画像の作り直しと、sRGB 変換の確認

**Files:**
- Modify: `scripts/optimize_images.py`（`PROCESSING_VERSION`）

**Interfaces:**
- Consumes: Task 4 で push したプロセス化
- Produces: `PROCESSING_VERSION = 2` で作り直された Amplify のキャッシュと、公開サイトの画像

- [ ] **Step 1: 処理バージョンを上げる**

`scripts/optimize_images.py` の `PROCESSING_VERSION = 1` を `PROCESSING_VERSION = 2` に変える。

Run: `uv run -q --with pyvips==3.2.0 python -m unittest tests.test_optimize_images 2>&1 | tail -3 && uvx -q pyright 2>&1 | tail -1`
Expected: `OK` と `0 errors, 0 warnings, 0 informations`

- [ ] **Step 2: コミットして push する**

```bash
git add scripts/optimize_images.py
git commit -m "fix: rebuild cached images with sRGB conversion

Workers now run in recycled processes, so a full rebuild fits in the
Amplify build's memory. Bump the processing version to regenerate every
cached output with ICC profiles converted to sRGB."
```

push は Task 4 Step 4 と同じ手順で行う。

- [ ] **Step 3: Amplify の作り直しを確認する**

Run: `aws amplify list-jobs --profile hugo --region ap-northeast-1 --app-id d8gzy6xdskncg --branch-name main --max-items 1 --query 'jobSummaries[0].[jobId,status,commitId]' --output text | cat`
Expected: ジョブが 60 分以内に `SUCCEED` になる。待つ間は `run_in_background` で 30 秒ごとに確かめる。ビルドログで `Found 530 images to process`、`Processed: 530`、`Errors: 0` を確かめる。失敗した場合は、ビルドログの最後の `Finished n/530` と、終了コードを報告する。

- [ ] **Step 4: 公開された画像が sRGB に変換されていることを確かめる**

Run:

```bash
cd /Users/shibtats/git/rewse-blog
cat > /tmp/verify_published.py <<'EOF'
import sys
import urllib.request
from pathlib import Path
import pyvips
sys.path.insert(0, ".")
from scripts import optimize_images as o

pyvips.cache_set_max(0)
sources = [
    Path("content/posts/ubiquiti-unifi-udm-se-review-software/unifi-network-system.png"),
    Path("content/posts/ubiquiti-unifi-udm-se-review-hardware-initial-setup/IMG_2845.png"),
]
for source in sources:
    output = o.get_output_path(source, 800, "original", o.get_file_hash(source))
    url = "https://blog.rewse.jp/" + str(output.relative_to("static"))
    data = urllib.request.urlopen(url).read()
    published = pyvips.Image.new_from_buffer(data, "")
    raw = pyvips.Image.new_from_file(str(source))
    reference = raw.icc_transform("srgb", embedded=True, intent="relative")
    reference = reference.resize(published.width / reference.width)
    def flatten(image):
        return image.flatten(background=[255, 255, 255]) if image.bands == 4 else image
    delta = flatten(reference)[:3].colourspace("lab").dE00(
        flatten(published)[:3].copy(interpretation="srgb").colourspace("lab")
    )
    print(f"{source.name}: mean dE00={delta.avg():.2f} icc={'icc-profile-data' in published.get_fields()} {url}")
EOF
uv run -q --with pyvips==3.2.0 python /tmp/verify_published.py
```

Expected: 2 枚とも `mean dE00` が 0.10 以下で、`icc=False`。修正前の出力では、Adobe RGB の `unifi-network-system.png` は平均 0.18 だった。キャッシュが残っていて古い画像が返る場合は、URL に `?v=2` を付けて取り直す。
