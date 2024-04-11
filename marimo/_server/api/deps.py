# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Union

from marimo._config.manager import UserConfigManager
from marimo._server.ids import SessionId
from marimo._server.model import SessionMode
from marimo._server.sessions import Session, SessionManager

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.websockets import WebSocket
    from uvicorn import Server


def app_state(request: Request) -> AppState:
    """Get the app state."""
    return AppState(request.app)


class AppState:
    """The app state."""

    def __init__(self, request: Union[Request, WebSocket]) -> None:
        """Initialize the app state."""
        self.request = request

        assert (
            request.app.state.session_manager is not None
        ), "Session manager not initialized"
        self.session_manager: SessionManager = (
            request.app.state.session_manager
        )

        assert (
            request.app.state.base_url is not None
        ), "Base URL not initialized"
        self._base_url: str = request.app.state.base_url

        assert (
            request.app.state.config_manager is not None
        ), "Config manager not initialized"
        self._config_manager: UserConfigManager = (
            request.app.state.config_manager
        )

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
            raise ValueError(f"Invalid session id: {session_id}")
        return session

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
        assert self.request.app.state.host is not None, "Host not initialized"
        host: str = self.request.app.state.host
        return host

    @property
    def port(self) -> int:
        assert self.request.app.state.port is not None, "Port not initialized"
        post: int = self.request.app.state.port
        return post

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def server_token(self) -> str:
        return self.session_manager.server_token

    @property
    def server(self) -> Server:
        assert (
            self.request.app.state.server is not None
        ), "Server not initialized"
        server: Server = self.request.app.state.server
        return server

    @property
    def config_manager(self) -> UserConfigManager:
        return self._config_manager

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
