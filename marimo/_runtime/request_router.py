# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from marimo._runtime.commands import CommandMessage


class RequestRouter:
    """Dispatches kernel command messages to registered async handlers."""

    def __init__(self) -> None:
        self._handlers: dict[
            type[CommandMessage],
            Callable[[Any], Awaitable[None]],
        ] = {}

    def register(
        self,
        request_type: type[CommandMessage],
        handler: Callable[[Any], Awaitable[None]],
    ) -> None:
        self._handlers[request_type] = handler

    async def dispatch(self, request: CommandMessage) -> None:
        handler = self._handlers.get(type(request))
        if handler:
            return await handler(request)
        raise ValueError(f"Unknown request {request}")
