# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import json
from textwrap import dedent
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, Mock

import msgspec
import pytest

from marimo._ast.app_config import _AppConfig
from marimo._config.config import DEFAULT_CONFIG
from marimo._messaging.types import KernelMessage
from marimo._pyodide.pyodide_session import (
    AsyncQueueManager,
    PyodideBridge,
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
    FunctionCallRequest,
    InstallMissingPackagesRequest,
    ListSecretKeysRequest,
    PreviewDatasetColumnRequest,
    PreviewDataSourceConnectionRequest,
    PreviewSQLTableListRequest,
    PreviewSQLTableRequest,
    RenameRequest,
    SetCellConfigRequest,
    SetModelMessageRequest,
    SetUIElementValueRequest,
    StopRequest,
    SyncGraphRequest,
)
from marimo._server.model import SessionMode
from marimo._server.notebook import AppFileManager
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
        (
            '{"sourceType": "duckdb", "source": "test.db", "tableName": "users", "columnName": "id"}',
            PreviewDatasetColumnRequest,
        ),
        (
            '{"requestId": "req-1", "engine": "duckdb", "database": "test.db", '
            '"schema": "main", "tableName": "users"}',
            PreviewSQLTableRequest,
        ),
        (
            '{"requestId": "req-2", "engine": "duckdb", "database": "test.db", "schema": "main"}',
            PreviewSQLTableListRequest,
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
        (
            '{"modelId": "model-1", "message": {"state": {}, "bufferPaths": []}}',
            SetModelMessageRequest,
        ),
        (
            '{"functionCallId": "fc-1", "namespace": "test", "functionName": "foo", "args": {}}',
            FunctionCallRequest,
        ),
        # Requests with single or few required fields
        # DeleteCellRequest comes before PdbRequest
        # Note: Can't test PdbRequest since DeleteCellRequest will always match first
        ('{"cellId": "cell-1"}', DeleteCellRequest),
        ('{"code": "print(1)"}', ExecuteScratchpadRequest),
        (
            '{"cells": {"cell-1": "x=1"}, "runIds": ["cell-1"], "deleteIds": []}',
            SyncGraphRequest,
        ),
        ('{"filename": "test.py"}', RenameRequest),
        ('{"configs": {"cell-1": {"hide_code": true}}}', SetCellConfigRequest),
        ('{"requestId": "req-1"}', ListSecretKeysRequest),
        ('{"engine": "duckdb"}', PreviewDataSourceConnectionRequest),
        # Note: Can't test SetUserConfigRequest or ValidateSQLRequest uniquely
        # - SetUserConfigRequest requires a full MarimoConfig which is complex
        # - ValidateSQLRequest has requestId which matches ListSecretKeysRequest first
        # Empty objects - StopRequest matches first among the empty requests
        # Note: Can't test RefreshSecretsRequest, ClearCacheRequest, GetCacheInfoRequest,
        # or ExecuteStaleRequest since StopRequest will always match first (they all have no required fields)
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


def test_control_request_parsing_invalid() -> None:
    """Test that invalid JSON raises DecodeError."""
    with pytest.raises(msgspec.DecodeError):
        parse_wasm_control_request("invalid json")


async def test_async_queue_manager_close() -> None:
    """Test closing queues puts a StopRequest."""
    manager = AsyncQueueManager()
    manager.close_queues()

    request = await manager.control_queue.get()
    assert isinstance(request, StopRequest)


async def test_pyodide_session_on_message(
    pyodide_session: PyodideSession,
) -> None:
    """Test that _on_message calls all consumers."""
    mock_consumer1 = Mock()
    mock_consumer2 = Mock()

    pyodide_session.consumers = [mock_consumer1, mock_consumer2]

    test_msg: KernelMessage = {
        "op": "completed-run",
        "cell_id": CellId_t("test"),
    }
    pyodide_session._on_message(test_msg)

    mock_consumer1.assert_called_once_with(test_msg)
    mock_consumer2.assert_called_once_with(test_msg)


async def test_pyodide_session_put_completion_request(
    pyodide_session: PyodideSession,
) -> None:
    """Test putting completion requests."""
    from marimo._runtime.requests import CodeCompletionRequest

    completion_request = CodeCompletionRequest(
        id="test",
        document="test code",
        cell_id=CellId_t("test"),
    )

    pyodide_session.put_completion_request(completion_request)

    assert not pyodide_session._queue_manager.completion_queue.empty()
    result = await pyodide_session._queue_manager.completion_queue.get()
    assert result == completion_request


# ===== PyodideBridge Tests =====


@pytest.fixture
def pyodide_bridge(
    pyodide_session: PyodideSession,
) -> PyodideBridge:
    """Create a PyodideBridge instance for testing."""
    return PyodideBridge(session=pyodide_session)


def test_pyodide_bridge_init(pyodide_bridge: PyodideBridge) -> None:
    """Test PyodideBridge initialization."""
    assert pyodide_bridge.session is not None
    assert pyodide_bridge.file_system is not None


def test_pyodide_bridge_put_control_request(
    pyodide_bridge: PyodideBridge,
) -> None:
    """Test putting control requests through the bridge."""
    request_json = '{"cellIds": ["cell-1"], "codes": ["print(1)"]}'
    pyodide_bridge.put_control_request(request_json)

    assert not pyodide_bridge.session._queue_manager.control_queue.empty()


def test_pyodide_bridge_put_input(pyodide_bridge: PyodideBridge) -> None:
    """Test putting input through the bridge."""
    test_input = "test input"
    pyodide_bridge.put_input(test_input)

    assert not pyodide_bridge.session._queue_manager.input_queue.empty()


def test_pyodide_bridge_code_complete(pyodide_bridge: PyodideBridge) -> None:
    """Test code completion through the bridge."""
    request_json = '{"id": "test", "document": "test code", "cellId": "test"}'
    pyodide_bridge.code_complete(request_json)

    assert not pyodide_bridge.session._queue_manager.completion_queue.empty()


def test_pyodide_bridge_read_code(
    pyodide_bridge: PyodideBridge,
    pyodide_app_file: Path,
) -> None:
    """Test reading code through the bridge."""
    del pyodide_app_file
    result = pyodide_bridge.read_code()
    response = json.loads(result)

    assert "contents" in response
    assert "marimo.App()" in response["contents"]


async def test_pyodide_bridge_format(pyodide_bridge: PyodideBridge) -> None:
    """Test formatting code through the bridge."""
    request_json = json.dumps(
        {
            "codes": {"cell-1": "x=1+2"},
            "lineLength": 79,
        }
    )

    result = await pyodide_bridge.format(request_json)
    response = json.loads(result)

    assert "codes" in response
    assert "cell-1" in response["codes"]


def test_pyodide_bridge_save(
    pyodide_bridge: PyodideBridge,
    pyodide_app_file: Path,
) -> None:
    """Test saving notebook through the bridge."""
    request_json = json.dumps(
        {
            "cellIds": ["test"],
            "codes": ["# Updated code"],
            "names": ["_"],
            "configs": [{}],  # Must match length of cell_ids
            "filename": str(pyodide_app_file),
        }
    )

    pyodide_bridge.save(request_json)


def test_pyodide_bridge_save_app_config(
    pyodide_bridge: PyodideBridge,
    pyodide_app_file: Path,
) -> None:
    del pyodide_app_file
    """Test saving app config through the bridge."""
    request_json = json.dumps(
        {
            "config": {
                "width": "full",
            }
        }
    )

    # Should not raise
    pyodide_bridge.save_app_config(request_json)


def test_pyodide_bridge_save_user_config(
    pyodide_bridge: PyodideBridge,
) -> None:
    """Test saving user config through the bridge."""
    request_json = json.dumps(
        {
            "config": {
                "completion": {"activate_on_typing": True},
            }
        }
    )

    pyodide_bridge.save_user_config(request_json)

    # Should have put a SetUserConfigRequest in the queue
    assert not pyodide_bridge.session._queue_manager.control_queue.empty()


def test_pyodide_bridge_rename_file(
    pyodide_bridge: PyodideBridge,
    tmp_path: Path,
) -> None:
    """Test renaming file through the bridge."""
    new_filename = str(tmp_path / "renamed.py")
    pyodide_bridge.rename_file(new_filename)

    assert pyodide_bridge.session.app_manager.filename == new_filename


def test_pyodide_bridge_list_files(
    pyodide_bridge: PyodideBridge,
    tmp_path: Path,
) -> None:
    """Test listing files through the bridge."""
    # Create some test files
    (tmp_path / "test1.py").write_text("# test1")
    (tmp_path / "test2.py").write_text("# test2")

    request_json = json.dumps({"path": str(tmp_path)})
    result = pyodide_bridge.list_files(request_json)
    response = json.loads(result)

    assert "files" in response
    assert "root" in response
    assert response["root"] == str(tmp_path)


def test_pyodide_bridge_file_details(
    pyodide_bridge: PyodideBridge,
    tmp_path: Path,
) -> None:
    """Test getting file details through the bridge."""
    test_file = tmp_path / "test.py"
    test_file.write_text("# test")

    request_json = json.dumps({"path": str(test_file)})
    result = pyodide_bridge.file_details(request_json)
    response = json.loads(result)

    assert "file" in response
    assert "contents" in response
    assert response["file"]["path"] == str(test_file)


def test_pyodide_bridge_create_file(
    pyodide_bridge: PyodideBridge,
    tmp_path: Path,
) -> None:
    """Test creating file through the bridge."""
    import base64

    test_content = b"# new file"
    encoded_content = base64.b64encode(test_content).decode()

    request_json = json.dumps(
        {
            "path": str(tmp_path),
            "type": "file",
            "name": "new_file.py",
            "contents": encoded_content,
        }
    )

    result = pyodide_bridge.create_file_or_directory(request_json)
    response = json.loads(result)

    assert response["success"] is True
    assert (tmp_path / "new_file.py").exists()


def test_pyodide_bridge_delete_file(
    pyodide_bridge: PyodideBridge,
    tmp_path: Path,
) -> None:
    """Test deleting file through the bridge."""
    test_file = tmp_path / "to_delete.py"
    test_file.write_text("# delete me")

    request_json = json.dumps({"path": str(test_file)})
    result = pyodide_bridge.delete_file_or_directory(request_json)
    response = json.loads(result)

    assert response["success"] is True
    assert not test_file.exists()


def test_pyodide_bridge_move_file(
    pyodide_bridge: PyodideBridge,
    tmp_path: Path,
) -> None:
    """Test moving file through the bridge."""
    test_file = tmp_path / "old.py"
    test_file.write_text("# move me")
    new_path = tmp_path / "new.py"

    request_json = json.dumps(
        {
            "path": str(test_file),
            "newPath": str(new_path),
        }
    )

    result = pyodide_bridge.move_file_or_directory(request_json)
    response = json.loads(result)

    assert response["success"] is True
    assert not test_file.exists()
    assert new_path.exists()


def test_pyodide_bridge_update_file(
    pyodide_bridge: PyodideBridge,
    tmp_path: Path,
) -> None:
    """Test updating file through the bridge."""
    test_file = tmp_path / "update.py"
    test_file.write_text("# old content")

    new_content = "# new content"
    request_json = json.dumps(
        {
            "path": str(test_file),
            "contents": new_content,
        }
    )

    result = pyodide_bridge.update_file(request_json)
    response = json.loads(result)

    assert response["success"] is True
    assert test_file.read_text() == new_content


def test_pyodide_bridge_export_html(
    pyodide_bridge: PyodideBridge,
) -> None:
    """Test exporting HTML through the bridge."""
    request_json = json.dumps(
        {
            "download": False,
            "files": [],
            "includeCode": True,
        }
    )

    result = pyodide_bridge.export_html(request_json)
    html = json.loads(result)

    assert isinstance(html, str)
    # HTML should contain marimo-related content
    assert len(html) > 0


def test_pyodide_bridge_export_markdown(
    pyodide_bridge: PyodideBridge,
) -> None:
    """Test exporting markdown through the bridge."""
    result = pyodide_bridge.export_markdown("{}")
    markdown = json.loads(result)

    assert isinstance(markdown, str)
    assert len(markdown) > 0


async def test_pyodide_bridge_read_snippets(
    pyodide_bridge: PyodideBridge,
) -> None:
    """Test reading snippets through the bridge."""
    result = await pyodide_bridge.read_snippets()
    data = json.loads(result)

    assert isinstance(data, dict)
    assert "snippets" in data
    assert isinstance(data["snippets"], list)
