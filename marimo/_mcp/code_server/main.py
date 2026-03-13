# Copyright 2026 Marimo. All rights reserved.
"""
Code Mode MCP Server for Marimo

A minimal MCP server that lets external AI agents execute Python code
in a running marimo kernel via the scratchpad.
"""

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING, Any

from marimo._ai._tools.types import (
    CodeExecutionResult,
    ListSessionsResult,
    MarimoNotebookInfo,
)
from marimo._dependencies.dependencies import DependencyManager
from marimo._loggers import marimo_logger
from marimo._messaging.cell_output import CellChannel
from marimo._messaging.notification import CellNotification
from marimo._messaging.serde import deserialize_kernel_message
from marimo._runtime.scratch import SCRATCH_CELL_ID
from marimo._session.events import SessionEventBus, SessionEventListener
from marimo._types.ids import SessionId

LOGGER = marimo_logger()

if TYPE_CHECKING:
    from starlette.applications import Starlette
    from starlette.types import Receive, Scope, Send

    from marimo._messaging.types import KernelMessage
    from marimo._session.session import Session

_EXECUTION_TIMEOUT = 30.0  # seconds


class _ScratchCellListener(SessionEventListener):
    """Listens for scratch cell idle notifications and signals waiters.

    Implements SessionExtension so it can be dynamically attached to a
    session via session.attach_extension / session.detach_extension.
    """

    def __init__(self) -> None:
        self._waiters: dict[str, asyncio.Event] = {}

    def wait_for(self, session_id: str) -> asyncio.Event:
        event = asyncio.Event()
        self._waiters[session_id] = event
        return event

    # SessionExtension protocol
    def on_attach(self, session: Session, event_bus: SessionEventBus) -> None:
        del session
        event_bus.subscribe(self)

    def on_detach(self) -> None:
        pass

    def on_notification_sent(
        self, session: Session, notification: KernelMessage
    ) -> None:
        del session
        msg = deserialize_kernel_message(notification)
        if not isinstance(msg, CellNotification):
            return
        if msg.cell_id != SCRATCH_CELL_ID:
            return
        if msg.status != "idle":
            return
        # Signal any waiter for this session
        for sid, event in list(self._waiters.items()):
            if not event.is_set():
                event.set()
            del self._waiters[sid]


def setup_code_mcp_server(
    app: Starlette, *, allow_remote: bool = False
) -> None:
    """Create and configure the Code Mode MCP server.

    Mounts at /mcp with a single /server streamable HTTP endpoint.
    Exposes two tools: `list_sessions` and `execute_code`.

    Args:
        app: Starlette application instance for accessing marimo state
        allow_remote: If True, disable DNS rebinding protection to allow remote access behind proxies.
    """
    if not DependencyManager.mcp.has():
        from click import ClickException

        msg = "MCP dependencies not available. Install with `pip install marimo[mcp]` or `uv add marimo[mcp]`"
        raise ClickException(msg)

    from mcp.server.fastmcp import FastMCP
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse
    from starlette.routing import Mount

    from marimo._runtime.commands import ExecuteScratchpadCommand
    from marimo._server.api.deps import AppStateBase
    from marimo._session.model import ConnectionState

    transport_security = None
    if allow_remote:
        from mcp.server.transport_security import TransportSecuritySettings

        transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=False,
        )

    mcp = FastMCP(
        "marimo-code-mcp",
        stateless_http=True,
        log_level="WARNING",
        streamable_http_path="/server",
        transport_security=transport_security,
    )

    # Per-session locks to prevent overlapping scratchpad executions
    session_locks: dict[str, asyncio.Lock] = {}
    listener = _ScratchCellListener()

    @mcp.tool()
    async def list_sessions() -> ListSessionsResult:
        """List active marimo sessions.

        Returns a list of active sessions, each with 'name', 'path',
        and 'session_id' fields.
        Use the session_id with execute_code to run code in that session.
        """
        state = AppStateBase.from_app(app)
        session_manager = state.session_manager

        sessions: list[MarimoNotebookInfo] = []
        for session_id, session in session_manager.sessions.items():
            conn_state = session.connection_state()
            if conn_state in (ConnectionState.OPEN, ConnectionState.ORPHANED):
                full_path = session.app_file_manager.path
                filename = session.app_file_manager.filename
                basename = os.path.basename(filename) if filename else None
                sessions.append(
                    MarimoNotebookInfo(
                        name=basename or "new notebook",
                        path=full_path or "(unsaved notebook)",
                        session_id=SessionId(session_id),
                    )
                )

        return ListSessionsResult(sessions=sessions[::-1])

    @mcp.tool()
    async def execute_code(session_id: str, code: str) -> CodeExecutionResult:
        """Execute Python code in a notebook's kernel scratchpad.

        The code runs in the scratchpad — a temporary execution environment
        that has access to all variables defined in the notebook but does not
        affect the notebook's cells or dependency graph.

        Args:
            session_id: The session ID of the notebook (from list_sessions).
            code: Python code to execute.
        """
        state = AppStateBase.from_app(app)
        session = state.session_manager.get_session(SessionId(session_id))

        if session is None:
            return CodeExecutionResult(
                success=False,
                error=f"Session '{session_id}' not found. "
                "Use list_sessions to find valid session IDs.",
            )

        # Attach listener as a session extension
        session.attach_extension(listener)

        lock = session_locks.setdefault(session_id, asyncio.Lock())
        async with lock:
            try:
                # Set up event before sending command
                done = listener.wait_for(session_id)

                # Send the scratchpad execution command
                session.put_control_request(
                    ExecuteScratchpadCommand(code=code),
                    from_consumer_id=None,
                )

                # Wait for the scratch cell to become idle
                await asyncio.wait_for(done.wait(), timeout=_EXECUTION_TIMEOUT)
            except asyncio.TimeoutError:
                return CodeExecutionResult(
                    success=False,
                    error=f"Execution timed out after {_EXECUTION_TIMEOUT}s",
                )
            finally:
                session.detach_extension(listener)

            return _extract_result(session)

    # Build the streamable HTTP app
    mcp_app = mcp.streamable_http_app()

    class RequiresEditMiddleware(BaseHTTPMiddleware):
        async def __call__(
            self, scope: Scope, receive: Receive, send: Send
        ) -> None:
            auth = scope.get("auth")
            if auth is None or "edit" not in auth.scopes:
                response = JSONResponse(
                    {"detail": "Forbidden"}, status_code=403
                )
                return await response(scope, receive, send)
            return await self.app(scope, receive, send)

    mcp_app.add_middleware(RequiresEditMiddleware)

    app.routes.insert(0, Mount("/mcp", mcp_app))
    app.state.code_mcp = mcp


def _extract_result(session: Any) -> CodeExecutionResult:
    """Read the scratch cell's final state from the session view."""
    cell_notif = session.session_view.cell_notifications.get(SCRATCH_CELL_ID)
    if cell_notif is None:
        return CodeExecutionResult(success=True)

    # Output
    output_data = None
    if cell_notif.output is not None:
        data = cell_notif.output.data
        if isinstance(data, str):
            output_data = data
        elif isinstance(data, dict):
            output_data = data.get(
                "text/plain", data.get("text/html", str(data))
            )
        # list → errors, handled below

    # Console
    stdout: list[str] = []
    stderr: list[str] = []
    for out in (
        cell_notif.console if isinstance(cell_notif.console, list) else []
    ):
        if out is None:
            continue
        if out.channel == CellChannel.STDOUT:
            stdout.append(str(out.data))
        elif out.channel == CellChannel.STDERR:
            stderr.append(str(out.data))

    # Errors
    errors: list[str] = []
    if cell_notif.output is not None and isinstance(
        cell_notif.output.data, list
    ):
        for err in cell_notif.output.data:
            errors.append(str(getattr(err, "msg", None) or err))

    return CodeExecutionResult(
        success=len(errors) == 0,
        output=output_data,
        stdout=stdout,
        stderr=stderr,
        errors=errors,
    )
