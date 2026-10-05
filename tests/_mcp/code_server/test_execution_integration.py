# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

pytest.importorskip("mcp", reason="MCP requires Python 3.10+")

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp_types import (
    CLIENT_CAPABILITIES_META_KEY,
    PROTOCOL_VERSION_META_KEY,
)

from tests._cli._pair_server import PairTestServer, pair_test_server

if TYPE_CHECKING:
    from collections.abc import Generator


# Windows schedules KeyboardInterrupt at a Python evaluation boundary;
# short sleeps let it arrive promptly without ending the workload early.
_LONG_RUNNING_CODE = """\
import time
deadline = time.monotonic() + 60
while time.monotonic() < deadline:
    time.sleep(0.05)
"""


@pytest.fixture(scope="module")
def server(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[PairTestServer, None, None]:
    with pair_test_server(
        tmp_path_factory.mktemp("mcp-execution"), code_mcp=True
    ) as running:
        yield running


async def test_client_cancellation_interrupts_kernel_and_recovers(
    server: PairTestServer,
) -> None:
    # Modern MCP translates SDK cancellation into closing the request's
    # HTTP stream. Exercise the translation with a real process kernel.
    transport = streamable_http_client(f"{server.url}/mcp/server")
    async with Client(transport, mode="2026-07-28") as client:
        task = asyncio.create_task(
            client.call_tool(
                "execute_code",
                {
                    "session_id": server.session_id,
                    "code": _LONG_RUNNING_CODE,
                },
            )
        )
        try:
            await asyncio.to_thread(server.wait_for_kernel, "running")
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            await asyncio.to_thread(server.wait_for_kernel, "idle")

            recovered = await asyncio.wait_for(
                client.call_tool(
                    "execute_code",
                    {"session_id": server.session_id, "code": "print(42)"},
                ),
                timeout=10,
            )
            assert recovered.is_error is False
            assert recovered.structured_content is not None
            assert recovered.structured_content["success"] is True
            assert recovered.structured_content["stdout"] == ["42\n"]
        finally:
            if not task.done():
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task


async def test_http_stream_disconnect_interrupts_kernel_and_recovers(
    server: PairTestServer,
) -> None:
    # Bypass the SDK cancellation path: close an actual streamed HTTP
    # response without sending a cancellation notification.
    async with httpx2.AsyncClient(timeout=25) as http_client:
        async with http_client.stream(
            "POST",
            f"{server.url}/mcp/server",
            headers={
                "Accept": "application/json, text/event-stream",
                "MCP-Protocol-Version": "2026-07-28",
                "MCP-Method": "tools/call",
                "MCP-Name": "execute_code",
            },
            json={
                "jsonrpc": "2.0",
                "id": "disconnect-test",
                "method": "tools/call",
                "params": {
                    "name": "execute_code",
                    "arguments": {
                        "session_id": server.session_id,
                        "code": _LONG_RUNNING_CODE,
                    },
                    "_meta": {
                        PROTOCOL_VERSION_META_KEY: "2026-07-28",
                        CLIENT_CAPABILITIES_META_KEY: {},
                    },
                },
            },
        ) as response:
            response.raise_for_status()
            assert response.headers["content-type"].startswith(
                "text/event-stream"
            )
            await asyncio.to_thread(server.wait_for_kernel, "running")
            await response.aclose()

    await asyncio.to_thread(server.wait_for_kernel, "idle")
    transport = streamable_http_client(f"{server.url}/mcp/server")
    async with Client(transport, mode="2026-07-28") as client:
        recovered = await asyncio.wait_for(
            client.call_tool(
                "execute_code",
                {"session_id": server.session_id, "code": "print(42)"},
            ),
            timeout=10,
        )
        assert recovered.is_error is False
        assert recovered.structured_content is not None
        assert recovered.structured_content["success"] is True
        assert recovered.structured_content["stdout"] == ["42\n"]
