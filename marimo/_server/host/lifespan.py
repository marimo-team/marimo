# Copyright 2026 Marimo. All rights reserved.
"""Host API startup and shutdown."""

from __future__ import annotations

import asyncio
import contextlib
import secrets
from typing import TYPE_CHECKING

from marimo import _loggers
from marimo._server.api.deps import AppStateBase
from marimo._server.api.utils import format_url_host
from marimo._server.host.bridge import SessionBridge
from marimo._server.host.context import HostContext
from marimo._server.host.record import HostRecordFile, host_url
from marimo._server.scratchpad import scratchpad_request_metadata
from marimo._session.model import SessionMode

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from starlette.applications import Starlette

LOGGER = _loggers.marimo_logger()


async def ensure_app_host(app: Starlette) -> HostContext:
    """Initialize a private app host, including for mounts without a lifespan."""
    state = AppStateBase.from_app(app)
    if state.mode is not SessionMode.RUN:
        raise RuntimeError("Run lifespan requires run mode")
    if state.host_context is not None:
        return state.host_context
    bridge = SessionBridge(state.session_manager, state.config_manager)
    # App open only subscribes to session events: it does not index files or
    # await adoption. Concurrent first connections share this context.
    await bridge.open()
    context = HostContext(bridge=bridge, token="", port=0)
    app.state.host_context = context
    return context


async def ensure_host(app: Starlette) -> HostContext:
    """Return the host used by session brokering and the server lifespan."""
    state = AppStateBase.from_app(app)
    if state.mode is SessionMode.RUN:
        return await ensure_app_host(app)
    if state.host_context is not None:
        return state.host_context
    server = state.server.config
    url_host = format_url_host(
        server.host, server.port, route_bind_all_to_loopback=True
    )
    server_url = f"http://{url_host}:{server.port}{state.base_url.rstrip('/')}"
    bridge = SessionBridge(
        state.session_manager,
        state.config_manager,
        request_metadata=lambda session: scratchpad_request_metadata(
            session,
            server_url=server_url,
            auth_token=str(state.session_manager.auth_token),
        ),
    )
    await bridge.open()
    token = secrets.token_urlsafe(32)
    context = HostContext(bridge=bridge, token=token, port=server.port)
    app.state.host_context = context

    return context


@contextlib.asynccontextmanager
async def host(app: Starlette) -> AsyncIterator[None]:
    """Serve notebook sessions; publish local discovery only in edit mode."""
    state = AppStateBase.from_app(app)
    if state.mode is SessionMode.RUN:
        context = await ensure_app_host(app)
        try:
            yield
        finally:
            context.bridge.close()
            app.state.host_context = None
        return

    context = await ensure_host(app)
    server = state.server.config
    url = host_url(server.host, server.port, state.base_url)

    async def maintain() -> None:
        while True:
            await asyncio.sleep(1)
            context.mutations.expire()

    maintenance = asyncio.create_task(maintain(), name="host.retention")
    record = None
    if url is None:
        LOGGER.warning("No host record: loopback cannot reach %s", server.host)
    else:
        record = HostRecordFile(url=url, token=context.token)
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
        context.bridge.close()
        app.state.host_context = None
