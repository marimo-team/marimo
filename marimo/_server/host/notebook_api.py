# Copyright 2026 Marimo. All rights reserved.
"""HTTP routes for the notebook operations, and problem responses."""

from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING, TypeVar

import msgspec
from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.routing import Route

from marimo import _loggers
from marimo._core import operations, protocol
from marimo._core.calls import CALLS, dispatch
from marimo._core.errors import HostError
from marimo._core.operations import Reply

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.requests import HTTPConnection, Request

    from marimo._core.calls import OperationCall
    from marimo._server.host.context import HostContext

LOGGER = _loggers.marimo_logger()
_Body = TypeVar("_Body", bound=msgspec.Struct)


def _context(request: HTTPConnection) -> HostContext:
    context = getattr(request.app.state, "host_context", None)
    assert context is not None, "HostApiMiddleware admits requests only then"
    return context  # type: ignore[no-any-return]


def _response(status: int, body: msgspec.Struct | None) -> Response:
    media_type = (
        "application/problem+json"
        if isinstance(body, protocol.Problem)
        else "application/json"
        if body is not None
        else None
    )
    return Response(
        b"" if body is None else msgspec.json.encode(body),
        status_code=status,
        media_type=media_type,
    )


def problem(
    status: int, kind: str | None = None, detail: str | None = None
) -> Response:
    if kind is None:
        kind = {
            400: "invalid-request",
            404: "not-found",
            405: "method-not-allowed",
            409: "conflict",
        }.get(status)
    if kind is None:
        LOGGER.error("The host API raised an unmapped status %s", status)
        status, kind, detail = 500, "internal", "The host failed"
    return _response(status, operations.problem(status, kind, detail))


async def _decode(request: Request, kind: type[_Body]) -> _Body:
    return msgspec.json.decode(await request.body() or b"{}", type=kind)


def _mutation(
    operation: str,
) -> Callable[
    [Callable[[Request], Awaitable[Reply]]],
    Callable[[Request], Awaitable[Response]],
]:
    """Use the same receipt store for catalog operations implemented by the server."""

    def decorate(
        endpoint: Callable[[Request], Awaitable[Reply]],
    ) -> Callable[[Request], Awaitable[Response]]:
        @wraps(endpoint)
        async def handle(request: Request) -> Response:
            try:
                status, body = await _context(request).mutations.execute(
                    operation,
                    notebook_id=request.path_params.get("notebook_id"),
                    key=request.headers.get("Idempotency-Key", ""),
                    payload=(
                        request.method,
                        request.url.path,
                        await request.body(),
                        request.headers.get("If-Match", ""),
                    ),
                    call=lambda: endpoint(request),
                )
            except msgspec.DecodeError as e:
                return problem(400, "invalid-request", str(e))
            except HTTPException as e:
                return problem(e.status_code, detail=e.detail)
            except HostError as e:
                failure = operations.problem_for(e)
                return _response(failure.status, failure)
            return _response(status, body)

        return handle

    return decorate


def _endpoint(
    kind: type[OperationCall],
) -> Callable[[Request], Awaitable[Response]]:
    async def handle(request: Request) -> Response:
        # Assemble the call from the request's parts, the shape the client
        # sends to any transport, so every call passes the same validation.
        parts: dict[str, object] = {
            "operation": kind.__struct_config__.tag,
            "params": request.path_params,
            "headers": dict(request.headers),
        }
        if "body" in kind.__struct_fields__:
            parts["body"] = msgspec.Raw(await request.body() or b"{}")
        try:
            call = msgspec.json.decode(msgspec.json.encode(parts), type=kind)
        except msgspec.DecodeError as e:
            return problem(400, "invalid-request", str(e))
        context = _context(request)
        status, body = await dispatch(context.mutations, context.bridge, call)
        return _response(status, body)

    return handle


def notebook_routes() -> list[Route]:
    """Serve each notebook operation at its path in the spec."""
    return [
        Route(kind.PATH, _endpoint(kind), methods=[kind.METHOD])
        for kind in CALLS
    ]


def editor_notebook_routes(prefix: str) -> list[Route]:
    """Serve each notebook operation below `prefix` to the editor."""
    return [
        Route(
            prefix + kind.PATH,
            _editor_endpoint(_endpoint(kind)),
            methods=[kind.METHOD],
        )
        for kind in CALLS
    ]


def _editor_endpoint(
    serve: Callable[[Request], Awaitable[Response]],
) -> Callable[[Request], Awaitable[Response]]:
    async def handle(request: Request) -> Response:
        # The editor's middleware has already authenticated the request.
        scopes = request.auth.scopes
        if "edit" in scopes:
            return await serve(request)
        if scopes:
            return problem(
                403, "forbidden", "This editor cannot edit notebooks"
            )
        return problem(401, "unauthorized", "Sign in to the editor")

    return handle
