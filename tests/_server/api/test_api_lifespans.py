# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from marimo._server.api import lifespans
from marimo._session.model import SessionMode


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
