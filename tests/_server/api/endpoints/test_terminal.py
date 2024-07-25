# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest
from starlette.websockets import WebSocketDisconnect

from marimo._server.model import SessionMode
from marimo._server.sessions import SessionManager
from tests._server.conftest import get_session_manager

if TYPE_CHECKING:
    from starlette.testclient import TestClient

is_windows = sys.platform == "win32"


@pytest.mark.skipif(is_windows, reason="Skip on Windows")
def test_terminal_ws(client: TestClient) -> None:
    with client.websocket_connect("/terminal/ws") as websocket:
        # Send echo message
        websocket.send_text("echo hello")
        data = websocket.receive_text()
        assert "echo hello" in data


def test_terminal_ws_not_allowed_in_run(client: TestClient) -> None:
    session_manager: SessionManager = get_session_manager(client)
    session_manager.mode = SessionMode.RUN
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/terminal/ws") as websocket:
            websocket.send_text("echo hello")
    session_manager.mode = SessionMode.EDIT
