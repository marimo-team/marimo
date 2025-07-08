# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import os
import select
import signal
import subprocess

from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

from marimo import _loggers
from marimo._server.api.deps import AppState
from marimo._server.model import SessionMode
from marimo._server.router import APIRouter

LOGGER = _loggers.marimo_logger()

router = APIRouter()


async def _read_from_pty(master: int, websocket: WebSocket) -> None:
    loop = asyncio.get_running_loop()

    def on_data_received() -> None:
        try:
            data = os.read(master, 1024)
            if data:
                asyncio.create_task(websocket.send_text(data.decode()))
        except OSError as e:
            if e.errno == 9:  # Bad file descriptor
                LOGGER.debug("File descriptor closed, stopping read loop")
                loop.remove_reader(master)
            else:
                raise

    loop.add_reader(master, on_data_received)
    try:
        # Keep the task running until the websocket is closed
        while websocket.application_state != WebSocketState.DISCONNECTED:
            await asyncio.sleep(0.1)
    finally:
        loop.remove_reader(master)


async def _write_to_pty(master: int, websocket: WebSocket) -> None:
    try:
        buffer = ""
        with os.fdopen(master, "wb", buffering=0) as master_file:
            while True:
                try:
                    data = await websocket.receive_text()
                    LOGGER.debug("Received: %s", data)

                    buffer += data
                    if data in ["\r", "\n"]:  # Check for line ending
                        if buffer.strip().lower() == "exit":
                            LOGGER.debug(
                                "Exit command received, closing connection"
                            )
                            # End the connection
                            return
                        buffer = ""  # Reset buffer after processing a command

                    master_file.write(data.encode())
                    master_file.flush()
                except (asyncio.CancelledError, WebSocketDisconnect):
                    break
    except OSError as e:
        if e.errno == 9:  # Bad file descriptor
            LOGGER.debug("File descriptor closed, stopping write loop")
            return
        raise


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    app_state = AppState(websocket)
    if app_state.mode != SessionMode.EDIT:
        await websocket.close()
        return

    await websocket.accept()
    LOGGER.debug("Terminal websocket accepted")
    import pty

    child_pid, fd = pty.fork()
    if child_pid == 0:
        default_shell = os.environ.get("SHELL", "/bin/bash")
        subprocess.run([default_shell], shell=True)  # noqa: ASYNC221
        return

    reader_task = asyncio.create_task(_read_from_pty(fd, websocket))
    writer_task = asyncio.create_task(_write_to_pty(fd, websocket))

    try:
        _done, pending = await asyncio.wait(
            [reader_task, writer_task], return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
    except WebSocketDisconnect:
        pass
    except Exception as e:
        LOGGER.exception(e)
    finally:
        try:
            if websocket.application_state != WebSocketState.DISCONNECTED:
                await websocket.close()
        except RuntimeError:
            pass
        if reader_task and not reader_task.done():
            reader_task.cancel()
        if writer_task and not writer_task.done():
            writer_task.cancel()
        os.kill(child_pid, signal.SIGKILL)
        os.waitpid(child_pid, 0)  # noqa: ASYNC222
    LOGGER.debug("Terminal websocket closed")
