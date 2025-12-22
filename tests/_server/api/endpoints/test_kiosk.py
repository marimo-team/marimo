# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

import pytest

from marimo._messaging.msgspec_encoder import asdict
from marimo._messaging.notifcation import KernelCapabilities, KernelReady
from marimo._utils.parse_dataclass import parse_raw
from tests._server.mocks import token_header

if TYPE_CHECKING:
    from starlette.testclient import TestClient, WebSocketTestSession


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


HEADERS = {
    **token_header("fake-token"),
    "Marimo-Session-Id": "123",
}


def assert_kernel_ready_response(
    raw_data: dict[str, Any], response: Optional[dict[str, Any]] = None
) -> None:
    if response is None:
        response = create_response({})
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
    assert data.kiosk == expected.kiosk
    assert data.capabilities == expected.capabilities


def assert_parse_ready_response(raw_data: dict[str, Any]) -> None:
    data = parse_raw(raw_data["data"], KernelReady)
    assert data is not None


@pytest.mark.skip
async def test_connect_kiosk_with_session(client: TestClient) -> None:
    # Create the first session
    with client.websocket_connect("/ws?session_id=123") as websocket:
        data = websocket.receive_json()
        assert_kernel_ready_response(data)

        # Connect in kiosk mode
        with client.websocket_connect(
            "/ws?session_id=456&kiosk=true"
        ) as other_websocket:
            data = other_websocket.receive_json()
            assert_kernel_ready_response(
                data, create_response({"kiosk": True, "resumed": True})
            )

            # Send sync cell_ids
            response = client.post(
                "/api/kernel/sync/cell_ids",
                headers=HEADERS,
                json={"cell_ids": ["cell-123"]},
            )
            assert response.status_code == 200, response.text

            # Assert kiosk session received the sync cell_ids
            data = other_websocket.receive_json()
            assert data == {
                "op": "update-cell-ids",
                "data": {"cell_ids": ["cell-123"]},
            }

            # Send run cell
            response = client.post(
                "/api/kernel/run",
                headers=HEADERS,
                json={
                    "cell_ids": ["cell-1", "cell-2"],
                    "codes": [
                        "print('Hello, cell-1')",
                        "print('Hello, cell-2')",
                    ],
                },
            )

            # Assert kiosk session received the updated cell codes
            data = other_websocket.receive_json()
            assert data == {
                "op": "update-cell-codes",
                "data": {
                    "cell_ids": ["cell-1", "cell-2"],
                    "codes": [
                        "print('Hello, cell-1')",
                        "print('Hello, cell-2')",
                    ],
                },
            }

            # Send run single cell
            response = client.post(
                "/api/kernel/run",
                headers=HEADERS,
                json={
                    "cell_ids": ["cell-3"],
                    "codes": ["print('Hello, cell-3')"],
                },
            )

            # Assert kiosk session received the updated cell codes
            data = _receive_until("update-cell-codes", other_websocket)
            assert data == {
                "op": "update-cell-codes",
                "data": {
                    "cell_ids": ["cell-3"],
                    "codes": ["print('Hello, cell-3')"],
                    "code_is_stale": False,
                },
            }
            # And a focused cell
            data = _receive_until("focus-cell", other_websocket)
            assert data == {
                "op": "focus-cell",
                "data": {"cell_id": "cell-3"},
            }

    client.post("/api/kernel/shutdown", headers=HEADERS)


def _receive_until(op: str, websocket: WebSocketTestSession) -> dict[str, Any]:
    while True:
        data = websocket.receive_json()
        if data["op"] == op:
            return data
