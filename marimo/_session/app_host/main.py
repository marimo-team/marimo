# Copyright 2026 Marimo. All rights reserved.
"""The entry point for the app host process, which serves multiple clients.

Each app host manages kernel threads for a single notebook file (one thread per
client session).
"""

from __future__ import annotations

import dataclasses
import os
import pickle
import queue
import signal
import sys
import threading
import typing

from marimo import _loggers
from marimo._messaging.thread_local_streams import install_thread_local_proxies
from marimo._output.formatters.formatters import register_formatters
from marimo._runtime import runtime
from marimo._runtime.commands import StopKernelCommand
from marimo._runtime.parent_poller import start_parent_poller
from marimo._session.app_host.commands import (
    AppHostArgs,
    AppHostReadyResponse,
    Channel,
    CreateKernelCmd,
    KernelCreatedResponse,
    KernelExited,
    ShutdownAppHostCmd,
    StopKernelCmd,
    decode_mgmt_command,
    encode_mgmt_response,
)

LOGGER = _loggers.marimo_logger()


@dataclasses.dataclass
class _KernelQueues:
    control: queue.Queue[typing.Any]
    ui_element: queue.Queue[typing.Any]
    completion: queue.Queue[typing.Any]
    input: queue.Queue[typing.Any]


@dataclasses.dataclass
class _KernelInfo:
    thread: threading.Thread
    queues: _KernelQueues
    session_id: str


class _TaggedStreamQueue:
    """Queue that tags messages with session_id and puts in shared outbox.

    Passed to launch_kernel as stream_queue. The kernel calls put() to send
    output; messages are tagged with session_id and forwarded to the shared
    outbox queue, which a collector thread reads and sends over ZMQ.
    """

    def __init__(
        self, session_id: str, outbox: queue.Queue[typing.Any]
    ) -> None:
        self._session_id = session_id
        self._outbox = outbox

    def put(
        self,
        item: object,
        /,
        block: bool = True,
        timeout: float | None = None,
    ) -> None:
        self._outbox.put(
            (self._session_id, item), block=block, timeout=timeout
        )

    def put_nowait(self, item: object, /) -> None:
        self._outbox.put_nowait((self._session_id, item))

    def get(
        self, block: bool = True, timeout: float | None = None
    ) -> typing.Any:
        raise NotImplementedError("TaggedStreamQueue is write-only")

    def get_nowait(self) -> typing.Any:
        raise NotImplementedError("TaggedStreamQueue is write-only")

    def empty(self) -> bool:
        return True


def _handle_command(
    cmd_socket: typing.Any,
    kernels: dict[str, _KernelInfo],
) -> None:
    """Read one multiplexed command from ZMQ and route to the kernel queue."""
    frames = cmd_socket.recv_multipart()
    session_id = frames[0].decode()
    channel = Channel(frames[1])
    payload = pickle.loads(frames[2])

    info = kernels.get(session_id)
    if info is None:
        LOGGER.debug("Dropping command for unknown session %s", session_id)
        return

    if channel is Channel.CONTROL:
        info.queues.control.put(payload)
    elif channel is Channel.UI_ELEMENT:
        info.queues.ui_element.put(payload)
    elif channel is Channel.COMPLETION:
        info.queues.completion.put(payload)
    elif channel is Channel.INPUT:
        info.queues.input.put(payload)


def _stream_collector_loop(
    stream_outbox: queue.Queue[typing.Any],
    stream_socket: typing.Any,
) -> None:
    """Read tagged stream messages from outbox and send over ZMQ."""
    while True:
        item = stream_outbox.get()
        if item is None:
            break
        session_id, msg = item
        try:
            stream_socket.send_multipart(
                [session_id.encode(), pickle.dumps(msg)]
            )
        except Exception:
            LOGGER.exception(
                "Error sending stream message for session %s", session_id
            )


def _shutdown_all_kernels(
    kernels: dict[str, _KernelInfo],
) -> None:
    for info in kernels.values():
        try:
            info.queues.control.put(StopKernelCommand())
        except Exception:
            LOGGER.exception(
                "Error stopping kernel for session %s", info.session_id
            )
    kernels.clear()


def _handle_stop_kernel(
    cmd: StopKernelCmd,
    kernels: dict[str, _KernelInfo],
) -> None:
    info = kernels.pop(cmd.session_id, None)
    if info is not None:
        info.queues.control.put(StopKernelCommand())
        LOGGER.debug("Kernel stopped for session %s", cmd.session_id)


def _handle_create_kernel(
    cmd: CreateKernelCmd,
    kernels: dict[str, _KernelInfo],
    stream_outbox: queue.Queue[typing.Any],
    response_socket: typing.Any,
) -> None:
    try:
        command_queues = _KernelQueues(
            control=queue.Queue(),
            ui_element=queue.Queue(),
            completion=queue.Queue(),
            input=queue.Queue(maxsize=1),
        )
        stream_queue = _TaggedStreamQueue(cmd.session_id, stream_outbox)

        def launch_kernel_with_cleanup() -> None:
            try:
                runtime.launch_kernel(
                    control_queue=command_queues.control,
                    set_ui_element_queue=command_queues.ui_element,
                    completion_queue=command_queues.completion,
                    input_queue=command_queues.input,
                    stream_queue=stream_queue,
                    socket_addr=None,
                    is_edit_mode=False,
                    configs=cmd.configs,
                    app_metadata=cmd.app_metadata,
                    user_config=cmd.user_config,
                    virtual_file_storage=cmd.virtual_file_storage,
                    redirect_console_to_browser=cmd.redirect_console_to_browser,
                    interrupt_queue=None,
                    log_level=cmd.log_level,
                    is_ipc=False,
                )
            except Exception:
                LOGGER.exception(
                    "Kernel thread crashed for session %s", cmd.session_id
                )
            finally:
                stream_queue.put(KernelExited())

        thread = threading.Thread(
            target=launch_kernel_with_cleanup,
            daemon=True,
        )
        thread.start()

        kernels[cmd.session_id] = _KernelInfo(
            thread=thread,
            queues=command_queues,
            session_id=cmd.session_id,
        )

        response_socket.send(
            encode_mgmt_response(
                KernelCreatedResponse(session_id=cmd.session_id, success=True)
            )
        )
        LOGGER.debug("Kernel created for session %s", cmd.session_id)

    except Exception as e:
        LOGGER.exception(
            "Failed to create kernel for session %s", cmd.session_id
        )
        response_socket.send(
            encode_mgmt_response(
                KernelCreatedResponse(
                    session_id=cmd.session_id, success=False, error=str(e)
                )
            )
        )


def app_host_main(args: AppHostArgs) -> None:
    """App host main loop.

    Connects to the management ZMQ sockets and data channels, then processes
    management commands to create/stop kernel threads. Kernel commands and
    stream output flow through multiplexed data channels, not per-kernel
    ZMQ connections.
    """
    import zmq

    # Ignore SIGINT in app host processes. The main process handles Ctrl-C
    # and sends ShutdownAppHostCmd via the management channel.
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    if sys.platform != "win32":
        os.setsid()
        start_parent_poller(args.parent_pid)

    _loggers.set_level(args.log_level)
    LOGGER.debug(
        "App host started for %s (pid=%d)", args.file_path, os.getpid()
    )

    # Register formatters once, shared by all kernel threads in this app host.
    register_formatters()

    # Install thread-local stream proxies once at process startup, shared by
    # all kernel threads (not per-kernel).
    install_thread_local_proxies()

    context = zmq.Context()

    # Management channel
    mgmt_socket = context.socket(zmq.PULL)
    mgmt_socket.connect(args.mgmt_addr)
    response_socket = context.socket(zmq.PUSH)
    response_socket.connect(args.response_addr)

    # Multiplexed command and output channels
    cmd_socket = context.socket(zmq.PULL)
    cmd_socket.connect(args.cmd_addr)
    stream_socket = context.socket(zmq.PUSH)
    stream_socket.connect(args.stream_addr)

    # A separate thread collects outputs from kernels and forwards them to the
    # AppHost that started this process.
    stream_outbox: queue.Queue[typing.Any] = queue.Queue()
    collector_thread = threading.Thread(
        target=_stream_collector_loop,
        args=(stream_outbox, stream_socket),
        daemon=True,
    )
    collector_thread.start()
    response_socket.send(encode_mgmt_response(AppHostReadyResponse()))

    kernels: dict[str, _KernelInfo] = {}
    poller = zmq.Poller()
    poller.register(mgmt_socket, zmq.POLLIN)
    poller.register(cmd_socket, zmq.POLLIN)
    while True:
        events = dict(poller.poll())

        if cmd_socket in events:
            _handle_command(cmd_socket, kernels)

        if mgmt_socket in events:
            data = mgmt_socket.recv()
            cmd = decode_mgmt_command(data)

            if isinstance(cmd, CreateKernelCmd):
                _handle_create_kernel(
                    cmd, kernels, stream_outbox, response_socket
                )
            elif isinstance(cmd, StopKernelCmd):
                _handle_stop_kernel(cmd, kernels)
            elif isinstance(cmd, ShutdownAppHostCmd):
                LOGGER.debug("App host shutting down for %s", args.file_path)
                _shutdown_all_kernels(kernels)
                stream_outbox.put(None)  # Stop collector thread
                break
            else:
                LOGGER.warning(
                    "App host received unknown command: %s", type(cmd)
                )

    mgmt_socket.close(linger=0)
    response_socket.close(linger=0)
    cmd_socket.close(linger=0)
    stream_socket.close(linger=0)
    context.destroy(linger=0)


def main() -> None:
    # Read startup args with a timeout. If the parent process crashes before
    # closing stdin, read() would block forever.
    result: list[bytes] = []
    reader = threading.Thread(
        target=lambda: result.append(sys.stdin.buffer.read()),
        daemon=True,
    )
    reader.start()
    reader.join(timeout=30)
    if not result:
        sys.stderr.write(
            "Timed out reading startup args from parent process\n"
        )
        sys.exit(1)
    args = AppHostArgs.decode_json(result[0])
    app_host_main(args)


if __name__ == "__main__":
    main()
