# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from starlette.datastructures import State
    from uvicorn import Server

    from marimo._config.manager import MarimoConfigManager
    from marimo._server.session_manager import SessionManager


@dataclass(frozen=True)
class StarletteServerStateInit:
    """State for the Starlette server.

    This enforces that we always supply all the required state to the app.state object.
    """

    port: int
    host: str
    base_url: str
    asset_url: str | None
    headless: bool
    quiet: bool
    session_manager: SessionManager
    config_manager: MarimoConfigManager
    remote_url: str | None
    mcp_server_enabled: bool
    skew_protection: bool
    enable_auth: bool

    def apply(self, state: State) -> None:
        for field, value in self.__dict__.items():
            setattr(state, field, value)


class StarletteServerState(StarletteServerStateInit):
    """Typed state for the Starlette server."""

    server: Server
