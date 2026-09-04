# Copyright 2026 Marimo. All rights reserved.
"""Transport security boundary for the local discovery API."""

from __future__ import annotations

import ipaddress
from typing import TYPE_CHECKING, Any, cast

from starlette.responses import JSONResponse

from marimo._server.discovery import DISCOVERY_API_PATH

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Message, Receive, Scope, Send

    from marimo._server.discovery.manager import DiscoveryManager


class DiscoverySecurityMiddleware:
    """Require literal-loopback clients and the discovery bearer token."""

    def __init__(self, app: ASGIApp, *, base_url: str) -> None:
        self.app = app
        self._prefix = f"{base_url.rstrip('/')}{DISCOVERY_API_PATH}"

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        if scope["type"] != "http" or not self._matches(scope.get("path", "")):
            await self.app(scope, receive, send)
            return

        manager = cast(
            "DiscoveryManager | None",
            getattr(scope["app"].state, "discovery_manager", None),
        )
        if manager is None:
            await self._error(scope, receive, send, 404, "Not found")
            return
        if not _is_loopback_peer(scope.get("client")):
            await self._error(
                scope, receive, send, 403, "Loopback connection required"
            )
            return

        authorization = _header(scope, b"authorization")
        scheme, separator, token = authorization.partition(" ")
        if (
            separator != " "
            or scheme.lower() != "bearer"
            or not manager.is_authorized(token)
        ):
            await self._error(
                scope,
                receive,
                send,
                401,
                "Invalid discovery token",
                headers={"WWW-Authenticate": "Bearer"},
            )
            return

        async def secure_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = [
                    (key, value)
                    for key, value in message.get("headers", [])
                    if not key.lower().startswith(b"access-control-")
                    and key.lower() != b"cache-control"
                    and key.lower() != b"location"
                ]
                headers.append((b"cache-control", b"no-store"))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, secure_send)

    def _matches(self, path: str) -> bool:
        return path == self._prefix or path.startswith(f"{self._prefix}/")

    async def _error(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        status_code: int,
        message: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        response = JSONResponse(
            {"message": message},
            status_code=status_code,
            headers={"Cache-Control": "no-store", **(headers or {})},
        )
        await response(scope, receive, send)


def _header(scope: Scope, name: bytes) -> str:
    for key, value in scope.get("headers", []):
        if key.lower() == name:
            return cast(bytes, value).decode("latin-1")
    return ""


def _is_loopback_peer(client: Any) -> bool:
    if not isinstance(client, (tuple, list)) or not client:
        return False
    host = str(client[0]).strip("[]").split("%", 1)[0]
    try:
        address = ipaddress.ip_address(host)
        if isinstance(address, ipaddress.IPv6Address):
            mapped = address.ipv4_mapped
            if mapped is not None:
                return mapped.is_loopback
        return address.is_loopback
    except ValueError:
        return False
