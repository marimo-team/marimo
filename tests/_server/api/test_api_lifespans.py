# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import threading
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from marimo._server.api import lifespans
from marimo._session.model import SessionMode


async def test_browser_launch_does_not_block_event_loop_or_lifespan() -> None:
    state = MagicMock()
    state.headless = False
    state.config_manager.get_config.return_value = {
        "server": {"browser": "default"}
    }
    loop = asyncio.get_running_loop()
    started = asyncio.Event()
    finished = asyncio.Event()
    release = threading.Event()
    threads: list[threading.Thread] = []

    def blocked_launch(_browser: str, _url: str) -> None:
        threads.append(threading.current_thread())
        loop.call_soon_threadsafe(started.set)
        release.wait(timeout=5)
        loop.call_soon_threadsafe(finished.set)

    with (
        patch.object(lifespans.AppState, "from_app", return_value=state),
        patch.object(
            lifespans, "_startup_url", return_value="http://localhost:2718"
        ),
        patch.object(
            lifespans, "open_url_in_browser", side_effect=blocked_launch
        ) as launch,
    ):
        try:
            async with lifespans.open_browser(MagicMock()):
                await asyncio.wait_for(started.wait(), timeout=1)
                assert not finished.is_set()
                assert threads[0].daemon
            assert not finished.is_set()
        finally:
            release.set()
            await asyncio.wait_for(finished.wait(), timeout=1)
            threads[0].join(timeout=1)

    launch.assert_called_once_with("default", "http://localhost:2718")


async def test_cleanup_mcp_task_disconnects_client() -> None:
    mcp_client = MagicMock()
    mcp_client.disconnect_from_all_servers = AsyncMock()
    task = MagicMock()
    task.cancelled.return_value = False
    task.result.return_value = mcp_client

    with patch.object(
        lifespans, "cancel_and_wait", new_callable=AsyncMock
    ) as cancel_and_wait:
        await lifespans._cleanup_mcp_task(task)

    cancel_and_wait.assert_awaited_once_with(task)
    mcp_client.disconnect_from_all_servers.assert_awaited_once_with()


async def test_cleanup_mcp_task_logs_task_failure() -> None:
    task = MagicMock()
    task.cancelled.return_value = False
    task.result.side_effect = RuntimeError("connect failed")

    with (
        patch.object(
            lifespans, "cancel_and_wait", new_callable=AsyncMock
        ) as cancel_and_wait,
        patch.object(lifespans.LOGGER, "exception") as log_exception,
    ):
        await lifespans._cleanup_mcp_task(task)

    cancel_and_wait.assert_awaited_once_with(task)
    log_exception.assert_called_once_with(
        "MCP connection task failed during cleanup"
    )


async def test_cleanup_mcp_task_logs_disconnect_failure() -> None:
    mcp_client = MagicMock()
    mcp_client.disconnect_from_all_servers = AsyncMock(
        side_effect=RuntimeError("disconnect failed")
    )
    task = MagicMock()
    task.cancelled.return_value = False
    task.result.return_value = mcp_client

    with (
        patch.object(lifespans, "cancel_and_wait", new_callable=AsyncMock),
        patch.object(lifespans.LOGGER, "exception") as log_exception,
    ):
        await lifespans._cleanup_mcp_task(task)

    log_exception.assert_called_once_with(
        "Failed to disconnect from MCP servers"
    )


async def test_lsp_cleanup_after_error() -> None:
    state = MagicMock()
    state.config_manager.get_config.return_value = {}
    state.session_manager.mode = SessionMode.EDIT
    task = MagicMock()

    with (
        patch.object(lifespans.AppState, "from_app", return_value=state),
        patch.object(lifespans, "any_lsp_server_running", return_value=True),
        patch.object(lifespans, "supervised_task", return_value=task),
        patch.object(
            lifespans, "cancel_and_wait", new_callable=AsyncMock
        ) as cancel_and_wait,
    ):
        with pytest.raises(RuntimeError, match="server failed"):
            async with lifespans.lsp(MagicMock()):
                raise RuntimeError("server failed")

    cancel_and_wait.assert_awaited_once_with(task)
