# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, Union, cast

from marimo import _loggers as loggers
from marimo._config.manager import UserConfigManager
from marimo._server.ids import SessionId
from marimo._server.model import SessionMode
from marimo._server.sessions import Session, SessionManager
from marimo._server.tokens import SkewProtectionToken

if TYPE_CHECKING:
    from starlette.applications import Starlette
    from starlette.datastructures import State
    from starlette.requests import Request
    from starlette.websockets import WebSocket
    from uvicorn import Server

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
        self.state = state

    @property
    def session_manager(self) -> SessionManager:
        return cast(SessionManager, self.state.session_manager)

    @property
    def mode(self) -> SessionMode:
        return self.session_manager.mode

    @property
    def quiet(self) -> bool:
        return self.session_manager.quiet

    @property
    def development_mode(self) -> bool:
        return self.session_manager.development_mode

    @property
    def host(self) -> str:
        host: str = self.state.host
        return host

    @property
    def port(self) -> int:
        post: int = self.state.port
        return post

    @property
    def maybe_port(self) -> Optional[int]:
        return self.state._state.get("port")

    @property
    def base_url(self) -> str:
        base_url: str = self.state.base_url
        return base_url

    @property
    def server(self) -> Server:
        server: Server = self.state.server
        return server

    @property
    def config_manager(self) -> UserConfigManager:
        cm: UserConfigManager = self.state.config_manager
        return cm

    @property
    def watch(self) -> bool:
        watch: bool = self.state.watch
        return watch

    @property
    def headless(self) -> bool:
        headless: bool = self.state.headless
        return headless

    @property
    def skew_protection_token(self) -> SkewProtectionToken:
        return self.session_manager.skew_protection_token


class AppState(AppStateBase):
    """The app state with a request."""

    def __init__(self, request: Union[Request, WebSocket]) -> None:
        """Initialize the app state with a request."""
        super().__init__(request.app.state)
        self.request = request

    def get_current_session_id(self) -> Optional[SessionId]:
        """Get the current session."""
        return self.request.headers.get("Marimo-Session-Id")

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
                "Valid sessions: %s",
                list(self.session_manager.sessions.keys()),
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
