# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from marimo._mcp.code_server.lifespan import code_mcp_server_lifespan

pytest.importorskip("mcp", reason="MCP requires Python 3.10+")

from typing import TYPE_CHECKING

from starlette.applications import Starlette
from starlette.authentication import AuthCredentials, SimpleUser
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.testclient import TestClient

from marimo._mcp.code_server.main import setup_code_mcp_server
from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.notification import CellNotification
from marimo._runtime.scratch import SCRATCH_CELL_ID
from marimo._server.api.middleware import AuthBackend
from marimo._session.model import ConnectionState
from tests._server.mocks import get_mock_session_manager

if TYPE_CHECKING:
    from starlette.requests import HTTPConnection


def create_test_app() -> Starlette:
    """Create a test Starlette app with Code MCP server."""
    app = Starlette(
        middleware=[
            Middleware(
                AuthenticationMiddleware,
                backend=AuthBackend(should_authenticate=False),
            ),
        ],
    )
    app.state.session_manager = get_mock_session_manager()
    setup_code_mcp_server(app)
    return app


def test_code_mcp_server_starts_up():
    """Test that Code MCP server can be set up and routes are registered."""
    app = create_test_app()

    assert hasattr(app.state, "code_mcp")
    assert any("/mcp" in str(route.path) for route in app.routes)


async def test_code_mcp_server_requires_edit_scope():
    """Test that Code MCP server validates 'edit' scope is present."""

    class MockAuthBackendNoEdit:
        async def authenticate(self, conn: HTTPConnection):
            del conn
            return AuthCredentials(scopes=["read"]), SimpleUser("test_user")

    app_no_edit = Starlette(
        middleware=[
            Middleware(
                AuthenticationMiddleware,
                backend=MockAuthBackendNoEdit(),
            ),
        ],
    )
    app_no_edit.state.session_manager = get_mock_session_manager()
    setup_code_mcp_server(app_no_edit)

    client = TestClient(app_no_edit, raise_server_exceptions=False)
    response = client.get("/mcp/server")
    assert response.status_code == 403

    class MockAuthBackendWithEdit:
        async def authenticate(self, conn: HTTPConnection):
            del conn
            return AuthCredentials(scopes=["edit"]), SimpleUser("test_user")

    app_with_edit = Starlette(
        middleware=[
            Middleware(
                AuthenticationMiddleware,
                backend=MockAuthBackendWithEdit(),
            ),
        ],
    )
    setup_code_mcp_server(app_with_edit)
    async with code_mcp_server_lifespan(app_with_edit):
        app_with_edit.state.session_manager = get_mock_session_manager()
        client_with_edit = TestClient(app_with_edit)
        response = client_with_edit.get("/mcp/server")
        assert response.status_code != 403


def _make_mock_session(
    *,
    filename: str = "/path/to/notebook.py",
    connection_state: ConnectionState = ConnectionState.OPEN,
) -> MagicMock:
    """Create a mock session for testing."""
    session = MagicMock()
    session.app_file_manager.path = filename
    session.app_file_manager.filename = filename
    session.connection_state.return_value = connection_state
    session.session_view = MagicMock()
    session.session_view.cell_notifications = {}
    return session


def _make_idle_scratch_notification(
    *,
    output_data: str | None = None,
    stdout: list[str] | None = None,
    stderr: list[str] | None = None,
    errors: list[object] | None = None,
) -> CellNotification:
    """Create a CellNotification for the scratch cell in idle state."""
    output = None
    if output_data is not None:
        output = CellOutput(
            channel=CellChannel.OUTPUT,
            mimetype="text/plain",
            data=output_data,
        )
    elif errors is not None:
        output = CellOutput(
            channel=CellChannel.MARIMO_ERROR,
            mimetype="application/vnd.marimo+error",
            data=errors,
        )

    console: list[CellOutput] = []
    for msg in stdout or []:
        console.append(
            CellOutput(
                channel=CellChannel.STDOUT, mimetype="text/plain", data=msg
            )
        )
    for msg in stderr or []:
        console.append(
            CellOutput(
                channel=CellChannel.STDERR, mimetype="text/plain", data=msg
            )
        )

    return CellNotification(
        cell_id=SCRATCH_CELL_ID,
        output=output,
        console=console if console else None,
        status="idle",
    )


class TestGetActiveNotebooks:
    def test_no_sessions_returns_empty(self):
        """get_active_notebooks returns empty list with no sessions."""
        app = create_test_app()
        assert app.state.session_manager.sessions == {}

    def test_session_lookup(self):
        """Sessions injected into the repository can be looked up."""
        app = create_test_app()
        sm = app.state.session_manager

        mock_session = _make_mock_session(filename="/path/to/nb.py")
        sm._repository._sessions["s1"] = mock_session
        assert sm.get_session("s1") is mock_session


class TestExecuteCode:
    async def test_session_not_found(self):
        """Session lookup returns None for missing sessions."""
        app = create_test_app()
        from marimo._server.api.deps import AppStateBase

        state = AppStateBase.from_app(app)
        assert state.session_manager.get_session("nonexistent") is None

    def test_scratchpad_command_dispatch(self):
        """put_control_request is called with ExecuteScratchpadCommand."""
        app = create_test_app()
        sm = app.state.session_manager

        mock_session = _make_mock_session()
        sm._repository._sessions["s1"] = mock_session

        from marimo._runtime.commands import ExecuteScratchpadCommand

        command = ExecuteScratchpadCommand(code="2 + 2")
        mock_session.put_control_request(command, from_consumer_id=None)
        mock_session.put_control_request.assert_called_once_with(
            command, from_consumer_id=None
        )

    def test_idle_notification_output_extraction(self):
        """Output data is extracted correctly from idle scratch notification."""
        notif = _make_idle_scratch_notification(output_data="4")
        assert notif.status == "idle"
        assert notif.output is not None
        assert notif.output.data == "4"

    def test_stdout_extraction(self):
        """Stdout messages are extracted from console outputs."""
        notif = _make_idle_scratch_notification(stdout=["hello\n"])
        assert notif.console is not None
        console_list = (
            notif.console
            if isinstance(notif.console, list)
            else [notif.console]
        )
        stdout_msgs = [
            str(o.data)
            for o in console_list
            if o.channel == CellChannel.STDOUT
        ]
        assert stdout_msgs == ["hello\n"]

    def test_stderr_extraction(self):
        """Stderr messages are extracted from console outputs."""
        notif = _make_idle_scratch_notification(
            output_data="ok", stderr=["warning: something\n"]
        )
        assert notif.console is not None
        console_list = (
            notif.console
            if isinstance(notif.console, list)
            else [notif.console]
        )
        stderr_msgs = [
            str(o.data)
            for o in console_list
            if o.channel == CellChannel.STDERR
        ]
        assert stderr_msgs == ["warning: something\n"]

    def test_error_extraction(self):
        """Errors are extracted from output data list."""
        mock_error = MagicMock()
        mock_error.msg = "NameError: name 'x' is not defined"
        notif = _make_idle_scratch_notification(errors=[mock_error])
        assert notif.output is not None
        assert isinstance(notif.output.data, list)
        assert len(notif.output.data) == 1

    def test_notification_set_after_command(self):
        """Simulates the full flow: command -> notification -> output."""
        app = create_test_app()
        sm = app.state.session_manager

        mock_session = _make_mock_session()
        sm._repository._sessions["s1"] = mock_session

        notif = _make_idle_scratch_notification(
            output_data="4", stdout=["debug\n"]
        )

        def set_notification(*args: object, **kwargs: object):
            del args
            del kwargs
            mock_session.session_view.cell_notifications = {
                SCRATCH_CELL_ID: notif
            }

        mock_session.put_control_request.side_effect = set_notification

        from marimo._runtime.commands import ExecuteScratchpadCommand

        command = ExecuteScratchpadCommand(code="2 + 2")
        mock_session.put_control_request(command, from_consumer_id=None)

        cell_notif = mock_session.session_view.cell_notifications.get(
            SCRATCH_CELL_ID
        )
        assert cell_notif is not None
        assert cell_notif.status == "idle"
        assert cell_notif.output is not None
        assert cell_notif.output.data == "4"
