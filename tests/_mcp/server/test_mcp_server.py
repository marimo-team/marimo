# Copyright 2024 Marimo. All rights reserved.
import pytest

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
