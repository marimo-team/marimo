# Copyright 2026 Marimo. All rights reserved.
"""Protocol definitions for session management components.

These protocols define the public interfaces for all major session management
classes, enabling type checking, easier testing, and potential alternative
implementations.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    import asyncio
    import threading
    from collections.abc import Iterator, Mapping

    from marimo._config.manager import MarimoConfigManager
    from marimo._messaging.notebook.document import NotebookDocument
    from marimo._messaging.notification import NotificationMessage
    from marimo._messaging.types import KernelMessage
    from marimo._runtime import commands
    from marimo._session.consumer import SessionConsumer
    from marimo._session.extensions.types import SessionExtension
    from marimo._session.model import (
        ConnectionState,
        SessionMode,
    )
    from marimo._session.notebook.file_manager import AppFileManager
    from marimo._session.queue import ProcessLike, QueueType
    from marimo._session.state.session_view import SessionView
    from marimo._types.ids import ConsumerId
    from marimo._utils.typed_connection import TypedConnection


class QueueManager(Protocol):
    """Protocol for queue management."""

    control_queue: QueueType[commands.CommandMessage]
    set_ui_element_queue: QueueType[commands.BatchableCommand]
    completion_queue: QueueType[commands.CodeCompletionCommand]
    input_queue: QueueType[str]
    stream_queue: QueueType[KernelMessage | None] | None
    win32_interrupt_queue: QueueType[bool] | None

    def close_queues(self) -> None:
        """Close all queues."""
        ...

    def put_control_request(self, request: commands.CommandMessage) -> None:
        """Put a control request in the control queue."""
        ...

    def put_input(self, text: str) -> None:
        """Put an input() request in the input queue."""
        ...


class KernelManager(Protocol):
    """Protocol for kernel management."""

    kernel_task: ProcessLike | threading.Thread | None
    mode: SessionMode

    def start_kernel(self) -> None:
        """Start the kernel process or thread."""
        ...

    def is_alive(self) -> bool:
        """Check if the kernel is still running."""
        ...

    def interrupt_kernel(self) -> None:
        """Interrupt the running kernel."""
        ...

    def close_kernel(self) -> None:
        """Close the kernel and clean up resources."""
        ...

    @property
    def pid(self) -> int | None:
        """Get the PID of the kernel."""
        ...

    @property
    def kernel_connection(self) -> TypedConnection[KernelMessage]:
        """Get the kernel connection for reading messages."""
        ...

    @property
    def profile_path(self) -> str | None:
        """Get the profile path for the kernel."""
        ...


class KernelState(Enum):
    """Kernel state."""

    NOT_STARTED = "not_started"
    RUNNING = "running"
    STOPPED = "stopped"


@dataclass(frozen=True)
class KernelExitInfo:
    """Information about how a kernel exited.

    Populated after the kernel task has stopped. ``exitcode`` follows the
    convention of ``multiprocessing.Process.exitcode``: ``>= 0`` for a normal
    exit with that status, and ``< 0`` if the process was terminated by signal
    ``-exitcode``. ``None`` means the exit status is unavailable -- either the
    task has not yet terminated, or the underlying task type does not expose
    one (e.g. threads). ``cause`` is a short machine-readable tag and
    ``message`` is a human-readable one-liner suitable for logs or end-user
    display.
    """

    exitcode: int | None
    cause: str
    message: str


class Session(Protocol):
    """Protocol for session management."""

    initialization_id: str
    app_file_manager: AppFileManager
    config_manager: MarimoConfigManager
    session_view: SessionView
    ttl_seconds: int
    scratchpad_lock: asyncio.Lock

    @property
    def document(self) -> NotebookDocument:
        """The notebook document this session reflects."""
        ...

    @property
    def consumers(self) -> Mapping[SessionConsumer, ConsumerId]:
        """Get the consumers in the session."""
        ...

    def kernel_state(self) -> KernelState:
        """Get the state of the kernel."""
        ...

    def kernel_pid(self) -> int | None:
        """Get the PID of the kernel."""
        ...

    def kernel_exit_info(self) -> KernelExitInfo | None:
        """Describe how the kernel exited, or ``None`` if it is still running.

        Only meaningful once ``kernel_state() == KernelState.STOPPED``.
        """
        ...

    def try_interrupt(self) -> None:
        """Try to interrupt the kernel."""
        ...

    def flush_messages(self) -> None:
        """Flush any pending messages."""
        ...

    async def rename_path(self, new_path: str) -> None:
        """Rename the path of the session."""
        ...

    def put_control_request(
        self,
        request: commands.CommandMessage,
        from_consumer_id: ConsumerId | None,
    ) -> None:
        """Put a control request in the control queue."""
        ...

    def put_input(self, text: str) -> None:
        """Put an input() request in the input queue."""
        ...

    def disconnect_consumer(self, session_consumer: SessionConsumer) -> None:
        """Stop the session consumer but keep the kernel running."""
        ...

    def disconnect_main_consumer(self) -> None:
        """Disconnect the main session consumer if it connected."""
        ...

    def connect_consumer(
        self, session_consumer: SessionConsumer, *, main: bool
    ) -> None:
        """Connect or resume the session with a new consumer."""
        ...

    def connection_state(self) -> ConnectionState:
        """Return the connection state of the session."""
        ...

    def notify(
        self,
        operation: NotificationMessage | KernelMessage,
        from_consumer_id: ConsumerId | None,
    ) -> None:
        """Broadcast a notification to session consumers."""
        ...

    def instantiate(
        self,
        request: Any,
        *,
        http_request: commands.HTTPRequest | None,
    ) -> None:
        """Instantiate the app."""
        ...

    @contextlib.contextmanager
    def scoped(
        self,
        extension: SessionExtension,
    ) -> Iterator[SessionExtension]:
        """Attach an extension for the duration of the context."""
        ...

    def close(self) -> None:
        """Close the session."""
        ...
