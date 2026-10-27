# Copyright 2026 Marimo. All rights reserved.
"""HTTP routes for notebooks, runtimes, runs, and event streams."""

from __future__ import annotations

import asyncio
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import quote

import msgspec
from anyio import create_task_group
from starlette.exceptions import HTTPException
from starlette.responses import Response, StreamingResponse
from starlette.routing import Route, Router, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

from marimo import _loggers
from marimo._core import protocol
from marimo._core.errors import (
    Conflict,
    NotFound,
)
from marimo._core.operations import Reply
from marimo._server.api.auth import TOKEN_QUERY_PARAM, validate_auth
from marimo._server.api.deps import AppState, AppStateBase
from marimo._server.api.endpoints.ws.ws_connection_validator import (
    ConnectionRejection,
    parse_connection_params,
)
from marimo._server.api.endpoints.ws_endpoint import DOC_MANAGER
from marimo._server.api.utils import format_url_host, open_url_in_browser
from marimo._server.host import (
    ATTACHMENT_IDENTITY,
    ATTACHMENT_KIND,
    ATTACHMENT_NAME,
    HOST_API_PATH,
    stream_options,
)
from marimo._server.host.events import serialize_event, serialize_sse_event
from marimo._server.host.notebook_api import (
    _context,
    _decode,
    _mutation,
    notebook_routes,
    problem,
)
from marimo._server.host.session import SessionEventStream
from marimo._server.sse import SSE_HEADERS
from marimo._server.tokens import AuthToken

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Iterator

    from anyio import CancelScope
    from starlette.requests import HTTPConnection, Request

    from marimo._core.notebook import Notebook
    from marimo._core.stream import RoutedEvent
    from marimo._server.host.bridge import SessionBridge
    from marimo._server.host.context import HostContext

LOGGER = _loggers.marimo_logger()


_ATTACHMENT_HEADERS = {
    "identity": ATTACHMENT_IDENTITY,
    "kind": ATTACHMENT_KIND,
    "name": ATTACHMENT_NAME,
}
"""Attachment fields and the request headers that supply them."""

PING = b": ping\n\n"
PING_SECONDS = 15.0


def build_app() -> Router:
    """Build the host API router."""
    routes = [
        Route("/events", _events, methods=["GET"]),
        Route("/notebooks", _create_notebook, methods=["POST"]),
        Route("/notebooks/{notebook_id}", _update_notebook, methods=["PATCH"]),
        Route(
            "/notebooks/{notebook_id}", _delete_notebook, methods=["DELETE"]
        ),
        Route(
            "/notebooks/{notebook_id}/events",
            _notebook_events,
            methods=["GET"],
        ),
        WebSocketRoute(
            "/notebooks/{notebook_id}/events/ws", _notebook_events_ws
        ),
        Route(
            "/notebooks/{notebook_id}/open", _open_notebook, methods=["POST"]
        ),
        *notebook_routes(),
    ]
    for route in routes:
        # Starlette implies HEAD for every GET route, but a HEAD here would
        # open a real stream and attach a client nobody can see.
        if isinstance(route, Route) and route.methods == {"GET", "HEAD"}:
            route.methods = {"GET"}
    return Router(
        routes=routes,
        default=_not_found,
        # Clients never follow redirects, so a trailing slash is a miss.
        redirect_slashes=False,
    )


async def _not_found(scope, receive, send) -> None:  # type: ignore[no-untyped-def]
    if scope["type"] == "websocket":
        await WebSocket(scope, receive, send).close(
            code=1008, reason="No such route"
        )
        return
    await problem(404, "not-found", "No such route")(scope, receive, send)


async def _notebook(request: HTTPConnection) -> Notebook:
    return await _context(request).bridge.host.notebook(
        request.path_params["notebook_id"]
    )


def _record(request: Request) -> protocol.Notebook:
    notebook_id = request.path_params["notebook_id"]
    host = _context(request).bridge.host
    record = host.notebooks.get(notebook_id)
    if record is None:
        raise NotFound(f"no notebook {notebook_id}")
    return record


# ---- streams -------------------------------------------------------------------


async def _events(request: Request) -> Response:
    """Stream catalog snapshots and updates.

    `Last-Event-ID` resumes from a cursor. `types` filters event kinds.
    """
    context = _context(request)
    cursor = _cursor(request)
    if isinstance(cursor, Response):
        return cursor
    types = _types(request)
    if isinstance(types, Response):
        return types
    # Refresh on connection because the catalog has no directory watcher.
    await context.bridge.refresh()
    return _stream(context, cursor, types, notebook_id=None)


async def _notebook_events(request: Request) -> Response:
    """Stream notebook events, attaching the client until disconnect."""
    context = _context(request)
    try:
        notebook = await _notebook(request)
    except NotFound as e:
        return problem(404, "not-found", str(e))
    except Conflict as e:
        return problem(409, "conflict", str(e))
    cursor = _cursor(request)
    if isinstance(cursor, Response):
        return cursor
    types = _types(request)
    if isinstance(types, Response):
        return types
    run_id = request.query_params.get("run_id")
    if run_id == "":
        return problem(400, "invalid-request", "run_id must not be empty")
    try:
        attachment = notebook.attach(
            identity=request.headers.get(ATTACHMENT_IDENTITY),
            kind=request.headers.get(ATTACHMENT_KIND),
            name=request.headers.get(ATTACHMENT_NAME),
        )
    except msgspec.ValidationError as e:
        return problem(400, "invalid-request", _attachment_problem(e))
    return _stream(
        context,
        cursor,
        types,
        notebook_id=notebook.id,
        run_id=run_id,
        on_close=lambda: notebook.detach(attachment.id),
    )


def editor_events_route(base_url: str = "") -> WebSocketRoute:
    """Expose the notebook event socket through editor authentication."""
    return WebSocketRoute(
        f"{base_url}{HOST_API_PATH}/notebooks/{{notebook_id}}/events/ws",
        _editor_events_ws,
    )


async def _editor_events_ws(websocket: WebSocket) -> None:
    state = AppStateBase.from_app(websocket.app)
    if state.enable_auth and not validate_auth(websocket):
        await websocket.close(
            code=1008, reason="Editor authentication required"
        )
        return
    # TODO: Move editor lifecycle and recipient routing to host attachments so
    # event subscriptions no longer need the legacy session_id.
    if "session_id" not in websocket.query_params:
        await _notebook_events_ws(websocket)
        return

    if "run_id" in websocket.query_params:
        await websocket.close(
            code=1008,
            reason="Editor sessions do not support run_id filtering",
        )
        return

    cursor = _cursor(websocket)
    if isinstance(cursor, Response):
        await websocket.close(code=1008, reason="Invalid event cursor")
        return
    types = _types(websocket)
    if isinstance(types, Response):
        await websocket.close(code=1008, reason="Invalid event types")
        return
    app_state = AppState(websocket)
    params = parse_connection_params(app_state)
    if isinstance(params, ConnectionRejection):
        await websocket.close(params.code, params.reason)
        return
    bridge = _context(websocket).bridge
    try:
        notebook = await _notebook(websocket)
    except (NotFound, Conflict) as exc:
        await websocket.close(code=1008, reason=str(exc))
        return
    manager = app_state.session_manager
    app = manager.app_manager(params.file_key)
    record = bridge.index.notebook_for(app.path)
    existing = manager.get_session(params.session_id)
    if (
        record is None
        or record.id != notebook.id
        or (
            existing is not None and existing.app_file_manager.path != app.path
        )
    ):
        await websocket.close(
            code=1008, reason="Session notebook does not match"
        )
        return
    await SessionEventStream(
        websocket,
        notebook=notebook,
        bridge=bridge,
        manager=manager,
        params=params,
        doc_manager=DOC_MANAGER,
        types=types,
        cursor=cursor,
    ).start()


async def _notebook_events_ws(websocket: WebSocket) -> None:
    """Send a snapshot or replay, then live notebook events."""
    cursor = _cursor(websocket)
    if isinstance(cursor, Response):
        await websocket.close(code=1008, reason="Invalid event cursor")
        return
    types = _types(websocket)
    if isinstance(types, Response):
        await websocket.close(code=1008, reason="Invalid event types")
        return
    run_id = websocket.query_params.get("run_id")
    if run_id == "":
        await websocket.close(code=1008, reason="run_id must not be empty")
        return
    try:
        notebook = await _notebook(websocket)
        attachment = notebook.attach(
            identity=websocket.headers.get(ATTACHMENT_IDENTITY),
            kind=websocket.headers.get(ATTACHMENT_KIND),
            name=websocket.headers.get(ATTACHMENT_NAME),
        )
    except (NotFound, Conflict) as exc:
        await websocket.close(code=1008, reason=str(exc))
        return
    except msgspec.ValidationError as exc:
        await websocket.close(code=1008, reason=_attachment_problem(exc))
        return

    bridge = _context(websocket).bridge

    async def send_events(
        subscription: _EventSubscription, cancel_scope: CancelScope
    ) -> None:
        try:
            for event in subscription.initial:
                await websocket.send_text(serialize_event(event))
            while True:
                event = await subscription.next()
                await websocket.send_text(serialize_event(event))
        except WebSocketDisconnect:
            cancel_scope.cancel()

    message = None
    try:
        with _subscribe_events(
            bridge,
            cursor,
            types,
            notebook_id=notebook.id,
            run_id=run_id,
            include_session=True,
        ) as subscription:
            await websocket.accept()
            async with create_task_group() as tasks:
                tasks.start_soon(send_events, subscription, tasks.cancel_scope)
                try:
                    message = await websocket.receive()
                finally:
                    tasks.cancel_scope.cancel()
            if (
                message is not None
                and message["type"] != "websocket.disconnect"
            ):
                await websocket.close(
                    code=1003, reason="This socket only sends events"
                )
    except WebSocketDisconnect:
        pass
    finally:
        notebook.detach(attachment.id)


def _cursor(request: HTTPConnection) -> str | Response | None:
    try:
        return stream_options.cursor(request)
    except ValueError as exc:
        return problem(400, "invalid-request", str(exc))


def _types(request: HTTPConnection) -> set[str] | Response | None:
    try:
        return stream_options.types(request)
    except ValueError as exc:
        return problem(400, "invalid-request", str(exc))


def _attachment_problem(error: msgspec.ValidationError) -> str:
    """Name the request header behind a rejected attachment field."""
    detail = str(error)
    for field, header in _ATTACHMENT_HEADERS.items():
        if detail.endswith(f"`$.{field}`"):
            return f"{header} is invalid"
    return "attachment headers are invalid"


def _initial_events(
    bridge: SessionBridge,
    cursor: str | None,
    types: set[str] | None,
    *,
    notebook_id: protocol.NotebookId | None,
    run_id: str | None = None,
    include_session: bool = False,
) -> list[RoutedEvent]:
    """Capture a snapshot or replay, with `ready` marking its end."""
    events = bridge.host.events(
        cursor, notebook_id=notebook_id, types=types, run_id=run_id
    )
    needs_snapshot = cursor is None or isinstance(
        events[0].event, protocol.ResetEvent
    )
    if include_session and notebook_id is not None and needs_snapshot:
        ready = events.pop()
        events.extend(
            event
            for event in bridge.session_snapshot(notebook_id)
            if event.wanted(types, run_id)
        )
        events.append(ready)
    return events


class _EventSubscription:
    def __init__(
        self, initial: list[RoutedEvent], queue: asyncio.Queue[RoutedEvent]
    ) -> None:
        self.initial = initial
        self._queue = queue
        self._ready_id = initial[-1].position or 0

    async def next(self) -> RoutedEvent:
        """Wait for a live event not already covered by the initial state."""
        while True:
            event = await self._queue.get()
            if event.position is None or event.position > self._ready_id:
                return event


@contextmanager
def _subscribe_events(
    bridge: SessionBridge,
    cursor: str | None,
    types: set[str] | None,
    *,
    notebook_id: protocol.NotebookId | None,
    run_id: str | None = None,
    include_session: bool = False,
) -> Iterator[_EventSubscription]:
    queue: asyncio.Queue[RoutedEvent] = asyncio.Queue()
    # Subscribe and capture state in one event-loop turn to avoid lost updates.
    unsubscribe = bridge.host.subscribe(
        queue.put_nowait,
        notebook_id=notebook_id,
        types=types,
        run_id=run_id,
    )
    try:
        initial = _initial_events(
            bridge,
            cursor,
            types,
            notebook_id=notebook_id,
            run_id=run_id,
            include_session=include_session,
        )
        yield _EventSubscription(initial, queue)
    finally:
        unsubscribe()


def _stream(
    context: HostContext,
    cursor: str | None,
    types: set[str] | None,
    *,
    notebook_id: protocol.NotebookId | None,
    run_id: str | None = None,
    on_close: Callable[[], None] | None = None,
) -> Response:
    async def body() -> AsyncIterator[bytes]:
        try:
            with _subscribe_events(
                context.bridge,
                cursor,
                types,
                notebook_id=notebook_id,
                run_id=run_id,
            ) as subscription:
                for event in subscription.initial:
                    yield _frame(event)
                while True:
                    try:
                        event = await asyncio.wait_for(
                            subscription.next(), PING_SECONDS
                        )
                    except TimeoutError:
                        yield PING
                        continue
                    yield _frame(event)
        finally:
            if on_close is not None:
                on_close()

    return StreamingResponse(
        body(), media_type="text/event-stream", headers=SSE_HEADERS
    )


def _frame(event: RoutedEvent) -> bytes:
    """Encode an event as an SSE frame."""
    return serialize_sse_event(event).encode()


# ---- notebooks -----------------------------------------------------------------


def _inside_project(path: str) -> Path:
    if "\x00" in path:
        raise HTTPException(400, "path must not contain NUL")
    relative = Path(path)
    if relative.is_absolute() or ".." in relative.parts:
        raise HTTPException(400, "path must stay in the project")
    return relative


@_mutation("notebook.create")
async def _create_notebook(request: Request) -> Reply:
    """Create an empty notebook in the project."""
    context = _context(request)
    key = request.headers["Idempotency-Key"]
    body = await _decode(request, protocol.CreateNotebookRequest)

    index = context.bridge.index
    if index.root is None or body.project_id != index.project_id:
        raise HTTPException(404, f"No project {body.project_id}")
    if body.path is msgspec.UNSET:
        raise HTTPException(400, "path is required")
    relative = _inside_project(body.path)
    file = index.root / relative
    notebook = await context.bridge.create(
        file,
        name=None if body.name is msgspec.UNSET else body.name,
        request_id=key,
    )
    return 201, notebook


@_mutation("notebook.update")
async def _update_notebook(request: Request) -> Reply:
    """Change a notebook's path or display name, preserving its runtime."""
    context = _context(request)
    key = request.headers["Idempotency-Key"]
    record = _record(request)
    body = await _decode(request, protocol.UpdateNotebookRequest)

    if body.path is msgspec.UNSET and body.name is msgspec.UNSET:
        raise HTTPException(400, "path or name is required")
    index = context.bridge.index
    target = None
    if body.path is not msgspec.UNSET:
        if index.root is None:
            raise HTTPException(409, "The notebook has no file to move")
        relative = _inside_project(body.path)
        target = index.root / relative
    notebook = await context.bridge.update(
        record.id,
        target=target,
        name=None if body.name is msgspec.UNSET else body.name,
        request_id=key,
    )
    return 200, notebook


@_mutation("notebook.delete")
async def _delete_notebook(request: Request) -> Reply:
    """Delete the notebook and its file if it has no runtime."""
    context = _context(request)
    key = request.headers["Idempotency-Key"]
    await context.bridge.delete(_record(request).id, request_id=key)
    return 204, None


@_mutation("notebook.open")
async def _open_notebook(request: Request) -> Reply:
    """Open the notebook in the configured browser."""
    record = _record(request)
    file = _context(request).bridge.index.file_of(record.id)
    if file is None:
        raise HTTPException(409, "The notebook has no file to open")

    state = AppStateBase.from_app(request.app)
    authority = f"{format_url_host(state.host, state.port)}:{state.port}"
    url = f"http://{authority}{state.base_url}/?file={quote(str(file))}"
    auth_token = state.session_manager.auth_token
    if not AuthToken.is_empty(auth_token):
        url += f"&{TOKEN_QUERY_PARAM}={quote(str(auth_token))}"
    browser = state.config_manager.get_config()["server"]["browser"]
    # Keep blocking browser discovery off the event loop.
    threading.Thread(
        target=_open_quietly, args=(browser, url), daemon=True
    ).start()
    return 200, protocol.OpenNotebookResponse(url=url)


def _open_quietly(browser: str, url: str) -> None:
    try:
        open_url_in_browser(browser, url)
    except Exception as e:
        LOGGER.warning("Could not open the notebook in a browser: %s", e)


# ---- runtimes ------------------------------------------------------------------


# ---- runs ----------------------------------------------------------------------
