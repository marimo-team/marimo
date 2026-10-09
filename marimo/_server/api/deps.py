# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

from marimo import _loggers as loggers
from marimo._cli.tips import CliTip
from marimo._config.manager import MarimoConfigManager, ScriptConfigManager
from marimo._messaging.attachments import Attachment, AttachmentKind
from marimo._server.config import StarletteServerState
from marimo._server.session_manager import SessionManager
from marimo._server.tokens import SkewProtectionToken
from marimo._session.model import SessionMode
from marimo._types.ids import SessionId, StableSessionId
from marimo._utils.env import pair_preview_enabled
from marimo._utils.http import HTTPException, HTTPStatus

if TYPE_CHECKING:
    from starlette.applications import Starlette
    from starlette.datastructures import State
    from starlette.requests import Request
    from starlette.websockets import WebSocket
    from uvicorn import Server

    from marimo._session import Session

LOGGER = loggers.marimo_logger()

STABLE_SESSION_ID_HEADER = "Marimo-Stable-Session-Id"
ATTACHMENT_ID_HEADER = "Marimo-Attachment-Id"
ATTACHMENT_KIND_HEADER = "Marimo-Attachment-Kind"
ATTACHMENT_NAME_HEADER = "Marimo-Attachment-Name"


class AppStateBase:
    """The app state."""

    @staticmethod
    def from_request(request: Request | WebSocket) -> AppState:
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
    def maybe_port(self) -> int | None:
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
    def remote_url(self) -> str | None:
        if hasattr(self.state, "remote_url"):
            return self.state.remote_url
        return None

    @property
    def mcp_server_enabled(self) -> bool:
        return self.state.mcp_server_enabled

    @property
    def asset_url(self) -> str | None:
        if hasattr(self.state, "asset_url"):
            return self.state.asset_url
        return None

    @property
    def enable_auth(self) -> bool:
        if hasattr(self.state, "enable_auth"):
            return self.state.enable_auth
        return True

    @property
    def startup_tip(self) -> CliTip | None:
        startup_tip = getattr(self.state, "startup_tip", None)
        return cast(CliTip | None, startup_tip)

    @property
    def html_head(self) -> str | None:
        if hasattr(self.state, "html_head"):
            return cast(str | None, self.state.html_head)
        return None


class AppState(AppStateBase):
    """The app state with a request."""

    def __init__(self, request: Request | WebSocket) -> None:
        """Initialize the app state with a request."""
        super().__init__(request.app.state)
        self.request = request

    def get_current_session_id(self) -> SessionId | None:
        """Get the current session."""
        session_id = self.request.headers.get("Marimo-Session-Id")
        return SessionId(session_id) if session_id is not None else None

    def require_current_session_id(self) -> SessionId:
        """Get the current session or raise an error."""
        session_id = self.get_current_session_id()
        if session_id is None:
            raise ValueError("Missing Marimo-Session-Id header")
        return session_id

    def get_current_session(self) -> Session | None:
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
                    list(session.room.consumers)
                    for session in self.session_manager.sessions.values()
                    if session.room.consumers
                ],
            )
            raise ValueError(f"Invalid session id: {session_id}")
        return session

    def require_current_session_with_stable_id(self) -> Session:
        """Resolve a session from the stable or browser routing header."""
        stable_session_id = self.request.headers.get(STABLE_SESSION_ID_HEADER)
        if stable_session_id is None:
            return self.require_current_session()
        if self.get_current_session_id() is not None:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=(
                    f"{STABLE_SESSION_ID_HEADER} cannot be combined with "
                    "Marimo-Session-Id."
                ),
            )

        return self.session_by_stable_id(stable_session_id)

    def require_pair_preview(self) -> None:
        """Reject Pair routes when the preview is disabled."""
        if not pair_preview_enabled():
            raise HTTPException(status_code=HTTPStatus.NOT_FOUND)

    def attachment_from_request(self) -> Attachment:
        """Read stream identity or mint an anonymous client attachment."""
        raw_id = self.request.headers.get(ATTACHMENT_ID_HEADER)
        if raw_id is None:
            return Attachment(
                id=f"att_{uuid4()}",
                kind="client",
                name=None,
                since=time.time(),
            )
        kind = self.request.headers.get(ATTACHMENT_KIND_HEADER, "client")
        if not raw_id or kind not in ("agent", "client"):
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=(
                    f"{ATTACHMENT_ID_HEADER} must be nonempty and "
                    f"{ATTACHMENT_KIND_HEADER} must be agent or client."
                ),
            )
        return Attachment(
            id=raw_id,
            kind=cast(AttachmentKind, kind),
            name=self.request.headers.get(ATTACHMENT_NAME_HEADER),
            since=time.time(),
        )

    def session_by_stable_id(self, stable_id: str) -> Session:
        """Resolve a notebook's stable session ID.

        Args:
            stable_id (str): Stable session ID from the route.
        """
        session = self.session_manager.get_session_by_stable_id(
            StableSessionId(stable_id)
        )
        if session is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail=f"Invalid stable session id: {stable_id}",
            )
        return session

    def require_query_params(self, param: str) -> str:
        """Get a query parameter or raise an error."""
        value = self.request.query_params[param]
        if not value:
            raise ValueError(f"Missing query parameter: {param}")
        return value

    def query_params(self, param: str) -> str | None:
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
        config_manager = super().config_manager
        # The file key can be relative to the workspace directory, so resolve
        # it to a validated absolute path before reading inline script
        # metadata — otherwise ScriptConfigManager would read relative to the
        # server's cwd. New/unsaved or missing files have no inline config to
        # apply; let other rejections (e.g. path traversal) propagate.
        try:
            resolved = self.session_manager.workspace.resolve(path)
        except HTTPException as e:
            if e.status_code == HTTPStatus.NOT_FOUND:
                return config_manager
            raise
        if resolved is None:
            return config_manager
        return config_manager.with_overrides(
            ScriptConfigManager(resolved).get_config()
        )
