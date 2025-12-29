# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import json
import os
import select
import signal
import struct
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Literal, TypedDict

from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

from marimo import _loggers
from marimo._server.api.deps import AppState
from marimo._server.router import APIRouter
from marimo._session.model import SessionMode

if TYPE_CHECKING:
    from collections.abc import Iterable

LOGGER = _loggers.marimo_logger()

router = APIRouter()


# Configuration constants
MAX_CHUNK_SIZE = 8192
MAX_BUFFER_SIZE = 65536
MAX_COMMAND_BUFFER_SIZE = 1024
KEEP_COMMAND_CHARS = 512
HEALTH_CHECK_INTERVAL = 5.0
READ_TIMEOUT = 0.05
IDLE_SLEEP = 0.01


def _resize_pty(fd: int, rows: int, cols: int) -> None:
    """Resize the PTY to the specified dimensions."""
    try:
        # Use TIOCSWINSZ ioctl to set window size
        import fcntl
        import termios

        # Format: struct winsize { unsigned short ws_row, ws_col, ws_xpixel, ws_ypixel }
        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)
        LOGGER.debug(f"PTY resized to {cols}x{rows}")
    except Exception as e:
        LOGGER.warning(f"Failed to resize PTY: {e}")


def _send_sigwinch(pid: int) -> None:
    """Send SIGWINCH signal to the child process to notify of terminal resize."""
    try:
        os.kill(pid, signal.SIGWINCH)
        LOGGER.debug(f"Sent SIGWINCH to process {pid}")
    except (OSError, ProcessLookupError) as e:
        LOGGER.debug(f"Failed to send SIGWINCH to {pid}: {e}")


def _create_shell_environment(
    cwd: str | None = None,
) -> tuple[str, dict[str, str]]:
    """Create a proper shell environment with working directory and env vars."""
    # Set working directory to a reasonable default
    if cwd is None:
        try:
            cwd = os.getcwd()
        except (OSError, PermissionError):
            try:
                cwd = str(Path.home())
            except Exception:
                cwd = "/tmp"

    # Set up environment variables
    env = os.environ.copy()
    env["TERM"] = "xterm-256color"
    env["LANG"] = env.get("LANG", "en_US.UTF-8")
    env["LC_ALL"] = env.get("LC_ALL", "en_US.UTF-8")

    # Determine shell
    default_shell = os.environ.get("SHELL")
    if not default_shell or not os.path.exists(default_shell):
        # Try common shells
        for shell in ["/bin/bash", "/bin/zsh", "/bin/sh"]:
            if os.path.exists(shell):
                default_shell = shell
                break
        else:
            default_shell = "/bin/sh"  # Fallback

    return default_shell, env


def _setup_child_process(shell: str, env: dict[str, str], cwd: str) -> None:
    """Set up the child process environment and start the shell."""
    try:
        os.chdir(cwd)
        os.execve(shell, [shell], env)
    except Exception as e:
        LOGGER.error(f"Failed to start shell: {e}")
        sys.exit(1)


def _create_process_cleanup_handler(
    child_pid: int, fd: int
) -> Callable[[], None]:
    """Create a cleanup handler for the child process and file descriptor."""

    def cleanup() -> None:
        try:
            # Try graceful termination first
            os.kill(child_pid, signal.SIGTERM)
            # Give the process a moment to terminate gracefully
            try:
                os.waitpid(child_pid, os.WNOHANG)
            except (OSError, ChildProcessError):
                pass
            # Force kill if still running
            try:
                os.kill(child_pid, signal.SIGKILL)
                os.waitpid(child_pid, 0)
            except (OSError, ProcessLookupError, ChildProcessError):
                pass
        except Exception as e:
            LOGGER.debug(f"Error during cleanup: {e}")

        # Close the pty file descriptor
        try:
            os.close(fd)
        except OSError:
            pass

    return cleanup


def _decode_pty_data(
    buffer: bytes, max_buffer_size: int = MAX_BUFFER_SIZE
) -> tuple[str, bytes]:
    """Decode PTY data handling partial UTF-8 sequences."""
    try:
        # Decode and send data, handling partial UTF-8 sequences
        text = buffer.decode("utf-8", errors="ignore")
        return text, b""
    except UnicodeDecodeError:
        # Keep buffer if we have incomplete UTF-8 sequence
        if len(buffer) > max_buffer_size:
            # Force send to prevent memory issues
            text = buffer.decode("utf-8", errors="replace")
            return text, b""
        return "", buffer


def _should_close_on_command(command_buffer: str, data: str) -> bool:
    """Check if the terminal should close based on the command."""
    if data in ["\r", "\n"]:
        return command_buffer.strip().lower() == "exit"
    return False


def _manage_command_buffer(
    buffer: str, data: str, max_size: int = MAX_COMMAND_BUFFER_SIZE
) -> str:
    """Manage the command buffer size to prevent memory issues."""
    buffer += data
    if len(buffer) > max_size:
        return buffer[-KEEP_COMMAND_CHARS:]  # Keep last chars
    return buffer


async def _read_from_pty(master: int, websocket: WebSocket) -> None:
    """Read data from PTY and send to websocket with proper buffering."""
    loop = asyncio.get_running_loop()
    buffer = b""

    try:
        with os.fdopen(master, "rb", buffering=0) as master_file:
            while True:
                try:
                    # Check for available data with a timeout
                    r, _, _ = await loop.run_in_executor(
                        None,
                        select.select,
                        [master_file],
                        [],
                        [],
                        READ_TIMEOUT,
                    )

                    if r:
                        # Read available data
                        try:
                            chunk = os.read(master, MAX_CHUNK_SIZE)
                            if not chunk:
                                break
                            buffer += chunk
                        except OSError as e:
                            if (
                                e.errno == 5
                            ):  # Input/output error (process died)
                                break
                            raise

                    # Send buffered data if we have any
                    if buffer:
                        text, buffer = _decode_pty_data(buffer)
                        if text:
                            await websocket.send_text(text)
                    else:
                        # Small delay to prevent busy-waiting when no data
                        await asyncio.sleep(IDLE_SLEEP)

                except (asyncio.CancelledError, WebSocketDisconnect):
                    break
    except OSError as e:
        if e.errno == 9:  # Bad file descriptor
            LOGGER.debug("File descriptor closed, stopping read loop")
            return
        raise  # Re-raise other OSErrors


class ResizeMessage(TypedDict):
    type: Literal["resize"]
    cols: int
    rows: int


async def _maybe_handle_resize(
    *, master: int, child_pid: int, message: str
) -> bool:
    """Handle resize messages from websocket."""

    try:
        parsed_message: ResizeMessage = json.loads(message)
        if (
            isinstance(parsed_message, dict)
            and parsed_message.get("type") == "resize"
        ):
            cols = parsed_message.get("cols")
            rows = parsed_message.get("rows")
            if (
                isinstance(cols, int)
                and isinstance(rows, int)
                and cols > 0
                and rows > 0
            ):
                _resize_pty(master, rows, cols)
                _send_sigwinch(child_pid)
                return True
            else:
                LOGGER.warning("Invalid resize message")
                return False
    except (json.JSONDecodeError, TypeError):
        # Not a JSON message, treat as regular terminal input
        pass

    return False


async def _write_to_pty(
    master: int, websocket: WebSocket, child_pid: int
) -> None:
    """Write data from websocket to PTY with command monitoring and resize handling."""
    try:
        command_buffer = ""
        with os.fdopen(master, "wb", buffering=0) as master_file:
            while True:
                try:
                    data = await websocket.receive_text()
                    LOGGER.debug("Received: %s", repr(data))

                    # Check if this is a resize message
                    if await _maybe_handle_resize(
                        master=master, child_pid=child_pid, message=data
                    ):
                        continue

                    # Handle special key combinations and commands
                    command_buffer = _manage_command_buffer(
                        command_buffer, data
                    )

                    # Check for exit command
                    if _should_close_on_command(command_buffer, data):
                        LOGGER.debug(
                            "Exit command received, closing connection"
                        )
                        return

                    # Reset buffer on line endings
                    if data in ["\r", "\n"]:
                        command_buffer = ""

                    # Write data to PTY
                    try:
                        encoded_data = data.encode("utf-8")
                        master_file.write(encoded_data)
                        master_file.flush()
                    except OSError as e:
                        if e.errno == 5:  # Input/output error (process died)
                            LOGGER.debug("Process died, stopping write loop")
                            break
                        raise

                except (asyncio.CancelledError, WebSocketDisconnect):
                    break
    except OSError as e:
        if e.errno == 9:  # Bad file descriptor
            LOGGER.debug("File descriptor closed, stopping write loop")
            return
        raise


async def _cancel_tasks(tasks: Iterable[asyncio.Task[Any]]) -> None:
    for task in tasks:
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    app_state = AppState(websocket)
    if app_state.mode != SessionMode.EDIT:
        await websocket.close(
            code=1008, reason="Terminal only available in edit mode"
        )
        return

    try:
        await websocket.accept()
        LOGGER.debug("Terminal websocket accepted")
    except Exception as e:
        LOGGER.error(f"Failed to accept websocket connection: {e}")
        return

    import pty

    child_pid, fd = pty.fork()
    if child_pid == 0:
        # Child process - set up the shell environment
        shell, env = _create_shell_environment()
        cwd = env.get("PWD", os.getcwd())
        _setup_child_process(shell, env, cwd)

    # Set up cleanup handler
    cleanup_child = _create_process_cleanup_handler(child_pid, fd)

    reader_task = asyncio.create_task(_read_from_pty(fd, websocket))
    writer_task = asyncio.create_task(_write_to_pty(fd, websocket, child_pid))

    try:
        _done, pending = await asyncio.wait(
            [reader_task, writer_task], return_when=asyncio.FIRST_COMPLETED
        )

        # Cancel all pending tasks
        await _cancel_tasks(pending)

    except WebSocketDisconnect:
        LOGGER.debug("Client disconnected from terminal")
    except Exception as e:
        LOGGER.exception(f"Terminal websocket error: {e}")
    finally:
        # Ensure all tasks are cleaned up
        await _cancel_tasks([reader_task, writer_task])

        # Close websocket if still connected
        try:
            if websocket.application_state != WebSocketState.DISCONNECTED:
                await websocket.close(
                    code=1000, reason="Terminal session ended"
                )
        except Exception as e:
            LOGGER.debug(f"Error closing websocket: {e}")

        # Clean up process and file descriptor
        cleanup_child()
    LOGGER.debug("Terminal websocket closed")
