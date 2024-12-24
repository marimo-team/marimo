# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

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

    @staticmethod
    async def test_micropip_auto_install(
        executing_kernel: Kernel, exec_req: ExecReqProvider, monkeypatch
    ) -> None:
        # Track micropip.install calls and import attempts
        install_called = False
        import_attempts = 0
        test_package = "requests"

        async def mock_install(_: str) -> bool:
            nonlocal install_called
            install_called = True
            return True

        def mock_import(  # noqa: ARG001
            name: str,
            global_ns: dict[str, Any] | None = None,  # noqa: ARG001
            local_ns: dict[str, Any] | None = None,  # noqa: ARG001
            fromlist: tuple[str, ...] = (),  # noqa: ARG001
            level: int = 0  # noqa: ARG001
        ) -> Any:
            nonlocal import_attempts
            import_attempts += 1
            if import_attempts == 1:
                # First attempt fails to trigger auto-install
                raise ModuleNotFoundError(f"No module named '{name}'")
            # Subsequent attempts succeed
            return type(name, (), {})()

        # Mock micropip, is_pyodide, and __import__
        monkeypatch.setattr("marimo._utils.platform.is_pyodide", lambda: True)
        monkeypatch.setattr("micropip.install", mock_install)
        monkeypatch.setattr("builtins.__import__", mock_import)

        # First attempt should trigger ModuleNotFoundError and auto-installation
        with capture_stderr() as buf:
            result = await executing_kernel.run(
                [exec_req.get(f"import {test_package}")]
            )

        # Verify the error was handled and installation was triggered
        assert install_called, "micropip.install should have been called"
        assert import_attempts == 1, "First import attempt should have failed"
        assert not buf.getvalue(), "No error should be printed to stderr"

        # Second attempt should succeed since package is now "installed"
        result = await executing_kernel.run(
            [exec_req.get(f"import {test_package}")]
        )
        assert not result.error, "Import should succeed after installation"
        assert import_attempts == 2, "Second import attempt should succeed"
