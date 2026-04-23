# Copyright 2026 Marimo. All rights reserved.
"""A container for a single notebook supporting multiple client sessions."""

from __future__ import annotations

import pickle
import subprocess
import sys
import threading
from typing import TYPE_CHECKING, cast

from marimo import _loggers
from marimo._messaging.types import KernelMessage
from marimo._session.app_host.commands import (
    AppHostReadyResponse,
    Channel,
    CreateKernelCmd,
    KernelCreatedResponse,
    KernelExited,
    ShutdownAppHostCmd,
    StopKernelCmd,
    decode_mgmt_response,
    encode_mgmt_command,
)
from marimo._session.app_host.connection import AppHostConnection
from marimo._session.queue import ProcessLike
from marimo._utils.subprocess import try_kill_process_and_group

if TYPE_CHECKING:
    import queue
    from collections.abc import Callable

    from marimo._ast.cell import CellConfig
    from marimo._config.config import MarimoConfig
    from marimo._runtime.commands import AppMetadata
    from marimo._runtime.virtual_file import VirtualFileStorageType
    from marimo._types.ids import CellId_t

LOGGER = _loggers.marimo_logger()


class AppHost:
    """Encapsulates an app with multiple client sessions.

    The AppHost runs client kernels for a single app in a separate process,
    coordinating communication between the server and client sessions and
    multiplexing by session ID.

    Args:
        file_path: the notebook's absolute path, for debugging
        python: absolute path to the Python executable
        sandbox_dir: where to store the temporary venv if the notebook is sandboxed
        on_empty: callable invoked when the AppHost spins down to zero sessions
    """

    def __init__(
        self,
        file_path: str,
        python: str | None = None,
        sandbox_dir: str | None = None,
        on_empty: Callable[[], None] | None = None,
    ) -> None:
        self._file_path = file_path
        self._python = python or sys.executable
        self._sandbox_dir = sandbox_dir
        self._on_empty = on_empty

        # The process hosting client kernels.
        self._process: subprocess.Popen[bytes] | None = None
        self._conn: AppHostConnection | None = None

        # Set by shutdown(); checked by the stream receiver loop and
        # by send helpers to avoid operating on closed sockets.
        self._closed = threading.Event()

        # A map from each client session to a unique queue for its kernel's outputs
        # This map is protected by a lock, because a receiver thread drains its
        # outputs.
        self._stream_lock = threading.Lock()
        self._stream_receivers: dict[
            str, queue.Queue[KernelMessage | None]
        ] = {}

        # Serializes mgmt send and response recv so concurrent create_kernel
        # calls don't interleave on the shared ZMQ sockets.
        self._mgmt_lock = threading.Lock()

        # Session IDs are accessed on kernel creation but also on
        # session removal.
        self._session_lock = threading.Lock()
        self._session_ids: set[str] = set()

    def _fire_on_empty(self) -> bool:
        """If no sessions remain, fire _on_empty on a background thread."""
        callback = None
        with self._session_lock:
            if not self._session_ids:
                callback = self._on_empty
                self._on_empty = None
        if callback is not None:
            LOGGER.debug(
                "AppHost for %s has no active sessions, invoking cleanup",
                self._file_path,
            )
            # Run on a separate thread; calling shutdown directly
            # would close the ZMQ socket the caller may be reading.
            threading.Thread(target=callback, daemon=True).start()
            return True
        return False

    def _stream_receiver_loop(self) -> None:
        """Read stream messages from the app host and route to sessions."""
        import zmq

        conn = self._conn
        assert conn is not None  # start() sets _conn before this thread

        while not self._closed.is_set():
            try:
                # Poll with a timeout so we periodically re-check
                # _closed.  A blocking recv_multipart() would prevent
                # context.destroy() from completing.
                if not conn.stream.poll(timeout=1000):
                    # If the subprocess died, no more KernelExited
                    # sentinels will arrive.  Fire _on_empty so the
                    # pool can clean up this AppHost.
                    if not self.is_alive():
                        with self._session_lock:
                            self._session_ids.clear()
                        self._fire_on_empty()
                        break
                    continue

                frames = conn.stream.recv_multipart()
                session_id = frames[0].decode()
                payload = pickle.loads(frames[1])

                if isinstance(payload, KernelExited):
                    with self._session_lock:
                        self._session_ids.discard(session_id)
                        LOGGER.debug(
                            "Kernel thread exited for session %s",
                            session_id,
                        )
                    if self._fire_on_empty():
                        break
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

    def start(self) -> None:
        conn, args = AppHostConnection.create(self._file_path)
        self._conn = conn

        cmd = [
            self._python,
            "-m",
            "marimo._session.app_host.main",
        ]
        LOGGER.debug("Launching app host: %s", " ".join(cmd))

        # stdin is piped to send startup args; stdout/stderr inherit the
        # parent's file descriptors to make sure we don't interfere
        # with kernels' console outputs.
        self._process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
        )

        proc_stdin = self._process.stdin
        if proc_stdin is None:
            self.shutdown()
            raise RuntimeError("Failed to open stdin for app host")

        ready_timeout_ms = 30_000
        try:
            proc_stdin.write(args.encode_json())
            proc_stdin.flush()
            proc_stdin.close()
            if not conn.response.poll(timeout=ready_timeout_ms):
                raise RuntimeError(
                    f"App host timed out ({ready_timeout_ms // 1000}s) "
                    f"for {self._file_path}"
                )

            data = conn.response.recv()
            ready_response = decode_mgmt_response(data)
            if not isinstance(ready_response, AppHostReadyResponse):
                raise RuntimeError(
                    f"Unexpected response during startup: "
                    f"{type(ready_response)}"
                )
        except Exception:
            self.shutdown()
            raise

        stream_thread = threading.Thread(
            target=self._stream_receiver_loop, daemon=True
        )
        stream_thread.start()

        LOGGER.debug(
            "App host started for %s (pid=%s)",
            self._file_path,
            self._process.pid,
        )

    def send_command(
        self, session_id: str, channel: Channel, payload: object
    ) -> None:
        """Send a command to a kernel in the app host."""
        conn = self._conn
        if conn is None or self._closed.is_set():
            return
        try:
            conn.cmd.send_multipart(
                [
                    session_id.encode(),
                    channel.value,
                    pickle.dumps(payload),
                ]
            )
        except Exception:
            pass

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
        virtual_file_storage: VirtualFileStorageType | None,
        redirect_console_to_browser: bool,
        log_level: int,
    ) -> KernelCreatedResponse:
        conn = self._conn
        if conn is None or self._closed.is_set():
            raise RuntimeError("App host not started")

        cmd = CreateKernelCmd(
            session_id=session_id,
            configs=configs,
            app_metadata=app_metadata,
            user_config=user_config,
            virtual_file_storage=virtual_file_storage,
            redirect_console_to_browser=redirect_console_to_browser,
            log_level=log_level,
        )

        # Pre-register so _on_empty won't fire while we wait for the
        # response.  Also prevents a KernelExited that arrives before
        # the response from leaving a zombie entry (the discard will
        # find the id in the set).
        with self._session_lock:
            self._session_ids.add(session_id)

        # Serialize send+recv so concurrent create_kernel calls don't
        # interleave on the shared mgmt/response ZMQ sockets.
        try:
            with self._mgmt_lock:
                conn.mgmt.send(encode_mgmt_command(cmd))

                response_timeout_ms = 30_000
                if conn.response.poll(timeout=response_timeout_ms):
                    data = conn.response.recv()
                    response = decode_mgmt_response(data)
                    if not isinstance(response, KernelCreatedResponse):
                        raise RuntimeError(
                            f"Unexpected response type: {type(response)}"
                        )
                    if not response.success:
                        with self._session_lock:
                            self._session_ids.discard(session_id)
                    return response
                raise TimeoutError(
                    f"Timed out waiting for kernel creation "
                    f"in {self._file_path}"
                )
        except Exception:
            with self._session_lock:
                self._session_ids.discard(session_id)
            raise

    def stop_kernel(self, session_id: str) -> None:
        conn = self._conn
        if conn is None or self._closed.is_set():
            return
        try:
            conn.mgmt.send(
                encode_mgmt_command(StopKernelCmd(session_id=session_id))
            )
        except Exception:
            pass

    def has_active_session(self, session_id: str) -> bool:
        """Check if a specific kernel thread is alive in this host."""
        with self._session_lock:
            has_session = session_id in self._session_ids
        return (
            has_session
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

        if self._closed.is_set():
            return
        self._closed.set()

        # Signal all registered stream receivers to stop, so their
        # QueueDistributor threads don't hang waiting for messages.
        with self._stream_lock:
            for q in self._stream_receivers.values():
                try:
                    q.put(None)
                except Exception:
                    pass
            self._stream_receivers.clear()

        conn = self._conn
        if conn is not None:
            try:
                conn.mgmt.send(encode_mgmt_command(ShutdownAppHostCmd()))
            except zmq.ZMQError:
                pass

        if self._process is not None:
            try:
                try_kill_process_and_group(cast(ProcessLike, self._process))
            except ProcessLookupError:
                pass
            except Exception as e:
                LOGGER.warning(e)

        # Close all sockets (with linger=0).  This interrupts any
        # pending poll()/recv() in _stream_receiver_loop with ETERM,
        # causing it to exit cleanly.  send_command/stop_kernel/
        # create_kernel check _closed before touching sockets.
        if conn is not None:
            conn.close()

        if self._sandbox_dir is not None:
            from marimo._cli.sandbox import cleanup_sandbox_dir

            cleanup_sandbox_dir(self._sandbox_dir)
            self._sandbox_dir = None

        LOGGER.debug("App host shut down for %s", self._file_path)
