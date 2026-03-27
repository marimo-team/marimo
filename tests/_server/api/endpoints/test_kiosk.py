# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from tests._server.api.endpoints.ws_helpers import (
    HEADERS as _HEADERS,
    assert_kernel_ready_response,
    create_response,
)

if TYPE_CHECKING:
    from starlette.testclient import TestClient, WebSocketTestSession


HEADERS = {
    **_HEADERS,
    "Marimo-Session-Id": "123",
}


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

            # Send document transaction to reorder cells
            response = client.post(
                "/api/document/transaction",
                headers=HEADERS,
                json={
                    "changes": [
                        {
                            "type": "reorder-cells",
                            "cellIds": ["cell-123"],
                        }
                    ],
                },
            )
            assert response.status_code == 200, response.text

            # Assert kiosk session received the document transaction
            data = other_websocket.receive_json()
            assert data["op"] == "notebook-document-transaction"

            # Send run single cell
            response = client.post(
                "/api/kernel/run",
                headers=HEADERS,
                json={
                    "cell_ids": ["cell-3"],
                    "codes": ["print('Hello, cell-3')"],
                },
            )

            # Assert kiosk session received a focused cell notification
            data = _receive_until("focus-cell", other_websocket)
            assert data == {
                "op": "focus-cell",
                "data": {"cell_id": "cell-3"},
            }


def _receive_until(op: str, websocket: WebSocketTestSession) -> dict[str, Any]:
    while True:
        data = websocket.receive_json()
        if data["op"] == op:
            return data
