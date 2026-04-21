# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import io
import multiprocessing
import sys
import threading
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._runtime.capture import capture_stderr
from marimo._runtime.patches import (
    patch_main_module,
    patch_polars_write_json,
    restore_main_module,
    save_main_module,
)
from marimo._runtime.runtime import Kernel
from marimo._utils.platform import is_pyodide
from tests._messaging.mocks import MockStream
from tests._runtime._patches_spawn_target import noop_target
from tests.conftest import ExecReqProvider

if TYPE_CHECKING:
    from pathlib import Path


class TestMicropip:
    @staticmethod
    def _assert_micropip_warning_printed(message: str) -> None:
        assert "micropip is only available in WASM notebooks" in message

    @staticmethod
    async def test_micropip_available(
        executing_kernel: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await executing_kernel.run([exec_req.get("import micropip")])
        assert "micropip" in executing_kernel.globals

    @staticmethod
    async def test_micropip_once(
        executing_kernel: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await executing_kernel.run([exec_req.get("import sys")])
        assert (
            executing_kernel.globals["sys"].meta_path[-1].__class__.__name__
            == "_MicropipFinder"
        )
        # Double patched at this point, barring explicit fix.
        assert (
            executing_kernel.globals["sys"].meta_path[-2].__class__.__name__
            != "_MicropipFinder"
        )

    @staticmethod
    async def test_micropip_install(
        executing_kernel: Kernel, exec_req: ExecReqProvider
    ) -> None:
        if not is_pyodide():
            with capture_stderr() as buf:
                await executing_kernel.run(
                    [
                        exec_req.get("import micropip"),
                        exec_req.get("await micropip.install('foo')"),
                    ]
                )
            TestMicropip._assert_micropip_warning_printed(buf.getvalue())

    @staticmethod
    async def test_micropip_list(
        executing_kernel: Kernel, exec_req: ExecReqProvider
    ) -> None:
        if not is_pyodide():
            with capture_stderr() as buf:
                await executing_kernel.run(
                    [
                        exec_req.get("import micropip"),
                        exec_req.get("micropip.list()"),
                    ]
                )
            TestMicropip._assert_micropip_warning_printed(buf.getvalue())

    @staticmethod
    async def test_micropip_freeze(
        executing_kernel: Kernel, exec_req: ExecReqProvider
    ) -> None:
        if not is_pyodide():
            with capture_stderr() as buf:
                await executing_kernel.run(
                    [
                        exec_req.get("import micropip"),
                        exec_req.get("micropip.freeze()"),
                    ]
                )
            TestMicropip._assert_micropip_warning_printed(buf.getvalue())

    @staticmethod
    async def test_micropip_add_mock_package(
        executing_kernel: Kernel, exec_req: ExecReqProvider
    ) -> None:
        if not is_pyodide():
            with capture_stderr() as buf:
                await executing_kernel.run(
                    [
                        exec_req.get("import micropip"),
                        exec_req.get(
                            "micropip.add_mock_package('foo', '0.1')"
                        ),
                    ]
                )
            TestMicropip._assert_micropip_warning_printed(buf.getvalue())

    @staticmethod
    async def test_micropip_list_mock_packages(
        executing_kernel: Kernel, exec_req: ExecReqProvider
    ) -> None:
        if not is_pyodide():
            with capture_stderr() as buf:
                await executing_kernel.run(
                    [
                        exec_req.get("import micropip"),
                        exec_req.get("micropip.list_mock_packages()"),
                    ]
                )
            TestMicropip._assert_micropip_warning_printed(buf.getvalue())

    @staticmethod
    async def test_micropip_uninstall(
        executing_kernel: Kernel, exec_req: ExecReqProvider
    ) -> None:
        if not is_pyodide():
            with capture_stderr() as buf:
                await executing_kernel.run(
                    [
                        exec_req.get("import micropip"),
                        exec_req.get("micropip.uninstall('foo')"),
                    ]
                )
            TestMicropip._assert_micropip_warning_printed(buf.getvalue())

    @staticmethod
    async def test_micropip_set_index_urls(
        executing_kernel: Kernel, exec_req: ExecReqProvider
    ) -> None:
        if not is_pyodide():
            with capture_stderr() as buf:
                await executing_kernel.run(
                    [
                        exec_req.get("import micropip"),
                        exec_req.get("micropip.set_index_urls('foo')"),
                    ]
                )
            TestMicropip._assert_micropip_warning_printed(buf.getvalue())


async def test_webbrowser_injection(
    mocked_kernel: Kernel, exec_req: ExecReqProvider
):
    await mocked_kernel.k.run(
        [
            exec_req.get("""
          import webbrowser
          MarimoBrowser = __marimo__._runtime.marimo_browser.build_browser_fallback()
          webbrowser.register(
              "marimo-output", None, MarimoBrowser(), preferred=True
          )
          """),
        ]
    )
    await mocked_kernel.k.run(
        [
            cell := exec_req.get("webbrowser.open('https://marimo.io');"),
        ]
    )
    assert "webbrowser" in mocked_kernel.k.globals
    outputs: list[str] = []
    stream = MockStream(mocked_kernel.stream)
    for msg in stream.operations:
        if msg["op"] == "cell-op" and msg["output"] is not None:
            outputs.append(msg["output"]["data"])

    assert "<iframe" in outputs[-1]


async def test_webbrowser_easter_egg(
    mocked_kernel: Kernel, exec_req: ExecReqProvider
):
    await mocked_kernel.k.run(
        [
            exec_req.get("""
          import webbrowser
          MarimoBrowser = __marimo__._runtime.marimo_browser.build_browser_fallback()
          webbrowser.register(
              "marimo-output", None, MarimoBrowser(), preferred=True
          )
          """),
        ]
    )
    await mocked_kernel.k.run(
        [
            cell := exec_req.get("import antigravity;"),
        ]
    )
    assert "antigravity" in mocked_kernel.k.globals
    outputs: list[str] = []
    stream = MockStream(mocked_kernel.stream)
    for msg in stream.operations:
        if msg["op"] == "cell-op" and msg["output"] is not None:
            outputs.append(msg["output"]["data"])

    assert "<iframe" not in outputs[-1]
    assert "<img" in outputs[-1]


@pytest.mark.skipif(
    not DependencyManager.polars.has(),
    reason="Polars is not installed",
)
@patch.dict(sys.modules, {"pyodide": Mock()})
def test_polars_write_json_patch(tmp_path: Path):
    import polars as pl

    file_path = tmp_path / "test.json"

    # Make write_json throw an error
    with patch(
        "polars.DataFrame.write_json",
        side_effect=ValueError("Test error"),
    ):
        # Test it fails
        df = pl.DataFrame({"a": [1, 2], "b": ["x", "y"]})
        with pytest.raises(ValueError, match="Test error"):
            df.write_json(file_path)

        # Patch to fallback to write_csv
        unpatch_polars_write_json = patch_polars_write_json()

        expected_json = '[{"a": "1", "b": "x"}, {"a": "2", "b": "y"}]'

        # Test it succeeds with file path
        df.write_json(file_path)
        assert file_path.read_text() == expected_json

        # Test it succeeds with string path
        df.write_json(str(file_path))
        assert file_path.read_text() == expected_json

        # Test it succeeds with buffer
        buffer = io.StringIO()
        df.write_json(buffer)
        assert buffer.getvalue() == expected_json

        # Test it succeeds with None
        assert df.write_json() == expected_json

        # Patch the patch
        unpatch_polars_write_json()

        # Test it fails again
        with pytest.raises(ValueError, match="Test error"):
            df.write_json(file_path)


class TestSaveRestoreMainModule:
    """save_main_module / restore_main_module refcount helpers.

    patch_main_module mutates sys.modules['__main__'] without a restore
    path, leaking a synthetic module into any host that shares sys.modules
    with the kernel (i.e. RUN-mode thread kernels). The helpers let
    callers explicitly scope the mutation.
    """

    def test_restore_returns_original_main(self) -> None:
        original = sys.modules["__main__"]
        save_main_module()
        try:
            patch_main_module(
                file=None, input_override=None, print_override=None
            )
            assert sys.modules["__main__"] is not original
        finally:
            restore_main_module()
        assert sys.modules["__main__"] is original

    def test_refcounted_multiple_savers_share_original(self) -> None:
        original = sys.modules["__main__"]
        # Two overlapping sessions each call save.
        save_main_module()
        save_main_module()
        try:
            patch_main_module(
                file=None, input_override=None, print_override=None
            )
            mutated = sys.modules["__main__"]
            assert mutated is not original
            # First release: refcount still > 0, no restore yet.
            restore_main_module()
            assert sys.modules["__main__"] is mutated
        finally:
            # Last release: restore to the originally captured value.
            restore_main_module()
        assert sys.modules["__main__"] is original

    def test_over_release_is_noop(self) -> None:
        original = sys.modules["__main__"]
        # No outstanding save; restore should do nothing.
        restore_main_module()
        assert sys.modules["__main__"] is original

    def test_concurrent_save_restore_cycles_preserve_main(self) -> None:
        """Concurrent save/restore cycles converge back to the original main."""
        original = sys.modules["__main__"]
        n_threads = 8
        iterations_per_thread = 25

        def worker() -> None:
            for _ in range(iterations_per_thread):
                save_main_module()
                patch_main_module(
                    file=None, input_override=None, print_override=None
                )
                restore_main_module()

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert sys.modules["__main__"] is original

    def test_save_when_main_is_absent_is_safe(self) -> None:
        """Saving when sys.modules has no __main__ skips the restore write."""
        saved_main = sys.modules.pop("__main__", None)
        try:
            save_main_module()
            # A save that captured None must not install a None __main__.
            restore_main_module()
            assert "__main__" not in sys.modules
        finally:
            if saved_main is not None:
                sys.modules["__main__"] = saved_main

    def test_host_spawn_works_after_save_and_restore(self) -> None:
        """End-to-end: restoring __main__ lets the host spawn subprocesses.

        Matches the reproduction in the bug report. Without the restore,
        ``multiprocessing.get_context('spawn').Process(...).start()`` fails
        because the synthetic __main__ has no handle to module-level
        targets. With the restore, it succeeds.
        """
        save_main_module()
        try:
            patch_main_module(
                file=None, input_override=None, print_override=None
            )
        finally:
            restore_main_module()

        proc = multiprocessing.get_context("spawn").Process(target=noop_target)
        proc.start()
        proc.join(timeout=10)
        assert proc.exitcode == 0, (
            "spawn subprocess failed after save/patch/restore cycle; "
            "restore did not recover host's __main__"
        )
