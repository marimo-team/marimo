# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import dataclasses
import inspect
import os
import re
import sys
import textwrap
from tempfile import TemporaryDirectory
from typing import Any, Generator

import pytest

from marimo._ast.app import CellManager
from marimo._ast.cell import CellId_t
from marimo._config.config import DEFAULT_CONFIG
from marimo._messaging.mimetypes import KnownMimeType
from marimo._messaging.streams import (
    ThreadSafeStderr,
    ThreadSafeStdin,
    ThreadSafeStdout,
    ThreadSafeStream,
)
from marimo._output.formatters.formatters import register_formatters
from marimo._runtime import patches
from marimo._runtime.context import teardown_context
from marimo._runtime.context.kernel_context import initialize_kernel_context
from marimo._runtime.input_override import input_override
from marimo._runtime.marimo_pdb import MarimoPdb
from marimo._runtime.requests import AppMetadata, ExecutionRequest
from marimo._runtime.runtime import Kernel
from marimo._server.model import SessionMode

# register import hooks for third-party module formatters
register_formatters()


@dataclasses.dataclass
class _MockStream(ThreadSafeStream):
    """Captures the ops sent through the stream"""

    messages: list[tuple[str, dict[Any, Any]]] = dataclasses.field(
        default_factory=list
    )

    def write(self, op: str, data: dict[Any, Any]) -> None:
        self.messages.append((op, data))


class MockStdout(ThreadSafeStdout):
    """Captures the output sent through the stream"""

    def __init__(self, stream: _MockStream) -> None:
        super().__init__(stream)
        self.messages: list[str] = []

    def _write_with_mimetype(self, data: str, mimetype: KnownMimeType) -> int:
        del mimetype
        self.messages.append(data)
        return len(data)

    def __repr__(self) -> str:
        return "".join(self.messages)


class MockStderr(ThreadSafeStderr):
    """Captures the output sent through the stream"""

    messages: list[str] = dataclasses.field(default_factory=list)

    def __init__(self, stream: _MockStream) -> None:
        super().__init__(stream)
        self.messages: list[str] = []

    def _write_with_mimetype(self, data: str, mimetype: KnownMimeType) -> int:
        del mimetype
        self.messages.append(data)
        return len(data)

    def __repr__(self) -> str:
        # Error messages are commonly formatted for output in HTML
        return re.sub(r"<.*?>", "", "".join(self.messages))


class MockStdin(ThreadSafeStdin):
    """Echoes the prompt."""

    def __init__(self, stream: _MockStream) -> None:
        super().__init__(stream)
        self.messages: list[str] = []

    def _readline_with_prompt(self, prompt: str = "") -> str:
        return prompt


@dataclasses.dataclass
class MockedKernel:
    """Should only be created in fixtures b/c inits a runtime context"""

    stream: _MockStream = dataclasses.field(default_factory=_MockStream)

    def __post_init__(self) -> None:
        self.stdout = MockStdout(self.stream)
        self.stderr = MockStderr(self.stream)
        self.stdin = MockStdin(self.stream)
        self._main = sys.modules["__main__"]
        module = patches.patch_main_module(
            file=None, input_override=input_override
        )

        self.k = Kernel(
            stream=self.stream,
            stdout=self.stdout,
            stderr=self.stderr,
            stdin=self.stdin,
            cell_configs={},
            user_config=DEFAULT_CONFIG,
            app_metadata=AppMetadata(
                query_params={}, filename=None, cli_args={}
            ),
            debugger_override=MarimoPdb(stdout=self.stdout, stdin=self.stdin),
            enqueue_control_request=lambda _: None,
            module=module,
        )

        initialize_kernel_context(
            kernel=self.k,
            stream=self.stream,  # type: ignore
            stdout=self.stdout,  # type: ignore
            stderr=self.stderr,  # type: ignore
            virtual_files_supported=True,
            mode=SessionMode.EDIT,
        )

    def teardown(self) -> None:
        # must be called by fixtures that instantiate this
        teardown_context()
        self.stdout._watcher.stop()
        self.stderr._watcher.stop()
        if self.k.module_watcher is not None:
            self.k.module_watcher.stop()
        sys.modules["__main__"] = self._main


# fixture that provides a kernel (and tears it down)
@pytest.fixture
def k() -> Generator[Kernel, None, None]:
    mocked = MockedKernel()
    yield mocked.k
    mocked.teardown()


# kernel configured with runtime=lazy
@pytest.fixture
def lazy_kernel(k: Kernel) -> Kernel:
    k.execution_type = "relaxed"
    k.reactive_execution_mode = "lazy"
    return k


# kernel configured with strict execution
@pytest.fixture
def strict_kernel() -> Generator[Kernel, None, None]:
    mocked = MockedKernel()
    mocked.k.execution_type = "strict"
    mocked.k.reactive_execution_mode = "autorun"
    yield mocked.k
    mocked.teardown()


@pytest.fixture(params=["k", "strict_kernel"])
def execution_kernel(request: Any) -> Kernel:
    return request.getfixturevalue(request.param)


@pytest.fixture(params=["k", "strict_kernel", "lazy_kernel"])
def any_kernel(request: Any) -> Kernel:
    return request.getfixturevalue(request.param)


# fixture that wraps a kernel and other mocked objects
@pytest.fixture
def mocked_kernel() -> Generator[MockedKernel, None, None]:
    mocked = MockedKernel()
    yield mocked
    mocked.teardown()


# Installs an execution context without stream redirection
@pytest.fixture
def executing_kernel() -> Generator[Kernel, None, None]:
    mocked = MockedKernel()
    mocked.k.stdout = None
    mocked.k.stderr = None
    mocked.k.stdin = None
    with mocked.k._install_execution_context(cell_id="0"):
        yield mocked.k
    mocked.teardown()


@pytest.fixture
def temp_marimo_file() -> Generator[str, None, None]:
    tmp_dir = TemporaryDirectory()
    tmp_file = os.path.join(tmp_dir.name, "notebook.py")
    content = inspect.cleandoc(
        """
        import marimo
        app = marimo.App()

        @app.cell
        def __():
            import marimo as mo
            return mo,

        @app.cell
        def __(mo):
            slider = mo.ui.slider(0, 10)
            return slider,

        if __name__ == "__main__":
            app.run()
        """
    )

    try:
        with open(tmp_file, "w") as f:
            f.write(content)
        yield tmp_file
    finally:
        tmp_dir.cleanup()


@pytest.fixture
def temp_async_marimo_file() -> Generator[str, None, None]:
    tmp_dir = TemporaryDirectory()
    tmp_file = os.path.join(tmp_dir.name, "notebook.py")
    content = inspect.cleandoc(
        """
        import marimo
        app = marimo.App()

        @app.cell
        async def __():
            import asyncio
            await asyncio.sleep(0.1)
            return asyncio,

        if __name__ == "__main__":
            app.run()
        """
    )

    try:
        with open(tmp_file, "w") as f:
            f.write(content)
            f.flush()
        yield tmp_file
    finally:
        tmp_dir.cleanup()


@pytest.fixture
def temp_unparsable_marimo_file() -> Generator[str, None, None]:
    tmp_dir = TemporaryDirectory()
    tmp_file = os.path.join(tmp_dir.name, "notebook.py")
    content = inspect.cleandoc(
        """
        import marimo
        app = marimo.App()

        app._unparsable_cell(
            r\"""
            return
            \""",
            name="__"
        )

        app._unparsable_cell(
            r\"""
            partial_statement =
            \""",
            name="__"
        )

        @app.cell
        def __():
            valid_statement = 1
            return valid_statement,

        if __name__ == "__main__":
            app.run()
        """
    )

    try:
        with open(tmp_file, "w") as f:
            f.write(content)
            f.flush()
        yield tmp_file
    finally:
        tmp_dir.cleanup()


@pytest.fixture
def temp_marimo_file_with_md() -> Generator[str, None, None]:
    tmp_dir = TemporaryDirectory()
    tmp_file = os.path.join(tmp_dir.name, "notebook.py")
    content = inspect.cleandoc(
        """
        import marimo
        app = marimo.App()

        @app.cell
        def __(mo):
            control_dep = None
            mo.md("markdown")
            return control_dep

        @app.cell
        def __(mo, control_dep):
            control_dep
            mo.md(f"parameterized markdown {123}")
            return

        @app.cell
        def __():
            mo.md("plain markdown")
            return mo,

        @app.cell
        def __():
            import marimo as mo
            return mo,

        if __name__ == "__main__":
            app.run()
        """
    )

    try:
        with open(tmp_file, "w") as f:
            f.write(content)
        yield tmp_file
    finally:
        tmp_dir.cleanup()


@pytest.fixture
def temp_md_marimo_file() -> Generator[str, None, None]:
    tmp_dir = TemporaryDirectory()
    tmp_file = os.path.join(tmp_dir.name, "notebook.md")
    content = inspect.cleandoc(
        """
        ---
        title: Notebook
        marimo-version: 0.0.0
        ---

        # This is a markdown document.
        <!---->
        This is a another cell.

        ```{.python.marimo}
        import marimo as mo
        ```

        ```{.python.marimo}
        slider = mo.ui.slider(0, 10)
        ```
        """
    )

    try:
        with open(tmp_file, "w") as f:
            f.write(content)
        yield tmp_file
    finally:
        tmp_dir.cleanup()


# Factory to create ExecutionRequests and abstract away cell ID
class ExecReqProvider:
    def __init__(self) -> None:
        self.cell_manager = CellManager()

    def get(self, code: str) -> ExecutionRequest:
        key = self.cell_manager.create_cell_id()
        return ExecutionRequest(cell_id=key, code=textwrap.dedent(code))

    def get_with_id(self, cell_id: CellId_t, code: str) -> ExecutionRequest:
        return ExecutionRequest(cell_id=cell_id, code=textwrap.dedent(code))


# fixture that provides an ExecReqProvider
@pytest.fixture
def exec_req() -> ExecReqProvider:
    return ExecReqProvider()
