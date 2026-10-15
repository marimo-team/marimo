# Copyright 2026 Marimo. All rights reserved.
"""Host API startup and shutdown."""

from __future__ import annotations

import asyncio
import contextlib
import secrets
from typing import TYPE_CHECKING

from marimo import _loggers
from marimo._server.api.deps import AppStateBase
from marimo._server.host.bridge import SessionBridge
from marimo._server.host.context import HostContext
from marimo._server.host.record import HostRecordFile, host_url
from marimo._session.model import SessionMode

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from starlette.applications import Starlette

LOGGER = _loggers.marimo_logger()


@contextlib.asynccontextmanager
async def host(app: Starlette) -> AsyncIterator[None]:
    """Initialize the host API and discovery record in edit mode."""
    state = AppStateBase.from_app(app)
    if state.mode is not SessionMode.EDIT:
        yield
        return

    bridge = SessionBridge(state.session_manager, state.config_manager)
    await bridge.open()
    token = secrets.token_urlsafe(32)
    server = state.server.config
    url = host_url(server.host, server.port, state.base_url)
    context = HostContext(bridge=bridge, token=token, port=server.port)
    app.state.host_context = context

    async def maintain() -> None:
        while True:
            await asyncio.sleep(1)
            context.expire()

    maintenance = asyncio.create_task(maintain(), name="host.retention")
    record = None
    if url is None:
        LOGGER.warning("No host record: loopback cannot reach %s", server.host)
    else:
        record = HostRecordFile(url=url, token=token)
        try:
            record.write()
        except Exception as e:
            LOGGER.warning("Could not write the host record: %s", e)
    try:
        yield
    finally:
        maintenance.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await maintenance
        if record is not None:
            record.remove()
        bridge.close()
        app.state.host_context = None
