# Copyright 2026 Marimo. All rights reserved.
"""Standalone kernel server entry point for IPC (using ZeroMQ)."""

from __future__ import annotations

import sys

from marimo._ipc.queue_manager import QueueManager
from marimo._ipc.types import KernelArgs
from marimo._runtime import runtime


def main() -> None:
    """Launch a marimo kernel using ZeroMQ for IPC.

    This function is the entry point for the kernel subprocess. It reads
    connection information from stdin and sets up ZeroMQ queues that proxy
    to marimo's internal kernel.

    Typically, this entry point is invoked via the command line with:

        python -m marimo._ipc.launch_kernel

    IMPORTANT: The module path "marimo._ipc.launch_kernel" is a public API
    used by external consumers (e.g., marimo-lsp). Changing this path is a
    BREAKING CHANGE and should be done with care and proper deprecation.
    """
    args = KernelArgs.decode_json(sys.stdin.buffer.read())
    queue_manager = QueueManager.connect(args.connection_info)

    sys.stdout.write("KERNEL_READY\n")
    sys.stdout.flush()

    runtime.launch_kernel(
        set_ui_element_queue=queue_manager.set_ui_element_queue,
        interrupt_queue=queue_manager.win32_interrupt_queue,
        completion_queue=queue_manager.completion_queue,
        control_queue=queue_manager.control_queue,
        input_queue=queue_manager.input_queue,
        app_metadata=args.app_metadata,
        log_level=args.log_level,
        user_config=args.user_config,
        configs=args.configs,
        profile_path=args.profile_path,
        virtual_files_supported=args.virtual_files_supported,
        redirect_console_to_browser=args.redirect_console_to_browser,
        # NB: Unique parameter combination required for ZeroMQ. The `stream_queue`
        # and `socket_addr` are mutually exclusive. We use stream_queue for IPC
        # with edit mode behavior for interrupts.
        stream_queue=queue_manager.stream_queue,
        socket_addr=None,
        is_edit_mode=True,
    )


if __name__ == "__main__":
    main()
