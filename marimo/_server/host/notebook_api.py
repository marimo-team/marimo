# Copyright 2026 Marimo. All rights reserved.
"""HTTP routes for the host's operations, and problem responses."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import quote

import msgspec
from starlette.responses import Response
from starlette.routing import Route

from marimo import _loggers
from marimo._core import operations, protocol
from marimo._core.errors import Conflict, Invalid, NotFound
from marimo._core.handlers import HostHandlers, NotebookHandlers, dispatch
from marimo._core.result import Ok
from marimo._messaging.notification import ConsumerCapabilities
from marimo._runtime.commands import HTTPRequest
from marimo._server.api.auth import TOKEN_QUERY_PARAM
from marimo._server.api.deps import AppState, AppStateBase
from marimo._server.api.utils import format_url_host, open_url_in_browser
from marimo._server.host.auth import bearer_matches
from marimo._server.tokens import AuthToken
from marimo._types.ids import ConsumerId

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.requests import HTTPConnection, Request

    from marimo._server.host.context import HostContext

LOGGER = _loggers.marimo_logger()
api = protocol.api

# The operations a host's catalog serves, which the editor does not.
_CATALOG: tuple[api.Operation, ...] = (
    api.Host.Create,
    api.Notebook.Update,
    api.Notebook.Delete,
    api.Notebook.Open,
)


def _context(request: HTTPConnection) -> HostContext:
    context = getattr(request.app.state, "host_context", None)
    assert context is not None, "HostApiMiddleware admits requests only then"
    return context  # type: ignore[no-any-return]


def _response(status: int, body: msgspec.Struct | None) -> Response:
    media_type = (
        None
        if body is None
        else "application/problem+json"
        if status >= 400
        else "application/json"
    )
    return Response(
        b"" if body is None else msgspec.json.encode(body),
        status_code=status,
        media_type=media_type,
    )


def problem(kind: operations.PlainKind, detail: str | None = None) -> Response:
    body = operations.problem(kind, detail)
    return _response(body.status, body)


_ROUTER_KINDS: dict[int, operations.PlainKind] = {
    400: "invalid-request",
    404: "not-found",
    405: "method-not-allowed",
    409: "conflict",
}


def status_problem(status: int, detail: str | None = None) -> Response:
    """Describe a status that the router or a route raised."""
    kind = _ROUTER_KINDS.get(status)
    if kind is None:
        LOGGER.error("The host API raised an unmapped status %s", status)
        return problem("internal", "The host failed")
    return problem(kind, detail)


def _inside_project(path: str) -> Path:
    if "\x00" in path:
        raise Invalid("path must not contain NUL")
    relative = Path(path)
    if relative.is_absolute() or ".." in relative.parts:
        raise Invalid("path must stay in the project")
    return relative


class _HostHandlers(HostHandlers):
    """Catalog operations for notebooks kept as files."""

    def __init__(self, context: HostContext) -> None:
        self._context = context

    async def create(
        self, call: api.Host.Create.Call
    ) -> api.Host.Create.Result:
        index = self._context.bridge.index
        if index.root is None or call.body.project_id != index.project_id:
            raise NotFound(f"No project {call.body.project_id}")
        if call.body.path is msgspec.UNSET:
            raise Invalid("path is required")
        name = call.body.name
        return Ok(
            await self._context.bridge.create(
                index.root / _inside_project(call.body.path),
                name=None if name is msgspec.UNSET else name,
                request_id=call.headers.idempotency_key,
            )
        )


class _NotebookHandlers(NotebookHandlers):
    """Notebook operations, including those on the notebook's file."""

    def __init__(
        self,
        context: HostContext,
        request: Request,
        *,
        allow_input: bool,
    ) -> None:
        super().__init__(
            context.bridge,
            request=_submitting_request(request),
            allow_input=allow_input,
        )
        self._context = context
        self._app = request.app

    def _record(self, notebook_id: str) -> protocol.Notebook:
        record = self._context.bridge.host.notebooks.get(notebook_id)
        if record is None:
            raise NotFound(f"no notebook {notebook_id}")
        return record

    async def update(
        self, call: api.Notebook.Update.Call
    ) -> api.Notebook.Update.Result:
        """Change a notebook's path or display name, preserving its runtime."""
        record = self._record(call.params.notebook_id)
        path, name = call.body.path, call.body.name
        if path is msgspec.UNSET and name is msgspec.UNSET:
            raise Invalid("path or name is required")
        index = self._context.bridge.index
        target = None
        if path is not msgspec.UNSET:
            if index.root is None:
                raise Conflict("The notebook has no file to move")
            target = index.root / _inside_project(path)
        return Ok(
            await self._context.bridge.update(
                record.id,
                target=target,
                name=None if name is msgspec.UNSET else name,
                request_id=call.headers.idempotency_key,
            )
        )

    async def delete(
        self, call: api.Notebook.Delete.Call
    ) -> api.Notebook.Delete.Result:
        """Delete the notebook and its file if it has no runtime."""
        await self._context.bridge.delete(
            self._record(call.params.notebook_id).id,
            request_id=call.headers.idempotency_key,
        )
        return Ok(None)

    async def open(
        self, call: api.Notebook.Open.Call
    ) -> api.Notebook.Open.Result:
        """Open the notebook in the configured browser."""
        record = self._record(call.params.notebook_id)
        file = self._context.bridge.index.file_of(record.id)
        if file is None:
            raise Conflict("The notebook has no file to open")

        state = AppStateBase.from_app(self._app)
        authority = f"{format_url_host(state.host, state.port)}:{state.port}"
        url = f"http://{authority}{state.base_url}/?file={quote(str(file))}"
        auth_token = state.session_manager.auth_token
        if not AuthToken.is_empty(auth_token):
            url += f"&{TOKEN_QUERY_PARAM}={quote(str(auth_token))}"
        browser = state.config_manager.get_config().server.browser
        # Keep blocking browser discovery off the event loop.
        threading.Thread(
            target=_open_quietly, args=(browser, url), daemon=True
        ).start()
        return Ok(protocol.OpenNotebookResponse(url=url))


def _open_quietly(browser: str, url: str) -> None:
    try:
        open_url_in_browser(browser, url)
    except Exception as e:
        LOGGER.warning("Could not open the notebook in a browser: %s", e)


def _endpoint(
    operation: api.Operation,
) -> Callable[[Request], Awaitable[Response]]:
    kind: type[api.Call] = operation.Call

    async def handle(request: Request) -> Response:
        # Assemble the call from the request's parts, the shape the client
        # sends to any transport, so every call passes the same validation.
        parts: dict[str, object] = {
            "operation": operation.ID,
            "params": request.path_params,
            "headers": dict(request.headers),
        }
        raw_body = await request.body()
        try:
            if "body" in kind.__struct_fields__:
                parts["body"] = msgspec.json.decode(raw_body or b"{}")
            elif raw_body:
                return problem(
                    "invalid-request", "This operation takes no body"
                )
            call: api.Call = msgspec.convert(parts, type=kind)
        except msgspec.DecodeError as e:
            return problem("invalid-request", str(e))
        context = _context(request)
        session = AppState(request).get_current_session()
        notebook_id = request.path_params.get("notebook_id")
        status, body = await dispatch(
            context.mutations,
            api.Api(
                host=_HostHandlers(context),
                notebook=_NotebookHandlers(
                    context,
                    request,
                    allow_input=(
                        session is not None
                        and notebook_id is not None
                        and context.bridge.session_for_notebook(notebook_id)
                        is session
                    ),
                ),
            ),
            call,
        )
        return _response(status, body)

    return handle


def _submitting_request(request: Request) -> HTTPRequest:
    """Describe the request to notebook code without the token that admitted it."""
    submitted = HTTPRequest.from_request(request)
    if bearer_matches(
        request.headers.get("authorization"), _context(request).token
    ):
        submitted.headers.pop("authorization", None)
    return submitted


def operation_routes() -> list[Route]:
    """Serve each operation at its path in the spec."""
    return [
        Route(operation.PATH, _endpoint(operation), methods=[operation.METHOD])
        for operation in api.OPERATIONS
    ]


def editor_notebook_routes(prefix: str) -> list[Route]:
    """Serve each notebook operation below `prefix` to the editor."""
    return [
        Route(
            prefix + operation.PATH,
            _editor_endpoint(operation),
            methods=[operation.METHOD],
        )
        for operation in api.OPERATIONS
        if operation not in _CATALOG
    ]


def _editor_endpoint(
    operation: api.Operation,
) -> Callable[[Request], Awaitable[Response]]:
    serve = _endpoint(operation)

    async def handle(request: Request) -> Response:
        # The editor's middleware has already authenticated the request.
        scopes = request.auth.scopes
        if not scopes:
            return problem("unauthorized", "Sign in to the editor")
        if "edit" not in scopes:
            return problem("forbidden", "This editor cannot edit notebooks")
        if not _connection_may_call(request, operation):
            return problem(
                "forbidden",
                "This connection is read-only for this action.",
            )
        return await serve(request)

    return handle


def _connection_may_call(request: Request, operation: api.Operation) -> bool:
    """Whether the connection may issue this notebook operation.

    Host commands are system-originated, so enforce connection capabilities
    here. Headerless requests rely on the editor's scope alone.
    """
    app_state = AppState(request)
    session_id = app_state.get_current_session_id()
    if session_id is None:
        return True
    session = app_state.get_current_session()
    if session is None:
        return False
    consumer = session.room.get_consumer(ConsumerId(session_id))
    capabilities = (
        session.room.get_capabilities(consumer)
        if consumer is not None
        else ConsumerCapabilities.VIEWER
    )
    return (
        capabilities.interact
        if operation is api.Notebook.Reply
        else capabilities.edit
    )
