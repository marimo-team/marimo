# Copyright 2024 Marimo. All rights reserved.
from typing import cast

from starlette.testclient import TestClient

from marimo._server.sessions import SessionManager


def test_ws(client: TestClient) -> None:
    cast(SessionManager, client.app.state.session_manager)
    with client.websocket_connect("/ws?session_id=123") as websocket:
        data = websocket.receive_text()
        assert (
            data
            == '{"op": "kernel-ready", "data": {"codes": ["import marimo as mo"], "names": ["my_cell"], "layout": null, "configs": [{"disabled": false, "hide_code": true}]}}'  # noqa: E501
        )
        client.post("/api/kernel/shutdown")
