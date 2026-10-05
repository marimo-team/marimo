# Copyright 2026 Marimo. All rights reserved.
"""The host API's routes: two streams and the operations.

Each route is a thin translation. It reads the request, asks the `Host`
for a command, and writes the protocol's reply: `200`, `201`, `202`, or
`204` with the object, or a `Problem`. Authentication happens before any
of this, in `HostApiMiddleware`, so a route can assume the caller may act.
"""

from __future__ import annotations

import asyncio
import hashlib
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import quote

import msgspec
from starlette.responses import Response, StreamingResponse
from starlette.routing import Mount, Route, Router

from marimo import _loggers
from marimo._host import protocol, wire
from marimo._host.model import Attachment
from marimo._host.stream import CATALOG, NOTEBOOK
from marimo._host.transitions import (
    Attach,
    Conflict,
    Detach,
    NotebookGone,
    NotFound,
)
from marimo._server.api.deps import AppState
from marimo._server.api.utils import format_url_host, open_url_in_browser
from marimo._server.host.context import KeyReused
from marimo._server.sse import SSE_HEADERS
from marimo._types.ids import AttachmentId, NotebookId
from marimo._utils.ids import new_id

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from starlette.requests import Request
    from starlette.types import ASGIApp

    from marimo._host.model import Notebook
    from marimo._host.stream import Event
    from marimo._server.host.context import HostContext

LOGGER = _loggers.marimo_logger()

PROBLEM_TYPE_PREFIX = "tag:marimo.io,2026:host/"
"""Every problem type the protocol defines starts with this prefix."""

PING = b": ping\n\n"
PING_SECONDS = 15.0

_TITLES = {
    "invalid-request": "Invalid request",
    "unauthorized": "Unauthorized",
    "forbidden": "Forbidden",
    "not-found": "Not found",
    "not-acceptable": "Not acceptable",
    "conflict": "Conflict",
    "no-runtime": "No runtime",
    "unsupported-operation": "Unsupported operation",
    "internal": "Internal error",
}


def problem(status: int, kind: str, detail: str | None = None) -> Response:
    """Returns an error reply in the protocol's one error shape."""
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


def build_app(prefix: str) -> ASGIApp:
    """Returns the host API as an ASGI app serving under `prefix`."""
    routes = Router(
        routes=[
            Route("/events", events, methods=["GET"]),
            Route("/notebooks", create_notebook, methods=["POST"]),
            Route("/notebooks/{id}", update_notebook, methods=["PATCH"]),
            Route("/notebooks/{id}", delete_notebook, methods=["DELETE"]),
            Route("/notebooks/{id}/events", notebook_events, methods=["GET"]),
            Route("/notebooks/{id}/open", open_notebook, methods=["POST"]),
            Route("/notebooks/{id}/export", export_notebook, methods=["GET"]),
            Route("/notebooks/{id}/runtime", start_runtime, methods=["PUT"]),
            Route("/notebooks/{id}/runtime", stop_runtime, methods=["DELETE"]),
            Route(
                "/notebooks/{id}/runtime/restart",
                restart_runtime,
                methods=["POST"],
            ),
            Route("/notebooks/{id}/executions", execute, methods=["POST"]),
            Route(
                "/notebooks/{id}/executions/{execution_id}",
                interrupt,
                methods=["DELETE"],
            ),
        ],
        default=_not_found,
    )
    return Router(routes=[Mount(prefix, app=routes)], default=_not_found)


async def _not_found(scope, receive, send) -> None:  # type: ignore[no-untyped-def]
    await problem(404, "not-found", "No such route")(scope, receive, send)


def _context(request: Request) -> HostContext:
    context = getattr(request.app.state, "host_context", None)
    assert context is not None, "HostApiMiddleware admits requests only then"
    return context  # type: ignore[no-any-return]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _offered(context: HostContext, operation: str) -> Response | None:
    """Refuses an operation the host does not list, with `501`.

    A host advertises what it can do, and a route for anything else
    exists only to say so.
    """
    if operation in context.host.operations:
        return None
    return problem(
        501, "unsupported-operation", f"This host does not offer {operation}"
    )


# Idempotency


def _fingerprint(request: Request, body: bytes) -> str:
    digest = hashlib.sha256(body).hexdigest()
    return f"{request.method} {request.url.path} {digest}"


async def _keyed(
    request: Request, context: HostContext
) -> tuple[str, bytes, str] | Response:
    """Reads the key and body, or answers for a request already seen.

    Returns the key, the body, and the request's fingerprint, or the
    reply to send instead: the remembered one for a repeat, a `conflict`
    for a key reused with a different request, or `invalid-request` with
    no key at all.
    """
    key = request.headers.get("Idempotency-Key")
    if not key:
        return problem(400, "invalid-request", "Idempotency-Key is required")
    body = await request.body()
    fingerprint = _fingerprint(request, body)
    try:
        remembered = context.replies.get(key, fingerprint)
    except KeyReused:
        return problem(
            409,
            "conflict",
            f"Idempotency-Key {key} was used for another request",
        )
    if remembered is not None:
        return _reply(*remembered)
    return key, body, fingerprint


def _reply(status: int, body: bytes) -> Response:
    if not body:
        return Response(status_code=status)
    return Response(body, status_code=status, media_type="application/json")


def _remember(
    context: HostContext,
    key: str,
    fingerprint: str,
    status: int,
    body: msgspec.Struct | None,
) -> Response:
    encoded = b"" if body is None else msgspec.json.encode(body)
    context.replies.put(key, fingerprint, status, encoded)
    return _reply(status, encoded)


def _decode(
    body: bytes, kind: type[msgspec.Struct]
) -> msgspec.Struct | Response:
    try:
        return msgspec.json.decode(body or b"{}", type=kind)
    except (msgspec.DecodeError, msgspec.ValidationError) as e:
        return problem(400, "invalid-request", str(e))


def _offered_or_501(request: Request, operation: str) -> Response:
    refused = _offered(_context(request), operation)
    assert refused is not None, f"{operation} is routed but not implemented"
    return refused


# Streams


async def events(request: Request) -> Response:
    """Streams the catalog and then every change, as the contract says.

    `Last-Event-ID` resumes from a cursor. `types` narrows the stream to
    the named kinds; `ready` and `reset` always come through.
    """
    context = _context(request)
    cursor = _cursor(request)
    if isinstance(cursor, Response):
        return cursor
    wanted = _types(request, CATALOG)

    # New and deleted files show up here, since nothing watches the
    # directory between connections. The scan is bounded and runs off
    # the loop.
    await context.index.refresh_in_thread()
    return _stream(context, cursor, wanted, notebook_id=None, on_close=None)


async def notebook_events(request: Request) -> Response:
    """Streams one notebook, with its runtime, attachments, and executions.

    Opening the stream attaches the client to the notebook; closing it
    detaches.
    """
    context = _context(request)
    notebook_id = NotebookId(request.path_params["id"])
    if notebook_id not in context.host.state.notebooks:
        return problem(404, "not-found", "No such notebook")
    cursor = _cursor(request)
    if isinstance(cursor, Response):
        return cursor
    wanted = _types(request, NOTEBOOK)

    attachment = Attachment(
        AttachmentId(new_id("att")), "client", None, _utcnow()
    )
    try:
        context.host.command(Attach(notebook_id, attachment))
    except (NotFound, Conflict):
        return problem(404, "not-found", "No such notebook")

    def detach() -> None:
        context.host.observe(Detach(notebook_id, attachment.id))

    return _stream(
        context, cursor, wanted, notebook_id=notebook_id, on_close=detach
    )


def _cursor(request: Request) -> int | Response | None:
    raw = request.headers.get("Last-Event-ID")
    if raw is None:
        return None
    if not raw.isdigit():
        return problem(400, "invalid-request", "Last-Event-ID must be an id")
    return int(raw)


def _types(request: Request, carried: tuple[str, ...]) -> set[str]:
    asked = request.query_params.get("types")
    if not asked:
        return set(carried)
    return {kind for kind in asked.split(",") if kind in carried}


def _stream(
    context: HostContext,
    cursor: int | None,
    wanted: set[str],
    *,
    notebook_id: NotebookId | None,
    on_close: Callable[[], None] | None,
) -> Response:
    async def body() -> AsyncIterator[bytes]:
        queue: asyncio.Queue[Event] = asyncio.Queue()
        # Subscribe first, then snapshot: an event published in between
        # shows up in both, and is dropped below by its id.
        unsubscribe = context.host.subscribe(queue.put_nowait)
        try:
            initial = context.host.events(cursor, notebook_id=notebook_id)
            for event in initial:
                if _wanted(event, wanted):
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
                if (
                    notebook_id is not None
                    and event.notebook_id != notebook_id
                ):
                    continue
                if _wanted(event, wanted):
                    yield _frame(event)
        finally:
            unsubscribe()
            if on_close is not None:
                on_close()

    return StreamingResponse(
        body(), media_type="text/event-stream", headers=SSE_HEADERS
    )


def _wanted(event: Event, kinds: set[str]) -> bool:
    return event.name in ("ready", "reset") or event.kind in kinds


def _frame(event: Event) -> bytes:
    """Frames one event: an `id` line when it has one, its name, its data."""
    lines = []
    if event.id is not None:
        lines.append(f"id: {event.id}")
    lines.append(f"event: {event.name}")
    data = b"{}" if event.data is None else msgspec.json.encode(event.data)
    lines.append(f"data: {data.decode()}")
    return ("\n".join(lines) + "\n\n").encode()


# Notebooks


async def create_notebook(request: Request) -> Response:
    """`notebook.create`: writes an empty notebook under the project root.

    `201` with the notebook. `409` if a file is already there, which is
    left alone. `400` for a path that is absolute or leaves the root.
    """
    context = _context(request)
    if (refused := _offered(context, "notebook.create")) is not None:
        return refused
    keyed = await _keyed(request, context)
    if isinstance(keyed, Response):
        return keyed
    key, raw, fingerprint = keyed
    body = _decode(raw, protocol.CreateNotebookRequest)
    if isinstance(body, Response):
        return body
    assert isinstance(body, protocol.CreateNotebookRequest)

    root = context.index.root
    if root is None or body.project_id != context.index.project_id:
        return problem(404, "not-found", f"No project {body.project_id}")
    relative = Path(body.path)
    if relative.is_absolute() or ".." in relative.parts:
        return problem(400, "invalid-request", "path must stay in the project")
    file = root / relative
    if file.exists():
        return problem(409, "conflict", f"{body.path} already exists")

    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(_empty_notebook(), encoding="utf-8")
    notebook_id = context.index.ensure(str(file), request_id=key)
    assert notebook_id is not None
    notebook = context.host.state.notebooks[notebook_id]
    return _remember(context, key, fingerprint, 201, wire.notebook(notebook))


def _empty_notebook() -> str:
    from marimo._convert.converters import MarimoConvert
    from marimo._session.notebook import AppFileManager

    return MarimoConvert.from_ir(AppFileManager(None).app.to_ir()).to_py()


async def update_notebook(request: Request) -> Response:
    """`notebook.update`: moves the file to `path` under the same root.

    An attached runtime follows its file. `409` if something is already
    at `path`; `400` for a path that is absolute or leaves the root.
    """
    context = _context(request)
    if (refused := _offered(context, "notebook.update")) is not None:
        return refused
    keyed = await _keyed(request, context)
    if isinstance(keyed, Response):
        return keyed
    key, raw, fingerprint = keyed
    notebook = _notebook(request, context)
    if isinstance(notebook, Response):
        return notebook
    body = _decode(raw, protocol.UpdateNotebookRequest)
    if isinstance(body, Response):
        return body
    assert isinstance(body, protocol.UpdateNotebookRequest)

    source = _file_of(context, notebook)
    root = context.index.root
    if source is None or root is None:
        return problem(409, "conflict", "The notebook has no file to move")
    relative = Path(body.path)
    if relative.is_absolute() or ".." in relative.parts:
        return problem(400, "invalid-request", "path must stay in the project")
    target = root / relative
    if target.exists():
        return problem(409, "conflict", f"{body.path} already exists")

    target.parent.mkdir(parents=True, exist_ok=True)
    if notebook.runtime is not None:
        error = await context.runtime.rename(notebook.runtime.id, str(target))
        if error is not None:
            return problem(409, "conflict", error)
    else:
        source.rename(target)
    moved = context.index.moved(notebook.id, relative, request_id=key)
    if moved is None:
        return problem(400, "invalid-request", "path must stay in the project")
    return _remember(context, key, fingerprint, 200, wire.notebook(moved))


async def delete_notebook(request: Request) -> Response:
    """`notebook.delete`: removes the file. `409` while a runtime is attached."""
    context = _context(request)
    if (refused := _offered(context, "notebook.delete")) is not None:
        return refused
    keyed = await _keyed(request, context)
    if isinstance(keyed, Response):
        return keyed
    key, _, fingerprint = keyed
    notebook = _notebook(request, context)
    if isinstance(notebook, Response):
        return notebook
    if notebook.runtime is not None:
        return problem(409, "conflict", "The notebook has a runtime")

    file = _file_of(context, notebook)
    if file is not None:
        try:
            file.unlink(missing_ok=True)
        except OSError as e:
            return problem(409, "conflict", f"The file cannot be removed: {e}")
    context.host.observe(NotebookGone(notebook.id), request_id=key)
    return _remember(context, key, fingerprint, 204, None)


async def open_notebook(request: Request) -> Response:
    """`notebook.open`: shows the notebook in the browser and returns the URL.

    The URL is the one the home page would use, without any token; a
    client may open it itself instead of relying on the browser here.
    """
    context = _context(request)
    if (refused := _offered(context, "notebook.open")) is not None:
        return refused
    keyed = await _keyed(request, context)
    if isinstance(keyed, Response):
        return keyed
    key, _, fingerprint = keyed
    notebook = _notebook(request, context)
    if isinstance(notebook, Response):
        return notebook
    if notebook.path is None:
        return problem(409, "conflict", "The notebook has no file to open")

    state = AppState(request)
    authority = f"{format_url_host(state.host, state.port)}:{state.port}"
    url = (
        f"http://{authority}{state.base_url}/?file={quote(str(notebook.path))}"
    )
    browser = state.config_manager.get_config()["server"]["browser"]
    # Browser discovery can block, so it stays off the event loop.
    threading.Thread(
        target=_open_quietly, args=(browser, url), daemon=True
    ).start()
    return _remember(
        context, key, fingerprint, 200, protocol.OpenNotebookResponse(url=url)
    )


def _open_quietly(browser: str, url: str) -> None:
    try:
        open_url_in_browser(browser, url)
    except Exception as e:
        LOGGER.warning("Could not open %s in a browser: %s", url, e)


async def export_notebook(request: Request) -> Response:
    """`notebook.export`: the notebook as bytes, in the format asked for.

    `py` is the file as saved, with no outputs. `html` is not rendered by
    this host yet, and answers `not-acceptable`.
    """
    context = _context(request)
    if (refused := _offered(context, "notebook.export")) is not None:
        return refused
    notebook = _notebook(request, context)
    if isinstance(notebook, Response):
        return notebook
    fmt = request.query_params.get("format")
    if fmt not in ("py", "html"):
        return problem(400, "invalid-request", "format must be py or html")
    if fmt == "html":
        return problem(406, "not-acceptable", "This host does not render html")
    file = _file_of(context, notebook)
    if file is None:
        return problem(409, "conflict", "The notebook has no file")
    try:
        source = file.read_bytes()
    except OSError as e:
        return problem(409, "conflict", f"The notebook cannot be read: {e}")
    return Response(
        source,
        media_type="text/x-python",
        headers={"Marimo-Outputs": "none"},
    )


def _notebook(request: Request, context: HostContext) -> Notebook | Response:
    notebook = context.host.state.notebooks.get(
        NotebookId(request.path_params["id"])
    )
    if notebook is None:
        return problem(404, "not-found", "No such notebook")
    return notebook


def _file_of(context: HostContext, notebook: Notebook) -> Path | None:
    project = context.host.state.projects.get(notebook.project_id)
    if notebook.path is None or project is None or project.root is None:
        return None
    return project.root / notebook.path


# Runtimes


async def start_runtime(request: Request) -> Response:
    """`runtime.start` is not offered yet; see the host's operations."""
    return _offered_or_501(request, "runtime.start")


async def stop_runtime(request: Request) -> Response:
    """`runtime.stop` is not offered yet; see the host's operations."""
    return _offered_or_501(request, "runtime.stop")


async def restart_runtime(request: Request) -> Response:
    """`runtime.restart` is not offered yet; see the host's operations."""
    return _offered_or_501(request, "runtime.restart")


# Executions


async def execute(request: Request) -> Response:
    """`runtime.execute` is not offered yet; see the host's operations."""
    return _offered_or_501(request, "runtime.execute")


async def interrupt(request: Request) -> Response:
    """`runtime.execute` is not offered yet; see the host's operations."""
    return _offered_or_501(request, "runtime.execute")
