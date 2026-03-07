# Copyright 2026 Marimo. All rights reserved.
"""App process entry point for per-app process isolation.

This module is the target for multiprocessing.Process. Each app process
manages kernel threads for a single notebook file, providing OS-level
isolation of sys.modules between different apps.
"""

from __future__ import annotations

import dataclasses
import os
import queue
import signal
import threading
from typing import TYPE_CHECKING

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
)

if TYPE_CHECKING:
    from multiprocessing import Queue as MPQueue

LOGGER = _loggers.marimo_logger()


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
    cmd: object,
    kernels: dict[str, _KernelInfo],
    response_queue: MPQueue[object],
) -> None:
    assert isinstance(cmd, StopKernelCmd)
    info = kernels.pop(cmd.session_id, None)
    if info is not None:
        info.queue_manager.control_queue.put(StopKernelCommand())
        LOGGER.debug("Kernel stopped for session %s", cmd.session_id)
    response_queue.put(KernelStoppedResponse(session_id=cmd.session_id))


def _handle_create_kernel(
    cmd: CreateKernelCmd,
    kernels: dict[str, _KernelInfo],
    response_queue: MPQueue[object],
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

        response_queue.put(
            KernelCreatedResponse(session_id=cmd.session_id, success=True)
        )
        LOGGER.debug("Kernel created for session %s", cmd.session_id)

    except Exception as e:
        LOGGER.exception(
            "Failed to create kernel for session %s", cmd.session_id
        )
        response_queue.put(
            KernelCreatedResponse(
                session_id=cmd.session_id, success=False, error=str(e)
            )
        )


def app_process_main(
    mgmt_queue: MPQueue[object],
    response_queue: MPQueue[object],
    file_path: str,
    log_level: int,
) -> None:
    """App process main loop.

    Listens on mgmt_queue for management commands and starts/stops
    kernel threads as requested. Each kernel thread communicates with
    the main process via ZeroMQ channels.

    Args:
        mgmt_queue: Receives commands from the main process.
        response_queue: Sends responses back to the main process.
        file_path: The notebook file this app process serves.
        log_level: Log level for the app process.
    """
    # Ignore SIGINT in app processes — the main process handles Ctrl-C
    # and sends ShutdownAppProcessCmd via mgmt_queue for graceful teardown.
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    _loggers.set_level(log_level)
    LOGGER.debug("App process started for %s (pid=%d)", file_path, os.getpid())

    # Register formatters once, shared by all kernel threads in this app process.
    register_formatters()

    kernels: dict[str, _KernelInfo] = {}

    while True:
        try:
            cmd = mgmt_queue.get(timeout=1.0)
        except queue.Empty:
            continue

        if isinstance(cmd, CreateKernelCmd):
            _handle_create_kernel(cmd, kernels, response_queue)
        elif isinstance(cmd, StopKernelCmd):
            _handle_stop_kernel(cmd, kernels, response_queue)
        elif isinstance(cmd, ShutdownAppProcessCmd):
            LOGGER.debug("App process shutting down for %s", file_path)
            _shutdown_all_kernels(kernels)
            break
        else:
            LOGGER.warning(
                "App process received unknown command: %s", type(cmd)
            )
