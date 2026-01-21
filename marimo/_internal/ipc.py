# Copyright 2026 Marimo. All rights reserved.
"""Internal API for inter-process communication (IPC)."""

from marimo._ipc.connection import Channel, Connection
from marimo._ipc.queue_manager import QueueManager
from marimo._ipc.types import ConnectionInfo, KernelArgs

__all__ = [
    "Channel",
    "Connection",
    "ConnectionInfo",
    "KernelArgs",
    "QueueManager",
]
