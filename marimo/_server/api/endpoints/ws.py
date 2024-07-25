# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import json
from enum import IntEnum
from typing import Any, Callable, Optional

from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

from marimo import _loggers
from marimo._ast.cell import CellConfig, CellId_t
from marimo._messaging.ops import (
    Alert,
    Banner,
    CompletionResult,
    FocusCell,
    KernelCapabilities,
    KernelReady,
    MessageOperation,
    Reconnected,
    UpdateCellCodes,
    UpdateCellIdsRequest,
    serialize,
)
from marimo._messaging.types import KernelMessage, NoopStream
from marimo._plugins.core.json_encoder import WebComponentEncoder
from marimo._plugins.core.web_component import JSONType
from marimo._runtime.params import QueryParams
from marimo._server.api.deps import AppState
from marimo._server.file_router import MarimoFileKey
from marimo._server.ids import ConsumerId
from marimo._server.model import (
    ConnectionState,
    SessionConsumer,
    SessionMode,
)
from marimo._server.router import APIRouter
from marimo._server.sessions import Session, SessionManager

LOGGER = _loggers.marimo_logger()

router = APIRouter()

SESSION_QUERY_PARAM_KEY = "session_id"
FILE_QUERY_PARAM_KEY = "file"
KIOSK_QUERY_PARAM_KEY = "kiosk"


class WebSocketCodes(IntEnum):
    ALREADY_CONNECTED = 1003
    NORMAL_CLOSE = 1000
    FORBIDDEN = 1008


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
) -> None:
    """
    responses:
        200:
            description: Websocket endpoint
    """
    app_state = AppState(websocket)
    session_id = app_state.query_params(SESSION_QUERY_PARAM_KEY)
    if session_id is None:
        await websocket.close(
            WebSocketCodes.NORMAL_CLOSE, "MARIMO_NO_SESSION_ID"
        )
        return

    file_key: Optional[MarimoFileKey] = (
        app_state.query_params(FILE_QUERY_PARAM_KEY)
        or app_state.session_manager.file_router.get_unique_file_key()
    )

    if file_key is None:
        await websocket.close(
            WebSocketCodes.NORMAL_CLOSE, "MARIMO_NO_FILE_KEY"
        )
        return

    kiosk = app_state.query_params(KIOSK_QUERY_PARAM_KEY) == "true"

    await WebsocketHandler(
        websocket=websocket,
        manager=app_state.session_manager,
        session_id=session_id,
        mode=app_state.mode,
        file_key=file_key,
        kiosk=kiosk,
    ).start()


KIOSK_ONLY_OPERATIONS = {
    FocusCell.name,
    UpdateCellCodes.name,
    UpdateCellIdsRequest.name,
}
KIOSK_EXCLUDED_OPERATIONS = {
    CompletionResult.name,
}


class WebsocketHandler(SessionConsumer):
    """WebSocket that sessions use to send messages to frontends.

    Each new socket gets a unique session. At most one session can exist when
    in edit mode.
    """

    def __init__(
        self,
        websocket: WebSocket,
        manager: SessionManager,
        session_id: str,
        mode: SessionMode,
        file_key: MarimoFileKey,
        kiosk: bool,
    ):
        self.websocket = websocket
        self.manager = manager
        self.session_id = session_id
        self.file_key = file_key
        self.mode = mode
        self.status: ConnectionState
        self.kiosk = kiosk
        self.cancel_close_handle: Optional[asyncio.TimerHandle] = None
        self.heartbeat_task: Optional[asyncio.Task[None]] = None
        # Messages from the kernel are put in this queue
        # to be sent to the frontend
        self.message_queue: asyncio.Queue[KernelMessage]

        super().__init__(consumer_id=ConsumerId(session_id))

    def _write_kernel_ready(
        self,
        session: Session,
        resumed: bool,
        ui_values: dict[str, JSONType],
        last_executed_code: dict[CellId_t, str],
        last_execution_time: dict[CellId_t, float],
        kiosk: bool,
    ) -> None:
        """Communicates to the client that the kernel is ready.

        Sends cell code and other metadata to client.
        """
        mgr = self.manager
        file_manager = session.app_file_manager
        app = file_manager.app

        codes: tuple[str, ...]
        names: tuple[str, ...]
        configs: tuple[CellConfig, ...]

        if mgr.should_send_code_to_frontend():
            codes, names, configs, cell_ids = tuple(
                zip(
                    *tuple(
                        (
                            cell_data.code,
                            cell_data.name,
                            cell_data.config,
                            cell_data.cell_id,
                        )
                        for cell_data in app.cell_manager.cell_data()
                    )
                )
            )
        else:
            codes, names, configs, cell_ids = tuple(
                zip(
                    *tuple(
                        # Don't send code to frontend in run mode
                        ("", "", cell_data.config, cell_data.cell_id)
                        for cell_data in app.cell_manager.cell_data()
                    )
                )
            )

            last_executed_code = {}
            last_execution_time = {}

        self.message_queue.put_nowait(
            (
                KernelReady.name,
                serialize(
                    KernelReady(
                        codes=codes,
                        names=names,
                        configs=configs,
                        layout=file_manager.read_layout_config(),
                        cell_ids=cell_ids,
                        resumed=resumed,
                        ui_values=ui_values,
                        last_executed_code=last_executed_code,
                        last_execution_time=last_execution_time,
                        app_config=app.config,
                        kiosk=kiosk,
                        capabilities=KernelCapabilities(),
                    )
                ),
            )
        )

    def _reconnect_session(self, session: "Session", replay: bool) -> None:
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
        self.write_operation(Reconnected())

        # If not replaying, just send a toast
        if not replay:
            self.write_operation(
                Alert(
                    title="Reconnected",
                    description="You have reconnected to an existing session.",
                )
            )
            return

        operations = session.get_current_state().operations
        # Replay the current session view
        LOGGER.debug(
            f"Replaying {len(operations)} operations to the consumer",
        )

        self._write_kernel_ready(
            session=session,
            resumed=True,
            ui_values=session.get_current_state().ui_values,
            last_executed_code=session.get_current_state().last_executed_code,
            last_execution_time=session.get_current_state().last_execution_time,
            kiosk=self.kiosk,
        )
        self.write_operation(
            Banner(
                title="Reconnected",
                description="You have reconnected to an existing session.",
                action="restart",
            )
        )

        for op in operations:
            LOGGER.debug("Replaying operation %s", serialize(op))
            self.write_operation(op)

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

        self.status = ConnectionState.OPEN
        session.connect_consumer(self, main=False)

        operations = session.get_current_state().operations
        # Replay the current session view
        LOGGER.debug(
            f"Replaying {len(operations)} operations to the kiosk consumer",
        )

        self._write_kernel_ready(
            session=session,
            resumed=True,
            ui_values=session.get_current_state().ui_values,
            last_executed_code=session.get_current_state().last_executed_code,
            last_execution_time=session.get_current_state().last_execution_time,
            kiosk=True,
        )

        for op in operations:
            LOGGER.debug("Replaying operation %s", serialize(op))
            self.write_operation(op)

    def _on_disconnect(
        self,
        e: Exception,
        cleanup_fn: Callable[[], Any],
    ) -> None:
        LOGGER.debug(
            "Websocket disconnected for session %s with exception %s, type %s",
            self.session_id,
            str(e),
            type(e),
        )

        # Change the status
        self.status = ConnectionState.CLOSED
        # Disconnect the consumer
        session = self.manager.get_session(self.session_id)
        if session:
            session.disconnect_consumer(self)

        if self.manager.mode == SessionMode.RUN:
            # When the websocket is closed, we wait TTL_SECONDS before
            # closing the session. This is to prevent the session from
            # being closed if the during an intermittent network issue.
            def _close() -> None:
                if self.status != ConnectionState.OPEN:
                    LOGGER.debug(
                        "Closing session %s (TTL EXPIRED)",
                        self.session_id,
                    )
                    # wait until TTL is expired before calling the cleanup
                    # function
                    cleanup_fn()
                    self.manager.close_session(self.session_id)

            session = self.manager.get_session(self.session_id)
            cancellation_handle = asyncio.get_event_loop().call_later(
                Session.TTL_SECONDS, _close
            )
            if session is not None:
                self.cancel_close_handle = cancellation_handle
        else:
            cleanup_fn()

    async def start(self) -> None:
        # Accept the websocket connection
        await self.websocket.accept()
        # Create a new queue for this session
        self.message_queue = asyncio.Queue()

        session_id = self.session_id
        mgr = self.manager
        LOGGER.debug(
            "Websocket open request for session with id %s", session_id
        )
        LOGGER.debug("Existing sessions: %s", mgr.sessions)

        # Only one frontend can be connected at a time in edit mode.
        if (
            mgr.mode == SessionMode.EDIT
            and mgr.any_clients_connected(self.file_key)
            and not self.kiosk
        ):
            LOGGER.debug(
                "Refusing connection; a frontend is already connected."
            )
            if self.websocket.application_state is WebSocketState.CONNECTED:
                await self.websocket.close(
                    WebSocketCodes.ALREADY_CONNECTED,
                    "MARIMO_ALREADY_CONNECTED",
                )
            return

        def get_session() -> Session:
            # 1. If we are in kiosk mode, connect to the existing session
            if self.kiosk:
                if self.mode is not SessionMode.EDIT:
                    LOGGER.debug("Kiosk mode is only supported in edit mode")
                    raise WebSocketDisconnect(
                        WebSocketCodes.FORBIDDEN, "MARIMO_KIOSK_NOT_ALLOWED"
                    )
                kiosk_session = mgr.get_session(session_id)
                if kiosk_session is None:
                    LOGGER.debug(
                        "Kiosk session not found for session id %s",
                        session_id,
                    )
                    kiosk_session = mgr.get_session_by_file_key(self.file_key)
                if kiosk_session is None:
                    LOGGER.debug(
                        "Kiosk session not found for file key %s",
                        self.file_key,
                    )
                    raise WebSocketDisconnect(
                        WebSocketCodes.NORMAL_CLOSE, "MARIMO_NO_SESSION"
                    )
                self.status = ConnectionState.OPEN
                LOGGER.debug("Connecting to kiosk session")
                self._connect_kiosk(kiosk_session)
                return kiosk_session

            # 2. Handle reconnection

            # The session already exists, but it was disconnected.
            # This can happen in local development when the client
            # goes to sleep and wakes later. Just replace the session's
            # socket, but keep its kernel
            existing_session = mgr.get_session(session_id)
            if existing_session is not None:
                LOGGER.debug("Reconnecting session %s", session_id)
                # In case there is a lingering connection, close it
                existing_session.maybe_disconnect_consumer()
                self._reconnect_session(existing_session, replay=False)
                return existing_session

            # 3. Handle resume

            # Get resumable possible resumable session
            resumable_session = mgr.maybe_resume_session(
                session_id, self.file_key
            )
            if resumable_session is not None:
                LOGGER.debug("Resuming session %s", session_id)
                self._reconnect_session(resumable_session, replay=True)
                return resumable_session

            # 4. Create a new session

            # If the client refreshed their page, there will be one
            # existing session with a closed socket for a different session
            # id; that's why we call `close_all_sessions`.
            # if mgr.mode == SessionMode.EDIT:
            #     mgr.close_all_sessions()

            # Grab the query params from the websocket
            # Note: if we resume a session, we don't pick up the new query
            # params, and instead use the query params from when the
            # session was created.
            query_params = QueryParams({}, NoopStream())
            for key, value in self.websocket.query_params.multi_items():
                if key in QueryParams.IGNORED_KEYS:
                    continue
                query_params.append(key, value)

            new_session = mgr.create_session(
                query_params=query_params.to_dict(),
                session_id=session_id,
                session_consumer=self,
                file_key=self.file_key,
            )
            self.status = ConnectionState.OPEN
            # Let the frontend know it can instantiate the app.
            self._write_kernel_ready(
                new_session,
                resumed=False,
                ui_values={},
                last_executed_code={},
                last_execution_time={},
                kiosk=False,
            )
            return new_session

        get_session()

        async def listen_for_messages() -> None:
            while True:
                (op, data) = await self.message_queue.get()

                if op in KIOSK_ONLY_OPERATIONS and not self.kiosk:
                    LOGGER.debug(
                        "Ignoring operation %s, not in kiosk mode",
                        op,
                    )
                    continue
                if op in KIOSK_EXCLUDED_OPERATIONS and self.kiosk:
                    LOGGER.debug(
                        "Ignoring operation %s, in kiosk mode",
                        op,
                    )
                    continue

                try:
                    text = json.dumps(
                        {
                            "op": op,
                            "data": data,
                        },
                        cls=WebComponentEncoder,
                    )
                except TypeError as e:
                    # This is a deserialization error
                    LOGGER.error(
                        "Failed to send message to frontend: %s", str(e)
                    )
                    LOGGER.error("Message: %s", data)
                    continue

                try:
                    await self.websocket.send_text(text)
                except WebSocketDisconnect as e:
                    self._on_disconnect(
                        e,
                        cleanup_fn=lambda: listen_for_disconnect_task.cancel(),
                    )
                except RuntimeError as e:
                    # Starlette can raise a runtime error if a message is sent
                    # when the socket is closed. In case the disconnection
                    # error hasn't made its way to listen_for_disconnect, do
                    # the cleanup here.
                    if (
                        self.websocket.application_state
                        == WebSocketState.DISCONNECTED
                    ):
                        self._on_disconnect(
                            e,
                            cleanup_fn=lambda: listen_for_disconnect_task.cancel(),  # noqa: E501
                        )

        async def listen_for_disconnect() -> None:
            try:
                await self.websocket.receive_text()
            except WebSocketDisconnect as e:
                self._on_disconnect(
                    e, cleanup_fn=lambda: listen_for_messages_task.cancel()
                )

        listen_for_messages_task = asyncio.create_task(listen_for_messages())
        listen_for_disconnect_task = asyncio.create_task(
            listen_for_disconnect()
        )

        try:
            self.future = asyncio.gather(
                listen_for_messages_task,
                listen_for_disconnect_task,
            )
            await self.future
        except asyncio.CancelledError:
            LOGGER.debug("Websocket terminated with CancelledError")
            pass

    def on_start(
        self,
    ) -> Callable[[KernelMessage], None]:
        def listener(response: KernelMessage) -> None:
            self.message_queue.put_nowait(response)

        return listener

    def write_operation(self, op: MessageOperation) -> None:
        self.message_queue.put_nowait((op.name, serialize(op)))

    def on_stop(self) -> None:
        # Cancel the heartbeat task, reader
        if self.heartbeat_task and not self.heartbeat_task.cancelled():
            self.heartbeat_task.cancel()

        # If the websocket is open, send a close message
        if (
            self.status == ConnectionState.OPEN
            and self.websocket.application_state is WebSocketState.CONNECTED
        ):
            asyncio.create_task(
                self.websocket.close(
                    WebSocketCodes.NORMAL_CLOSE, "MARIMO_SHUTDOWN"
                )
            )

        self.future.cancel()

    def connection_state(self) -> ConnectionState:
        return self.status
