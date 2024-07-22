from __future__ import annotations

import asyncio
import os
import select
import signal
import subprocess

from starlette.websockets import WebSocket, WebSocketDisconnect

from marimo import _loggers
from marimo._server.api.deps import AppState
from marimo._server.model import SessionMode
from marimo._server.router import APIRouter

LOGGER = _loggers.marimo_logger()

router = APIRouter()


async def _read_from_pty(master: int, websocket: WebSocket) -> None:
    loop = asyncio.get_running_loop()
    try:
        with os.fdopen(master, "rb", buffering=0) as master_file:
            while True:
                try:
                    r, _, _ = await loop.run_in_executor(
                        None, select.select, [master_file], [], [], 0.1
                    )
                    if not r:
                        await asyncio.sleep(0.1)  # Prevent busy-waiting
                        continue
                    data = os.read(master, 1024)
                    if not data:
                        break
                    await websocket.send_text(data.decode())
                except (asyncio.CancelledError, WebSocketDisconnect):
                    break
    except OSError as e:
        if e.errno == 9:  # Bad file descriptor
            LOGGER.debug("File descriptor closed, stopping read loop")
            return
        raise  # Re-raise other OSErrors


async def _write_to_pty(master: int, websocket: WebSocket) -> None:
    with os.fdopen(master, "wb", buffering=0) as master_file:
        while True:
            try:
                data = await websocket.receive_text()
                LOGGER.debug("Received: %s", data)
                master_file.write(data.encode())
                master_file.flush()
            except (asyncio.CancelledError, WebSocketDisconnect):
                break


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
        subprocess.run([default_shell], shell=True)  ## noqa: ASYNC221
        return

    reader_task = asyncio.create_task(_read_from_pty(fd, websocket))
    writer_task = asyncio.create_task(_write_to_pty(fd, websocket))

    try:
        await asyncio.gather(reader_task, writer_task)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.close()
        LOGGER.exception(e)
    finally:
        if reader_task and not reader_task.done():
            reader_task.cancel()
        if writer_task and not writer_task.done():
            writer_task.cancel()
        os.kill(child_pid, signal.SIGKILL)
        os.waitpid(child_pid, 0)  ## noqa: ASYNC222
    LOGGER.debug("Terminal websocket closed")
