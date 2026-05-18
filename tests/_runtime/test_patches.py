# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import io
from contextlib import nullcontext
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from marimo._runtime._wasm._patches import WasmPatchSet
from marimo._runtime._wasm._polars import patch_polars_for_wasm
from marimo._runtime.capture import capture_stderr
from marimo._runtime.runtime import Kernel
from marimo._utils.platform import is_pyodide
from tests._messaging.mocks import MockStream
from tests.conftest import ExecReqProvider, mock_pyodide

if TYPE_CHECKING:
    from collections.abc import Callable
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


@pytest.mark.requires("polars")
@mock_pyodide()
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
        unpatch = patch_polars_for_wasm()

        expected_json = '[{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]'

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

        # Unpatch
        unpatch()

        # Test it fails again
        with pytest.raises(ValueError, match="Test error"):
            df.write_json(file_path)


def _const_fallback(value: object) -> Callable[..., object]:
    """Build a fallback that ignores its arguments and returns ``value``."""

    def _fb(*_args: object, **_kwargs: object) -> object:
        return value

    return _fb


class TestWasmPatchSet:
    @staticmethod
    def test_noop_outside_pyodide() -> None:
        import types

        mod = types.SimpleNamespace(fn=lambda x: x + 1)
        original = mod.fn
        patches = WasmPatchSet()
        patches.patch(mod, "fn", _const_fallback(999))
        # Outside pyodide, no patch is installed.
        assert mod.fn is original
        assert mod.fn(1) == 2
        patches.unpatch_all()()

    @staticmethod
    @mock_pyodide()
    def test_fallback_on_caught_exception() -> None:
        import types

        def divide_by_zero(_x: int) -> float:
            return 1 / 0

        mod = types.SimpleNamespace(fn=divide_by_zero)
        patches = WasmPatchSet()
        patches.patch(
            mod,
            "fn",
            _const_fallback("fallback"),
            catch=(ZeroDivisionError,),
        )
        assert mod.fn(0) == "fallback"

        unpatch = patches.unpatch_all()
        unpatch()
        with pytest.raises(ZeroDivisionError):
            mod.fn(0)

    @staticmethod
    @mock_pyodide()
    def test_fallback_failure_chains_original_error() -> None:
        import types

        def boom(*_: object, **__: object) -> object:
            raise NameError("primary boom")

        def fallback_fail(*_: object, **__: object) -> object:
            raise RuntimeError("fallback boom")

        mod = types.SimpleNamespace(fn=boom)
        patches = WasmPatchSet()
        patches.patch(mod, "fn", fallback_fail)

        with pytest.raises(NameError, match="primary boom") as exc_info:
            mod.fn()
        assert isinstance(exc_info.value.__cause__, RuntimeError)
        patches.unpatch_all()()

    @staticmethod
    @mock_pyodide()
    def test_skips_missing_attr() -> None:
        import types

        mod = types.SimpleNamespace()
        patches = WasmPatchSet()
        # Should silently skip without raising.
        patches.patch(mod, "missing", _const_fallback(None))
        assert not hasattr(mod, "missing")
        patches.unpatch_all()()


def test_fetch_url_bytes_forwards_request_and_urlopen_kwargs() -> None:
    import urllib.request

    from marimo._runtime._wasm._fetch import fetch_url_bytes

    with patch(
        "urllib.request.urlopen",
        return_value=nullcontext(io.BytesIO(b"ok")),
    ) as urlopen:
        assert (
            fetch_url_bytes(
                "https://example.com/cars.csv",
                request_kwargs={
                    "headers": {"User-Agent": "marimo"},
                    "method": "GET",
                },
                urlopen_kwargs={"timeout": 5},
            )
            == b"ok"
        )

    request = urlopen.call_args.args[0]
    assert isinstance(request, urllib.request.Request)
    assert request.get_header("User-agent") == "marimo"
    assert request.get_method() == "GET"
    assert urlopen.call_args.kwargs == {"timeout": 5}


@pytest.mark.requires("polars", "pyarrow")
class TestPolarsIoWasmPatch:
    @staticmethod
    def test_noop_outside_pyodide() -> None:
        import polars as pl

        original = pl.read_csv
        unpatch = patch_polars_for_wasm()
        assert pl.read_csv is original
        unpatch()
        assert pl.read_csv is original

    @staticmethod
    @mock_pyodide()
    def test_read_csv_falls_back_on_name_error() -> None:
        import polars as pl

        csv_bytes = b"a,b\n1,x\n2,y\n"
        with patch(
            "polars.read_csv",
            side_effect=NameError("simulated wasm failure"),
        ):
            unpatch = patch_polars_for_wasm()
            try:
                df = pl.read_csv(io.BytesIO(csv_bytes))
                assert df.shape == (2, 2)
                assert df.columns == ["a", "b"]
                assert df["b"].to_list() == ["x", "y"]
            finally:
                unpatch()

    @staticmethod
    @mock_pyodide()
    def test_read_csv_falls_back_on_generic_exception() -> None:
        import polars as pl

        csv_bytes = b"a,b\n1,x\n"
        with patch(
            "polars.read_csv",
            side_effect=RuntimeError("network unavailable"),
        ):
            unpatch = patch_polars_for_wasm()
            try:
                df = pl.read_csv(io.BytesIO(csv_bytes))
                assert df.shape == (1, 2)
            finally:
                unpatch()

    @staticmethod
    @mock_pyodide()
    def test_scan_csv_returns_lazyframe() -> None:
        import polars as pl

        csv_bytes = b"a,b\n1,x\n2,y\n"
        with patch(
            "polars.scan_csv",
            side_effect=NameError("simulated wasm failure"),
        ):
            unpatch = patch_polars_for_wasm()
            try:
                lf = pl.scan_csv(io.BytesIO(csv_bytes))
                assert isinstance(lf, pl.LazyFrame)
                assert lf.collect().shape == (2, 2)
            finally:
                unpatch()

    @staticmethod
    @mock_pyodide()
    def test_read_parquet_falls_back(tmp_path: Path) -> None:
        import polars as pl

        df_in = pl.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        path = tmp_path / "test.parquet"
        df_in.write_parquet(path)
        parquet_bytes = path.read_bytes()

        with patch(
            "polars.read_parquet",
            side_effect=NameError("simulated wasm failure"),
        ):
            unpatch = patch_polars_for_wasm()
            try:
                df = pl.read_parquet(io.BytesIO(parquet_bytes))
                assert df.shape == (3, 2)
                assert df["a"].to_list() == [1, 2, 3]
            finally:
                unpatch()

    @staticmethod
    @mock_pyodide()
    def test_unpatch_restores_original() -> None:
        import polars as pl

        unpatch = patch_polars_for_wasm()
        try:
            assert pl.read_csv is not None
            patched = pl.read_csv
            unpatch()
            assert pl.read_csv is not patched
        finally:
            # idempotent — calling again should be safe
            unpatch()

    @staticmethod
    @mock_pyodide()
    def test_unpatch_is_idempotent() -> None:
        unpatch = patch_polars_for_wasm()
        unpatch()
        unpatch()  # second call must not raise

    @staticmethod
    @mock_pyodide()
    def test_fallback_propagates_original_error_when_fallback_fails() -> None:
        import polars as pl

        with patch(
            "polars.read_csv",
            side_effect=NameError("simulated wasm failure"),
        ):
            unpatch = patch_polars_for_wasm()
            try:
                # Pass an unsupported source type so the fallback raises.
                with pytest.raises(NameError, match="simulated wasm failure"):
                    pl.read_csv(12345)  # type: ignore[arg-type]
            finally:
                unpatch()

    @staticmethod
    @mock_pyodide()
    def test_missing_pyarrow_bubbles_module_not_found_error() -> None:
        """ModuleNotFoundError must propagate so marimo can prompt to install."""
        import polars as pl

        from marimo._dependencies.dependencies import DependencyManager

        with (
            patch(
                "polars.read_csv",
                side_effect=NameError("simulated wasm failure"),
            ),
            patch.object(DependencyManager.pyarrow, "has", return_value=False),
        ):
            unpatch = patch_polars_for_wasm()
            try:
                with pytest.raises(ModuleNotFoundError) as exc_info:
                    pl.read_csv(io.BytesIO(b"a,b\n1,x\n"))
                assert exc_info.value.name == "pyarrow"
            finally:
                unpatch()
