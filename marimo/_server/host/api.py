# Copyright 2026 Marimo. All rights reserved.
"""HTTP routes for notebooks, runtimes, runs, and event streams."""

from __future__ import annotations

import asyncio
import hashlib
import threading
from collections.abc import Awaitable, Callable
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING, TypeAlias, TypeVar
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
    DecisionRequired,
    EditConflict,
    Invalid,
    NoRuntime,
    NotFound,
)
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
from marimo._server.host.context import CachedMutation
from marimo._server.host.events import serialize_event, serialize_sse_event
from marimo._server.host.session import SessionEventStream
from marimo._server.sse import SSE_HEADERS
from marimo._server.tokens import AuthToken

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

    from anyio import CancelScope
    from starlette.requests import HTTPConnection, Request

    from marimo._core.notebook import Notebook
    from marimo._core.stream import RoutedEvent
    from marimo._server.host.bridge import SessionBridge
    from marimo._server.host.context import HostContext

LOGGER = _loggers.marimo_logger()

_Endpoint: TypeAlias = Callable[["Request"], Awaitable[Response]]
_Body = TypeVar("_Body", bound=msgspec.Struct)

PROBLEM_TYPE_PREFIX = "tag:marimo.io,2026:host/"
"""Prefix for host protocol problem types."""


_ATTACHMENT_HEADERS = {
    "identity": ATTACHMENT_IDENTITY,
    "kind": ATTACHMENT_KIND,
    "name": ATTACHMENT_NAME,
}
"""Attachment fields and the request headers that supply them."""

PING = b": ping\n\n"
PING_SECONDS = 15.0


_TITLES = {
    "invalid-request": "Invalid request",
    "unauthorized": "Unauthorized",
    "forbidden": "Forbidden",
    "not-found": "Not found",
    "method-not-allowed": "Method not allowed",
    "conflict": "Conflict",
    "no-runtime": "No runtime",
    "decision-required": "Decision required",
    "unsupported-operation": "Unsupported operation",
    "internal": "Internal error",
}


_HTTP_KINDS = {
    400: "invalid-request",
    404: "not-found",
    405: "method-not-allowed",
    409: "conflict",
}


def problem(
    status: int,
    kind: str | None = None,
    detail: str | None = None,
    *,
    edit: protocol.EditConflict | None = None,
    decisions: tuple[protocol.Decision, ...] | None = None,
) -> Response:
    """Return a protocol error as an HTTP problem response.

    Without a kind, the status picks one. A status this protocol does
    not name is a server bug, so it becomes a 500 rather than a problem
    of an unknown kind. A conflict over an edit carries `edit`, and a
    request that needs a choice first carries `decisions`.
    """
    kind = _HTTP_KINDS.get(status) if kind is None else kind

    if kind is None:
        LOGGER.error("The host API raised an unmapped status %s", status)
        status, kind, detail = 500, "internal", "The host failed"
    body = protocol.Problem(
        type=PROBLEM_TYPE_PREFIX + kind,
        title=_TITLES[kind],
        status=status,
        detail=msgspec.UNSET if detail is None else detail,
        edit=msgspec.UNSET if edit is None else edit,
        decisions=msgspec.UNSET if decisions is None else decisions,
    )
    return Response(
        msgspec.json.encode(body),
        status_code=status,
        media_type="application/problem+json",
    )


def build_app() -> Router:
    """Build the host API router."""
    routes = [
        Route("/events", _events, methods=["GET"]),
        Route("/notebooks", _create_notebook, methods=["POST"]),
        Route("/notebooks/{id}", _update_notebook, methods=["PATCH"]),
        Route("/notebooks/{id}", _delete_notebook, methods=["DELETE"]),
        Route("/notebooks/{id}/events", _notebook_events, methods=["GET"]),
        WebSocketRoute("/notebooks/{id}/events/ws", _notebook_events_ws),
        Route("/notebooks/{id}/edits", _edit_notebook, methods=["POST"]),
        Route("/notebooks/{id}/save", _save_notebook, methods=["POST"]),
        Route("/notebooks/{id}/open", _open_notebook, methods=["POST"]),
        Route("/notebooks/{id}/runtime", _start_runtime, methods=["PUT"]),
        Route("/notebooks/{id}/runtime", _stop_runtime, methods=["DELETE"]),
        Route(
            "/notebooks/{id}/runtime/restart",
            _restart_runtime,
            methods=["POST"],
        ),
        Route("/notebooks/{id}/runtime/runs", _run, methods=["POST"]),
        Route(
            "/notebooks/{id}/runtime/runs/{run_id}",
            _interrupt,
            methods=["DELETE"],
        ),
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


def _context(request: HTTPConnection) -> HostContext:
    context = getattr(request.app.state, "host_context", None)
    assert context is not None, "HostApiMiddleware admits requests only then"
    return context  # type: ignore[no-any-return]


async def _notebook(request: HTTPConnection) -> Notebook:
    return await _context(request).bridge.host.notebook(
        request.path_params["id"]
    )


def _record(request: Request) -> protocol.Notebook:
    notebook_id = request.path_params["id"]
    host = _context(request).bridge.host
    record = host.notebooks.get(notebook_id)
    if record is None:
        raise NotFound(f"no notebook {notebook_id}")
    return record


def _mutation(operation: str) -> Callable[[_Endpoint], _Endpoint]:
    """Apply capability checks, idempotency, and protocol errors to a command."""

    def decorate(endpoint: _Endpoint) -> _Endpoint:
        @wraps(endpoint)
        async def handle(request: Request) -> Response:
            context = _context(request)
            if operation not in context.bridge.host.operations:
                return problem(
                    501,
                    "unsupported-operation",
                    f"This host does not offer {operation}",
                )
            key = request.headers.get("Idempotency-Key", "")
            if not key:
                return problem(
                    400, "invalid-request", "Idempotency-Key is required"
                )
            digest = hashlib.sha256(await request.body()).hexdigest()
            # A precondition is part of the request, so a retry that
            # names another revision is another request.
            if_match = request.headers.get("If-Match", "")
            fingerprint = (
                f"{request.method} {request.url.path} {digest} {if_match}"
            )
            remembered = context.remembered(key)
            if remembered is not None:
                if remembered.fingerprint != fingerprint:
                    return problem(
                        409,
                        "conflict",
                        f"Idempotency-Key {key} was used for another request",
                    )
                response = await asyncio.shield(remembered.task)
                if remembered.run is not None:
                    return _reply(202, remembered.run)
                return response

            task = asyncio.create_task(_execute_mutation(endpoint, request))
            mutation = CachedMutation(fingerprint, task)
            context.replies[key] = mutation
            unsubscribe: Callable[[], None] | None = None
            lifecycle_accepted: Callable[[Response], None] | None = None
            if operation == "runtime.run" and request.method == "POST":
                # The receipt outlives results without retaining their payloads.
                def updated(event: RoutedEvent) -> None:
                    if isinstance(event.event, protocol.RunEvent):
                        run = event.event.data.run
                        if event.event.data.request_id == key:
                            mutation.run = run
                            if (
                                run.status == "completed"
                                and unsubscribe is not None
                            ):
                                context.settle(mutation)
                                unsubscribe()

                unsubscribe = context.bridge.host.subscribe(
                    updated,
                    notebook_id=request.path_params["id"],
                    types={"run"},
                )
            elif operation in {
                "runtime.start",
                "runtime.stop",
                "runtime.restart",
            }:
                lifecycle_accepted, unsubscribe = _watch_lifecycle(
                    context,
                    mutation,
                    operation=operation,
                    notebook_id=request.path_params["id"],
                    request_id=key,
                )

            def completed(task: asyncio.Task[Response]) -> None:
                if (
                    task.cancelled()
                    or task.exception() is not None
                    or task.result().status_code >= 400
                ):
                    context.replies.pop(key, None)
                    if unsubscribe is not None:
                        unsubscribe()
                elif lifecycle_accepted is not None:
                    lifecycle_accepted(task.result())
                elif mutation.expires_at is None and (
                    mutation.run is None or mutation.run.status == "completed"
                ):
                    context.settle(mutation)

            task.add_done_callback(completed)
            # A disconnected waiter must not cancel a shared mutation.
            return await asyncio.shield(task)

        return handle

    return decorate


def _watch_lifecycle(
    context: HostContext,
    mutation: CachedMutation,
    *,
    operation: str,
    notebook_id: str,
    request_id: str,
) -> tuple[Callable[[Response], None], Callable[[], None]]:
    runtime_id: protocol.RuntimeId | None = None
    previous_id: protocol.RuntimeId | None = None
    early: list[RoutedEvent] = []

    def settle() -> None:
        context.settle(mutation)
        unsubscribe()

    def updated(event: RoutedEvent) -> None:
        nonlocal previous_id
        if mutation.expires_at is not None:
            return
        if runtime_id is None:
            # A backend can finish synchronously, before the response exists.
            early.append(event)
            return
        if isinstance(event.event, protocol.NotebookRemovedEvent):
            settle()
        elif isinstance(event.event, protocol.RuntimeEvent):
            runtime = event.event.data.runtime
            if (
                operation == "runtime.restart"
                and event.event.data.request_id == request_id
                and runtime.status == "terminating"
                and runtime.id != runtime_id
            ):
                previous_id = runtime.id
            if (
                operation != "runtime.stop"
                and runtime.id == runtime_id
                and runtime.status in ("running", "failed")
            ):
                settle()
        elif isinstance(event.event, protocol.RuntimeRemovedEvent):
            if event.event.data.id == runtime_id or (
                event.event.data.id == previous_id
                and event.event.data.request_id != request_id
            ):
                # A later stop can cancel a restart before its replacement starts.
                settle()

    unsubscribe = context.bridge.host.subscribe(
        updated, notebook_id=notebook_id, types={"runtime", "notebook"}
    )

    def accepted(response: Response) -> None:
        nonlocal runtime_id
        if response.status_code == 202:
            runtime_id = msgspec.json.decode(
                response.body, type=protocol.Runtime
            ).id
            for event in early:
                updated(event)
        else:
            settle()
        early.clear()

    return accepted, unsubscribe


async def _execute_mutation(endpoint: _Endpoint, request: Request) -> Response:
    try:
        return await endpoint(request)
    except NoRuntime as e:
        return problem(409, "no-runtime", str(e))
    except DecisionRequired as e:
        return problem(409, "decision-required", str(e), decisions=e.decisions)
    except EditConflict as e:
        return problem(
            409,
            "conflict",
            str(e),
            edit=protocol.EditConflict(
                change=e.change, cell=e.cell, document=e.document
            ),
        )
    except Conflict as e:
        return problem(409, "conflict", str(e))
    except Invalid as e:
        return problem(400, "invalid-request", str(e))
    except NotFound as e:
        return problem(404, "not-found", str(e))
    except msgspec.DecodeError as e:
        return problem(400, "invalid-request", str(e))
    except HTTPException as e:
        return problem(e.status_code, detail=e.detail)


def _reply(status: int, body: msgspec.Struct | None = None) -> Response:
    return Response(
        b"" if body is None else msgspec.json.encode(body),
        status_code=status,
        media_type="application/json" if body is not None else None,
    )


async def _decode(request: Request, kind: type[_Body]) -> _Body:
    return msgspec.json.decode(await request.body() or b"{}", type=kind)


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
        f"{base_url}{HOST_API_PATH}/notebooks/{{id}}/events/ws",
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
                    except asyncio.TimeoutError:
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
async def _create_notebook(request: Request) -> Response:
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
    return _reply(201, notebook)


@_mutation("notebook.update")
async def _update_notebook(request: Request) -> Response:
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
    return _reply(200, notebook)


@_mutation("notebook.delete")
async def _delete_notebook(request: Request) -> Response:
    """Delete the notebook and its file if it has no runtime."""
    context = _context(request)
    key = request.headers["Idempotency-Key"]
    await context.bridge.delete(_record(request).id, request_id=key)
    return _reply(204, None)


@_mutation("notebook.edit")
async def _edit_notebook(request: Request) -> Response:
    """Apply an edit as one unit; 409 with `edit` when a precondition is stale."""
    context = _context(request)
    key = request.headers["Idempotency-Key"]
    notebook = await _notebook(request)
    body = await _decode(request, protocol.EditRequest)
    response = await context.bridge.edit(
        notebook.id, body.changes, request_id=key
    )
    return _reply(200, response)


@_mutation("notebook.save")
async def _save_notebook(request: Request) -> Response:
    """Write the document to its file; 409 with `edit` when `If-Match` is stale."""
    context = _context(request)
    key = request.headers["Idempotency-Key"]
    notebook = await _notebook(request)
    body = await _decode(request, protocol.SaveRequest)
    response = await context.bridge.save(
        notebook.id,
        if_match=_if_match(request.headers.get("If-Match")),
        decisions={} if body.decisions is msgspec.UNSET else body.decisions,
        request_id=key,
    )
    return _reply(200, response)


def _if_match(header: str | None) -> tuple[str, ...] | None:
    """The etags an `If-Match` header accepts, or `None` when it accepts any.

    The header is `*` or a comma-separated list of entity tags, each
    optionally quoted. `If-Match` compares strongly (RFC 9110, 13.1.1),
    so a tag marked weak with `W/` never matches and is left out.
    """
    if header is None or header.strip() == "*":
        return None
    tags = []
    for part in header.split(","):
        tag = part.strip()
        if tag and not tag.startswith("W/"):
            tags.append(tag.strip('"'))
    return tuple(tags)


@_mutation("notebook.open")
async def _open_notebook(request: Request) -> Response:
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
    return _reply(200, protocol.OpenNotebookResponse(url=url))


def _open_quietly(browser: str, url: str) -> None:
    try:
        open_url_in_browser(browser, url)
    except Exception as e:
        LOGGER.warning("Could not open the notebook in a browser: %s", e)


# ---- runtimes ------------------------------------------------------------------


@_mutation("runtime.start")
async def _start_runtime(request: Request) -> Response:
    """Start a runtime and return 202, or 200 if it already exists."""
    key = request.headers["Idempotency-Key"]
    notebook = await _notebook(request)
    await _decode(request, protocol.StartRuntimeRequest)
    runtime, created = notebook.start(request_id=key)
    return _reply(202 if created else 200, runtime)


@_mutation("runtime.stop")
async def _stop_runtime(request: Request) -> Response:
    """Request shutdown and return 202 with the runtime marked terminating."""
    key = request.headers["Idempotency-Key"]
    notebook = await _notebook(request)
    runtime = notebook.stop(request_id=key)
    return _reply(202, runtime)


@_mutation("runtime.restart")
async def _restart_runtime(request: Request) -> Response:
    """Return 202 with the replacement runtime in its starting state."""
    key = request.headers["Idempotency-Key"]
    notebook = await _notebook(request)
    runtime = notebook.restart(request_id=key)
    return _reply(202, runtime)


# ---- runs ----------------------------------------------------------------------


@_mutation("runtime.run")
async def _run(request: Request) -> Response:
    """Queue a run and return 202. Results arrive through notebook events."""
    key = request.headers["Idempotency-Key"]
    notebook = await _notebook(request)
    body = await _decode(request, protocol.RunRequest)
    if isinstance(body.code, str) and body.cells is msgspec.UNSET:
        started = notebook.run(body.code, request_id=key)
    elif body.code is msgspec.UNSET and isinstance(body.cells, tuple):
        started = notebook.run(cells=body.cells, request_id=key)
    else:
        return problem(
            400, "invalid-request", "A run names code or cells, not both"
        )
    return _reply(202, started)


@_mutation("runtime.run")
async def _interrupt(request: Request) -> Response:
    """Interrupt an active run and return 202, or 409 if it has completed."""
    notebook = await _notebook(request)
    run_id = request.path_params["run_id"]
    try:
        interrupted = notebook.interrupt(run_id)
    except NotFound:
        # A completed scratch run is host history, not notebook state.
        run = _context(request).bridge.host.run(notebook.id, run_id)
        if run is not None and run.status == "completed":
            raise Conflict(f"run {run_id} has already ended.") from None
        raise
    return _reply(202, interrupted)
