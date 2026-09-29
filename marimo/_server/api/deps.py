# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast, get_args

from marimo import _loggers as loggers
from marimo._cli.tips import CliTip
from marimo._config.manager import MarimoConfigManager, ScriptConfigManager
from marimo._messaging.participants import ParticipantKind
from marimo._server.config import StarletteServerState
from marimo._server.session_manager import SessionManager
from marimo._server.tokens import SkewProtectionToken
from marimo._session.model import SessionMode
from marimo._session.participants import (
    ParticipantConflictError,
    ParticipantRegistryClosedError,
    ParticipantState,
)
from marimo._types.ids import SessionId, StableSessionId
from marimo._utils.env import is_env_true
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
PARTICIPANT_ID_HEADER = "Marimo-Participant-Id"
PARTICIPANT_HARNESS_HEADER = "Marimo-Participant-Harness"
PARTICIPANT_KIND_HEADER = "Marimo-Participant-Kind"
PAIR_PREVIEW_ENV = "MARIMO_PAIR_NEXT"

UNKNOWN_HARNESS = "unknown"
DEFAULT_PARTICIPANT_KIND: ParticipantKind = "agent"


@dataclass(frozen=True)
class ParticipantSession:
    """A resolved Session plus the participant that contacted it.

    `participant` is None for a browser or legacy request that carries no
    participant identity.
    """

    session: Session
    participant: ParticipantState | None


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

        session = self.session_manager.get_session_by_stable_id(
            StableSessionId(stable_session_id)
        )
        if session is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail=f"Invalid stable session id: {stable_session_id}",
            )
        return session

    async def require_participant_session(
        self, *, participant_required: bool = False
    ) -> ParticipantSession:
        """Resolve the Session and record contact for an identified request.

        A request that carries `Marimo-Participant-Id` must also carry the
        stable session header. The participant record is created or resumed,
        the one-agent check runs, the attachment TTL is renewed, and the
        contact time is recorded. A request without the participant header,
        or any request while the Pair preview is off, resolves the Session
        only.
        """
        participant_id = self.request.headers.get(PARTICIPANT_ID_HEADER)
        if participant_id is None:
            if participant_required:
                raise HTTPException(
                    status_code=HTTPStatus.BAD_REQUEST,
                    detail=f"Missing {PARTICIPANT_ID_HEADER} header.",
                )
            return ParticipantSession(
                session=self.require_current_session_with_stable_id(),
                participant=None,
            )
        if not is_env_true(PAIR_PREVIEW_ENV):
            return ParticipantSession(
                session=self.require_current_session_with_stable_id(),
                participant=None,
            )
        if self.request.headers.get(STABLE_SESSION_ID_HEADER) is None:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=(
                    f"{PARTICIPANT_ID_HEADER} requires "
                    f"{STABLE_SESSION_ID_HEADER}."
                ),
            )
        session = self.require_current_session_with_stable_id()
        harness = (
            self.request.headers.get(PARTICIPANT_HARNESS_HEADER)
            or UNKNOWN_HARNESS
        )
        kind = self._participant_kind()

        try:
            state = await session.participants.attach(
                participant_id, harness=harness, kind=kind
            )
        except ParticipantConflictError as error:
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                detail=(
                    f"Another participant ({error.holder_harness}) is "
                    "attached to this session."
                ),
            ) from error
        except ParticipantRegistryClosedError as error:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail=f"Session {session.stable_id} is closed.",
            ) from error
        return ParticipantSession(session=session, participant=state)

    def _participant_kind(self) -> ParticipantKind:
        raw = self.request.headers.get(PARTICIPANT_KIND_HEADER)
        if raw is None:
            return DEFAULT_PARTICIPANT_KIND
        allowed = get_args(ParticipantKind)
        if raw not in allowed:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=(
                    f"{PARTICIPANT_KIND_HEADER} must be one of "
                    f"{', '.join(allowed)}."
                ),
            )
        return cast(ParticipantKind, raw)

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
