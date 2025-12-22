# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from starlette.websockets import WebSocket

    from marimo._server.api.endpoints.ws.ws_connection_validator import (
        ConnectionParams,
    )
    from marimo._server.api.endpoints.ws_endpoint import WebSocketHandler
    from marimo._server.sessions import Session, SessionManager

from starlette.websockets import WebSocketDisconnect

from marimo import _loggers
from marimo._messaging.types import NoopStream
from marimo._runtime.params import QueryParams
from marimo._server.codes import WebSocketCodes
from marimo._server.model import SessionMode

LOGGER = _loggers.marimo_logger()


class ConnectionType(Enum):
    """Type of session connection established."""

    KIOSK = "kiosk"
    RECONNECT = "reconnect"
    RTC_EXISTING = "rtc_existing"
    RESUME = "resume"
    NEW = "new"


class SessionConnector:
    """Handles different session connection strategies."""

    def __init__(
        self,
        manager: SessionManager,
        handler: WebSocketHandler,
        params: ConnectionParams,
        websocket: WebSocket,
    ):
        self.manager = manager
        self.handler = handler
        self.params = params
        self.websocket = websocket

    def connect(self) -> tuple[Session, ConnectionType]:
        """Determine connection type and establish session connection.

        Returns:
            Tuple of (Session, ConnectionType) indicating the session
            and how it was connected.

        Raises:
            WebSocketDisconnect: If the connection cannot be established.
        """
        # 1. Kiosk mode
        if self.params.kiosk:
            return self._connect_kiosk()

        # 2. Reconnect to existing session with same ID
        existing_by_id = self.manager.get_session(self.params.session_id)
        if existing_by_id is not None:
            return self._reconnect_session(existing_by_id)

        # 3. Connect to existing session (RTC mode)
        existing_by_file = self.manager.get_session_by_file_key(
            self.params.file_key
        )
        if (
            existing_by_file is not None
            and self.params.rtc_enabled
            and self.manager.mode == SessionMode.EDIT
        ):
            return self._connect_rtc_session(existing_by_file)

        # 4. Resume previous session
        resumable = self.manager.maybe_resume_session(
            self.params.session_id, self.params.file_key
        )
        if resumable is not None:
            return self._resume_session(resumable)

        # 5. Create new session
        return self._create_new_session()

    def _connect_kiosk(self) -> tuple[Session, ConnectionType]:
        """Connect to kiosk session.

        Raises:
            WebSocketDisconnect: If kiosk mode is not supported or session
                not found.
        """
        if self.manager.mode is not SessionMode.EDIT:
            LOGGER.debug("Kiosk mode is only supported in edit mode")
            raise WebSocketDisconnect(
                WebSocketCodes.FORBIDDEN, "MARIMO_KIOSK_NOT_ALLOWED"
            )

        # Try to find session by ID first
        kiosk_session = self.manager.get_session(self.params.session_id)
        if kiosk_session is None:
            LOGGER.debug(
                "Kiosk session not found for session id %s",
                self.params.session_id,
            )
            # Try to find by file key
            kiosk_session = self.manager.get_session_by_file_key(
                self.params.file_key
            )

        if kiosk_session is None:
            LOGGER.debug(
                "Kiosk session not found for file key %s",
                self.params.file_key,
            )
            raise WebSocketDisconnect(
                WebSocketCodes.NORMAL_CLOSE, "MARIMO_NO_SESSION"
            )

        LOGGER.debug("Connecting to kiosk session")
        self.handler._connect_kiosk(kiosk_session)
        return kiosk_session, ConnectionType.KIOSK

    def _reconnect_session(
        self, session: Session
    ) -> tuple[Session, ConnectionType]:
        """Reconnect to existing session.

        The session already exists, but it was disconnected. This can happen
        in local development when the client goes to sleep and wakes later.
        """
        LOGGER.debug("Reconnecting session %s", self.params.session_id)
        # In case there is a lingering connection, close it
        session.disconnect_main_consumer()
        self.handler._reconnect_session(session, replay=False)
        return session, ConnectionType.RECONNECT

    def _connect_rtc_session(
        self, session: Session
    ) -> tuple[Session, ConnectionType]:
        """Connect to RTC-enabled session."""
        LOGGER.debug(
            "Connecting to existing session for file %s", self.params.file_key
        )
        self.handler._connect_to_existing_session(session)
        return session, ConnectionType.RTC_EXISTING

    def _resume_session(
        self, session: Session
    ) -> tuple[Session, ConnectionType]:
        """Resume a previous session."""
        LOGGER.debug("Resuming session %s", self.params.session_id)
        self.handler._reconnect_session(session, replay=True)
        return session, ConnectionType.RESUME

    def _create_new_session(self) -> tuple[Session, ConnectionType]:
        """Create a new session.

        Grabs query params from the websocket and creates a new session
        with the session manager.
        """
        # Grab the query params from the websocket
        # Note: if we resume a session, we don't pick up the new query
        # params, and instead use the query params from when the
        # session was created.
        query_params = QueryParams({}, NoopStream())
        for key, value in self.websocket.query_params.multi_items():
            if key in QueryParams.IGNORED_KEYS:
                continue
            query_params.append(key, value)

        new_session = self.manager.create_session(
            query_params=query_params.to_dict(),
            session_id=self.params.session_id,
            session_consumer=self.handler,
            file_key=self.params.file_key,
            auto_instantiate=self.params.auto_instantiate,
        )

        # Notify frontend that kernel is ready
        from marimo._server.model import ConnectionState

        self.handler.status = ConnectionState.CONNECTING
        self.handler._write_kernel_ready(
            new_session,
            resumed=False,
            ui_values={},
            last_executed_code={},
            last_execution_time={},
            kiosk=False,
        )
        self.handler.status = ConnectionState.OPEN
        self.handler._replay_previous_session(new_session)

        return new_session, ConnectionType.NEW
