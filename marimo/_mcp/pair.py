# Copyright 2026 Marimo. All rights reserved.
"""
Standalone MCP servers for ``marimo pair``.

- ``pair_stdio``: Direct in-process stdio MCP server.  Creates marimo
  sessions directly (no HTTP server, no subprocess) using ``SessionImpl``.
- ``pair_http``: Prints the ``claude mcp add`` command for an already-running
  ``marimo edit --mcp`` HTTP endpoint.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from typing import cast

from marimo import _loggers
from marimo._ai._tools.types import CodeExecutionResult

LOGGER = _loggers.marimo_logger()


# ---------------------------------------------------------------------------
# pair_http – just print the claude mcp add command
# ---------------------------------------------------------------------------


def pair_http(host: str, port: int) -> None:
    """Print the ``claude mcp add`` command for HTTP transport."""
    from marimo._server.print import print_pair_http_startup

    print_pair_http_startup(f"http://{host}:{port}/mcp/server")


# ---------------------------------------------------------------------------
# pair_stdio – direct in-process MCP server
# ---------------------------------------------------------------------------


def pair_stdio() -> None:
    """Run an in-process MCP stdio server with marimo sessions.

    Creates sessions directly via ``SessionImpl.create()`` — no HTTP
    server, no subprocess, no proxy layer.
    """
    asyncio.run(_run_stdio_server())


async def _run_stdio_server() -> None:
    """Create and run the direct MCP stdio server."""
    from mcp.server.fastmcp import FastMCP

    from marimo._config.config import RuntimeConfig
    from marimo._config.manager import get_default_config_manager
    from marimo._mcp.code_server.main import (
        _EXECUTION_TIMEOUT,
        _extract_result,
        _ScratchCellListener,
    )
    from marimo._messaging.types import KernelMessage
    from marimo._runtime.commands import (
        AppMetadata,
        ExecuteScratchpadCommand,
        SerializedCLIArgs,
    )
    from marimo._session.consumer import SessionConsumer
    from marimo._session.events import SessionEventBus
    from marimo._session.model import ConnectionState, SessionMode
    from marimo._session.notebook import AppFileManager
    from marimo._session.session import SessionImpl
    from marimo._session.types import Session
    from marimo._types.ids import ConsumerId

    mcp = FastMCP("marimo-pair")

    # Local session store
    sessions: dict[str, Session] = {}
    session_locks: dict[str, asyncio.Lock] = {}
    listener = _ScratchCellListener()

    class _NoOpSessionConsumer(SessionConsumer):
        """Minimal session consumer for MCP-managed sessions."""

        def __init__(self, consumer_id: str) -> None:
            self._consumer_id = ConsumerId(consumer_id)

        @property
        def consumer_id(self) -> ConsumerId:
            return self._consumer_id

        def notify(self, notification: KernelMessage) -> None:
            pass

        def connection_state(self) -> ConnectionState:
            return ConnectionState.OPEN

        def on_attach(
            self, session: Session, event_bus: SessionEventBus
        ) -> None:
            pass

        def on_detach(self) -> None:
            pass

    @mcp.tool()
    async def create_session() -> dict[str, str]:
        """Create a new marimo notebook session.

        Returns the session_id of the newly created session.
        Use this session_id with execute_code to run code.
        """
        session_id = uuid.uuid4().hex[:8]

        file_manager = AppFileManager(None)
        config_manager = get_default_config_manager(
            current_path=None
        ).with_overrides(
            {
                "runtime": cast(
                    RuntimeConfig,
                    {
                        "on_cell_change": "autorun",
                        "auto_instantiate": True,
                        "auto_reload": "off",
                        "watcher_on_save": "lazy",
                    },
                ),
            }
        )

        session = SessionImpl.create(
            initialization_id="_any_",
            session_consumer=_NoOpSessionConsumer(f"mcp-{session_id}"),
            mode=SessionMode.EDIT,
            app_metadata=AppMetadata(
                query_params={},
                filename=None,
                cli_args=SerializedCLIArgs({}),
                argv=None,
                app_config=file_manager.app.config,
            ),
            app_file_manager=file_manager,
            config_manager=config_manager,
            virtual_files_supported=False,
            redirect_console_to_browser=False,
            ttl_seconds=None,
            auto_instantiate=True,
        )

        sessions[session_id] = session
        return {"session_id": session_id}

    @mcp.tool()
    async def execute_code(session_id: str, code: str) -> CodeExecutionResult:
        """Execute Python code in a session's kernel scratchpad.

        The code runs in the scratchpad — a temporary execution environment
        that has access to all variables defined in the session but does not
        affect the notebook's cells or dependency graph.

        For detailed instructions on how to execute code, start in the GitHub repo https://github.com/marimo-team/marimo-pair
        and read the SKILL.md file.

        Args:
            session_id: The session ID (from create_session).
            code: Python code to execute.
        """
        session = sessions.get(session_id)
        if session is None:
            return CodeExecutionResult(
                success=False,
                error=f"Session '{session_id}' not found. "
                "Use create_session to create a session first.",
            )

        session.attach_extension(listener)

        lock = session_locks.setdefault(session_id, asyncio.Lock())
        async with lock:
            try:
                done = listener.wait_for(session_id)

                session.put_control_request(
                    ExecuteScratchpadCommand(code=code),
                    from_consumer_id=None,
                )

                await asyncio.wait_for(done.wait(), timeout=_EXECUTION_TIMEOUT)
                # Allow trailing console output to flush
                await asyncio.sleep(0.05)
            except asyncio.TimeoutError:
                return CodeExecutionResult(
                    success=False,
                    error=f"Execution timed out after {_EXECUTION_TIMEOUT}s",
                )
            finally:
                session.detach_extension(listener)

            return _extract_result(session)

    # --- run ----------------------------------------------------------

    print("marimo pair started (stdio)", file=sys.stderr)  # noqa: T201
    print(  # noqa: T201
        'To start pairing: claude -p "/marimo-pair"',
        file=sys.stderr,
    )

    try:
        await mcp.run_stdio_async()
    finally:
        # Clean up all sessions
        for sid, session in sessions.items():
            try:
                session.close()
            except Exception:
                LOGGER.debug("Failed to close session %s", sid)
