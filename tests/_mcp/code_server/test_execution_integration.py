# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import json
import sys
from typing import TYPE_CHECKING

import pytest

pytest.importorskip("mcp", reason="MCP requires Python 3.10+")

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp_types import (
    CLIENT_CAPABILITIES_META_KEY,
    PROTOCOL_VERSION_META_KEY,
    CallToolResult,
)

from tests._cli._pair_server import PairTestServer, pair_test_server

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path


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


@pytest.mark.parametrize(
    "code",
    [
        _LONG_RUNNING_CODE,
        pytest.param(
            "import time; time.sleep(60)",
            marks=pytest.mark.skipif(
                sys.platform == "win32",
                reason="Windows interrupts require a Python evaluation boundary",
            ),
            id="blocking-sleep",
        ),
    ],
    ids=["python-loop", "blocking-sleep"],
)
async def test_client_cancellation_interrupts_kernel_and_recovers(
    server: PairTestServer,
    code: str,
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
                    "code": code,
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


async def test_cancelled_scratchpad_queued_behind_notebook_does_not_run(
    server: PairTestServer, tmp_path: Path
) -> None:
    release = tmp_path / "release"
    completed = tmp_path / "completed"
    abandoned = tmp_path / "abandoned"
    async with httpx2.AsyncClient(timeout=25) as http_client:
        response = await http_client.post(
            f"{server.url}/api/kernel/run",
            headers={"Marimo-Session-Id": server.session_id},
            json={
                "cellIds": ["blocking"],
                "codes": [
                    (
                        "import time\nfrom pathlib import Path\n"
                        "_deadline = time.monotonic() + 40\n"
                        f"while not Path({str(release)!r}).exists():\n"
                        "    if time.monotonic() > _deadline:\n"
                        "        raise TimeoutError('test did not release notebook')\n"
                        "    time.sleep(0.05)\n"
                        f"Path({str(completed)!r}).touch()"
                    )
                ],
            },
        )
        response.raise_for_status()
        await asyncio.to_thread(server.wait_for_kernel, "running")
        try:
            # Receiving the deferred HTTP stream headers ensures the tool
            # request reached the server while the notebook is still busy.
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
                    "id": "cancel-queued-test",
                    "method": "tools/call",
                    "params": {
                        "name": "execute_code",
                        "arguments": {
                            "session_id": server.session_id,
                            "code": (
                                "from pathlib import Path\n"
                                f"Path({str(abandoned)!r}).touch()"
                            ),
                        },
                        "_meta": {
                            PROTOCOL_VERSION_META_KEY: "2026-07-28",
                            CLIENT_CAPABILITIES_META_KEY: {},
                        },
                    },
                },
            ) as response:
                response.raise_for_status()
                await response.aclose()
            # A subsequent call is a barrier for server-side cancellation.
            transport = streamable_http_client(f"{server.url}/mcp/server")
            async with Client(transport, mode="2026-07-28") as client:
                followup = asyncio.create_task(
                    client.call_tool(
                        "execute_code",
                        {"session_id": server.session_id, "code": "print(42)"},
                    )
                )
                release.touch()
                result = await asyncio.wait_for(followup, timeout=10)
                assert result.is_error is False
            assert completed.exists(), "cancellation interrupted notebook work"
            assert not abandoned.exists(), "cancelled queued code still ran"
        finally:
            release.touch()
            await asyncio.to_thread(server.wait_for_kernel, "idle")


async def test_cancelled_execution_hands_lock_to_waiting_call(
    server: PairTestServer,
) -> None:
    waiting_response = asyncio.Event()

    async def received_headers(response: httpx2.Response) -> None:
        if response.request.headers.get("MCP-Name") != "execute_code":
            return
        payload = json.loads(response.request.content)
        if payload["params"]["arguments"]["code"] == "print(42)":
            waiting_response.set()

    async with httpx2.AsyncClient(
        timeout=25, event_hooks={"response": [received_headers]}
    ) as http_client:
        transport = streamable_http_client(
            f"{server.url}/mcp/server", http_client=http_client
        )
        async with Client(transport, mode="2026-07-28") as client:
            first = asyncio.create_task(
                client.call_tool(
                    "execute_code",
                    {
                        "session_id": server.session_id,
                        "code": _LONG_RUNNING_CODE,
                    },
                )
            )
            second: asyncio.Task[CallToolResult] | None = None
            try:
                await asyncio.to_thread(server.wait_for_kernel, "running")
                second = asyncio.create_task(
                    client.call_tool(
                        "execute_code",
                        {"session_id": server.session_id, "code": "print(42)"},
                    )
                )
                # Deferred headers prove the second request reached the
                # server while the first is still running, without a sleep
                # guessing how long dispatch takes on a busy CI runner.
                await asyncio.wait_for(waiting_response.wait(), timeout=25)
                assert not second.done()
                first.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await first
                result = await asyncio.wait_for(second, timeout=10)
                assert result.is_error is False
                assert result.structured_content is not None
                assert result.structured_content["success"] is True
                assert result.structured_content["stdout"] == ["42\n"]
                assert result.structured_content["stderr"] == []
            finally:
                for task in (first, second):
                    if task is not None and not task.done():
                        task.cancel()
                        with pytest.raises(asyncio.CancelledError):
                            await task
                await asyncio.to_thread(server.wait_for_kernel, "idle")
