# Copyright 2026 Marimo. All rights reserved.
"""AppHost: wraps a subprocess for a single notebook file.

Manages four ZeroMQ channels to the subprocess:
- mgmt (PUSH): management commands (create/stop kernel, shutdown)
- response (PULL): management responses
- cmd (PUSH): kernel commands (control, UI, completion, input),
    multiplexed by client session
- stream (PULL): kernel output, multiplexed by session
"""

from __future__ import annotations

import pickle
import subprocess
import sys
import threading
from typing import TYPE_CHECKING

from marimo import _loggers
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._messaging.types import KernelMessage
from marimo._session.app_host.commands import (
    AppHostReadyResponse,
    CreateKernelCmd,
    KernelCreatedResponse,
    KernelExited,
    ShutdownAppHostCmd,
    StopKernelCmd,
    decode_response,
    encode_command,
)
from marimo._session.app_host.main import AppHostArgs

if TYPE_CHECKING:
    import queue
    from collections.abc import Callable

    import zmq

    from marimo._ast.cell import CellConfig
    from marimo._config.config import MarimoConfig
    from marimo._runtime.commands import AppMetadata
    from marimo._types.ids import CellId_t

LOGGER = _loggers.marimo_logger()

_RESPONSE_TIMEOUT = 30_000  # milliseconds
_BIND_ADDR = "tcp://127.0.0.1"


class AppHost:
    """Wraps a subprocess for a single notebook file.

    Manages four ZeroMQ channels to the subprocess:
    - mgmt (PUSH): management commands (create/stop kernel, shutdown)
    - response (PULL): management responses
    - cmd (PUSH): kernel commands (control, UI, completion, input),
        multiplexed by client session
    - stream (PULL): kernel output, multiplexed by session
    """

    def __init__(
        self,
        file_path: str,
        python: str | None = None,
        on_empty: Callable[[], None] | None = None,
    ) -> None:
        self._file_path = file_path
        self._python = python or sys.executable
        self._on_empty = on_empty
        self._process: subprocess.Popen[bytes] | None = None
        self._zmq_context: zmq.Context[zmq.Socket[bytes]] | None = None
        # Management commands and responses
        self._mgmt_socket: zmq.Socket[bytes] | None = None
        self._response_socket: zmq.Socket[bytes] | None = None
        # Multiplexed data channels
        self._cmd_socket: zmq.Socket[bytes] | None = None
        self._stream_socket: zmq.Socket[bytes] | None = None
        # Maps each client session to a unique queue for kernel outputs
        self._stream_receivers: dict[
            str, queue.Queue[KernelMessage | None]
        ] = {}
        # Protects the iterate-then-clear in shutdown() from racing
        # with the receiver loop's dict reads.
        self._stream_lock = threading.Lock()
        # Active session IDs with a live kernel thread in the subprocess.
        self._session_ids: set[str] = set()

    def start(self) -> None:
        import zmq

        context = zmq.Context()
        self._zmq_context = context

        mgmt_socket = context.socket(zmq.PUSH)
        mgmt_port = mgmt_socket.bind_to_random_port(_BIND_ADDR)
        self._mgmt_socket = mgmt_socket

        response_socket = context.socket(zmq.PULL)
        response_port = response_socket.bind_to_random_port(_BIND_ADDR)
        self._response_socket = response_socket

        cmd_socket = context.socket(zmq.PUSH)
        cmd_port = cmd_socket.bind_to_random_port(_BIND_ADDR)
        self._cmd_socket = cmd_socket

        stream_socket = context.socket(zmq.PULL)
        stream_port = stream_socket.bind_to_random_port(_BIND_ADDR)
        self._stream_socket = stream_socket

        args = AppHostArgs(
            mgmt_addr=f"{_BIND_ADDR}:{mgmt_port}",
            response_addr=f"{_BIND_ADDR}:{response_port}",
            cmd_addr=f"{_BIND_ADDR}:{cmd_port}",
            stream_addr=f"{_BIND_ADDR}:{stream_port}",
            file_path=self._file_path,
            log_level=GLOBAL_SETTINGS.LOG_LEVEL,
        )

        cmd = [
            self._python,
            "-m",
            "marimo._session.app_host.main",
        ]
        LOGGER.debug("Launching app host: %s", " ".join(cmd))

        # stdin is piped to send startup args; stdout/stderr inherit the
        # parent's fds so subprocess output (logging, print) appears in
        # the terminal — same as running without process isolation.
        self._process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
        )

        # Send startup args via stdin
        proc_stdin = self._process.stdin
        if proc_stdin is None:
            raise RuntimeError("Failed to open stdin for app host")
        proc_stdin.write(args.encode_json())
        proc_stdin.flush()
        proc_stdin.close()

        # Wait for ready signal over the ZMQ response channel.
        _READY_TIMEOUT_MS = 30_000  # milliseconds
        if not response_socket.poll(timeout=_READY_TIMEOUT_MS):
            raise RuntimeError(
                f"App host timed out ({_READY_TIMEOUT_MS // 1000}s) "
                f"for {self._file_path}"
            )
        data = response_socket.recv()
        ready_response = decode_response(data)
        if not isinstance(ready_response, AppHostReadyResponse):
            raise RuntimeError(
                f"Unexpected response during startup: {type(ready_response)}"
            )

        stream_thread = threading.Thread(
            target=self._stream_receiver_loop, daemon=True
        )
        stream_thread.start()

        LOGGER.debug(
            "App host started for %s (pid=%s)",
            self._file_path,
            self._process.pid,
        )

    def _stream_receiver_loop(self) -> None:
        """Read stream messages from app host and route to sessions."""
        import zmq

        while True:
            try:
                if self._stream_socket is None:
                    break
                frames = self._stream_socket.recv_multipart()
                session_id = frames[0].decode()
                payload = pickle.loads(frames[1])
                if isinstance(payload, KernelExited):
                    self._session_ids.discard(session_id)
                    LOGGER.debug(
                        "Kernel thread exited for session %s",
                        session_id,
                    )
                    if not self._session_ids:
                        # Grab and clear callback to prevent double-fire
                        callback = self._on_empty
                        self._on_empty = None
                        if callback is not None:
                            # Run on a separate thread — calling
                            # shutdown() here would close the ZMQ
                            # socket we're reading from.
                            threading.Thread(
                                target=callback, daemon=True
                            ).start()
                    continue
                with self._stream_lock:
                    q = self._stream_receivers.get(session_id)
                if q is not None:
                    q.put(payload)
                else:
                    LOGGER.debug(
                        "Dropping stream message for unknown session %s",
                        session_id,
                    )
            except zmq.ZMQError:
                break
            except Exception:
                LOGGER.warning("Error in stream receiver", exc_info=True)

    def send_command(
        self, session_id: str, channel: str, payload: object
    ) -> None:
        """Send a command to a kernel in the app host."""
        if self._cmd_socket is not None:
            self._cmd_socket.send_multipart(
                [
                    session_id.encode(),
                    channel.encode(),
                    pickle.dumps(payload),
                ]
            )

    def register_stream(
        self, session_id: str, q: queue.Queue[KernelMessage | None]
    ) -> None:
        """Register a stream queue to receive output for a session."""
        with self._stream_lock:
            self._stream_receivers[session_id] = q

    def unregister_stream(self, session_id: str) -> None:
        """Unregister a session's stream queue."""
        with self._stream_lock:
            self._stream_receivers.pop(session_id, None)

    def create_kernel(
        self,
        session_id: str,
        configs: dict[CellId_t, CellConfig],
        app_metadata: AppMetadata,
        user_config: MarimoConfig,
        virtual_files_supported: bool,
        redirect_console_to_browser: bool,
        log_level: int,
    ) -> KernelCreatedResponse:
        if self._mgmt_socket is None or self._response_socket is None:
            raise RuntimeError("App host not started")

        cmd = CreateKernelCmd(
            session_id=session_id,
            configs=configs,
            app_metadata=app_metadata,
            user_config=user_config,
            virtual_files_supported=virtual_files_supported,
            redirect_console_to_browser=redirect_console_to_browser,
            log_level=log_level,
        )
        self._mgmt_socket.send(encode_command(cmd))

        if self._response_socket.poll(timeout=_RESPONSE_TIMEOUT):
            data = self._response_socket.recv()
            response = decode_response(data)
            if not isinstance(response, KernelCreatedResponse):
                raise RuntimeError(
                    f"Unexpected response type: {type(response)}"
                )
            if response.success:
                self._session_ids.add(session_id)
            return response
        raise TimeoutError(
            f"Timed out waiting for kernel creation in {self._file_path}"
        )

    def stop_kernel(self, session_id: str) -> None:
        if self._mgmt_socket is not None:
            self._mgmt_socket.send(
                encode_command(StopKernelCmd(session_id=session_id))
            )

    def is_session_ids(self, session_id: str) -> bool:
        """Check if a specific kernel thread is alive in this host."""
        return (
            session_id in self._session_ids
            and self._process is not None
            and self._process.poll() is None
        )

    def is_alive(self) -> bool:
        return self._process is not None and self._process.poll() is None

    @property
    def pid(self) -> int | None:
        return self._process.pid if self._process else None

    def shutdown(self) -> None:
        import zmq

        # Signal all registered stream receivers to stop, so their
        # QueueDistributor threads don't hang waiting for messages.
        with self._stream_lock:
            for q in self._stream_receivers.values():
                try:
                    q.put(None)
                except Exception:
                    pass
            self._stream_receivers.clear()

        if self._mgmt_socket is not None:
            try:
                self._mgmt_socket.send(encode_command(ShutdownAppHostCmd()))
            except zmq.ZMQError:
                pass

        if self._process is not None:
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.terminate()
                try:
                    self._process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self._process.kill()

        if self._mgmt_socket is not None:
            self._mgmt_socket.close(linger=0)
        if self._response_socket is not None:
            self._response_socket.close(linger=0)
        if self._cmd_socket is not None:
            self._cmd_socket.close(linger=0)
        if self._stream_socket is not None:
            self._stream_socket.close(linger=0)
        if self._zmq_context is not None:
            self._zmq_context.destroy(linger=0)

        # Null out sockets so that any stale references from
        # AppHostQueueManager / AppHostKernelManager instances that
        # still point to this (now-dead) AppHost will silently
        # no-op instead of raising ZMQError on closed sockets.
        self._mgmt_socket = None
        self._response_socket = None
        self._cmd_socket = None
        self._stream_socket = None
        self._zmq_context = None

        LOGGER.debug("App host shut down for %s", self._file_path)
