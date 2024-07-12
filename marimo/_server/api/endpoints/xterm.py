from __future__ import annotations

import asyncio
import os
import pty
import signal
import subprocess

from starlette.websockets import WebSocket, WebSocketDisconnect

from marimo import _loggers
from marimo._server.router import APIRouter

LOGGER = _loggers.marimo_logger()

router = APIRouter()


async def _read_from_pty(master: int, websocket: WebSocket) -> None:
    with os.fdopen(master, "rb", buffering=0) as master_file:
        while True:
            data = await asyncio.get_event_loop().run_in_executor(
                None, master_file.read, 1024
            )
            if data:
                LOGGER.warning("Sending: %s", data)
                try:
                    await websocket.send_text(data.decode())
                except WebSocketDisconnect:
                    return


async def _write_to_pty(master: int, websocket: WebSocket) -> None:
    with os.fdopen(master, "wb", buffering=0) as master_file:
        while True:
            try:
                data = await websocket.receive_text()
            except WebSocketDisconnect:
                return
            LOGGER.warning("Received: %s", data)
            master_file.write(data.encode())
            master_file.flush()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()

    child_pid, fd = pty.fork()
    if child_pid == 0:
        # this is the child process fork.
        # anything printed here will show up in the pty, including the output
        # of this subprocess
        default_shell = os.environ.get("SHELL", "/bin/bash")
        subprocess.run([default_shell], shell=True)  # noqa: ASYNC221
        return

    reader_task = asyncio.create_task(_read_from_pty(fd, websocket))
    writer_task = asyncio.create_task(_write_to_pty(fd, websocket))

    # future: Any | None = None
    try:
        await asyncio.gather(reader_task, writer_task)
        # await asyncio.wait(
        #     [reader_task, writer_task], return_when=asyncio.FIRST_EXCEPTION
        # )
        # await future
    except WebSocketDisconnect:
        LOGGER.warning("WebSocket disconnected")
    except Exception as e:
        LOGGER.exception(e)
    except asyncio.CancelledError:
        LOGGER.warning("asyncio cancelled")
    finally:
        LOGGER.warning("Closing pty master and slave")
        # if future is not None:
        #     future.cancel()
        await websocket.close()
        # kill pty process
        os.kill(child_pid, signal.SIGKILL)
        os.wait()  # noqa: ASYNC222
    LOGGER.warning("Pty master and slave closed")
