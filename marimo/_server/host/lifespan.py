# Copyright 2026 Marimo. All rights reserved.
"""Serves the host protocol for as long as the server runs."""

from __future__ import annotations

import contextlib
import secrets
from typing import TYPE_CHECKING

from marimo import _loggers
from marimo._host.host import Host
from marimo._host.model import HostState
from marimo._server.api.deps import AppState
from marimo._server.host.context import HostContext
from marimo._server.host.index import WorkspaceIndex
from marimo._server.host.record import HostRecordFile, host_url, new_record
from marimo._server.host.runtime import SessionManagerRuntime
from marimo._session.model import SessionMode

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from starlette.applications import Starlette

LOGGER = _loggers.marimo_logger()

OPERATIONS = [
    "notebook.create",
    "notebook.update",
    "notebook.delete",
    "notebook.open",
    "notebook.export",
]
"""What this host can do, as advertised in its `host` object."""


@contextlib.asynccontextmanager
async def host(app: Starlette) -> AsyncIterator[None]:
    """Builds the host, writes its record, and removes the record at the end.

    Only `marimo edit` is a host. `marimo run` serves an app to other
    people and must not invite local clients in.
    """
    state = AppState.from_app(app)
    if state.mode is not SessionMode.EDIT:
        yield
        return

    manager = state.session_manager
    runtime = SessionManagerRuntime(manager)
    the_host = Host(HostState(), runtime, operations=OPERATIONS)
    index = WorkspaceIndex(the_host, manager.workspace)
    index.refresh()
    runtime.bind(the_host, index=index)

    token = secrets.token_urlsafe(32)
    url = host_url(state.host, state.port, state.base_url)
    app.state.host_context = HostContext(
        host=the_host,
        runtime=runtime,
        index=index,
        token=token,
        url=url,
        port=state.port,
    )
    record = HostRecordFile(new_record(name="marimo", url=url, token=token))
    try:
        record.write()
    except Exception as e:
        LOGGER.warning("Could not write the host record: %s", e)

    try:
        yield
    finally:
        record.remove()
        app.state.host_context = None
