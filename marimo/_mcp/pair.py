# Copyright 2026 Marimo. All rights reserved.
"""
Standalone MCP servers for ``marimo pair``.

- ``pair_stdio``: In-process stdio MCP server backed by a headless marimo
  HTTP server.  Sessions are viewable in the browser at a kiosk URL.
- ``pair_http``: Prints the ``claude mcp add`` command for an already-running
  ``marimo edit --mcp`` HTTP endpoint.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import os
import sys
import uuid
from datetime import date
from typing import TYPE_CHECKING, Union

from mcp.types import ImageContent, TextContent

from marimo._ai._tools.types import (
    CodeExecutionResult,
    ListSessionsResult,
    MarimoNotebookInfo,
)

if TYPE_CHECKING:
    from marimo._runtime.commands import HTTPRequest

_IMAGE_MIMETYPES = frozenset(
    {
        "image/png",
        "image/jpeg",
        "image/gif",
        "image/svg+xml",
        "image/bmp",
        "image/tiff",
        "image/avif",
    }
)


def _parse_data_url(data_url: str) -> tuple[str, str] | None:
    """Extract (mimetype, base64_data) from a data URL string.

    Returns None if the string is not a valid data URL.
    """
    if not isinstance(data_url, str) or not data_url.startswith("data:"):
        return None
    # Format: data:mime;base64,DATA
    try:
        header, base64_data = data_url.split(",", 1)
    except ValueError:
        return None
    # header is "data:mime;base64"
    mimetype = header.split(";")[0][5:]  # strip "data:"
    if mimetype not in _IMAGE_MIMETYPES:
        return None
    return mimetype, base64_data


def _extract_images_from_mimebundle(
    data: Union[str, dict[str, object]],
) -> list[tuple[str, str]]:
    """Extract (mimetype, base64_data) pairs from a mimebundle.

    The mimebundle can be a JSON string or a dict. Image keys are
    data URLs like ``data:image/png;base64,...``.
    """
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, ValueError):
            return []
    if not isinstance(data, dict):
        return []

    results: list[tuple[str, str]] = []
    for key, value in data.items():
        if key in _IMAGE_MIMETYPES and isinstance(value, str):
            parsed = _parse_data_url(value)
            if parsed:
                results.append(parsed)
    return results


def _images_from_output(mimetype: str, data: object) -> list[tuple[str, str]]:
    """Extract image pairs from a single output's mimetype and data."""
    if mimetype in _IMAGE_MIMETYPES:
        parsed = _parse_data_url(str(data))
        return [parsed] if parsed else []
    if mimetype == "application/vnd.marimo+mimebundle" and isinstance(
        data, (str, dict)
    ):
        return _extract_images_from_mimebundle(data)
    return []


def _extract_images(
    cell_notif: object,
) -> list[tuple[str, str]]:
    """Extract (mimetype, base64_data) pairs from a CellNotification.

    Checks both console MEDIA outputs and the cell output.
    """
    from marimo._messaging.cell_output import CellChannel
    from marimo._messaging.notification import CellNotification

    if not isinstance(cell_notif, CellNotification):
        return []

    results: list[tuple[str, str]] = []

    # 1. Console outputs — look for CellChannel.MEDIA
    if cell_notif.console is not None:
        console_list = (
            cell_notif.console
            if isinstance(cell_notif.console, list)
            else [cell_notif.console]
        )
        for out in console_list:
            if out is None or out.channel != CellChannel.MEDIA:
                continue
            results.extend(_images_from_output(str(out.mimetype), out.data))

    # 2. Cell output — the return value of the cell
    if cell_notif.output is not None:
        output = cell_notif.output
        results.extend(_images_from_output(str(output.mimetype), output.data))

    return results


def _result_to_text(result: CodeExecutionResult) -> TextContent:
    """Serialize a CodeExecutionResult to an MCP TextContent."""
    return TextContent(
        type="text",
        text=json.dumps(dataclasses.asdict(result)),
    )


def _build_http_request(
    screenshot_server_url: str,
    screenshot_auth_token: str,
) -> HTTPRequest:
    """Construct a minimal HTTPRequest carrying screenshot metadata.

    ``_code_mode``'s ``ctx.screenshot()`` reads these keys from
    ``request.meta`` to point Playwright at the backing HTTP server.
    """
    from marimo._runtime.commands import HTTPRequest

    return HTTPRequest(
        url={},
        base_url={},
        headers={},
        query_params={},
        path_params={},
        cookies={},
        user={},
        meta={
            "screenshot_server_url": screenshot_server_url,
            "screenshot_auth_token": screenshot_auth_token,
        },
    )


# ---------------------------------------------------------------------------
# pair_http – just print the claude mcp add command
# ---------------------------------------------------------------------------


def pair_http(host: str, port: int) -> None:
    """Print the ``claude mcp add`` command for HTTP transport."""
    from marimo._server.print import print_pair_http_startup

    print_pair_http_startup(f"http://{host}:{port}/mcp/server")


# ---------------------------------------------------------------------------
# pair_stdio – direct in-process MCP server + headless HTTP server
# ---------------------------------------------------------------------------


def pair_stdio(port: int | None, sandbox: bool) -> None:
    """Run an in-process MCP stdio server with a headless marimo HTTP server.

    The HTTP server makes sessions viewable in the browser at a kiosk URL.
    """
    # Use a manual event loop instead of asyncio.run() so that the
    # default SIGINT → KeyboardInterrupt behaviour is preserved.
    # asyncio.run() installs its own SIGINT handler that merely cancels
    # the main task; the MCP server catches CancelledError internally,
    # so Ctrl+C never actually kills the process.
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_run_stdio_server(port=port, sandbox=sandbox))
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


async def _run_stdio_server(port: int | None, sandbox: bool) -> None:
    """Create and run the MCP stdio server with a backing HTTP server."""
    import signal

    import uvicorn
    from mcp.server.fastmcp import FastMCP

    from marimo._cli.sandbox import SandboxMode
    from marimo._config.manager import get_default_config_manager
    from marimo._runtime.commands import SerializedCLIArgs
    from marimo._server.api import lifespans
    from marimo._server.config import StarletteServerStateInit
    from marimo._server.file_router import NewFileAppFileRouter
    from marimo._server.lsp import NoopLspServer
    from marimo._server.main import create_starlette_app
    from marimo._server.scratchpad import (
        EXECUTION_TIMEOUT,
        ScratchCellListener,
        extract_result,
    )
    from marimo._server.session_manager import SessionManager
    from marimo._server.utils import initialize_mimetypes
    from marimo._session.consumer import NoOpSessionConsumer
    from marimo._session.model import SessionMode
    from marimo._types.ids import SessionId
    from marimo._utils.lifespans import Lifespans
    from marimo._utils.net import find_free_port

    host = "127.0.0.1"
    port = port or find_free_port(2718, addr=host)

    # -- Session manager (same pattern as start.py) --
    file_router = NewFileAppFileRouter()
    config_manager = get_default_config_manager(current_path=None)

    sandbox_mode = SandboxMode.MULTI if sandbox else None

    session_manager = SessionManager(
        file_router=file_router,
        mode=SessionMode.EDIT,
        quiet=True,
        include_code=True,
        ttl_seconds=None,
        lsp_server=NoopLspServer(),
        config_manager=config_manager,
        cli_args=SerializedCLIArgs({}),
        argv=None,
        auth_token=None,
        redirect_console_to_browser=False,
        watch=False,
        sandbox_mode=sandbox_mode,
    )

    # -- Starlette app --
    app = create_starlette_app(
        base_url="",
        host=host,
        lifespan=Lifespans([lifespans.etc]),
        enable_auth=False,
        skew_protection=False,
    )

    StarletteServerStateInit(
        port=port,
        host=host,
        base_url="",
        asset_url=None,
        headless=True,
        quiet=True,
        session_manager=session_manager,
        config_manager=config_manager,
        remote_url=None,
        mcp_server_enabled=False,
        skew_protection=False,
        enable_auth=False,
    ).apply(app.state)

    initialize_mimetypes()

    # -- Start uvicorn as a background task --
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            port=port,
            host=host,
            log_level="error",
            timeout_keep_alive=int(1e9),
            ws_ping_interval=1,
            ws_ping_timeout=60,
            timeout_graceful_shutdown=1,
        )
    )
    app.state.server = server
    server_task = asyncio.create_task(server.serve())

    # Wait for uvicorn to signal that it's ready.  ``server.started``
    # is a bool set once the server has bound to the port and installed
    # its own SIGINT handler.  We then override that handler so that
    # Ctrl+C performs a clean shutdown via KeyboardInterrupt instead
    # of entering uvicorn's graceful-shutdown dance.
    while not server.started:  # noqa: ASYNC110
        await asyncio.sleep(0.05)

    def _shutdown_handler(*_args: object) -> None:
        """Perform cleanup then exit.

        We cannot raise KeyboardInterrupt here because the MCP stdio
        server holds a buffered reader lock on stdin in a daemon thread;
        raising during finalization triggers a fatal error.  Instead we
        clean up explicitly then hard-exit.
        """
        session_manager.shutdown()
        server.should_exit = True
        os._exit(0)

    signal.signal(signal.SIGINT, _shutdown_handler)

    # -- URL helpers --
    base_url = f"http://{host}:{port}"

    def kiosk_url(file_key: str) -> str:
        return f"{base_url}/?file={file_key}&kiosk=true"

    # -- MCP server --
    mcp = FastMCP("marimo-pair")

    @mcp.tool()
    async def create_session() -> dict[str, str]:
        """Create a new marimo notebook session.

        Returns the session_id, follow_along_url, and file_path of the
        newly created session. Use the session_id with execute_code to
        run code.

        IMPORTANT: You MUST immediately share the ``follow_along_url``
        with the user so they can open the live notebook in their
        browser and follow along as you work.
        """
        from marimo._utils.xdg import marimo_state_dir

        session_id = SessionId(uuid.uuid4().hex[:8])

        # Compute a persistent save path under the XDG state dir
        # and create the file so it can be used as the file_key.
        pair_dir = marimo_state_dir() / "pair"
        pair_dir.mkdir(parents=True, exist_ok=True)
        save_path = pair_dir / f"{date.today().isoformat()}-{session_id}.py"
        save_path.touch()

        file_key = str(save_path)

        session_manager.create_session(
            session_id=session_id,
            session_consumer=NoOpSessionConsumer(f"mcp-{session_id}"),
            query_params={},
            file_key=file_key,
            auto_instantiate=True,
        )

        return {
            "session_id": session_id,
            "follow_along_url": kiosk_url(file_key),
            "file_path": str(save_path),
        }

    @mcp.tool()
    async def list_sessions() -> ListSessionsResult:
        """List active marimo sessions.

        Returns a list of active sessions, each with 'name', 'path',
        'session_id', and 'follow_along_url' fields.
        Use the session_id with execute_code to run code in that session.

        IMPORTANT: You MUST immediately share the ``follow_along_url``
        with the user so they can open the live notebook in their
        browser.
        """
        result: list[MarimoNotebookInfo] = []
        for sid, session in session_manager.sessions.items():
            filename = session.app_file_manager.filename
            full_path = session.app_file_manager.path
            basename = os.path.basename(filename) if filename else None
            result.append(
                MarimoNotebookInfo(
                    name=basename or "new notebook",
                    path=full_path or "(unsaved notebook)",
                    session_id=SessionId(sid),
                    follow_along_url=kiosk_url(session.initialization_id),
                )
            )
        return ListSessionsResult(sessions=result)

    @mcp.tool()
    async def execute_code(
        session_id: str, code: str
    ) -> list[TextContent | ImageContent]:
        """Execute Python code in a session's kernel scratchpad.

        The code runs in the scratchpad — a temporary execution environment
        that has access to all variables defined in the session but does not
        affect the notebook's cells or dependency graph.

        For detailed instructions on how to execute code, start in the GitHub repo https://github.com/marimo-team/marimo-pair
        and read the SKILL.md file.

        ```python
        import urllib.request

        response = urllib.request.urlopen(
            "https://raw.githubusercontent.com/marimo-team/marimo-pair/main/SKILL.md"
        )
        print(response.read().decode("utf-8"))
        ```

        Args:
            session_id: The session ID (from create_session).
            code: Python code to execute.
        """
        from marimo._runtime.commands import ExecuteScratchpadCommand
        from marimo._runtime.scratch import SCRATCH_CELL_ID
        from marimo._server.models.models import InstantiateNotebookRequest

        session = session_manager.get_session(SessionId(session_id))
        if session is None:
            return [
                _result_to_text(
                    CodeExecutionResult(
                        success=False,
                        error=f"Session '{session_id}' not found. "
                        "Use create_session to create a session first.",
                    )
                )
            ]

        # Build a minimal HTTPRequest with the screenshot metadata that
        # ``_code_mode``'s ``ctx.screenshot()`` reads from ``request.meta``.
        http_req = _build_http_request(
            screenshot_server_url=base_url,
            screenshot_auth_token=str(session_manager.auth_token),
        )

        # Seed the dependency graph so ``_code_mode``'s ``run_cell`` can
        # resolve cells. No-op if the session is already instantiated.
        session.instantiate(
            InstantiateNotebookRequest(
                object_ids=[], values=[], auto_run=False
            ),
            http_request=http_req,
        )

        listener = ScratchCellListener()
        with session.scoped(listener):
            async with session.scratchpad_lock:
                session.put_control_request(
                    ExecuteScratchpadCommand(
                        code=code,
                        request=http_req,
                        notebook_cells=tuple(session.document.cells),
                    ),
                    from_consumer_id=None,
                )
                await listener.wait(timeout=EXECUTION_TIMEOUT)

            if listener.timed_out:
                return [
                    _result_to_text(
                        CodeExecutionResult(
                            success=False,
                            error=f"Execution timed out after {EXECUTION_TIMEOUT}s",
                        )
                    )
                ]

            result = extract_result(session, listener)

            contents: list[TextContent | ImageContent] = [
                _result_to_text(result)
            ]

            # Extract images from the scratch cell notification
            cell_notif = session.session_view.cell_notifications.get(
                SCRATCH_CELL_ID
            )
            if cell_notif is not None:
                for mimetype, base64_data in _extract_images(cell_notif):
                    contents.append(
                        ImageContent(
                            type="image",
                            data=base64_data,
                            mimeType=mimetype,
                        )
                    )

            return contents

    # --- run ----------------------------------------------------------

    print(  # noqa: T201
        "marimo pair started (stdio)", file=sys.stderr
    )
    print(  # noqa: T201
        f"Viewer URL: {base_url}", file=sys.stderr
    )
    print(  # noqa: T201
        'To start pairing: claude -p "/marimo-pair"',
        file=sys.stderr,
    )

    try:
        await mcp.run_stdio_async()
    finally:
        session_manager.shutdown()
        server.should_exit = True
        await server_task
