# Copyright 2026 Marimo. All rights reserved.
"""Admits requests to the host API.

The host API is stricter than the rest of the server: the caller must
be local, present the record's token, and address a loopback name on
this port. This middleware checks that itself and bypasses the server's
other middleware, which would otherwise interfere.
"""

from __future__ import annotations

import hmac
from typing import TYPE_CHECKING

from starlette.requests import Request

from marimo import _loggers
from marimo._server.host.api import build_app, problem
from marimo._server.host.context import HOST_API_PATH

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send

LOGGER = _loggers.marimo_logger()

_LOOPBACK = ("127.0.0.1", "::1", "::ffff:127.0.0.1", "localhost")


class HostApiMiddleware:
    """Routes host API requests to the host, after checking who is asking."""

    def __init__(self, app: ASGIApp, *, base_url: str = "") -> None:
        self.app = app
        self.prefix = base_url + HOST_API_PATH
        self.host_app = build_app(self.prefix)

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        if scope["type"] != "http" or not self._is_host_path(scope["path"]):
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        context = getattr(request.app.state, "host_context", None)
        if context is None:
            response = problem(404, "not-found", "This server is not a host")
        elif not _is_loopback(scope.get("client")):
            response = problem(
                403, "forbidden", "The host API answers only this machine"
            )
        elif not _host_header_ok(request.headers.get("host"), context.port):
            # A page can reach a loopback server through a name it owns;
            # the Host header shows which name was used.
            response = problem(
                403, "forbidden", "The host API answers only its own address"
            )
        elif not _bearer_matches(
            request.headers.get("Authorization"), context.token
        ):
            response = problem(
                401, "unauthorized", "Send the host record's token as a bearer"
            )
        else:
            try:
                await self.host_app(scope, receive, send)
            except Exception:
                LOGGER.exception("The host API failed on %s", scope["path"])
                response = problem(500, "internal", "The host failed")
                await response(scope, receive, send)
            return
        await response(scope, receive, send)

    def _is_host_path(self, path: str) -> bool:
        return path == self.prefix or path.startswith(self.prefix + "/")


def _is_loopback(client: tuple[str, int] | None) -> bool:
    if client is None:
        return False
    host = client[0]
    return host in _LOOPBACK or host.startswith("127.")


def _host_header_ok(header: str | None, port: int) -> bool:
    """Whether the request addressed a loopback name on this server's port."""
    if header is None:
        return False
    name, _, given = header.rpartition(":")
    if header.startswith("[") and "]" in header:
        name, _, after = header.partition("]")
        name = name[1:]
        given = after[1:] if after.startswith(":") else ""
    elif not _:
        name, given = header, ""
    if name not in _LOOPBACK and not name.startswith("127."):
        return False
    if given == "":
        return port == 80
    return given.isdigit() and int(given) == port


def _bearer_matches(authorization: str | None, token: str) -> bool:
    if authorization is None:
        return False
    scheme, _, credentials = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return False
    return hmac.compare_digest(credentials.strip(), token)
