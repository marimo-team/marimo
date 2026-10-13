# Copyright 2026 Marimo. All rights reserved.
"""Local access and bearer-token authentication for the host API.

Requests must come from loopback and address a loopback name on the
server's port. The bearer token comes from the host discovery record.
"""

from __future__ import annotations

import hmac
from ipaddress import IPv6Address, ip_address
from typing import TYPE_CHECKING

from starlette.requests import Request

from marimo import _loggers
from marimo._server.host import HOST_API_PATH
from marimo._server.host.api import build_app, problem

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send

LOGGER = _loggers.marimo_logger()


class HostApiMiddleware:
    """Authenticate and route host API requests."""

    def __init__(self, app: ASGIApp, *, base_url: str = "") -> None:
        self.app = app
        self.prefix = base_url + HOST_API_PATH
        self.host_app = build_app()

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        if scope["type"] != "http" or not self._is_host_path(scope["path"]):
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        client = scope.get("client")
        context = getattr(request.app.state, "host_context", None)
        if context is None:
            response = problem(404, "not-found", "This server is not a host")
        elif client is None or not _is_loopback(client[0]):
            response = problem(
                403, "forbidden", "The host API answers only this machine"
            )
        elif not _host_header_ok(request.headers.get("host"), context.port):
            # Reject remote domain names to prevent DNS rebinding attacks.
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
            scope = {**scope, "root_path": self.prefix}
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


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        address = ip_address(host)
    except ValueError:
        return False
    if isinstance(address, IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    return address.is_loopback


def _host_header_ok(header: str | None, port: int) -> bool:
    """Check that the Host header names a loopback address and server port."""
    if header is None:
        return False
    if header.startswith("["):
        name, _, after = header.partition("]")
        name = name[1:]
        given = after[1:] if after.startswith(":") else ""
    else:
        name, _, given = header.partition(":")
    if not _is_loopback(name):
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
