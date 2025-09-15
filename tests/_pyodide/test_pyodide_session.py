# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from textwrap import dedent
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from marimo._ast.app_config import _AppConfig
from marimo._config.config import DEFAULT_CONFIG
from marimo._messaging.types import KernelMessage
from marimo._pyodide.pyodide_session import (
    AsyncQueueManager,
    PyodideSession,
    parse_wasm_control_request,
)
from marimo._runtime.context.types import teardown_context
from marimo._runtime.requests import (
    AppMetadata,
    CreationRequest,
    DeleteCellRequest,
    ExecuteMultipleRequest,
    ExecuteScratchpadRequest,
    InstallMissingPackagesRequest,
    ListSecretKeysRequest,
    RenameRequest,
    SetCellConfigRequest,
    SetUIElementValueRequest,
    StopRequest,
)
from marimo._server.file_manager import AppFileManager
from marimo._server.model import SessionMode
from marimo._types.ids import CellId_t, UIElementId

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator
    from pathlib import Path


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
    mock.patch_all.return_value = None
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
async def pyodide_session(
    pyodide_app_file: Path,
) -> AsyncGenerator[PyodideSession, None]:
    def _on_write(msg: KernelMessage) -> None:
        pass

    session = PyodideSession(
        app=AppFileManager(filename=str(pyodide_app_file)),
        mode=SessionMode.EDIT,
        on_write=_on_write,
        app_metadata=AppMetadata(
            query_params={},
            cli_args={},
            app_config=_AppConfig(),
            filename=str(pyodide_app_file),
        ),
        user_config=DEFAULT_CONFIG,
    )
    yield session
    teardown_context()


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
    mock_pyodide_http.patch_all.assert_called_once()
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


@pytest.mark.parametrize(
    ("json_payload", "expected_type"),
    [
        # Most specific requests with many required fields
        (
            '{"executionRequests": [{"cellId": "cell-1", "code": "print(1)"}], '
            '"setUiElementValueRequest": {"objectIds": [], "values": []}, '
            '"autoRun": true}',
            CreationRequest,
        ),
        (
            '{"cellIds": ["cell-1"], "codes": ["print(1)"]}',
            ExecuteMultipleRequest,
        ),
        (
            '{"manager": "pip", "packages": ["numpy"], "versions": {}}',
            InstallMissingPackagesRequest,
        ),
        # SetUIElementValueRequest - has specific fields
        (
            '{"objectIds": ["test-1"], "values": [42], "token": "test-token"}',
            SetUIElementValueRequest,
        ),
        (
            '{"objectIds": ["test-1"], "values": [42]}',  # Without token
            SetUIElementValueRequest,
        ),
        # Requests with single required fields
        # DeleteCellRequest comes before PdbRequest
        # Note: Can't test PdbRequest since DeleteCellRequest will always match first
        ('{"cellId": "cell-1"}', DeleteCellRequest),
        ('{"code": "print(1)"}', ExecuteScratchpadRequest),
        ('{"filename": "test.py"}', RenameRequest),
        ('{"configs": {"cell-1": {"hide_code": true}}}', SetCellConfigRequest),
        ('{"requestId": "req-1"}', ListSecretKeysRequest),
        # Empty objects - StopRequest matches first among the empty requests
        # Note: Can't test RefreshSecretsRequest since StopRequest will always match first
        ("{}", StopRequest),
    ],
)
def test_control_request_parsing_order(
    json_payload: str, expected_type: type
) -> None:
    """Test that ControlRequest types are parsed in the correct order.

    This is critical for WASM/Pyodide where we iterate through types until
    one successfully parses. Types with overlapping structures must be
    ordered correctly.
    """

    parsed = parse_wasm_control_request(json_payload)
    assert type(parsed) is expected_type, (
        f"Expected {expected_type.__name__} but got {type(parsed).__name__} "
        f"for payload: {json_payload}"
    )
