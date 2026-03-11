# Copyright 2026 Marimo. All rights reserved.
"""App process management for per-app process isolation.

AppProcess: wraps a subprocess.Popen for one notebook.
AppProcessPool: manages app processes keyed by absolute file path.
AppProcessQueueManager: queue manager for app process kernels.
AppKernelManager: implements KernelManager protocol for app-process-backed kernels.
"""

from __future__ import annotations

import os
import pickle
import queue
import subprocess
import sys
import threading
from typing import TYPE_CHECKING, TypeVar

from marimo import _loggers
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._messaging.types import KernelMessage
from marimo._runtime import commands
from marimo._session.managers.app_process_commands import (
    CHANNEL_COMPLETION,
    CHANNEL_CONTROL,
    CHANNEL_INPUT,
    CHANNEL_UI_ELEMENT,
    AppProcessReadyResponse,
    CreateKernelCmd,
    KernelCreatedResponse,
    KernelExited,
    ShutdownAppProcessCmd,
    StopKernelCmd,
    decode_response,
    encode_command,
)
from marimo._session.managers.app_process_entry import AppProcessArgs
from marimo._session.model import SessionMode
from marimo._session.queue import ProcessLike, QueueType
from marimo._session.types import (
    KernelManager,
    QueueManager as QueueManagerProto,
)

if TYPE_CHECKING:
    import zmq

    from marimo._ast.cell import CellConfig
    from marimo._config.config import MarimoConfig
    from marimo._config.manager import MarimoConfigReader
    from marimo._runtime.commands import AppMetadata
    from marimo._types.ids import CellId_t
    from marimo._utils.typed_connection import TypedConnection

LOGGER = _loggers.marimo_logger()

_RESPONSE_TIMEOUT = 30_000  # milliseconds
_BIND_ADDR = "tcp://127.0.0.1"


class AppProcess:
    """Wraps a subprocess.Popen for a single notebook file.

    Manages four ZeroMQ channels to the subprocess:
    - mgmt (PUSH): management commands (create/stop kernel, shutdown)
    - response (PULL): management responses
    - cmd (PUSH): kernel commands (control, UI, completion, input),
        multiplexed by client session
    - stream (PULL): kernel output, multiplexed by session
    """

    def __init__(self, file_path: str, python: str | None = None) -> None:
        self._file_path = file_path
        self._python = python or sys.executable
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
        # Tracks which sessions have a live kernel thread in the
        # subprocess. Set to True on create_kernel, set to False when
        # a KernelExited sentinel arrives from the subprocess.
        self._kernel_alive: dict[str, bool] = {}

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

        args = AppProcessArgs(
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
            "marimo._session.managers.app_process_entry",
        ]
        LOGGER.debug("Launching app process: %s", " ".join(cmd))

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
            raise RuntimeError("Failed to open stdin for app process")
        proc_stdin.write(args.encode_json())
        proc_stdin.flush()
        proc_stdin.close()

        # Wait for ready signal over the ZMQ response channel.
        _READY_TIMEOUT_MS = 30_000  # milliseconds
        if not response_socket.poll(timeout=_READY_TIMEOUT_MS):
            raise RuntimeError(
                f"App process timed out ({_READY_TIMEOUT_MS // 1000}s) "
                f"for {self._file_path}"
            )
        data = response_socket.recv()
        ready_response = decode_response(data)
        if not isinstance(ready_response, AppProcessReadyResponse):
            raise RuntimeError(
                f"Unexpected response during startup: "
                f"{type(ready_response)}"
            )

        stream_thread = threading.Thread(
            target=self._stream_receiver_loop, daemon=True
        )
        stream_thread.start()

        LOGGER.debug(
            "App process started for %s (pid=%s)",
            self._file_path,
            self._process.pid,
        )

    def _stream_receiver_loop(self) -> None:
        """Read stream messages from app process and route to sessions."""
        import zmq

        while True:
            try:
                if self._stream_socket is None:
                    break
                frames = self._stream_socket.recv_multipart()
                session_id = frames[0].decode()
                payload = pickle.loads(frames[1])
                if isinstance(payload, KernelExited):
                    self._kernel_alive[session_id] = False
                    LOGGER.debug(
                        "Kernel thread exited for session %s",
                        session_id,
                    )
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
        """Send a command to a kernel in the app process."""
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
            raise RuntimeError("App process not started")

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
                self._kernel_alive[session_id] = True
            return response
        raise TimeoutError(
            f"Timed out waiting for kernel creation in {self._file_path}"
        )

    def stop_kernel(self, session_id: str) -> None:
        if self._mgmt_socket is not None:
            self._mgmt_socket.send(
                encode_command(StopKernelCmd(session_id=session_id))
            )

    def is_kernel_alive(self, session_id: str) -> bool:
        """Check if a specific kernel thread is alive in this process."""
        return (
            self._kernel_alive.get(session_id, False)
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
                self._mgmt_socket.send(encode_command(ShutdownAppProcessCmd()))
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
        # AppProcessQueueManager / AppKernelManager instances that
        # still point to this (now-dead) AppProcess will silently
        # no-op instead of raising ZMQError on closed sockets.
        self._mgmt_socket = None
        self._response_socket = None
        self._cmd_socket = None
        self._stream_socket = None
        self._zmq_context = None

        LOGGER.debug("App process shut down for %s", self._file_path)


class AppProcessPool:
    """Manages app processes keyed by absolute file path.

    Each app is run in its own process to avoid collisions
    in sys.modules and other Python global data structures.
    """

    def __init__(self) -> None:
        self._workers: dict[str, AppProcess] = {}
        self._lock = threading.Lock()

    def get_or_create(self, file_path: str) -> AppProcess:
        abs_path = os.path.abspath(file_path)
        with self._lock:
            worker = self._workers.get(abs_path)
            if worker is not None and worker.is_alive():
                return worker

            # Dead process or no process — create a new one
            if worker is not None:
                LOGGER.warning(
                    "App process for %s was dead, respawning", abs_path
                )
                worker.shutdown()

            worker = AppProcess(abs_path)
            worker.start()
            self._workers[abs_path] = worker
            return worker

    def shutdown(self) -> None:
        with self._lock:
            for worker in self._workers.values():
                worker.shutdown()
            self._workers.clear()


_T = TypeVar("_T")


class _AppProcessPushQueue(QueueType[_T]):
    """Queue that sends commands over the multiplexed ZMQ channel.

    Satisfies QueueType protocol for the main-process side. Only put()
    is meaningful; get() raises NotImplementedError since this queue
    is write-only from the main process perspective.
    """

    def __init__(
        self, app_process: AppProcess, session_id: str, channel: str
    ) -> None:
        self._app_process = app_process
        self._session_id = session_id
        self._channel = channel

    def put(
        self,
        item: _T,
        /,
        block: bool = True,
        timeout: float | None = None,
    ) -> None:
        del block, timeout
        self._app_process.send_command(self._session_id, self._channel, item)

    def put_nowait(self, item: _T, /) -> None:
        self.put(item)

    def get(self, block: bool = True, timeout: float | None = None) -> _T:
        raise NotImplementedError("AppProcessPushQueue is write-only")

    def get_nowait(self) -> _T:
        raise NotImplementedError("AppProcessPushQueue is write-only")

    def empty(self) -> bool:
        return True


class AppProcessQueueManager(QueueManagerProto):
    """QueueManager for multiplexed app process communication.

    Commands are sent over a shared ZMQ channel (tagged with session_id
    and channel type). Stream output arrives via a per-session queue
    filled by the AppProcess stream receiver thread.
    """

    def __init__(self, app_process: AppProcess, session_id: str) -> None:
        self._app_process = app_process
        self._session_id = session_id

        # Channel names must match _CHANNEL_* constants in app_process_entry.py
        self.control_queue: QueueType[commands.CommandMessage] = (
            _AppProcessPushQueue(app_process, session_id, CHANNEL_CONTROL)
        )
        self.set_ui_element_queue: QueueType[commands.BatchableCommand] = (
            _AppProcessPushQueue(app_process, session_id, CHANNEL_UI_ELEMENT)
        )
        self.completion_queue: QueueType[commands.CodeCompletionCommand] = (
            _AppProcessPushQueue(app_process, session_id, CHANNEL_COMPLETION)
        )
        self.input_queue: QueueType[str] = _AppProcessPushQueue(
            app_process, session_id, CHANNEL_INPUT
        )
        self.win32_interrupt_queue: None = None

        self.stream_queue: queue.Queue[KernelMessage | None] = queue.Queue()
        app_process.register_stream(session_id, self.stream_queue)

    def put_control_request(self, request: commands.CommandMessage) -> None:
        # Completions are on their own queue
        if isinstance(request, commands.CodeCompletionCommand):
            self.completion_queue.put(request)
            return

        self.control_queue.put(request)
        # UI element updates and model commands are on both queues
        # so they can be batched
        if isinstance(
            request,
            (commands.UpdateUIElementCommand, commands.ModelCommand),
        ):
            self.set_ui_element_queue.put(request)

    def put_input(self, text: str) -> None:
        self.input_queue.put(text)

    def close_queues(self) -> None:
        self._app_process.unregister_stream(self._session_id)
        self.stream_queue.put(None)  # Signal QueueDistributor to stop


class _AppProcessLike(ProcessLike):
    """Makes AppProcess satisfy ProcessLike for kernel_task."""

    def __init__(self, app_process: AppProcess, session_id: str) -> None:
        self._app_process = app_process
        self._session_id = session_id

    @property
    def pid(self) -> int | None:
        return self._app_process.pid

    def is_alive(self) -> bool:
        return self._app_process.is_kernel_alive(self._session_id)

    def terminate(self) -> None:
        pass  # Don't terminate the shared app process from here

    def join(self, timeout: float | None = None) -> None:
        pass  # Don't join the shared app process from here


class AppKernelManager(KernelManager):
    """KernelManager backed by an app subprocess.

    The kernel runs as a thread inside the app process.
    Commands are sent over multiplexed ZMQ channels; no per-kernel
    ZMQ connections are created.
    """

    def __init__(
        self,
        *,
        app_process: AppProcess,
        session_id: str,
        queue_manager: QueueManagerProto,
        mode: SessionMode,
        configs: dict[CellId_t, CellConfig],
        app_metadata: AppMetadata,
        config_manager: MarimoConfigReader,
        redirect_console_to_browser: bool,
    ) -> None:
        self._app_process = app_process
        self._session_id = session_id
        self.queue_manager = queue_manager
        self.mode = mode
        self._configs = configs
        self._app_metadata = app_metadata
        self._config_manager = config_manager
        self._redirect_console_to_browser = redirect_console_to_browser

        self.kernel_task: ProcessLike | threading.Thread | None = None

    def start_kernel(self) -> None:
        response = self._app_process.create_kernel(
            session_id=self._session_id,
            configs=self._configs,
            app_metadata=self._app_metadata,
            user_config=self._config_manager.get_config(hide_secrets=False),
            virtual_files_supported=True,
            redirect_console_to_browser=self._redirect_console_to_browser,
            log_level=GLOBAL_SETTINGS.LOG_LEVEL,
        )

        if not response.success:
            raise RuntimeError(
                f"Failed to create kernel in app process: {response.error}"
            )

        self.kernel_task = _AppProcessLike(
            self._app_process, self._session_id
        )

    @property
    def pid(self) -> int | None:
        return self._app_process.pid

    @property
    def profile_path(self) -> str | None:
        return None

    def is_alive(self) -> bool:
        return self._app_process.is_kernel_alive(self._session_id)

    def interrupt_kernel(self) -> None:
        # Run-mode threads can't be interrupted
        pass

    def close_kernel(self) -> None:
        self.queue_manager.close_queues()
        # StopKernelCmd on the mgmt channel both sends StopKernelCommand
        # to the kernel's control queue and removes it from the kernel
        # registry in the subprocess.
        self._app_process.stop_kernel(self._session_id)

    @property
    def kernel_connection(self) -> TypedConnection[KernelMessage]:
        # App process kernels use stream_queue, not kernel_connection
        raise NotImplementedError(
            "App process kernel uses stream_queue, not kernel_connection"
        )
