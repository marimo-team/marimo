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
    for msg in mocked_kernel.stream.messages:
        if msg[0] == "cell-op" and msg[1]["output"] is not None:
            outputs.append(msg[1]["output"]["data"])

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
    for msg in mocked_kernel.stream.messages:
        if msg[0] == "cell-op" and msg[1]["output"] is not None:
            outputs.append(msg[1]["output"]["data"])

    assert "<iframe" not in outputs[-1]
    assert "<img" in outputs[-1]
