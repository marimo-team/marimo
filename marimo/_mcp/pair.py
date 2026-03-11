# Copyright 2026 Marimo. All rights reserved.
"""
Standalone stdio MCP server for ``marimo pair``.

Uses the low-level ``mcp.server`` API to create an stdio MCP server
that discovers tools/prompts from a running marimo instance's HTTP
MCP endpoint and forwards every call via simple HTTP POST.

If no marimo server is running, one is auto-started and torn down
on exit.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import tempfile
import time
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from marimo import _loggers

LOGGER = _loggers.marimo_logger()

_SERVER_START_TIMEOUT_S = 30.0
_SERVER_POLL_INTERVAL_S = 0.2
_SERVER_SHUTDOWN_TIMEOUT_S = 5.0


class PairConnectionError(Exception):
    """Could not connect to the marimo server."""

    def __init__(self, host: str, port: int, detail: str = "") -> None:
        msg = (
            f"Could not connect to marimo at http://{host}:{port}. "
            "Start a server with: marimo edit --mcp"
        )
        if detail:
            msg = f"{msg}\n{detail}"
        super().__init__(msg)


def _is_server_ready(host: str, port: int) -> bool:
    """Check if the marimo server's health endpoint is reachable."""
    try:
        with urlopen(  # noqa: S310
            f"http://{host}:{port}/health", timeout=1
        ) as resp:
            return bool(resp.status == 200)
    except (URLError, OSError):
        return False


# ---------------------------------------------------------------------------
# ManagedServer – auto-start marimo edit --mcp as a subprocess
# Modelled after LiveNotebookServer in the export module.
# ---------------------------------------------------------------------------


class ManagedServer(AbstractContextManager["ManagedServer"]):
    """Start and manage a ``marimo edit --mcp`` subprocess."""

    def __init__(
        self, host: str, port: int, mcp_mode: str = "code-mode"
    ) -> None:
        self._host = host
        self._port = port
        self._mcp_mode = mcp_mode
        self._process: subprocess.Popen[str] | None = None
        self._log_file: tempfile._TemporaryFileWrapper[str] | None = None

    def __enter__(self) -> ManagedServer:
        self._log_file = tempfile.NamedTemporaryFile(
            mode="w+", encoding="utf-8", delete=False
        )
        self._process = subprocess.Popen(
            self._build_command(),
            stdout=self._log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )
        self._wait_until_ready()
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _tb: object,
    ) -> None:
        if self._process is not None:
            self._terminate(self._process)
            self._process = None
        if self._log_file is not None:
            log_name = self._log_file.name
            self._log_file.close()
            try:
                Path(log_name).unlink(missing_ok=True)
            except OSError:
                LOGGER.debug(
                    "Failed to clean up pair server log: %s", log_name
                )
            self._log_file = None

    def _build_command(self) -> list[str]:
        return [
            sys.executable, "-m", "marimo", "-y", "edit",
            "--mcp", self._mcp_mode,
            "--headless", "--no-token", "--no-skew-protection",
            "--host", self._host, "--port", str(self._port),
        ]  # fmt: skip

    def _wait_until_ready(self) -> None:
        start = time.monotonic()
        while time.monotonic() - start < _SERVER_START_TIMEOUT_S:
            proc = self._process
            if proc is None:
                raise PairConnectionError(self._host, self._port)
            if proc.poll() is not None:
                raise PairConnectionError(
                    self._host, self._port, detail=self._read_logs()
                )
            if _is_server_ready(self._host, self._port):
                return
            time.sleep(_SERVER_POLL_INTERVAL_S)
        raise PairConnectionError(
            self._host,
            self._port,
            detail=f"Timed out waiting for server.\n{self._read_logs()}",
        )

    def _read_logs(self) -> str:
        if self._log_file is None:
            return ""
        self._log_file.flush()
        self._log_file.seek(0)
        logs = self._log_file.read()
        return logs[-4_000:] if len(logs) > 4_000 else logs

    def _terminate(self, process: subprocess.Popen[str]) -> None:
        if process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=_SERVER_SHUTDOWN_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=_SERVER_SHUTDOWN_TIMEOUT_S)


# ---------------------------------------------------------------------------
# HTTP helpers – talk to the running marimo MCP endpoint
# ---------------------------------------------------------------------------


def _mcp_post(
    mcp_url: str, method: str, params: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Send a JSON-RPC request to the marimo MCP endpoint.

    The marimo MCP server uses ``stateless_http=True`` and returns
    ``text/event-stream`` (SSE).  We parse the ``data:`` lines.
    """
    import httpx

    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        payload["params"] = params

    resp = httpx.post(
        mcp_url,
        json=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        timeout=60,
    )
    resp.raise_for_status()

    # The response may be plain JSON or SSE.
    content_type = resp.headers.get("content-type", "")
    if "text/event-stream" in content_type:
        return _parse_sse(resp.text)
    return resp.json()  # type: ignore[no-any-return]


def _parse_sse(body: str) -> dict[str, Any]:
    """Extract the first JSON-RPC result from an SSE stream."""
    for line in body.splitlines():
        if line.startswith("data: "):
            return json.loads(line[6:])  # type: ignore[no-any-return]
    return {}


# ---------------------------------------------------------------------------
# pair_http – just print the claude mcp add command
# ---------------------------------------------------------------------------


def pair_http(host: str, port: int) -> None:
    """Print the ``claude mcp add`` command for HTTP transport."""
    from marimo._server.print import print_pair_http_startup

    print_pair_http_startup(f"http://{host}:{port}/mcp/server")


# ---------------------------------------------------------------------------
# pair_stdio – the main entry point
# ---------------------------------------------------------------------------


def pair_stdio(host: str, port: int, mcp_mode: str = "code-mode") -> None:
    """Run an MCP stdio server that forwards calls to a running marimo instance.

    Uses the low-level ``mcp.server.Server`` + ``mcp.server.stdio``
    APIs so we can pass through the exact tool/prompt schemas from the
    running marimo server without any schema translation.
    """
    managed: ManagedServer | None = None
    if not _is_server_ready(host, port):
        print(  # noqa: T201
            f"Starting marimo edit --mcp {mcp_mode} on port {port}...",
            file=sys.stderr,
        )
        managed = ManagedServer(host, port, mcp_mode=mcp_mode)
        managed.__enter__()

    mcp_url = f"http://{host}:{port}/mcp/server"

    try:
        asyncio.run(_run_stdio_server(mcp_url, host, port))
    finally:
        if managed is not None:
            managed.__exit__(None, None, None)


async def _run_stdio_server(mcp_url: str, host: str, port: int) -> None:
    """Create and run the low-level MCP stdio server."""
    import mcp.server.stdio as mcp_stdio
    import mcp.types as types
    from mcp.server.lowlevel import NotificationOptions, Server
    from mcp.server.models import InitializationOptions

    # Discover tools and prompts from the running marimo server.
    tools_data = _mcp_post(mcp_url, "tools/list")
    remote_tools: list[dict[str, Any]] = tools_data.get("result", {}).get(
        "tools", []
    )

    prompts_data = _mcp_post(mcp_url, "prompts/list")
    remote_prompts: list[dict[str, Any]] = prompts_data.get("result", {}).get(
        "prompts", []
    )

    server = Server("marimo-pair")

    # --- tools --------------------------------------------------------

    @server.list_tools()  # type: ignore[misc, no-untyped-call]
    async def handle_list_tools() -> list[types.Tool]:
        return [types.Tool(**t) for t in remote_tools]

    @server.call_tool()  # type: ignore[misc]
    async def handle_call_tool(
        name: str, arguments: dict[str, Any] | None
    ) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
        resp = _mcp_post(
            mcp_url,
            "tools/call",
            {"name": name, "arguments": arguments or {}},
        )
        result = resp.get("result", {})
        content = result.get("content", [])
        out: list[
            types.TextContent | types.ImageContent | types.EmbeddedResource
        ] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                out.append(
                    types.TextContent(type="text", text=block.get("text", ""))
                )
            elif isinstance(block, dict) and block.get("type") == "image":
                out.append(
                    types.ImageContent(
                        type="image",
                        data=block.get("data", ""),
                        mimeType=block.get("mimeType", "image/png"),
                    )
                )
        return out or [types.TextContent(type="text", text=json.dumps(result))]

    # --- prompts ------------------------------------------------------

    @server.list_prompts()  # type: ignore[misc, no-untyped-call]
    async def handle_list_prompts() -> list[types.Prompt]:
        return [types.Prompt(**p) for p in remote_prompts]

    @server.get_prompt()  # type: ignore[misc, no-untyped-call]
    async def handle_get_prompt(
        name: str, arguments: dict[str, str] | None
    ) -> types.GetPromptResult:
        resp = _mcp_post(
            mcp_url,
            "prompts/get",
            {"name": name, **({"arguments": arguments} if arguments else {})},
        )
        result = resp.get("result", {})
        messages: list[types.PromptMessage] = []
        for msg in result.get("messages", []):
            content = msg.get("content", {})
            text = (
                content.get("text", "")
                if isinstance(content, dict)
                else str(content)
            )
            messages.append(
                types.PromptMessage(
                    role=msg.get("role", "user"),
                    content=types.TextContent(type="text", text=text),
                )
            )
        return types.GetPromptResult(
            description=result.get("description"),
            messages=messages,
        )

    # --- run ----------------------------------------------------------

    print("marimo pair started (stdio)", file=sys.stderr)  # noqa: T201
    print(  # noqa: T201
        f"Connected to marimo at http://{host}:{port}", file=sys.stderr
    )
    print(  # noqa: T201
        'To start pairing: claude -p "/marimo-pair on this notebook"',
        file=sys.stderr,
    )

    async with mcp_stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="marimo-pair",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )
