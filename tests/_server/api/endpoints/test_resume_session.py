# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import asdict
from typing import TYPE_CHECKING, Any, Optional

from marimo._config.manager import UserConfigManager
from marimo._messaging.ops import CellOp, KernelCapabilities, KernelReady
from marimo._server.sessions import Session
from marimo._types.ids import SessionId
from marimo._utils.parse_dataclass import parse_raw
from tests._server.conftest import get_session_manager
from tests._server.mocks import token_header

if TYPE_CHECKING:
    from starlette.testclient import TestClient


def create_response(
    partial_response: dict[str, Any],
) -> dict[str, Any]:
    response: dict[str, Any] = {
        "cell_ids": ["Hbol"],
        "codes": ["import marimo as mo"],
        "names": ["__"],
        "layout": None,
        "resumed": False,
        "ui_values": {},
        "last_executed_code": {},
        "last_execution_time": {},
        "kiosk": False,
        "configs": [{"disabled": False, "hide_code": False}],
        "app_config": {"width": "full"},
        "capabilities": asdict(KernelCapabilities()),
    }
    response.update(partial_response)
    return response


def headers(session_id: str) -> dict[str, str]:
    return {
        "Marimo-Session-Id": session_id,
        **token_header("fake-token"),
    }


HEADERS = {
    **token_header("fake-token"),
}


def assert_kernel_ready_response(
    raw_data: dict[str, Any], response: dict[str, Any]
) -> None:
    data = parse_raw(raw_data["data"], KernelReady)
    expected = parse_raw(response, KernelReady)
    assert data.cell_ids == expected.cell_ids
    assert data.codes == expected.codes
    assert data.names == expected.names
    assert data.layout == expected.layout
    assert data.resumed == expected.resumed
    assert data.ui_values == expected.ui_values
    assert data.configs == expected.configs
    assert data.app_config == expected.app_config
    assert data.last_execution_time == expected.last_execution_time
    assert data.capabilities == expected.capabilities


def get_session(
    client: TestClient, session_id: SessionId
) -> Optional[Session]:
    return get_session_manager(client).get_session(session_id)


def test_refresh_session(client: TestClient) -> None:
    with client.websocket_connect("/ws?session_id=123") as websocket:
        data = websocket.receive_json()
        assert_kernel_ready_response(data, create_response({}))

    # Check the session still exists after closing the websocket
    session = get_session(client, SessionId("123"))
    assert session
    session_view = session.session_view

    # Mimic cell execution time save
    cell_op = CellOp("Hbol")
    session_view.save_execution_time(cell_op, "start")
    time.sleep(0.123)
    session_view.save_execution_time(cell_op, "end")
    last_exec_time = session_view.last_execution_time["Hbol"]

    # New session with new ID (simulates refresh)
    # We should resume the current session
    with client.websocket_connect("/ws?session_id=456") as websocket:
        # First message is the kernel reconnected
        data = websocket.receive_json()
        assert data == {"op": "reconnected", "data": {}}
        # Resume the session
        data = websocket.receive_json()
        assert_kernel_ready_response(
            data,
            create_response(
                {
                    "resumed": True,
                    "last_execution_time": {"Hbol": last_exec_time},
                }
            ),
        )
        # Send a value to the kernel
        response = client.post(
            "/api/kernel/set_ui_element_value",
            headers=headers("456"),
            json={
                "object_ids": ["ui-element-1", "ui-element-2"],
                "values": ["value1", "value2"],
            },
        )
        assert response.status_code == 200, response.text

    # Check the session switch IDs
    assert not get_session(client, "123")
    assert get_session(client, "456")

    # New session again
    # We should not resume the current session with the new values
    with client.websocket_connect("/ws?session_id=789") as websocket:
        # First message is the kernel reconnected
        data = websocket.receive_json()
        assert data == {"op": "reconnected", "data": {}}
        # Resume the session
        data = websocket.receive_json()
        assert_kernel_ready_response(
            data,
            create_response(
                {
                    "ui_values": {
                        "ui-element-1": "value1",
                        "ui-element-2": "value2",
                    },
                    "resumed": True,
                    "last_execution_time": {"Hbol": last_exec_time},
                }
            ),
        )
        assert response.status_code == 200, response.text

    # Check the session switch IDs
    assert not get_session(client, "456")
    assert get_session(client, "789")

    # Shutdown the kernel
    client.post("/api/kernel/shutdown", headers=HEADERS)


def test_save_session(client: TestClient) -> None:
    filename = (
        get_session_manager(client)
        .file_router.get_single_app_file_manager()
        .filename
    )
    with client.websocket_connect("/ws?session_id=123") as websocket:
        data = websocket.receive_json()
        assert_kernel_ready_response(data, create_response({}))
        # Send save request
        client.post(
            "/api/kernel/save",
            headers=headers("123"),
            json={
                "cell_ids": ["2", "1"],
                "filename": filename,
                "codes": [
                    "slider = mo.ui.slider(0, 100)",
                    "import marimo as mo",
                ],
                "names": ["cell_0", "cell_1"],
                "configs": [
                    {
                        "hideCode": True,
                        "disabled": True,
                    },
                    {
                        "hideCode": False,
                        "disabled": False,
                    },
                ],
            },
        )

    # Check the session still exists after closing the websocket
    assert get_session(client, "123")

    # New session with new ID (simulates refresh)
    # We should resume the current session
    with client.websocket_connect("/ws?session_id=456") as websocket:
        # First message is the kernel reconnected
        data = websocket.receive_json()
        assert data == {"op": "reconnected", "data": {}}
        # Resume the session
        data = websocket.receive_json()
        assert_kernel_ready_response(
            data,
            create_response(
                {
                    # The cell IDs that were saved should be the ones that are
                    # resumed
                    "cell_ids": ["2", "1"],
                    "names": ["cell_0", "cell_1"],
                    "codes": [
                        "slider = mo.ui.slider(0, 100)",
                        "import marimo as mo",
                    ],
                    "configs": [
                        {
                            "hideCode": True,
                            "disabled": True,
                        },
                        {
                            "hideCode": False,
                            "disabled": False,
                        },
                    ],
                    "resumed": True,
                }
            ),
        )

    # Check the session switch IDs
    assert not get_session(client, "123")
    assert get_session(client, "456")

    # Shutdown the kernel
    client.post("/api/kernel/shutdown", headers=HEADERS)


def test_save_config(client: TestClient) -> None:
    with client.websocket_connect("/ws?session_id=123") as websocket:
        data = websocket.receive_json()
        assert_kernel_ready_response(data, create_response({}))
        # Send save request
        client.post(
            "/api/kernel/save_app_config",
            headers=headers("123"),
            json={
                "config": {"width": "full"},
            },
        )

    # Check the session still exists after closing the websocket
    session = get_session(client, "123")
    assert session
    assert session.app_file_manager.app.config.width == "full"

    # Loading index page should have the new config
    response = client.get("/")
    assert response.status_code == 200
    assert '"width": "full"' in response.text

    # Shutdown the kernel
    client.post("/api/kernel/shutdown", headers=HEADERS)


def test_restart_session(client: TestClient) -> None:
    with client.websocket_connect("/ws?session_id=123") as websocket:
        data = websocket.receive_json()
        assert_kernel_ready_response(data, create_response({}))

    # Restart the session
    response = client.post(
        "/api/kernel/restart_session",
        headers=headers("123"),
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"success": True}

    # Check the session still exists after closing the websocket
    assert not get_session(client, "123")

    # New session with new ID (simulates refresh)
    # We start a new session
    with client.websocket_connect("/ws?session_id=456") as websocket:
        # First message is the kernel reconnected
        data = websocket.receive_json()
        assert_kernel_ready_response(
            data,
            create_response({}),
        )

    # Shutdown the kernel
    client.post("/api/kernel/shutdown", headers=HEADERS)


def test_resume_session_with_watch(client: TestClient) -> None:
    session_manager = get_session_manager(client)
    session_manager.watch = True

    with client.websocket_connect("/ws?session_id=123") as websocket:
        data = websocket.receive_json()
        assert_kernel_ready_response(data, create_response({}))

        # Write to the notebook file to trigger a reload
        # we write it as the second to last cell
        filename = session_manager.file_router.get_unique_file_key()
        assert filename
        with open(filename, "r+") as f:
            content = f.read()
            last_cell_pos = content.rindex("@app.cell")
            f.seek(last_cell_pos)
            f.write(
                "\n@app.cell\ndef _(): x=10; x\n" + content[last_cell_pos:]
            )
            f.close()

        data = websocket.receive_json()
        assert data == {
            "op": "update-cell-ids",
            "data": {"cell_ids": ["MJUe", "Hbol"]},
        }
        data = websocket.receive_json()
        assert data == {
            "op": "update-cell-codes",
            "data": {
                "cell_ids": ["MJUe"],
                "code_is_stale": False,
                "codes": ["x=10; x"],
            },
        }

    # Resume session with new ID (simulates refresh)
    # watcher_on_save is 'autorun', so we should expect the cell to be run
    with client.websocket_connect("/ws?session_id=456") as websocket:
        # First message is the kernel reconnected
        data = websocket.receive_json()
        assert data == {"op": "reconnected", "data": {}}

        # Check for KernelReady message
        data = websocket.receive_json()
        assert parse_raw(data["data"], KernelReady)
        messages: list[dict[str, Any]] = []

        # Wait for update-cell-codes message
        while True:
            data = websocket.receive_json()
            messages.append(data)
            if data["op"] == "update-cell-ids":
                break

        # 3 messages:
        # 1. banner
        # 2. update-cell-ids
        assert len(messages) == 2
        assert messages[0]["op"] == "banner"
        assert messages[1] == {
            "op": "update-cell-ids",
            "data": {"cell_ids": ["MJUe", "Hbol"]},
        }

    session = get_session(client, "456")
    assert session
    session_view = session.session_view
    assert session_view.last_executed_code == {"MJUe": "x=10; x"}

    session_manager.watch = False
    client.post("/api/kernel/shutdown", headers=HEADERS)


@contextmanager
def without_autorun_on_save(config: UserConfigManager):
    prev_config = config.get_config()
    try:
        config.save_config({"runtime": {"watcher_on_save": "lazy"}})
        yield
    finally:
        config.save_config(prev_config)
