# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from textwrap import dedent
from typing import TYPE_CHECKING, Callable
from unittest.mock import MagicMock

import pytest

from marimo._ast.app_config import _AppConfig
from marimo._config.config import DEFAULT_CONFIG
from marimo._messaging.types import KernelMessage
from marimo._pyodide.pyodide_session import AsyncQueueManager, PyodideSession
from marimo._runtime.requests import (
    AppMetadata,
    ExecuteMultipleRequest,
    SetUIElementValueRequest,
    StopRequest,
)
from marimo._server.file_manager import AppFileManager
from marimo._server.model import SessionMode
from marimo._types.ids import CellId_t, UIElementId

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path


@pytest.fixture
def mock_on_write() -> Callable[[KernelMessage], None]:
    def _on_write(msg: KernelMessage) -> None:
        pass

    return _on_write


@pytest.fixture
def pyodide_app_file(tmp_path: Path) -> Path:
    filename = tmp_path / "test.py"
    filename.write_text(
        """
import marimo

app = marimo.App()

@app.cell
def _():
    "Hello, world!"
    return
"""
    )
    return filename


@pytest.fixture
def mock_pyodide_http() -> Generator[MagicMock, None, None]:
    import sys

    mock = MagicMock()
    sys.modules["pyodide_http"] = mock
    mock.patch_urllib.return_value = None
    yield mock
    del sys.modules["pyodide_http"]


@pytest.fixture
def mock_pyodide() -> Generator[MagicMock, None, None]:
    import sys
    from types import ModuleType

    # Create a proper module structure for pyodide
    mock = MagicMock(spec=ModuleType)
    mock.code = MagicMock(spec=ModuleType)
    mock.code.find_imports = MagicMock(
        return_value=["numpy", "pandas", "sklearn"]
    )

    # Save original module if it exists
    original_module = sys.modules.get("pyodide", None)

    # Install our mock
    sys.modules["pyodide"] = mock
    sys.modules["pyodide.code"] = mock

    yield mock

    # Restore original state
    if original_module is not None:
        sys.modules["pyodide"] = original_module
    else:
        del sys.modules["pyodide"]


@pytest.fixture
def pyodide_session(
    mock_on_write: Callable[[KernelMessage], None],
    pyodide_app_file: Path,
) -> PyodideSession:
    return PyodideSession(
        app=AppFileManager(filename=str(pyodide_app_file)),
        mode=SessionMode.EDIT,
        on_write=mock_on_write,
        app_metadata=AppMetadata(
            query_params={},
            cli_args={},
            app_config=_AppConfig(),
            filename=str(pyodide_app_file),
        ),
        user_config=DEFAULT_CONFIG,
    )


async def test_async_queue_manager() -> None:
    async_queue_manager = AsyncQueueManager()
    # Test putting and getting from queues
    stop_request = StopRequest()
    set_ui_element_request = SetUIElementValueRequest(
        object_ids=[UIElementId("test")], values=["test"]
    )

    async_queue_manager.control_queue.put_nowait(stop_request)
    async_queue_manager.set_ui_element_queue.put_nowait(set_ui_element_request)

    assert await async_queue_manager.control_queue.get() == stop_request
    assert (
        await async_queue_manager.set_ui_element_queue.get()
        == set_ui_element_request
    )


async def test_pyodide_session_start(
    pyodide_session: PyodideSession,
    mock_pyodide_http: MagicMock,
) -> None:
    # Test starting the session
    start_task = asyncio.create_task(pyodide_session.start())
    await asyncio.sleep(0)  # Let the task start
    assert pyodide_session.kernel_task is not None
    mock_pyodide_http.patch_urllib.assert_called_once()
    pyodide_session.kernel_task.stop()
    start_task.cancel()
    try:
        await start_task
    except asyncio.CancelledError:
        pass


async def test_pyodide_session_put_control_request(
    pyodide_session: PyodideSession,
) -> None:
    # Test putting control requests
    execution_request = ExecuteMultipleRequest(
        cell_ids=[CellId_t("test")],
        codes=["test"],
    )
    set_ui_element_request = SetUIElementValueRequest(
        object_ids=[UIElementId("test")], values=["test"]
    )

    pyodide_session.put_control_request(execution_request)
    pyodide_session.put_control_request(set_ui_element_request)

    assert not pyodide_session._queue_manager.control_queue.empty()
    assert not pyodide_session._queue_manager.set_ui_element_queue.empty()


async def test_pyodide_session_find_packages(
    pyodide_session: PyodideSession,
    mock_pyodide: MagicMock,
) -> None:
    # Test finding packages in code
    code = dedent(
        """
        import numpy as np
        import pandas as pd
        from sklearn.linear_model import LinearRegression
        """
    )

    packages = pyodide_session.find_packages(code)
    # sklearn gets converted to scikit-learn
    assert sorted(packages) == sorted(["numpy", "pandas", "scikit-learn"])
    mock_pyodide.code.find_imports.assert_called_once_with(code)


async def test_pyodide_session_find_packages_with_script_metadata(
    pyodide_session: PyodideSession,
    mock_pyodide: MagicMock,
) -> None:
    # Test finding packages in code
    code = dedent(
        """
        # /// script
        # dependencies = [
        #     "foo",
        #     "bar==1.0.0",
        #     "baz>=2.0.0",
        # ]
        # ///

        import numpy as np
        import pandas as pd
        """
    )

    packages = pyodide_session.find_packages(code)
    assert sorted(packages) == sorted(["foo", "bar", "baz"])
    mock_pyodide.code.find_imports.assert_not_called()


async def test_pyodide_session_put_input(
    pyodide_session: PyodideSession,
) -> None:
    # Test putting input
    input_text = "test input"
    pyodide_session.put_input(input_text)

    assert not pyodide_session._queue_manager.input_queue.empty()
    assert await pyodide_session._queue_manager.input_queue.get() == input_text
