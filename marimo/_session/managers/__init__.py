# Copyright 2026 Marimo. All rights reserved.
"""Queue and Kernel managers for session management.

This module contains the infrastructure components for managing
kernel processes/threads and their associated communication queues.

Standard implementations (QueueManagerImpl, KernelManagerImpl):
    Use multiprocessing.Process for edit mode and threading.Thread for run mode.
    Communicate via multiprocessing or threading queues.

IPC implementations (IPCQueueManagerImpl, IPCKernelManagerImpl):
    Launch kernel as subprocess with ZeroMQ IPC.
    Each notebook gets its own sandboxed virtual environment.
"""

from marimo._session.managers.ipc import (
    IPCKernelManagerImpl,
    IPCQueueManagerImpl,
)
from marimo._session.managers.kernel import KernelManagerImpl
from marimo._session.managers.queue import QueueManagerImpl

__all__ = [
    "QueueManagerImpl",
    "KernelManagerImpl",
    "IPCQueueManagerImpl",
    "IPCKernelManagerImpl",
]
