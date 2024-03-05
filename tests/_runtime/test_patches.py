# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._runtime.capture import capture_stderr
from marimo._runtime.runtime import Kernel
from marimo._utils.platform import is_pyodide
from tests.conftest import ExecReqProvider


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
