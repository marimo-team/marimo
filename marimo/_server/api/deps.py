# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, Union, cast

from marimo import _loggers as loggers
from marimo._config.manager import MarimoConfigManager, ScriptConfigManager
from marimo._server.config import StarletteServerState
from marimo._server.session_manager import SessionManager
from marimo._server.tokens import SkewProtectionToken
from marimo._session.model import SessionMode
from marimo._types.ids import SessionId

if TYPE_CHECKING:
    from starlette.applications import Starlette
    from starlette.datastructures import State
    from starlette.requests import Request
    from starlette.websockets import WebSocket
    from uvicorn import Server

    from marimo._session import Session

LOGGER = loggers.marimo_logger()


class AppStateBase:
    """The app state."""

    @staticmethod
    def from_request(request: Union[Request, WebSocket]) -> AppState:
        """Get the app state with a request."""
        return AppState(request)

    @staticmethod
    def from_app(asgi: Starlette) -> AppStateBase:
        """Get the app state with an ASGIApp app."""
        return AppStateBase(cast(Any, asgi).state)

    def __init__(self, state: State) -> None:
        """Initialize the app state."""
        self.state = cast(StarletteServerState, state)

    @property
    def session_manager(self) -> SessionManager:
        return self.state.session_manager

    @property
    def mode(self) -> SessionMode:
        return self.session_manager.mode

    @property
    def quiet(self) -> bool:
        return self.state.quiet

    @property
    def host(self) -> str:
        return self.state.host

    @property
    def port(self) -> int:
        return self.state.port

    @property
    def maybe_port(self) -> Optional[int]:
        return getattr(self.state, "port", None)

    @property
    def base_url(self) -> str:
        return self.state.base_url

    @property
    def server(self) -> Server:
        return self.state.server

    @property
    def config_manager(self) -> MarimoConfigManager:
        return self.state.config_manager

    @property
    def headless(self) -> bool:
        return self.state.headless

    @property
    def skew_protection(self) -> bool:
        return self.state.skew_protection

    @property
    def skew_protection_token(self) -> SkewProtectionToken:
        return self.session_manager.skew_protection_token

    @property
    def remote_url(self) -> Optional[str]:
        if hasattr(self.state, "remote_url"):
            return self.state.remote_url
        return None

    @property
    def mcp_server_enabled(self) -> bool:
        return self.state.mcp_server_enabled

    @property
    def asset_url(self) -> Optional[str]:
        if hasattr(self.state, "asset_url"):
            return self.state.asset_url
        return None

    @property
    def enable_auth(self) -> bool:
        if hasattr(self.state, "enable_auth"):
            return self.state.enable_auth
        return True


class AppState(AppStateBase):
    """The app state with a request."""

    def __init__(self, request: Union[Request, WebSocket]) -> None:
        """Initialize the app state with a request."""
        super().__init__(request.app.state)
        self.request = request

    def get_current_session_id(self) -> Optional[SessionId]:
        """Get the current session."""
        session_id = self.request.headers.get("Marimo-Session-Id")
        return SessionId(session_id) if session_id is not None else None

    def require_current_session_id(self) -> SessionId:
        """Get the current session or raise an error."""
        session_id = self.get_current_session_id()
        if session_id is None:
            raise ValueError("Missing Marimo-Session-Id header")
        return session_id

    def get_current_session(self) -> Optional[Session]:
        """Get the current session."""
        session_id = self.get_current_session_id()
        if session_id is None:
            return None
        return self.session_manager.get_session(session_id)

    def require_current_session(self) -> Session:
        """Get the current session or raise an error."""
        session_id = self.require_current_session_id()
        session = self.session_manager.get_session(session_id)
        if session is None:
            LOGGER.warning(
                "Valid sessions ids: %s",
                list(self.session_manager.sessions.keys()),
            )
            LOGGER.warning(
                "Valid consumers ids: %s",
                [
                    list(session.consumers.values())
                    for session in self.session_manager.sessions.values()
                    if session.consumers
                ],
            )
            raise ValueError(f"Invalid session id: {session_id}")
        return session

    def require_query_params(self, param: str) -> str:
        """Get a query parameter or raise an error."""
        value = self.request.query_params[param]
        if not value:
            raise ValueError(f"Missing query parameter: {param}")
        return value

    def query_params(self, param: str) -> Optional[str]:
        """Get a query parameter."""
        if param not in self.request.query_params:
            return None
        return self.request.query_params[param]

    # Config manager for the marimo file that we are running.
    # This could have custom config in the script metadata.
    @property
    def app_config_manager(self) -> MarimoConfigManager:
        session = self.require_current_session()
        return session.config_manager

    # We may have not created a session yet, but we know the file where we will
    # create one.
    # Use this file to override the config manager.
    def config_manager_at_file(self, path: str) -> MarimoConfigManager:
        return super().config_manager.with_overrides(
            ScriptConfigManager(path).get_config()
        )
