# Copyright 2026 Marimo. All rights reserved.
"""Session management for marimo server.

This module provides session management functionality including:
- Session lifecycle (creation, resumption, closure)
- Kernel management (process/thread management, interruption)
- Queue management (control, completion, input queues)
- Room management (broadcasting to multiple consumers)
- File change handling

All public APIs are re-exported from this module for backward compatibility.
"""

from __future__ import annotations

from marimo._session.types import (
    KernelManager,
    QueueManager,
    Session,
)
from marimo._session.utils import send_message_to_consumer

__all__ = [
    "Session",
    "KernelManager",
    "QueueManager",
    "send_message_to_consumer",
]
