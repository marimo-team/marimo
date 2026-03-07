# Copyright 2026 Marimo. All rights reserved.
"""App process entry point for per-app process isolation.

Launched via subprocess.Popen as:

    python -m marimo._session.managers.app_process_entry

Reads startup args (management channel ports, file path, log level) from
stdin as JSON, then enters a loop processing management commands over ZeroMQ.
Each app process manages kernel threads for a single notebook file, providing
OS-level isolation of sys.modules between different apps.
"""

from __future__ import annotations

import dataclasses
import os
import signal
import sys
import threading
import typing

import msgspec
import msgspec.json

from marimo import _loggers
from marimo._ipc.queue_manager import QueueManager
from marimo._messaging.thread_local_streams import install_thread_local_proxies
from marimo._output.formatters.formatters import register_formatters
from marimo._runtime import runtime
from marimo._runtime.commands import StopKernelCommand
from marimo._session.managers.app_process_commands import (
    CreateKernelCmd,
    KernelCreatedResponse,
    KernelStoppedResponse,
    ShutdownAppProcessCmd,
    StopKernelCmd,
    decode_command,
    encode_response,
)

LOGGER = _loggers.marimo_logger()


class AppProcessArgs(msgspec.Struct):
    """Startup args sent from main process via stdin."""

    mgmt_port: int  # ZMQ PULL port for receiving commands
    response_port: int  # ZMQ PUSH port for sending responses
    file_path: str
    log_level: int

    def encode_json(self) -> bytes:
        return msgspec.json.encode(self)

    @classmethod
    def decode_json(cls, buf: bytes) -> AppProcessArgs:
        return msgspec.json.decode(buf, type=cls)


@dataclasses.dataclass
class _KernelInfo:
    thread: threading.Thread
    queue_manager: QueueManager
    session_id: str


def _shutdown_all_kernels(kernels: dict[str, _KernelInfo]) -> None:
    for info in kernels.values():
        try:
            info.queue_manager.control_queue.put(StopKernelCommand())
        except Exception:
            LOGGER.exception(
                "Error stopping kernel for session %s", info.session_id
            )
    kernels.clear()


def _handle_stop_kernel(
    cmd: StopKernelCmd,
    kernels: dict[str, _KernelInfo],
    response_socket: typing.Any,
) -> None:
    info = kernels.pop(cmd.session_id, None)
    if info is not None:
        info.queue_manager.control_queue.put(StopKernelCommand())
        LOGGER.debug("Kernel stopped for session %s", cmd.session_id)
    response_socket.send(
        encode_response(KernelStoppedResponse(session_id=cmd.session_id))
    )


def _handle_create_kernel(
    cmd: CreateKernelCmd,
    kernels: dict[str, _KernelInfo],
    response_socket: typing.Any,
) -> None:
    try:
        # Connect to the ZeroMQ channels created by the main process
        qm = QueueManager.connect(cmd.connection_info)

        # Install thread-local proxies for console redirection
        if cmd.redirect_console_to_browser:
            install_thread_local_proxies()

        def launch_kernel_with_cleanup() -> None:
            try:
                runtime.launch_kernel(
                    control_queue=qm.control_queue,
                    set_ui_element_queue=qm.set_ui_element_queue,
                    completion_queue=qm.completion_queue,
                    input_queue=qm.input_queue,
                    stream_queue=qm.stream_queue,
                    socket_addr=None,
                    is_edit_mode=False,
                    configs=cmd.configs,
                    app_metadata=cmd.app_metadata,
                    user_config=cmd.user_config,
                    virtual_files_supported=cmd.virtual_files_supported,
                    redirect_console_to_browser=cmd.redirect_console_to_browser,
                    interrupt_queue=qm.win32_interrupt_queue,
                    log_level=cmd.log_level,
                    # Not IPC — this is a thread within an app process
                    is_ipc=False,
                )
            except Exception:
                LOGGER.exception(
                    "Kernel thread crashed for session %s", cmd.session_id
                )

        thread = threading.Thread(
            target=launch_kernel_with_cleanup,
            daemon=True,
        )
        thread.start()

        kernels[cmd.session_id] = _KernelInfo(
            thread=thread,
            queue_manager=qm,
            session_id=cmd.session_id,
        )

        response_socket.send(
            encode_response(
                KernelCreatedResponse(session_id=cmd.session_id, success=True)
            )
        )
        LOGGER.debug("Kernel created for session %s", cmd.session_id)

    except Exception as e:
        LOGGER.exception(
            "Failed to create kernel for session %s", cmd.session_id
        )
        response_socket.send(
            encode_response(
                KernelCreatedResponse(
                    session_id=cmd.session_id, success=False, error=str(e)
                )
            )
        )


def app_process_main(args: AppProcessArgs) -> None:
    """App process main loop.

    Connects to the management ZMQ sockets and processes commands
    to create/stop kernel threads.
    """
    import zmq

    # Ignore SIGINT in app processes — the main process handles Ctrl-C
    # and sends ShutdownAppProcessCmd via the management channel.
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    _loggers.set_level(args.log_level)
    LOGGER.debug(
        "App process started for %s (pid=%d)", args.file_path, os.getpid()
    )

    # Register formatters once, shared by all kernel threads in this app process.
    register_formatters()

    context = zmq.Context()
    mgmt_socket = context.socket(zmq.PULL)
    mgmt_socket.connect(f"tcp://127.0.0.1:{args.mgmt_port}")

    response_socket = context.socket(zmq.PUSH)
    response_socket.connect(f"tcp://127.0.0.1:{args.response_port}")

    kernels: dict[str, _KernelInfo] = {}
    poller = zmq.Poller()
    poller.register(mgmt_socket, zmq.POLLIN)

    while True:
        events = dict(poller.poll(timeout=1000))
        if mgmt_socket not in events:
            continue

        data = mgmt_socket.recv()
        cmd = decode_command(data)

        if isinstance(cmd, CreateKernelCmd):
            _handle_create_kernel(cmd, kernels, response_socket)
        elif isinstance(cmd, StopKernelCmd):
            _handle_stop_kernel(cmd, kernels, response_socket)
        elif isinstance(cmd, ShutdownAppProcessCmd):
            LOGGER.debug("App process shutting down for %s", args.file_path)
            _shutdown_all_kernels(kernels)
            break
        else:
            LOGGER.warning(
                "App process received unknown command: %s", type(cmd)
            )

    mgmt_socket.close(linger=0)
    response_socket.close(linger=0)
    context.destroy(linger=0)


def main() -> None:
    """Entry point when run as a module."""
    args = AppProcessArgs.decode_json(sys.stdin.buffer.read())
    sys.stdout.write("APP_PROCESS_READY\n")
    sys.stdout.flush()
    app_process_main(args)


if __name__ == "__main__":
    main()
