# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import sys
from typing import Any, Callable, Optional

from starlette.websockets import WebSocket, WebSocketState

from marimo import _loggers
from marimo._cli.upgrade import check_for_updates
from marimo._config.cli_state import MarimoCLIState
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.notification import (
    AlertNotification,
    BannerNotification,
    NotificationMessage,
    ReconnectedNotification,
)
from marimo._messaging.serde import serialize_kernel_message
from marimo._messaging.types import KernelMessage
from marimo._plugins.core.web_component import JSONType
from marimo._server.api.deps import AppState
from marimo._server.api.endpoints.ws.ws_connection_validator import (
    ConnectionParams,
    WebSocketConnectionValidator,
)
from marimo._server.api.endpoints.ws.ws_kernel_ready import (
    build_kernel_ready,
    is_rtc_available,
)
from marimo._server.api.endpoints.ws.ws_message_loop import (
    WebSocketMessageLoop,
)
from marimo._server.api.endpoints.ws.ws_rtc_handler import RTCWebSocketHandler
from marimo._server.api.endpoints.ws.ws_session_connector import (
    SessionConnector,
)
from marimo._server.codes import WebSocketCodes
from marimo._server.router import APIRouter
from marimo._server.rtc.doc import LoroDocManager
from marimo._server.session_manager import SessionManager
from marimo._session import Session
from marimo._session.consumer import SessionConsumer
from marimo._session.events import SessionEventBus
from marimo._session.model import (
    ConnectionState,
    SessionMode,
)
from marimo._types.ids import CellId_t, ConsumerId

LOGGER = _loggers.marimo_logger()

LORO_ALLOWED = sys.version_info >= (3, 11)

router = APIRouter()

DOC_MANAGER = LoroDocManager()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
) -> None:
    """Main WebSocket endpoint for marimo sessions.

    responses:
        200:
            description: Websocket endpoint
    """
    app_state = AppState(websocket)
    validator = WebSocketConnectionValidator(websocket, app_state)

    # Validate authentication before proceeding
    if not await validator.validate_auth():
        return

    # Extract and validate connection parameters
    params = await validator.extract_connection_params()
    if params is None:
        return

    # Start handler
    await WebSocketHandler(
        websocket=websocket,
        manager=app_state.session_manager,
        params=params,
        mode=app_state.mode,
    ).start()


# WebSocket endpoint for LoroDoc synchronization
@router.websocket("/ws_sync")
async def ws_sync(
    websocket: WebSocket,
) -> None:
    """WebSocket endpoint for LoroDoc synchronization (RTC)."""
    app_state = AppState(websocket)
    validator = WebSocketConnectionValidator(websocket, app_state)

    # Validate authentication before proceeding
    if not await validator.validate_auth():
        return

    # Check if Loro is available
    if not (LORO_ALLOWED and DependencyManager.loro.has()):
        if not LORO_ALLOWED:
            LOGGER.warning(
                "RTC: Python version is not supported (requires 3.11+)"
            )
        else:
            LOGGER.warning("RTC: Loro is not installed, closing websocket")
        await websocket.close(
            WebSocketCodes.NORMAL_CLOSE, "MARIMO_LORO_NOT_INSTALLED"
        )
        return

    # Extract file key
    file_key = await validator.extract_file_key_only()
    if file_key is None:
        return

    # Verify session exists
    manager = app_state.session_manager
    session = manager.get_session_by_file_key(file_key)
    if session is None:
        LOGGER.warning(
            f"RTC: Closing websocket - no session found for file key {file_key}"
        )
        await websocket.close(WebSocketCodes.FORBIDDEN, "MARIMO_NOT_ALLOWED")
        return

    # Handle RTC connection
    handler = RTCWebSocketHandler(websocket, file_key, DOC_MANAGER)
    await handler.handle()


class WebSocketHandler(SessionConsumer):
    """WebSocket that sessions use to send messages to frontends.

    Each new socket gets a unique session. At most one session can exist when
    in edit mode (unless RTC is enabled).
    """

    def __init__(
        self,
        *,
        websocket: WebSocket,
        manager: SessionManager,
        params: ConnectionParams,
        mode: SessionMode,
    ):
        self.websocket = websocket
        self.manager = manager
        self.params = params
        self.mode = mode
        self.status: ConnectionState
        self.cancel_close_handle: Optional[asyncio.TimerHandle] = None
        # Messages from the kernel are put in this queue
        # to be sent to the frontend
        self.message_queue: asyncio.Queue[KernelMessage]
        self.ws_future: Optional[asyncio.Task[None]] = None
        self._consumer_id = ConsumerId(params.session_id)

    @property
    def consumer_id(self) -> ConsumerId:
        return self._consumer_id

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
            doc_manager=DOC_MANAGER,
            auto_instantiated=auto_instantiated,
        )
        self._serialize_and_notify(kernel_ready_msg)

    def _reconnect_session(self, session: Session, replay: bool) -> None:
        """Reconnect to an existing session (kernel).

        A websocket can be closed when a user's computer goes to sleep,
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
            "Websocket disconnected for session %s with exception %s, type %s",
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

        if self.manager.mode == SessionMode.RUN:
            # When the websocket is closed, we wait session.ttl_seconds before
            # closing the session. This is to prevent the session from being
            # closed if the during an intermittent network issue.
            def _close() -> None:
                if self.status != ConnectionState.OPEN:
                    LOGGER.debug(
                        "Closing session %s (TTL EXPIRED)",
                        self.params.session_id,
                    )
                    # wait until TTL is expired before calling the cleanup
                    # function
                    cleanup_fn()
                    self.manager.close_session(self.params.session_id)

            session = self.manager.get_session(self.params.session_id)
            if session is not None:
                cancellation_handle = asyncio.get_event_loop().call_later(
                    session.ttl_seconds, _close
                )
                self.cancel_close_handle = cancellation_handle
            else:
                _close()
        else:
            cleanup_fn()

    async def start(self) -> None:
        """Start the WebSocket handler.

        Accepts the connection, establishes a session, and starts the
        message loop.
        """
        # Accept the websocket connection
        await self.websocket.accept()
        # Create a new queue for this session
        self.message_queue = asyncio.Queue()

        LOGGER.debug(
            "Websocket open request for session with id %s",
            self.params.session_id,
        )
        LOGGER.debug("Existing sessions: %s", self.manager.sessions)

        # Check if connection is allowed
        if not self._can_connect():
            await self._close_already_connected()
            return

        # Use SessionConnector to establish session connection
        connector = SessionConnector(
            manager=self.manager,
            handler=self,
            params=self.params,
            websocket=self.websocket,
        )
        session, connection_type = connector.connect()
        LOGGER.debug(
            "Connected to session %s with type %s",
            session.initialization_id,
            connection_type,
        )

        # Start message loops
        message_loop = WebSocketMessageLoop(
            websocket=self.websocket,
            message_queue=self.message_queue,
            kiosk=self.params.kiosk,
            on_disconnect=self._on_disconnect,
            on_check_status_update=self._check_status_update,
        )

        try:
            self.ws_future = asyncio.create_task(message_loop.start())
            await self.ws_future
        except asyncio.CancelledError:
            LOGGER.debug("Websocket terminated with CancelledError")

    def _can_connect(self) -> bool:
        """Check if this connection is allowed.

        Only one frontend can be connected at a time in edit mode,
        if RTC is not enabled.
        """
        if (
            self.manager.mode == SessionMode.EDIT
            and self.manager.any_clients_connected(self.params.file_key)
            and not self.params.kiosk
            and not self.params.rtc_enabled
        ):
            LOGGER.debug(
                "Refusing connection; a frontend is already connected."
            )
            return False
        return True

    async def _close_already_connected(self) -> None:
        """Close the WebSocket with an 'already connected' error."""
        if self.websocket.application_state is WebSocketState.CONNECTED:
            await self.websocket.close(
                WebSocketCodes.ALREADY_CONNECTED,
                "MARIMO_ALREADY_CONNECTED",
            )

    def on_attach(self, session: Session, event_bus: SessionEventBus) -> None:
        del session
        del event_bus
        return None

    def on_detach(self) -> None:
        # If the websocket is open, send a close message
        is_connected = (
            self.status == ConnectionState.OPEN
            or self.status == ConnectionState.CONNECTING
        ) and self.websocket.application_state is WebSocketState.CONNECTED
        if is_connected:
            asyncio.create_task(
                self.websocket.close(
                    WebSocketCodes.NORMAL_CLOSE, "MARIMO_SHUTDOWN"
                )
            )

        if self.ws_future:
            self.ws_future.cancel()

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
            description = f"Check out the <a class='underline' target='_blank' href='{release_url}'>latest release on GitHub.</a>"  # noqa: E501

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

    def _connect_to_existing_session(self, session: Session) -> None:
        """Connect to an existing session and replay all messages."""
        self.status = ConnectionState.CONNECTING
        session.connect_consumer(self, main=False)

        # Write kernel ready with current state
        self._write_kernel_ready_from_session_view(session, kiosk=False)
        self.status = ConnectionState.OPEN

        # Replay all operations
        self._replay_previous_session(session)


has_toasted = False
