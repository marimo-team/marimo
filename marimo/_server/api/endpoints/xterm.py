# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import fcntl
import os
import signal
import subprocess
import traceback
from asyncio import Queue
from typing import TYPE_CHECKING

from starlette.websockets import WebSocket, WebSocketDisconnect

from marimo import _loggers
from marimo._server.router import APIRouter

if TYPE_CHECKING:
    import io

LOGGER = _loggers.marimo_logger()

# TODO: Play with timeouts
INPUT_TIMEOUT = 0.1
OUTPUT_TIMEOUT = 0.1
EXIT_GRACE = 0.1

READ_QUEUE_BUFFER = 1

SHUTDOWN = 5
SIGINT_RETURN = 42

READ_TIMEOUT = 0.1 / READ_QUEUE_BUFFER

BLANK = f"\r{80 * ' '}\r"

# Command tokens
EOT = b"\x04"  # end of transmission (ctrl+d)
NAK = b"\x15"  # negative acknowledge (ctrl+u)
BACK = b"\x7f"  # backspace

router = APIRouter()


def set_non_blocking_flag(pipe: io.IOBase) -> None:
    flags = fcntl.fcntl(pipe, fcntl.F_GETFL)
    fcntl.fcntl(pipe, fcntl.F_SETFL, flags | os.O_NONBLOCK)


async def read_buffer(pipe: io.IOBase) -> bytes:
    return pipe.read()


async def extract_buffer(pipe: io.IOBase) -> bytes:
    buffer = b""
    # This loop might not be needed, playing with it, I thought it smoothed out
    # large reads, but it might have just been confirmation bias.
    for _reads in range(READ_QUEUE_BUFFER):
        try:
            if s := await asyncio.wait_for(
                read_buffer(pipe), timeout=READ_TIMEOUT
            ):
                buffer += s
        except IOError:
            break
    return buffer


class TerminalManager:
    _terminals: dict[WebSocket, tuple[Queue[bytes], asyncio.Task[None]]] = {}

    @classmethod
    def get_terminal(cls, websocket: WebSocket) -> asyncio.Task[None]:
        if websocket not in cls._terminals:
            produce_queue = Queue[bytes]()
            consume_queue = Queue[bytes]()

            cls._terminals[websocket] = (
                produce_queue,
                asyncio.create_task(
                    spawn_cmd_task(websocket, produce_queue, consume_queue)
                ),
            )
        return cls._terminals[websocket][1]

    @classmethod
    async def stop_terminal(cls, websocket: WebSocket) -> None:
        if websocket in cls._terminals:
            try:
                await websocket.close()
            except WebSocketDisconnect:
                pass
            produce_queue, task = cls._terminals.pop(websocket)
            await produce_queue.put(EOT)
            task.cancel()

    def __del__(self):
        for websocket in self._terminals:
            asyncio.create_task(self.stop_terminal(websocket))


# Note! The args are switched for consistent context!
async def background_shell(
    consume_queue: Queue[bytes], produce_queue: Queue[tuple[bytes, bytes]]
) -> None:
    """Function to produce and consume data."""
    # This might also work for windows if bash is installed. Also don't
    # hardcode /bin/bash, since not technically posix compliant. My initial
    # attempt to spawn a process failed, since I use fish. Defaulting to bash
    # is catch all for alternative shells.
    # NOTE on ignore: Attempted with asyncio.create_subprocess_shell, but the
    # lag was untenable. Another solution might be to do a pure multiprocessing
    # solution implementation.
    shell = subprocess.Popen(  # noqa: ASYNC101 ASYNC220
        ["bash", "-si"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
        shell=False,
    )
    set_non_blocking_flag(shell.stdout)
    set_non_blocking_flag(shell.stderr)
    set_non_blocking_flag(shell.stdin)
    LOGGER.debug("Created Shell")

    try:
        unanswered_heart_beats = 0
        # There might be a way to spin off a process group and still guarantee
        # that the thread will not hang- but this has the process listen for
        # SIGINT, and exit- to much the same effect.
        assert shell.stdin
        shell.stdin.write(
            bytes(
                f"trap 'exit {SIGINT_RETURN}' SIGINT {BLANK}" + "\n", "utf-8"
            )
        )
        shell.stdin.flush()

        # Unaswered heartbeats is a way to check if the process is still alive,
        # and hopefully mitigate hung processes.
        while unanswered_heart_beats < 3:
            # Check if exit code is SIGINT_RETURN and trigger SIGINT on the
            # main process.
            try:
                # Handle exit status
                if shell.poll() is not None:
                    if shell.poll() == SIGINT_RETURN:
                        # Propagate SIGINT to main process
                        os.kill(os.getpid(), signal.SIGINT)
                    break

                command = await asyncio.wait_for(
                    consume_queue.get(), timeout=INPUT_TIMEOUT
                )
                unanswered_heart_beats = 0
            except asyncio.TimeoutError:
                command = NAK
                unanswered_heart_beats += 1

            if command == EOT:
                LOGGER.debug("Received EOT")
                shell.stdin.write(bytes(";exit\n", "utf-8"))
                shell.stdin.flush()
                await asyncio.sleep(EXIT_GRACE)
                break

            if command == NAK or command is None:
                assert shell.stderr
                assert shell.stdout
                shell.stderr.flush()
                shell.stdout.flush()
            else:
                LOGGER.debug(f"command: {command}")
                shell.stdin.write(bytes(command + "\n", "utf-8"))
                shell.stdin.flush()

            stdout, stderr = await asyncio.gather(
                extract_buffer(shell.stdout), extract_buffer(shell.stderr)
            )
            if stdout or stderr:
                LOGGER.debug(f"stdout: {stdout}")
                LOGGER.debug(f"stderr: {stderr}")
                await produce_queue.put((stdout, stderr))
    except Exception as e:
        LOGGER.error(traceback.format_exc())
        await produce_queue.put((b"", bytes(f"{e}", "utf-8")))
    finally:
        try:
            LOGGER.error("Terminating shell")
            shell.terminate()
            shell.wait(timeout=SHUTDOWN)  # wait for process to terminate
            LOGGER.error("Graceful termination")
        except subprocess.TimeoutExpired:
            LOGGER.error("Forced termination")
            shell.kill()  # process did not terminate in time, kill it
            os.kill(shell.pid, signal.SIGTERM)  # Force terminate


async def spawn_cmd_task(
    websocket: WebSocket,
    consume_queue: Queue[tuple[bytes, bytes]],
    produce_queue: Queue[bytes],
) -> None:
    # Start the data producer/consumer process
    def create_shell() -> asyncio.Task[None]:
        produce_queue.empty()
        consume_queue.empty()
        return asyncio.create_task(
            background_shell(produce_queue, consume_queue)
        )

    process = create_shell()

    command_buffer = ""
    prompt = ""
    try:
        while True:
            if process.done():
                await websocket.send_text("Shell has died. Restarting...")
                process = create_shell()

            timeout = False
            try:
                command_buffer += await asyncio.wait_for(
                    websocket.receive_text(), timeout=INPUT_TIMEOUT
                )
            except asyncio.TimeoutError:
                # Check and flush the terminal process.
                timeout = True

            if EOT in bytes(command_buffer, "utf-8"):
                break

            # Handle backspace
            clear = ""
            if BACK in bytes(command_buffer, "utf-8"):
                breaks = bytes(command_buffer, "utf-8").split(BACK)
                head = breaks[0]
                for segment in breaks[1:]:
                    head = head[:-1] + segment
                command_buffer = head.decode("utf-8")
                clear = " " * (len(breaks) - 1)

            if "\r" in command_buffer:
                commands = command_buffer.split("\r")
                await asyncio.gather(
                    # Pass to process
                    produce_queue.put(commands[0]),
                    # Clear line
                    websocket.send_text(BLANK),
                )
                for command in commands[1:]:
                    await produce_queue.put(command)
                command_buffer = ""
            else:
                await produce_queue.put(NAK)
                await websocket.send_text(
                    f"{BLANK}{prompt} {command_buffer}{clear}"
                )
                # Don't continue, because we want to get the flushed output.
                if not timeout:
                    continue

            try:
                stdout, stderr = await asyncio.wait_for(
                    consume_queue.get(), timeout=INPUT_TIMEOUT
                )
            except asyncio.TimeoutError:
                continue

            if stderr and timeout:
                response = stderr.split(b"\n")
                prompt = response[-1].decode("utf-8").strip()
                stderr = b"\n".join(response[:-1])

            sends = []
            for response in [stdout, stderr]:
                if response:
                    # TODO: Potentially add a tag for stdout/stderr
                    # As is, the text is indistinguishable.
                    # This is a UI choice.
                    sends.append(
                        websocket.send_text(
                            response.decode("utf-8").replace("\n", "\r\n")
                        )
                    )
            await asyncio.gather(*sends)
    except WebSocketDisconnect:
        LOGGER.warning("Websocket disconnected")
    except Exception:
        LOGGER.error(traceback.format_exc())
    finally:
        LOGGER.warning("Terminating process")
        await produce_queue.put(EOT)
        # Wait for the producer/consumer process to finish
        try:
            await asyncio.wait_for(process, timeout=SHUTDOWN + 1)
        except asyncio.TimeoutError:
            process.cancel()
        # Check if websocket is still open
        try:
            await websocket.send_text(
                f"\r{(80 + len(prompt)) * ' '} Terminal destroyed\r"
            )
        except (WebSocketDisconnect, RuntimeError):
            pass


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    LOGGER.debug("Starting xterm Task")
    await websocket.accept()
    await TerminalManager.get_terminal(websocket)
