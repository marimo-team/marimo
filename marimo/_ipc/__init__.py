# Copyright 2025 Marimo. All rights reserved.
"""Experimental IPC implementation (using ZeroMQ)."""

from marimo._ipc.queue_manager import QueueManager
from marimo._ipc.types import encode_kernel_args

__all__ = [
    "encode_kernel_args",
    "QueueManager",
]
