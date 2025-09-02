# Copyright 2024 Marimo. All rights reserved.
"""
Tests for MCP endpoint router.

Tests the MCPRouter ASGI forwarding behavior, including handler lookup
and basic ASGI protocol compliance.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from marimo._server.api.deps import AppStateBase
from marimo._server.api.endpoints.mcp import MCPRouter


class TestMCPRouter:
    """Test MCPRouter ASGI forwarding functionality."""

    async def test_mcp_handler_not_available(self):
        """Test 404 response when mcp_handler is None."""
        router = MCPRouter()

        # Mock app state with no mcp_handler
        mock_app = MagicMock()
        mock_app_state = MagicMock()
        mock_app_state.mcp_handler = None

        with pytest.MonkeyPatch().context() as m:
            m.setattr(AppStateBase, "from_app", lambda _app: mock_app_state)

            # Mock ASGI scope, receive, send
            scope = {"app": mock_app, "type": "http", "method": "POST"}
            receive = AsyncMock()
            send = AsyncMock()

            await router(scope, receive, send)

            # Verify 404 response
            send.assert_any_call(
                {
                    "type": "http.response.start",
                    "status": 404,
                    "headers": [(b"content-type", b"text/plain")],
                }
            )
            send.assert_any_call(
                {"type": "http.response.body", "body": b"MCP not available"}
            )

    async def test_mcp_handler_forwards_asgi(self):
        """Test ASGI forwarding when handler exists."""
        router = MCPRouter()

        # Track forwarded calls
        forwarded_calls = []

        async def mock_mcp_handler(scope, receive, send):
            forwarded_calls.append((scope, receive, send))
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [],
                }
            )
            await send({"type": "http.response.body", "body": b"forwarded"})

        # Mock app state with mcp_handler
        mock_app = MagicMock()
        mock_app_state = MagicMock()
        mock_app_state.mcp_handler = mock_mcp_handler

        with pytest.MonkeyPatch().context() as m:
            m.setattr(AppStateBase, "from_app", lambda _app: mock_app_state)

            scope = {"app": mock_app, "type": "http", "method": "POST"}
            receive = AsyncMock()
            send = AsyncMock()

            await router(scope, receive, send)

            # Verify forwarding occurred
            assert len(forwarded_calls) == 1
            forwarded_scope, forwarded_receive, forwarded_send = (
                forwarded_calls[0]
            )

            # Verify scope is passed through
            assert forwarded_scope is scope
            assert forwarded_receive is receive
            assert forwarded_send is send

    async def test_mcp_handler_no_app_in_scope(self):
        """Test behavior when no app in scope."""
        router = MCPRouter()

        # Scope without app
        scope = {"type": "http", "method": "POST"}
        receive = AsyncMock()
        send = AsyncMock()

        await router(scope, receive, send)

        # Should return 404 when no app
        send.assert_any_call(
            {
                "type": "http.response.start",
                "status": 404,
                "headers": [(b"content-type", b"text/plain")],
            }
        )
        send.assert_any_call(
            {"type": "http.response.body", "body": b"MCP not available"}
        )

    async def test_app_state_from_app_exception(self):
        """Test behavior when AppStateBase.from_app raises exception."""
        router = MCPRouter()

        mock_app = MagicMock()

        with pytest.MonkeyPatch().context() as m:
            # Mock from_app to raise an exception
            def failing_from_app(_app):
                raise AttributeError("No app state")

            m.setattr(AppStateBase, "from_app", failing_from_app)

            scope = {"app": mock_app, "type": "http", "method": "POST"}
            receive = AsyncMock()
            send = AsyncMock()

            # Exception should bubble up since MCPRouter doesn't handle it
            with pytest.raises(AttributeError, match="No app state"):
                await router(scope, receive, send)

    async def test_scope_path_preservation(self):
        """Test that scope path is not modified."""
        router = MCPRouter()

        captured_scope = None

        async def mock_mcp_handler(scope, _receive, send):
            nonlocal captured_scope
            captured_scope = scope
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [],
                }
            )
            await send({"type": "http.response.body", "body": b"ok"})

        mock_app = MagicMock()
        mock_app_state = MagicMock()
        mock_app_state.mcp_handler = mock_mcp_handler

        with pytest.MonkeyPatch().context() as m:
            m.setattr(AppStateBase, "from_app", lambda _app: mock_app_state)

            original_scope = {
                "app": mock_app,
                "type": "http",
                "method": "POST",
                "path": "/original/path",
            }
            receive = AsyncMock()
            send = AsyncMock()

            await router(original_scope, receive, send)

            # Verify scope was passed unchanged
            assert captured_scope is original_scope
            assert captured_scope["path"] == "/original/path"
