# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from tests._server.api.endpoints.ws_helpers import (
    HEADERS as _HEADERS,
    assert_kernel_ready_response,
)

if TYPE_CHECKING:
    from starlette.testclient import TestClient

HEADERS = {
    **_HEADERS,
    "Marimo-Session-Id": "123",
}


def test_create_cell_with_missing_anchor_is_appended(
    client: TestClient,
) -> None:
    with client.websocket_connect(
        "/ws?session_id=123", headers=_HEADERS
    ) as websocket:
        assert_kernel_ready_response(websocket.receive_json())

        response = client.post(
            "/api/document/transaction",
            headers=HEADERS,
            json={
                "changes": [
                    {
                        "type": "create-cell",
                        "cellId": "new1",
                        "code": "",
                        "name": "_",
                        "config": {
                            "column": None,
                            "disabled": False,
                            "hideCode": False,
                        },
                        "after": "ghost_cell_xyz",
                    }
                ],
            },
        )
        assert response.status_code == 200, response.text

        sm = client.app.state.session_manager
        session = next(iter(sm.sessions.values()))
        assert session.document.cell_ids[-1] == "new1"


def test_delete_of_missing_cell_is_a_no_op(client: TestClient) -> None:
    with client.websocket_connect(
        "/ws?session_id=123", headers=_HEADERS
    ) as websocket:
        assert_kernel_ready_response(websocket.receive_json())

        sm = client.app.state.session_manager
        session = next(iter(sm.sessions.values()))
        cell_ids_before = session.document.cell_ids

        response = client.post(
            "/api/document/transaction",
            headers=HEADERS,
            json={
                "changes": [
                    {"type": "delete-cell", "cellId": "ghost_cell_xyz"}
                ],
            },
        )
        assert response.status_code == 200, response.text
        assert session.document.cell_ids == cell_ids_before
