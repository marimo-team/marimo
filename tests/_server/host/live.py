# Copyright 2026 Marimo. All rights reserved.
"""A host serving one notebook from a real session and kernel."""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

from marimo._config.config import DEFAULT_CONFIG
from marimo._server.host.bridge import SessionBridge
from marimo._server.host.context import HostContext
from marimo._server.main import create_starlette_app
from marimo._server.workspace import SingleFileWorkspace
from marimo._utils.marimo_path import MarimoPath
from tests._server.host.drive import PORT, finished, request, wait_for
from tests._server.mocks import (
    get_mock_session_manager,
    get_starlette_server_state_init,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from starlette.applications import Starlette

    from marimo._config.config import OnCellChangeType
    from tests._server.host.drive import Response

TOKEN = "execution-test"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def key(value: str) -> dict[str, str]:
    return {**AUTH, "Idempotency-Key": value}


@contextlib.asynccontextmanager
async def open_host(
    tmp_path: Path,
    source: str,
    *,
    on_cell_change: OnCellChangeType = "autorun",
) -> AsyncIterator[tuple[Starlette, str, Response]]:
    """Serve `source` with a started runtime, following its events."""
    manager = get_mock_session_manager()
    file = tmp_path / "notebook.py"
    file.write_text(source)
    manager.workspace = SingleFileWorkspace.from_path(MarimoPath(file))
    manager.redirect_console_to_browser = True
    manager._config_manager = manager._config_manager.with_overrides(
        {
            "runtime": {
                **DEFAULT_CONFIG["runtime"],
                "on_cell_change": on_cell_change,
            }
        }
    )
    app = create_starlette_app(base_url="", enable_auth=True)
    get_starlette_server_state_init(session_manager=manager).apply(app.state)
    bridge = SessionBridge(manager)
    await bridge.open()
    app.state.host_context = HostContext(bridge=bridge, token=TOKEN, port=PORT)
    notebook = next(iter(bridge.host.notebooks.values()))
    events, task, disconnect = request(
        app, "GET", f"/notebooks/{notebook.id}/events", headers=AUTH
    )
    try:
        started = await finished(
            app,
            "PUT",
            f"/notebooks/{notebook.id}/runtime",
            headers=key("start"),
        )
        assert started.status == 202
        await wait_for(
            events,
            lambda response: any(
                r.get("data", {}).get("runtime", {}).get("status") == "running"
                for r in response.records
            ),
            timeout=15,
        )
        yield app, notebook.id, events
    finally:
        disconnect()
        await asyncio.wait_for(task, 5)
        bridge.close()
        await manager.shutdown()
