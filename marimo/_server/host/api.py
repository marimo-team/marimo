# Copyright 2026 Marimo. All rights reserved.
"""HTTP routes for notebooks, runtimes, runs, and event streams."""

from __future__ import annotations

import asyncio
import hashlib
import threading
from collections.abc import Awaitable, Callable
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING, TypeAlias, TypeVar, get_args
from urllib.parse import quote

import msgspec
from starlette.exceptions import HTTPException
from starlette.responses import Response, StreamingResponse
from starlette.routing import Route, Router

from marimo import _loggers
from marimo._core import protocol
from marimo._core.errors import Conflict, NoRuntime, NotFound
from marimo._server.api.auth import TOKEN_QUERY_PARAM
from marimo._server.api.deps import AppStateBase
from marimo._server.api.utils import format_url_host, open_url_in_browser
from marimo._server.host.context import CachedMutation
from marimo._server.sse import SSE_HEADERS
from marimo._server.tokens import AuthToken

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from starlette.requests import Request

    from marimo._core.notebook import Notebook
    from marimo._core.stream import Event
    from marimo._server.host.context import HostContext

LOGGER = _loggers.marimo_logger()

_Endpoint: TypeAlias = Callable[["Request"], Awaitable[Response]]
_Body = TypeVar("_Body", bound=msgspec.Struct)

PROBLEM_TYPE_PREFIX = "tag:marimo.io,2026:host/"
"""Prefix for host protocol problem types."""

ATTACHMENT_IDENTITY = "Marimo-Attachment-Identity"
ATTACHMENT_KIND = "Marimo-Attachment-Kind"
ATTACHMENT_NAME = "Marimo-Attachment-Name"

_ATTACHMENT_HEADERS = {
    "identity": ATTACHMENT_IDENTITY,
    "kind": ATTACHMENT_KIND,
    "name": ATTACHMENT_NAME,
}
"""Attachment fields and the request headers that supply them."""

PING = b": ping\n\n"
PING_SECONDS = 15.0

OBJECT_TYPES = frozenset(get_args(get_args(protocol.ObjectType)[0]))
"""Values the `types` stream filter accepts."""

_TITLES = {
    "invalid-request": "Invalid request",
    "unauthorized": "Unauthorized",
    "forbidden": "Forbidden",
    "not-found": "Not found",
    "method-not-allowed": "Method not allowed",
    "conflict": "Conflict",
    "no-runtime": "No runtime",
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
    status: int, kind: str | None = None, detail: str | None = None
) -> Response:
    """Return a protocol error as an HTTP problem response.

    Without a kind, the status picks one. A status this protocol does
    not name is a server bug, so it becomes a 500 rather than a problem
    of an unknown kind.
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
        if route.methods == {"GET", "HEAD"}:
            route.methods = {"GET"}
    return Router(
        routes=routes,
        default=_not_found,
        # Clients never follow redirects, so a trailing slash is a miss.
        redirect_slashes=False,
    )


async def _not_found(scope, receive, send) -> None:  # type: ignore[no-untyped-def]
    await problem(404, "not-found", "No such route")(scope, receive, send)


def _context(request: Request) -> HostContext:
    context = getattr(request.app.state, "host_context", None)
    assert context is not None, "HostApiMiddleware admits requests only then"
    return context  # type: ignore[no-any-return]


def _notebook(request: Request) -> Notebook:
    return _context(request).bridge.host.notebook(request.path_params["id"])


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
            fingerprint = f"{request.method} {request.url.path} {digest}"
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
                def updated(event: Event) -> None:
                    if isinstance(event.data, protocol.RunMessage):
                        run = event.data.run
                        if event.data.request_id == key:
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
    early: list[Event] = []

    def settle() -> None:
        context.settle(mutation)
        unsubscribe()

    def updated(event: Event) -> None:
        nonlocal previous_id
        if mutation.expires_at is not None:
            return
        if runtime_id is None:
            # A backend can finish synchronously, before the response exists.
            early.append(event)
            return
        if event.name == "notebook.removed":
            settle()
        elif isinstance(event.data, protocol.RuntimeMessage):
            runtime = event.data.runtime
            if (
                operation == "runtime.restart"
                and event.data.request_id == request_id
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
        elif event.name == "runtime.removed" and isinstance(
            event.data, protocol.RemovedMessage
        ):
            if event.data.id == runtime_id or (
                event.data.id == previous_id
                and event.data.request_id != request_id
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
    except Conflict as e:
        return problem(409, "conflict", str(e))
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

    `Last-Event-ID` resumes from a cursor; `types` filters event kinds.
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
        notebook = _notebook(request)
    except NotFound as e:
        return problem(404, "not-found", str(e))
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


def _cursor(request: Request) -> int | Response | None:
    raw = request.headers.get("Last-Event-ID")
    if raw is None:
        return None
    # Header text is latin-1, where superscripts count as digits.
    if not (raw.isascii() and raw.isdigit()):
        return problem(400, "invalid-request", "Last-Event-ID must be an id")
    try:
        return int(raw)
    except ValueError:
        return problem(400, "invalid-request", "Last-Event-ID is too long")


def _types(request: Request) -> set[str] | Response | None:
    asked = request.query_params.get("types")
    if not asked:
        return None
    types = {kind for kind in asked.split(",") if kind}
    unknown = types - OBJECT_TYPES
    if unknown:
        return problem(
            400,
            "invalid-request",
            f"types has no kind named {', '.join(sorted(unknown))}",
        )
    return types


def _attachment_problem(error: msgspec.ValidationError) -> str:
    """Name the request header behind a rejected attachment field."""
    detail = str(error)
    for field, header in _ATTACHMENT_HEADERS.items():
        if detail.endswith(f"`$.{field}`"):
            return f"{header} is invalid"
    return "attachment headers are invalid"


def _stream(
    context: HostContext,
    cursor: int | None,
    types: set[str] | None,
    *,
    notebook_id: str | None,
    run_id: str | None = None,
    on_close: Callable[[], None] | None = None,
) -> Response:
    host = context.bridge.host

    async def body() -> AsyncIterator[bytes]:
        queue: asyncio.Queue[Event] = asyncio.Queue()
        # Subscribe before reading initial events to avoid losing updates.
        # Queued events at or before the ready cursor are skipped.
        unsubscribe = host.subscribe(
            queue.put_nowait,
            notebook_id=notebook_id,
            types=types,
            run_id=run_id,
        )
        try:
            initial = host.events(
                cursor, notebook_id=notebook_id, types=types, run_id=run_id
            )
            for event in initial:
                yield _frame(event)
            ready_id = initial[-1].id or 0
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), PING_SECONDS)
                except asyncio.TimeoutError:
                    yield PING
                    continue
                if event.id is not None and event.id <= ready_id:
                    continue
                yield _frame(event)
        finally:
            unsubscribe()
            if on_close is not None:
                on_close()

    return StreamingResponse(
        body(), media_type="text/event-stream", headers=SSE_HEADERS
    )


def _frame(event: Event) -> bytes:
    """Encode an event as an SSE frame."""
    lines = []
    if event.id is not None:
        lines.append(f"id: {event.id}")
    lines.append(f"event: {event.name}")
    data = b"{}" if event.data is None else msgspec.json.encode(event.data)
    lines.append(f"data: {data.decode()}")
    return ("\n".join(lines) + "\n\n").encode()


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
    """Delete the notebook and file; return 409 while a runtime exists."""
    context = _context(request)
    key = request.headers["Idempotency-Key"]
    await context.bridge.delete(_notebook(request).id, request_id=key)
    return _reply(204, None)


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
    """Start a runtime: 202 if created, 200 if already present."""
    key = request.headers["Idempotency-Key"]
    notebook = _notebook(request)
    await _decode(request, protocol.StartRuntimeRequest)
    runtime, created = notebook.start(request_id=key)
    return _reply(202 if created else 200, runtime)


@_mutation("runtime.stop")
async def _stop_runtime(request: Request) -> Response:
    """Request shutdown and return 202 with the runtime marked terminating."""
    key = request.headers["Idempotency-Key"]
    notebook = _notebook(request)
    runtime = notebook.stop(request_id=key)
    return _reply(202, runtime)


@_mutation("runtime.restart")
async def _restart_runtime(request: Request) -> Response:
    """Return 202 with the replacement runtime in its starting state."""
    key = request.headers["Idempotency-Key"]
    notebook = _notebook(request)
    runtime = notebook.restart(request_id=key)
    return _reply(202, runtime)


# ---- runs ----------------------------------------------------------------------


@_mutation("runtime.run")
async def _run(request: Request) -> Response:
    """Queue a run and return 202; stream results through notebook events."""
    key = request.headers["Idempotency-Key"]
    notebook = _notebook(request)
    body = await _decode(request, protocol.RunRequest)
    if body.code is msgspec.UNSET or body.cells is not msgspec.UNSET:
        return problem(
            400, "invalid-request", "This host requires scratch code"
        )
    started = notebook.run(body.code, request_id=key)
    return _reply(202, started)


@_mutation("runtime.run")
async def _interrupt(request: Request) -> Response:
    """Request a run interruption: 202 if active, 409 if completed."""
    notebook = _notebook(request)
    interrupted = notebook.interrupt(request.path_params["run_id"])
    return _reply(202, interrupted)
