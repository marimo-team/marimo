# Copyright 2026 Marimo. All rights reserved.
"""Transport-agnostic session handling shared by WebSocket and SSE."""

from __future__ import annotations

import abc
import asyncio
from typing import TYPE_CHECKING

from marimo import _loggers
from marimo._cli.upgrade import check_for_updates
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._messaging.notification import (
    AlertNotification,
    BannerNotification,
    NotificationMessage,
    ReconnectedNotification,
)
from marimo._messaging.serde import serialize_kernel_message
from marimo._server.api.endpoints.ws.ws_kernel_ready import (
    build_kernel_ready,
    is_rtc_available,
)
from marimo._server.api.endpoints.ws.ws_session_connector import (
    SessionConnector,
    is_viewer_connection,
)
from marimo._server.codes import WebSocketCloseReason, WebSocketCodes
from marimo._session.consumer import SessionConsumer
from marimo._session.model import ConnectionState, SessionMode
from marimo._types.ids import ConsumerId

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from starlette.requests import HTTPConnection

    from marimo._config.cli_state import MarimoCLIState
    from marimo._messaging.types import KernelMessage
    from marimo._plugins.core.web_component import JSONType
    from marimo._server.api.endpoints.ws.ws_connection_validator import (
        ConnectionParams,
    )
    from marimo._server.api.endpoints.ws.ws_session_connector import (
        ConnectionType,
    )
    from marimo._server.rtc.doc import LoroDocManager
    from marimo._server.session_manager import SessionManager
    from marimo._session import Session
    from marimo._session.events import SessionEventBus
    from marimo._types.ids import CellId_t

LOGGER = _loggers.marimo_logger()


class SessionHandler(SessionConsumer, abc.ABC):
    """Base consumer that sessions use to send messages to frontends.

    Owns the transport-agnostic session lifecycle: connecting (new, resume,
    reconnect, kiosk), the kernel-ready handshake, message replay, and
    TTL-based session close on disconnect. Subclasses implement the small
    transport surface (`_request_close`, `_is_transport_connected`,
    `_cancel_message_loop`) and their own message loop that drains
    `message_queue`.
    """

    def __init__(
        self,
        *,
        manager: SessionManager,
        params: ConnectionParams,
        mode: SessionMode,
        doc_manager: LoroDocManager,
    ):
        self.manager = manager
        self.params = params
        self.mode = mode
        self.doc_manager = doc_manager
        self.status: ConnectionState
        self.cancel_close_handle: asyncio.TimerHandle | None = None
        # Messages from the kernel are put in this queue
        # to be sent to the frontend
        self.message_queue: asyncio.Queue[KernelMessage] = asyncio.Queue()
        self._consumer_id = ConsumerId(params.session_id)

    @property
    def consumer_id(self) -> ConsumerId:
        return self._consumer_id

    # Transport surface, implemented per transport

    @abc.abstractmethod
    def _request_close(self, code: int, reason: str) -> None:
        """Ask the transport to close with the given code and reason.

        Must not block; called from synchronous session callbacks.
        """

    @abc.abstractmethod
    def _is_transport_connected(self) -> bool:
        """Whether the transport can still deliver messages."""

    @abc.abstractmethod
    def _cancel_message_loop(self) -> None:
        """Stop the message loop that drains `message_queue`."""

    # Shared session lifecycle

    def _connect_session(
        self, connection: HTTPConnection
    ) -> tuple[Session, ConnectionType]:
        """Connect this handler to a session (new, resume, reconnect, ...).

        Raises:
            KernelStartupError: If the kernel fails to start.
            WebSocketDisconnect: If the connection is rejected; carries the
                close code and reason.
        """
        return SessionConnector(
            manager=self.manager,
            handler=self,
            params=self.params,
            connection=connection,
        ).connect()

    def _is_viewer(
        self, session: Session, connection_type: ConnectionType
    ) -> bool:
        """Whether this consumer gets read-only (kiosk) message filtering."""
        return is_viewer_connection(
            connection_type=connection_type,
            is_main_consumer=session.room.main_consumer is self,
        )

    def notify(self, notification: KernelMessage) -> None:
        self.message_queue.put_nowait(notification)

    def _serialize_and_notify(self, notification: NotificationMessage) -> None:
        self.notify(serialize_kernel_message(notification))

    def _write_kernel_ready_from_session_view(
        self, session: Session, kiosk: bool
    ) -> None:
        """Write kernel ready message using current session view state."""
        self._write_kernel_ready(
            session=session,
            resumed=True,
            ui_values=session.session_view.ui_values,
            last_executed_code=session.session_view.last_executed_code,
            last_execution_time=session.session_view.last_execution_time,
            kiosk=kiosk,
            auto_instantiated=False,
        )

    def _write_kernel_ready(
        self,
        session: Session,
        resumed: bool,
        ui_values: dict[str, JSONType],
        last_executed_code: dict[CellId_t, str],
        last_execution_time: dict[CellId_t, float],
        kiosk: bool,
        auto_instantiated: bool,
    ) -> None:
        """Communicates to the client that the kernel is ready.

        Sends cell code and other metadata to client.

        Args:
            session: Current session
            resumed: Whether this is a resumed session
            ui_values: UI element values
            last_executed_code: Last executed code for each cell
            last_execution_time: Last execution time for each cell
            kiosk: Whether this is kiosk mode
            auto_instantiated: Whether the kernel has already been instantiated
                server-side (run mode). If True, the frontend does not need
                to instantiate the app.
        """
        # Only send execution data if sending code to frontend
        should_send = self.manager.should_send_code_to_frontend()

        # RTC is only enabled if configured AND Loro is available
        effective_rtc_enabled = self.params.rtc_enabled and is_rtc_available()

        # Build kernel ready message
        kernel_ready_msg = build_kernel_ready(
            session=session,
            manager=self.manager,
            resumed=resumed,
            ui_values=ui_values,
            last_executed_code=last_executed_code if should_send else {},
            last_execution_time=last_execution_time if should_send else {},
            kiosk=kiosk,
            rtc_enabled=effective_rtc_enabled,
            file_key=self.params.file_key,
            mode=self.mode,
            doc_manager=self.doc_manager,
            auto_instantiated=auto_instantiated,
        )
        self._serialize_and_notify(kernel_ready_msg)

    def _reconnect_session(self, session: Session, replay: bool) -> None:
        """Reconnect to an existing session (kernel).

        A connection can be closed when a user's computer goes to sleep,
        spurious network issues, etc.
        """
        # Cancel previous close handle
        if self.cancel_close_handle is not None:
            self.cancel_close_handle.cancel()

        self.status = ConnectionState.OPEN
        session.connect_consumer(self, main=True)

        # Write reconnected message
        self._serialize_and_notify(ReconnectedNotification())

        # If not replaying, just send a toast
        if not replay:
            self._serialize_and_notify(
                AlertNotification(
                    title="Reconnected",
                    description="You have reconnected to an existing session.",
                )
            )
            return

        self._write_kernel_ready_from_session_view(session, self.params.kiosk)
        self._serialize_and_notify(
            BannerNotification(
                title="Reconnected",
                description="You have reconnected to an existing session.",
                action="restart",
            )
        )

        self._replay_previous_session(session)

    def _connect_kiosk(self, session: Session) -> None:
        """Connect to a kiosk session.

        A kiosk session is a write-ish session that is connected to a
        frontend. It can set UI elements and interact with the sidebar,
        but cannot change or execute code. This is not a permission limitation,
        but rather we don't have full multi-player support yet.

        Kiosk mode is useful when the user is using an editor (VSCode or VIM)
        that does not easily support our reactive frontend or our panels.
        The user uses VSCode or VIM to write code, and the
        marimo kiosk/frontend to visualize the output.
        """

        session.connect_consumer(self, main=False)
        self.status = ConnectionState.CONNECTING
        self._write_kernel_ready_from_session_view(session, kiosk=True)
        self.status = ConnectionState.OPEN
        self._replay_previous_session(session)

    def _connect_to_existing_session(self, session: Session) -> None:
        """Connect to an existing session and replay all messages."""
        self.status = ConnectionState.CONNECTING
        session.connect_consumer(self, main=False)

        # Write kernel ready with current state
        self._write_kernel_ready_from_session_view(session, kiosk=False)
        self.status = ConnectionState.OPEN

        # Replay all operations
        self._replay_previous_session(session)

    def _replay_previous_session(self, session: Session) -> None:
        """Replay the previous session view."""
        notifications = session.session_view.notifications
        if len(notifications) == 0:
            LOGGER.debug("No notifications to replay")
            return
        LOGGER.debug(f"Replaying {len(notifications)} notifications")
        for notif in notifications:
            LOGGER.debug("Replaying notification %s", notif)
            self._serialize_and_notify(notif)

    def _on_disconnect(
        self,
        e: Exception,
        cleanup_fn: Callable[[], Any],
    ) -> None:
        LOGGER.debug(
            "Connection closed for session %s with exception %s, type %s",
            self.params.session_id,
            str(e),
            type(e),
        )

        # Change the status
        self.status = ConnectionState.CLOSED
        # Disconnect the consumer
        session = self.manager.get_session(self.params.session_id)
        if session:
            session.disconnect_consumer(self)

        # When the connection is closed, we wait session.ttl_seconds before
        # closing the session. This prevents the session from being closed
        # during intermittent network issues.
        # In RUN mode, this always applies (sessions always have a default
        # TTL even if the manager's ttl_seconds is None).
        # In EDIT mode, this only applies when --session-ttl is explicitly set.
        should_ttl_close = (
            self.manager.ttl_seconds is not None
            or self.mode == SessionMode.RUN
        )
        if should_ttl_close:

            def _close() -> None:
                if self.status != ConnectionState.OPEN:
                    # Guard: if another consumer has taken over, the session
                    # is alive.
                    live = self.manager.get_session(self.params.session_id)
                    if (
                        live is not None
                        and live.connection_state() == ConnectionState.OPEN
                    ):
                        LOGGER.debug(
                            "Session %s has active consumer, skipping TTL close",
                            self.params.session_id,
                        )
                        return
                    LOGGER.debug(
                        "Closing session %s (TTL EXPIRED)",
                        self.params.session_id,
                    )
                    # wait until TTL is expired before calling the cleanup
                    # function
                    cleanup_fn()
                    self.manager.close_session(self.params.session_id)

            if session is not None:
                cancellation_handle = asyncio.get_running_loop().call_later(
                    session.ttl_seconds, _close
                )
                self.cancel_close_handle = cancellation_handle
            else:
                _close()
        else:
            cleanup_fn()

    def on_attach(self, session: Session, event_bus: SessionEventBus) -> None:
        del session
        del event_bus
        return

    def on_detach(self) -> None:
        # If the transport is open, send a close message
        is_connected = (
            self.status == ConnectionState.OPEN
            or self.status == ConnectionState.CONNECTING
        ) and self._is_transport_connected()
        if is_connected:
            self._request_close(
                WebSocketCodes.NORMAL_CLOSE, WebSocketCloseReason.SHUTDOWN
            )

        self._cancel_message_loop()

    def connection_state(self) -> ConnectionState:
        return self.status

    def _check_status_update(self) -> None:
        # Only check for updates if we're in edit mode
        if (
            not GLOBAL_SETTINGS.CHECK_STATUS_UPDATE
            or self.mode != SessionMode.EDIT
        ):
            return

        def on_update(current_version: str, state: MarimoCLIState) -> None:
            # Let's only toast once per marimo server
            # so we can just store this in memory.
            # We still want to check for updates (which are debounced 24 hours)
            # but don't keep toasting.
            global has_toasted
            if has_toasted:
                return

            has_toasted = True

            title = (
                f"Update available {current_version} → {state.latest_version}"
            )
            release_url = "https://github.com/marimo-team/marimo/releases"

            # Build description with notices if present
            description = f"Check out the <a class='underline' target='_blank' href='{release_url}'>latest release on GitHub.</a>"

            if state.notices:
                notices_text = (
                    "<br><br><strong>Recent updates:</strong><br>"
                    + "<br>".join(f"• {notice}" for notice in state.notices)
                )
                description += notices_text

            self._serialize_and_notify(
                AlertNotification(title=title, description=description)
            )

        check_for_updates(on_update)


has_toasted = False
