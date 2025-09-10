"""Standalone kernel server entry point for ZeroMQ-based IPC."""

from __future__ import annotations

import sys

from marimo._runtime import runtime
from marimo._zeromq.queue_manager import ZeroMqQueueManager
from marimo._zeromq.types import ConnectionInfo, LaunchKernelArgs


def main() -> None:
    """Launch a marimo kernel using ZeroMQ for IPC.

    This function is the entry point for the kernel subprocess. It reads
    connection information from stdin and sets up ZeroMQ queues that proxy
    to marimo's internal kernel.

    Typically, this entry point is invoked via the command line with:

        python -m marimo._zeromq.launch_kernel
    """
    info = ConnectionInfo.decode_json(sys.stdin.readline().strip())
    args = LaunchKernelArgs.decode_json(sys.stdin.readline().strip())

    queue_manager = ZeroMqQueueManager.connect(info)
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
        # Virtual files require a web server to serve file URLs. Since we're
        # not running one, content must be embedded as data URLs instead.
        virtual_files_supported=False,
        # NB: Unique parameter combination required for ZeroMQ. The `stream_queue`
        # and `socket_addr` are mutually exclusive. Normally RUN mode doesn't
        # redirect console, while EDIT mode does. Our ZeroMQ proxy needs both
        # `stream_queue` AND console redirection, but also other behavior of
        # EDIT, so we require this combination.
        stream_queue=queue_manager.stream_queue,
        socket_addr=None,
        is_edit_mode=True,
        redirect_console_to_browser=True,
    )


if __name__ == "__main__":
    main()
