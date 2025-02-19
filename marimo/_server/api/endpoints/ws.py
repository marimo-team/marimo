# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from enum import IntEnum
from functools import partial
from typing import TYPE_CHECKING, Any, Callable, Optional

from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

from marimo import _loggers
from marimo._ast.cell import CellConfig
from marimo._cli.upgrade import check_for_updates
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._messaging.ops import (
    Alert,
    Banner,
    CompletionResult,
    FocusCell,
    KernelCapabilities,
    KernelReady,
    MessageOperation,
    Reconnected,
    serialize,
)
from marimo._messaging.types import KernelMessage, NoopStream
from marimo._plugins.core.json_encoder import WebComponentEncoder
from marimo._plugins.core.web_component import JSONType
from marimo._runtime.params import QueryParams
from marimo._server.api.deps import AppState
from marimo._server.file_router import MarimoFileKey
from marimo._server.model import (
    ConnectionState,
    SessionConsumer,
    SessionMode,
)
from marimo._server.router import APIRouter
from marimo._server.sessions import Session, SessionManager
from marimo._types.ids import CellId_t, ConsumerId, SessionId

if TYPE_CHECKING:
    from pycrdt import Doc, Text, TransactionEvent

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
    raw_session_id = app_state.query_params(SESSION_QUERY_PARAM_KEY)
    if raw_session_id is None:
        await websocket.close(
            WebSocketCodes.NORMAL_CLOSE, "MARIMO_NO_SESSION_ID"
        )
        return

    session_id = SessionId(raw_session_id)

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

    config = app_state.config_manager.get_config()

    rtc_enabled: bool = config.get("experimental", {}).get("rtc", False)
    auto_instantiate = config["runtime"]["auto_instantiate"]

    await WebsocketHandler(
        websocket=websocket,
        manager=app_state.session_manager,
        rtc_enabled=rtc_enabled,
        session_id=session_id,
        mode=app_state.mode,
        file_key=file_key,
        kiosk=kiosk,
        auto_instantiate=auto_instantiate,
    ).start()


@dataclass
class YCell:
    ydoc: Doc[Text]
    clients: int
    cleaner: asyncio.Task[None] | None = None


# TODO: we should use a more robust key type than the filename
# since renaming the file will break RTC.
@dataclass
class CellIdAndFileKey:
    cell_id: str
    file_key: MarimoFileKey

    def __hash__(self) -> int:
        return hash((self.cell_id, self.file_key))


ycells: dict[CellIdAndFileKey, YCell] = {}
ycell_lock = asyncio.Lock()


def put_updates(
    update_queue: asyncio.Queue[bytes], event: TransactionEvent
) -> None:
    update = event.update
    update_queue.put_nowait(update)


async def send_updates(
    websocket: WebSocket,
    update_queue: asyncio.Queue[bytes],
    cell_id: str,
) -> None:
    from pycrdt import create_update_message

    try:
        while True:
            update = await update_queue.get()
            message = create_update_message(update)
            await websocket.send_bytes(message)
    except Exception:
        LOGGER.debug(
            f"Could not send Y update to client for cell with ID {cell_id}",
        )


async def clean_cell(
    cell_id_and_file_key: CellIdAndFileKey, timeout: float = 60
) -> None:
    # Clients disconnect/reconnect to keep the WebSocket connection alive,
    # or because of network issues.
    # Keep the ycell in memory for one minute after client disconnects,
    # so that it can be synchronized and to prevent content duplication.
    # This task will be cancelled when any client reconnets.
    await asyncio.sleep(timeout)
    async with ycell_lock:
        ycell = ycells[cell_id_and_file_key]
        if not ycell.clients:
            del ycells[cell_id_and_file_key]


@router.websocket("/ws/{cell_id}")
async def ycell_provider(
    websocket: WebSocket,
) -> None:
    from pycrdt import (
        Doc,
        Text,
        YMessageType,
        create_sync_message,
        handle_sync_message,
    )

    app_state = AppState(websocket)
    file_key: Optional[MarimoFileKey] = (
        app_state.query_params(FILE_QUERY_PARAM_KEY)
        or app_state.session_manager.file_router.get_unique_file_key()
    )

    if file_key is None:
        await websocket.close(
            WebSocketCodes.NORMAL_CLOSE, "MARIMO_NO_FILE_KEY"
        )
        return

    manager = app_state.session_manager
    session = manager.get_session_by_file_key(file_key)
    if session is None:
        await websocket.close(WebSocketCodes.FORBIDDEN, "MARIMO_NOT_ALLOWED")
        return
    await websocket.accept()
    cell_id = CellId_t(websocket.path_params["cell_id"])
    key = CellIdAndFileKey(cell_id, file_key)
    async with ycell_lock:
        if key in ycells:
            ycell = ycells[key]
            ydoc = ycell.ydoc
            ycell.clients += 1
            if ycell.cleaner is not None:
                ycell.cleaner.cancel()
                ycell.cleaner = None
        else:
            file_manager = session.app_file_manager
            mgr = file_manager.app.cell_manager
            if mgr.has_cell(cell_id):
                code = mgr.cell_data_at(cell_id).code
            else:
                code = ""
            ydoc = Doc[Text]()
            ytext = ydoc.get("code", type=Text)
            ytext += code
            ycell = YCell(ydoc=ydoc, clients=1)
            ycells[key] = ycell
    update_queue: asyncio.Queue[bytes] = asyncio.Queue()
    task = asyncio.create_task(send_updates(websocket, update_queue, cell_id))
    subscription = ydoc.observe(partial(put_updates, update_queue))
    sync_message = create_sync_message(ydoc)
    try:
        await websocket.send_bytes(sync_message)
        while True:
            message = await websocket.receive_bytes()
            message_type = message[0]
            if message_type == YMessageType.SYNC:
                reply = handle_sync_message(message[1:], ydoc)
                if reply is not None:
                    await websocket.send_bytes(reply)
    except Exception:
        pass
    finally:
        task.cancel()
        ydoc.unobserve(subscription)
        async with ycell_lock:
            ycell.clients -= 1
            if not ycell.clients:
                if ycell.cleaner is not None:
                    ycell.cleaner.cancel()
                    ycell.cleaner = None
                ycell.cleaner = asyncio.create_task(clean_cell(key))


KIOSK_ONLY_OPERATIONS = {
    FocusCell.name,
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
        *,
        websocket: WebSocket,
        manager: SessionManager,
        rtc_enabled: bool,
        session_id: SessionId,
        mode: SessionMode,
        file_key: MarimoFileKey,
        kiosk: bool,
        auto_instantiate: bool,
    ):
        self.websocket = websocket
        self.manager = manager
        self.rtc_enabled = rtc_enabled
        self.session_id = session_id
        self.file_key = file_key
        self.mode = mode
        self.status: ConnectionState
        self.kiosk = kiosk
        self.auto_instantiate = auto_instantiate
        self.cancel_close_handle: Optional[asyncio.TimerHandle] = None
        self.heartbeat_task: Optional[asyncio.Task[None]] = None
        # Messages from the kernel are put in this queue
        # to be sent to the frontend
        self.message_queue: asyncio.Queue[KernelMessage]
        self.ws_future: asyncio.Future[tuple[None, None]] | None = None

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
        self._write_kernel_ready(
            session=session,
            resumed=True,
            ui_values=session.get_current_state().ui_values,
            last_executed_code=session.get_current_state().last_executed_code,
            last_execution_time=session.get_current_state().last_execution_time,
            kiosk=True,
        )
        self.status = ConnectionState.OPEN
        self._replay_previous_session(session)

    def _replay_previous_session(self, session: Session) -> None:
        """Replay the previous session view."""
        operations = session.get_current_state().operations
        if len(operations) == 0:
            LOGGER.debug("No operations to replay")
            return
        LOGGER.debug(f"Replaying {len(operations)} operations")
        for op in operations:
            LOGGER.debug("Replaying operation %s", op)
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
            # When the websocket is closed, we wait session.ttl_seconds before
            # closing the session. This is to prevent the session from being
            # closed if the during an intermittent network issue.
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

        # Only one frontend can be connected at a time in edit mode,
        # if RTC is not enabled.
        if (
            mgr.mode == SessionMode.EDIT
            and mgr.any_clients_connected(self.file_key)
            and not self.kiosk
            and not self.rtc_enabled
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
                LOGGER.debug("Connecting to kiosk session")
                self._connect_kiosk(kiosk_session)
                return kiosk_session

            # 2. Handle reconnection

            # The session already exists, but it was disconnected.
            # This can happen in local development when the client
            # goes to sleep and wakes later. Just replace the session's
            # socket, but keep its kernel.
            existing_session = mgr.get_session(session_id)
            if existing_session is not None:
                LOGGER.debug("Reconnecting session %s", session_id)
                # In case there is a lingering connection, close it
                existing_session.maybe_disconnect_consumer()
                self._reconnect_session(existing_session, replay=False)
                return existing_session

            # 3. Check for existing session with same file
            existing_session = mgr.get_session_by_file_key(self.file_key)
            if (
                existing_session is not None
                and self.rtc_enabled
                and self.mode == SessionMode.EDIT
            ):
                LOGGER.debug(
                    "Connecting to existing session for file %s", self.file_key
                )
                self._connect_to_existing_session(existing_session)
                return existing_session

            # 4. Handle resume
            resumable_session = mgr.maybe_resume_session(
                session_id, self.file_key
            )
            if resumable_session is not None:
                LOGGER.debug("Resuming session %s", session_id)
                self._reconnect_session(resumable_session, replay=True)
                return resumable_session

            # 5. Create new session

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
            self.status = ConnectionState.CONNECTING
            # Let the frontend know it can instantiate the app.
            self._write_kernel_ready(
                new_session,
                resumed=False,
                ui_values={},
                last_executed_code={},
                last_execution_time={},
                kiosk=False,
            )
            self.status = ConnectionState.OPEN
            # if auto-instantiate if false, replay the previous session
            if not self.auto_instantiate:
                new_session.sync_session_view_from_cache()
                self._replay_previous_session(new_session)
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
                self._check_status_update()
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
            self.ws_future = asyncio.gather(
                listen_for_messages_task,
                listen_for_disconnect_task,
            )
            await self.ws_future
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
            or self.status == ConnectionState.CONNECTING
        ) and self.websocket.application_state is WebSocketState.CONNECTED:
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

        def on_update(current_version: str, latest_version: str) -> None:
            # Let's only toast once per marimo server
            # so we can just store this in memory.
            # We still want to check for updates (which are debounced 24 hours)
            # but don't keep toasting.
            global HAS_TOASTED
            if HAS_TOASTED:
                return

            HAS_TOASTED = True

            title = f"Update available {current_version} → {latest_version}"
            release_url = "https://github.com/marimo-team/marimo/releases"
            description = f"Check out the <a class='underline' target='_blank' href='{release_url}'>latest release on GitHub.</a>"  # noqa: E501
            self.write_operation(Alert(title=title, description=description))

        check_for_updates(on_update)

    def _connect_to_existing_session(self, session: Session) -> None:
        """Connect to an existing session and replay all messages."""
        self.status = ConnectionState.CONNECTING
        session.connect_consumer(self, main=False)

        # Write kernel ready with current state
        self._write_kernel_ready(
            session=session,
            resumed=True,
            ui_values=session.get_current_state().ui_values,
            last_executed_code=session.get_current_state().last_executed_code,
            last_execution_time=session.get_current_state().last_execution_time,
            kiosk=False,
        )
        self.status = ConnectionState.OPEN

        # Replay all operations
        self._replay_previous_session(session)


HAS_TOASTED = False
