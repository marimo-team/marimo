# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import json
import mimetypes
import os
import re
import stat
import typing
import warnings
from email.utils import formatdate
from enum import IntEnum
from typing import Callable, Optional
from uu import decode

from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import HTMLResponse, Response
from starlette.staticfiles import StaticFiles
from starlette.types import Receive, Scope, Send
from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

from marimo import __version__, _loggers
from marimo._ast.cell import CellConfig, CellId_t
from marimo._messaging.ops import (
    Alert,
    Banner,
    KernelReady,
    MessageOperation,
    Reconnected,
    serialize,
)
from marimo._messaging.types import KernelMessage, NoopStream
from marimo._plugins.core.json_encoder import WebComponentEncoder
from marimo._plugins.core.web_component import JSONType
from marimo._runtime.layout.layout import LayoutConfig, read_layout_config
from marimo._runtime.query_params import QueryParams
from marimo._runtime.virtual_file import EMPTY_VIRTUAL_FILE
from marimo._server.api.deps import AppState
from marimo._server.api.utils import parse_title
from marimo._server.model import (
    ConnectionState,
    SessionConsumer,
    SessionMode,
)
from marimo._server.router import APIRouter
from marimo._server.sessions import Session, SessionManager
from marimo._server.utils import import_files

LOGGER = _loggers.marimo_logger()

# Router for serving static assets
router = APIRouter()

# Root directory for static assets
root = os.path.realpath(str(import_files("marimo").joinpath("_static")))

# router.mount(
#     "/assets",
#     app=StaticFiles(directory=os.path.join(root, "assets")),
#     name="assets",
# )


@router.get("/")
async def index(request: Request) -> HTMLResponse:
    app_state = AppState(request)
    title = parse_title(app_state.filename)
    user_config = app_state.config_manager.get_config()
    app_config = app_state.session_manager.app_config().asdict()

    index_html = os.path.join(root, "index.html")
    with open(index_html, "r") as f:
        html = f.read()
        html = html.replace("{{ base_url }}", app_state.base_url)
        html = html.replace("{{ title }}", title)
        html = html.replace("{{ user_config }}", json.dumps(user_config))
        html = html.replace("{{ app_config }}", json.dumps(app_config))
        html = html.replace("{{ server_token }}", app_state.server_token)
        html = html.replace("{{ version }}", __version__)
        html = html.replace("{{ filename }}", app_state.filename or "")
        html = html.replace(
            "{{ mode }}",
            "read" if app_state.mode == SessionMode.RUN else "edit",
        )

    return HTMLResponse(html)


STATIC_FILES = [
    r"(favicon\.ico)",
    r"(manifest\.json)",
    r"(android-chrome-(192x192|512x512)\.png)",
    r"(apple-touch-icon\.png)",
]


@router.get("/@file/{filename_and_length:path}")
def virtual_file(
    request: Request,
) -> Response:
    """Handler for virtual files."""
    filename_and_length = request.path_params["filename_and_length"]

    LOGGER.debug("Getting virtual file: %s", filename_and_length)
    if filename_and_length == EMPTY_VIRTUAL_FILE.filename:
        return Response(content=b"", media_type="application/octet-stream")

    byte_length, filename = filename_and_length.split("-", 1)
    mimetype, _ = mimetypes.guess_type(filename)
    return Response(
        content=b"",
        media_type=mimetype,
        headers={"Cache-Control": "max-age=86400"},
    )


class FileResponse(Response):
    chunk_size = 64 * 1024

    def __init__(
        self,
        path: str | os.PathLike[str],
        status_code: int = 200,
        headers: typing.Mapping[str, str] | None = None,
        media_type: str | None = None,
        filename: str | None = None,
        stat_result: os.stat_result | None = None,
        method: str | None = None,
        content_disposition_type: str = "attachment",
    ) -> None:
        self.path = path
        self.status_code = status_code
        self.filename = filename
        if method is not None:
            warnings.warn(
                "The 'method' parameter is not used, and it will be removed.",
                DeprecationWarning,
            )
        if media_type is None:
            media_type = (
                mimetypes.guess_type(filename or path)[0] or "text/plain"
            )
        self.media_type = media_type
        self.init_headers(headers)
        self.headers["content-type"] = media_type
        self.headers["x-content-type-2"] = media_type
        if self.filename is not None:
            content_disposition_filename = self.filename
            if content_disposition_filename != self.filename:
                content_disposition = "{}; filename*=utf-8''{}".format(
                    content_disposition_type, content_disposition_filename
                )
            else:
                content_disposition = '{}; filename="{}"'.format(
                    content_disposition_type, self.filename
                )
            self.headers.setdefault("content-disposition", content_disposition)
        self.stat_result = stat_result
        if stat_result is not None:
            self.set_stat_headers(stat_result)

    def set_stat_headers(self, stat_result: os.stat_result) -> None:
        content_length = str(stat_result.st_size)
        last_modified = formatdate(stat_result.st_mtime, usegmt=True)
        str(stat_result.st_mtime) + "-" + str(stat_result.st_size)
        # etag = f'"{md5_hexdigest(etag_base.encode(), usedforsecurity=False)}"'

        self.headers.setdefault("content-length", content_length)
        self.headers.setdefault("last-modified", last_modified)
        # self.headers.setdefault("etag", etag)

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        if self.stat_result is None:
            try:
                # stat_result = await anyio.to_thread.run_sync(
                #     os.stat, self.path
                # )
                # self.set_stat_headers(stat_result)
                pass
            except FileNotFoundError:
                raise RuntimeError(f"File at path {self.path} does not exist.")
            else:
                # mode = stat_result.st_mode
                # if not stat.S_ISREG(mode):
                #     raise RuntimeError(
                #         f"File at path {self.path} is not a file."
                #     )
                pass
        headers = self.headers.items()
        await send(
            {
                "type": "http.response.start",
                "status": self.status_code,
                "headers": headers,
            }
        )
        if scope["method"].upper() == "HEAD":
            await send(
                {"type": "http.response.body", "body": b"", "more_body": False}
            )
        elif (
            "extensions" in scope
            and "http.response.pathsend" in scope["extensions"]
        ):
            await send(
                {"type": "http.response.pathsend", "path": str(self.path)}
            )
        else:
            with open(self.path, mode="rb") as file:
                await send(
                    {
                        "type": "http.response.body",
                        "body": file.read(),
                        "more_body": False,
                    }
                )
        # if self.background is not None:
        #     await self.background()


SESSION_QUERY_PARAM_KEY = "session_id"


class WebSocketCodes(IntEnum):
    ALREADY_CONNECTED = 1003
    NORMAL_CLOSE = 1000


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
) -> None:
    app_state = AppState(websocket)
    session_id = app_state.query_params(SESSION_QUERY_PARAM_KEY)
    if session_id is None:
        await websocket.close(
            WebSocketCodes.NORMAL_CLOSE, "MARIMO_NO_SESSION_ID"
        )
        return

    await WebsocketHandler(
        websocket=websocket,
        manager=app_state.session_manager,
        session_id=session_id,
        mode=app_state.mode,
    ).start()


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
    ):
        self.websocket = websocket
        self.manager = manager
        self.session_id = session_id
        self.mode = mode
        self.status: ConnectionState
        self.cancel_close_handle: Optional[asyncio.TimerHandle] = None
        self.heartbeat_task: Optional[asyncio.Task[None]] = None
        # Messages from the kernel are put in this queue
        # to be sent to the frontend
        self.message_queue: asyncio.Queue[KernelMessage]

    async def _write_kernel_ready(
        self,
        session: Session,
        resumed: bool,
        ui_values: dict[str, JSONType],
        last_executed_code: dict[CellId_t, str],
    ) -> None:
        """Communicates to the client that the kernel is ready.

        Sends cell code and other metadata to client.
        """
        mgr = self.manager
        app = session.app_file_manager.app

        codes: tuple[str, ...]
        names: tuple[str, ...]
        configs: tuple[CellConfig, ...]
        layout: Optional[LayoutConfig] = None

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

        if (
            app
            and app.config.layout_file is not None
            and isinstance(mgr.filename, str)
        ):
            app_dir = os.path.dirname(mgr.filename)
            layout = read_layout_config(app_dir, app.config.layout_file)

        await self.message_queue.put(
            (
                KernelReady.name,
                serialize(
                    KernelReady(
                        codes=codes,
                        names=names,
                        configs=configs,
                        layout=layout,
                        cell_ids=cell_ids,
                        resumed=resumed,
                        ui_values=ui_values,
                        last_executed_code=last_executed_code,
                    )
                ),
            )
        )

    async def _reconnect_session(
        self, session: "Session", replay: bool
    ) -> None:
        """Reconnect to an existing session (kernel).

        A websocket can be closed when a user's computer goes to sleep,
        spurious network issues, etc.
        """
        # Cancel previous close handle
        if self.cancel_close_handle is not None:
            self.cancel_close_handle.cancel()

        self.status = ConnectionState.OPEN
        session.connect_consumer(self)

        # Write reconnected message
        await self.write_operation(Reconnected())

        # If not replaying, just send a toast
        if not replay:
            await self.write_operation(
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

        await self._write_kernel_ready(
            session=session,
            resumed=True,
            ui_values=session.get_current_state().ui_values,
            last_executed_code=session.get_current_state().last_executed_code,
        )
        await self.write_operation(
            Banner(
                title="Reconnected",
                description="You have reconnected to an existing session.",
            )
        )

        for op in operations:
            LOGGER.debug("Replaying operation %s", serialize(op))
            await self.write_operation(op)

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
        if mgr.mode == SessionMode.EDIT and mgr.any_clients_connected():
            LOGGER.debug(
                "Refusing connection; a frontend is already connected."
            )
            if self.websocket.application_state is WebSocketState.CONNECTED:
                await self.websocket.close(
                    WebSocketCodes.ALREADY_CONNECTED,
                    "MARIMO_ALREADY_CONNECTED",
                )
            return

        async def get_session() -> Session:
            # 1. Handle reconnection

            # The session already exists, but it was disconnected.
            # This can happen in local development when the client
            # goes to sleep and wakes later. Just replace the session's
            # socket, but keep its kernel
            existing_session = mgr.get_session(session_id)
            if existing_session is not None:
                LOGGER.debug("Reconnecting session %s", session_id)
                await self._reconnect_session(existing_session, replay=False)
                return existing_session

            # 2. Handle resume

            # Get resumable possible resumable session
            resumable_session = mgr.maybe_resume_session(session_id)
            if resumable_session is not None:
                LOGGER.debug("Resuming session %s", session_id)
                await self._reconnect_session(resumable_session, replay=True)
                return resumable_session

            # 3. Create a new session

            # If the client refreshed their page, there will be one
            # existing session with a closed socket for a different session
            # id; that's why we call `close_all_sessions`.
            if mgr.mode == SessionMode.EDIT:
                mgr.close_all_sessions()

            # Grab the query params from the websocket
            # Note: if we resume a session, we don't pick up the new query
            # params, and instead use the query params from when the
            # session was created.
            query_params = QueryParams({}, NoopStream())
            for key, value in self.websocket.query_params.multi_items():
                if SESSION_QUERY_PARAM_KEY == key:
                    continue
                query_params.append(key, value)

            new_session = mgr.create_session(
                query_params=query_params.to_dict(),
                session_id=session_id,
                session_consumer=self,
            )
            self.status = ConnectionState.OPEN
            # Let the frontend know it can instantiate the app.
            await self._write_kernel_ready(
                new_session, resumed=False, ui_values={}, last_executed_code={}
            )
            return new_session

        await get_session()

        async def listen_for_messages() -> None:
            while True:
                (op, data) = await self.message_queue.get()
                await self.websocket.send_text(
                    json.dumps(
                        {
                            "op": op,
                            "data": data,
                        },
                        cls=WebComponentEncoder,
                    )
                )

        async def listen_for_disconnect() -> None:
            try:
                await self.websocket.receive_text()
            except WebSocketDisconnect as e:
                LOGGER.debug(
                    "Websocket disconnected for session %s with exception %s",
                    self.session_id,
                    str(e),
                )

                # Change the status
                self.status = ConnectionState.CLOSED
                # Disconnect the consumer
                session = self.manager.get_session(self.session_id)
                if session:
                    session.disconnect_consumer()

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
                            # wait until TTL is expired before canceling the
                            # listener task
                            listen_for_messages_task.cancel()
                            self.manager.close_session(self.session_id)

                    session = self.manager.get_session(self.session_id)
                    cancellation_handle = asyncio.get_event_loop().call_later(
                        Session.TTL_SECONDS, _close
                    )
                    if session is not None:
                        self.cancel_close_handle = cancellation_handle
                else:
                    # Stop listening for messages -- kernel will be torn down
                    listen_for_messages_task.cancel()

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
        check_alive: Callable[[], None],
    ) -> Callable[[KernelMessage], None]:
        # Start a heartbeat task
        async def _heartbeat() -> None:
            while True:
                await asyncio.sleep(1)
                check_alive()

        self.heartbeat_task = asyncio.create_task(_heartbeat())

        def listener(response: KernelMessage) -> None:
            self.message_queue.put_nowait(response)

        return listener

    async def write_operation(self, op: MessageOperation) -> None:
        await self.message_queue.put((op.name, serialize(op)))

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


# Catch all for serving static files
@router.get("/{path:path}")
async def serve_static(request: Request) -> FileResponse:
    path = request.path_params["path"]

    if any(
        re.match(pattern, path) for pattern in STATIC_FILES
    ) or path.startswith("assets"):
        return FileResponse(
            os.path.join(root, path),
            stat_result=os.stat(os.path.join(root, path)),
        )

    raise HTTPException(status_code=404, detail="Not Found!!")
