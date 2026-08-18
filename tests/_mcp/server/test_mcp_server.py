# Copyright 2026 Marimo. All rights reserved.
from unittest.mock import MagicMock

import pytest

from marimo._cli.errors import MarimoCLIMissingDependencyError
from marimo._dependencies.dependencies import DependencyManager
from marimo._mcp.server.lifespan import mcp_server_lifespan

pytest.importorskip("mcp", reason="MCP requires Python 3.10+")

from starlette.applications import Starlette
from starlette.authentication import AuthCredentials, SimpleUser
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.requests import HTTPConnection
from starlette.testclient import TestClient

from marimo._mcp.server.main import setup_mcp_server
from marimo._server.api.middleware import AuthBackend
from tests._server.mocks import get_mock_session_manager


def create_test_app() -> Starlette:
    """Create a test Starlette app with MCP server."""
    app = Starlette(
        middleware=[
            Middleware(
                AuthenticationMiddleware,
                backend=AuthBackend(should_authenticate=False),
            ),
        ],
    )
    app.state.session_manager = get_mock_session_manager()
    setup_mcp_server(app)
    return app


def test_mcp_server_starts_up():
    """Test that MCP server can be set up and routes are registered."""
    app = create_test_app()
    client = TestClient(app)

    # Verify the MCP server is mounted
    assert hasattr(app.state, "mcp")

    # Verify /mcp route exists
    assert any("/mcp" in str(route.path) for route in app.routes)


def test_mcp_server_requires_supported_mcp_version(monkeypatch):
    has_required_version = MagicMock(return_value=False)
    monkeypatch.setattr(
        DependencyManager.mcp,
        "has_required_version",
        has_required_version,
    )

    with pytest.raises(MarimoCLIMissingDependencyError):
        setup_mcp_server(Starlette())

    has_required_version.assert_called_once_with(quiet=True)


async def test_mcp_server_supports_modern_protocol():
    """The v2 server should negotiate the modern protocol directly."""
    from mcp import Client

    app = create_test_app()
    async with Client(app.state.mcp) as client:
        tools = await client.list_tools()
        prompts = await client.list_prompts()

        assert client.protocol_version == "2026-07-28"
        assert tools.tools
        assert {prompt.name for prompt in prompts.prompts} == {
            "active_notebooks",
            "errors_summary",
        }


async def test_mcp_server_supports_streamable_http():
    import httpx2
    from mcp import Client
    from mcp.client.streamable_http import streamable_http_client

    app = create_test_app()
    http_transport = httpx2.ASGITransport(app=app)
    async with mcp_server_lifespan(app):
        async with httpx2.AsyncClient(
            transport=http_transport,
            base_url="http://localhost:8000",
            follow_redirects=True,
        ) as http_client:
            transport = streamable_http_client(
                "http://localhost:8000/mcp/server",
                http_client=http_client,
            )
            async with Client(transport, mode="2026-07-28") as client:
                tools = await client.list_tools()

                assert client.protocol_version == "2026-07-28"
                assert tools.tools


async def test_mcp_server_requires_edit_scope():
    """Test that MCP server validates 'edit' scope is present."""
    app = create_test_app()

    # Mock a request without edit scope
    class MockAuthBackend:
        async def authenticate(self, conn: HTTPConnection):
            del conn
            # Return user without edit scope
            return AuthCredentials(scopes=["read"]), SimpleUser("test_user")

    # Create app with authentication that doesn't include edit scope
    app_no_edit = Starlette(
        middleware=[
            Middleware(
                AuthenticationMiddleware,
                backend=MockAuthBackend(),
            ),
        ],
    )
    app_no_edit.state.session_manager = get_mock_session_manager()
    setup_mcp_server(app_no_edit)

    client = TestClient(app_no_edit, raise_server_exceptions=False)

    # Try to access MCP endpoint without edit scope
    response = client.get("/mcp/server")
    assert response.status_code == 403

    # Mock a request with edit scope
    class MockAuthBackendWithEdit:
        async def authenticate(self, conn: HTTPConnection):
            del conn
            # Return user with edit scope
            return AuthCredentials(scopes=["edit"]), SimpleUser("test_user")

    # Create app with edit scope
    app_with_edit = Starlette(
        middleware=[
            Middleware(
                AuthenticationMiddleware,
                backend=MockAuthBackendWithEdit(),
            ),
        ],
    )

    setup_mcp_server(app_with_edit)
    async with mcp_server_lifespan(app_with_edit):
        app_with_edit.state.session_manager = get_mock_session_manager()

        client_with_edit = TestClient(app_with_edit)

        # Access should not be forbidden (may get other status codes based on MCP protocol)
        response = client_with_edit.get("/mcp/server")
        assert response.status_code != 403
