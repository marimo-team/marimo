# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from marimo._server.model import ConnectionState
from marimo._server.sessions import SessionMode
from tests._server.conftest import get_session_manager
from tests._server.mocks import token_header

if TYPE_CHECKING:
    from starlette.testclient import TestClient

HEADERS = {
    **token_header("fake-token"),
}


async def test_remove_session_in_run_mode_with_0_ttl(
    client: TestClient,
) -> None:
    """Test that sessions get destroyed in run mode"""
    session_manager = get_session_manager(client)
    session_manager.ttl_seconds = 0
    session_manager.mode = SessionMode.RUN

    # Create initial session
    with client.websocket_connect("/ws?session_id=123") as websocket:
        data = websocket.receive_text()
        assert data
        assert session_manager.get_session("123") is not None

    # Session should exist
    session = session_manager.get_session("123")
    assert session is None

    session_manager.mode = SessionMode.EDIT


async def test_remove_session_in_run_mode_with_small_ttl(
    client: TestClient,
) -> None:
    """Test that sessions get destroyed in run mode"""
    session_manager = get_session_manager(client)
    session_manager.ttl_seconds = 1
    session_manager.mode = SessionMode.RUN

    # Create initial session
    with client.websocket_connect("/ws?session_id=123") as websocket:
        data = websocket.receive_text()
        assert data
        assert session_manager.get_session("123") is not None

    # Session should exist
    session = session_manager.get_session("123")
    assert session is not None
    assert session.connection_state() == ConnectionState.ORPHANED

    await asyncio.sleep(2)

    # Session should be destroyed after TTL
    assert session_manager.get_session("123") is None

    session_manager.mode = SessionMode.EDIT


async def test_remove_session_in_edit_mode(client: TestClient) -> None:
    """Test that sessions persist in edit mode"""
    session_manager = get_session_manager(client)
    session_manager.ttl_seconds = 0
    session_manager.mode = SessionMode.EDIT

    # Create initial session
    with client.websocket_connect("/ws?session_id=123") as websocket:
        data = websocket.receive_text()
        assert data
        assert session_manager.get_session("123") is not None

    # Session should exist
    assert session_manager.get_session("123") is not None

    await asyncio.sleep(0.5)

    # Session should still exist after websocket closes in edit mode
    assert session_manager.get_session("123") is not None
