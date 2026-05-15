# Copyright 2026 Marimo. All rights reserved.
"""
Code Mode MCP Server for Marimo

A minimal MCP server that lets external AI agents execute Python code
in a running marimo kernel via the scratchpad.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from uuid import uuid4

from marimo._ai._tools.types import (
    CodeExecutionResult,
    ListSessionsResult,
    MarimoNotebookInfo,
)
from marimo._dependencies.dependencies import DependencyManager
from marimo._loggers import marimo_logger
from marimo._server.scratchpad import (
    EXECUTION_TIMEOUT,
    ScratchCellListener,
    extract_result,
)
from marimo._types.ids import SessionId

LOGGER = marimo_logger()

if TYPE_CHECKING:
    from starlette.applications import Starlette
    from starlette.types import Receive, Scope, Send


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

        # Correlation ID: see /api/kernel/execute for rationale.
        run_id = str(uuid4())
        listener = ScratchCellListener(run_id=run_id)
        with session.scoped(listener):
            async with session.scratchpad_lock:
                session.put_control_request(
                    ExecuteScratchpadCommand(code=code, run_id=run_id),
                    from_consumer_id=None,
                )
                await listener.wait(timeout=EXECUTION_TIMEOUT)

            if listener.timed_out:
                return CodeExecutionResult(
                    success=False,
                    error=f"Execution timed out after {EXECUTION_TIMEOUT}s",
                )

            return extract_result(session, listener)

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
