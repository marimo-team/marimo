# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Optional, Union

from starlette.requests import Request
from starlette.websockets import WebSocket
from uvicorn import Server

from marimo._ast.app import _AppConfig
from marimo._config.config import MarimoConfig
from marimo._server.model import SessionMode
from marimo._server.sessions import Session, SessionId, SessionManager


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
        assert (
            request.app.state.user_config is not None
        ), "User config not initialized"

        self.session_manager: SessionManager = (
            request.app.state.session_manager
        )
        self.user_config: MarimoConfig = request.app.state.user_config
        self._server: Server = request.app.state.server

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
    def filename(self) -> Optional[str]:
        return self.session_manager.filename

    @property
    def mode(self) -> SessionMode:
        return self.session_manager.mode

    @property
    def app_config(self) -> Optional[_AppConfig]:
        return self.session_manager.app_config

    @property
    def quiet(self) -> bool:
        return self.session_manager.quiet

    @property
    def development_mode(self) -> bool:
        return self.session_manager.development_mode

    @property
    def port(self) -> int:
        return self.session_manager.port

    @property
    def server_token(self) -> str:
        return self.session_manager.server_token

    @property
    def server(self) -> Server:
        return self._server

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
