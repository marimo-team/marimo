# Copyright 2024 Marimo. All rights reserved.
"""Protocol definitions for session management components.

These protocols define the public interfaces for all major session management
classes, enabling type checking, easier testing, and potential alternative
implementations.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any, Optional, Protocol, Union

from marimo._messaging.ops import MessageOperation
from marimo._messaging.types import KernelMessage
from marimo._runtime import requests
from marimo._server.model import ConnectionState, SessionConsumer, SessionMode
from marimo._server.notebook.file_manager import AppFileManager
from marimo._server.session.session_view import SessionView
from marimo._server.types import ProcessLike, QueueType
from marimo._types.ids import ConsumerId
from marimo._utils.typed_connection import TypedConnection

if TYPE_CHECKING:
    import threading
    from collections.abc import Mapping

    from marimo._config.manager import MarimoConfigManager


class QueueManager(Protocol):
    """Protocol for queue management."""

    control_queue: QueueType[requests.ControlRequest]
    set_ui_element_queue: QueueType[requests.SetUIElementValueRequest]
    completion_queue: QueueType[requests.CodeCompletionRequest]
    input_queue: QueueType[str]
    stream_queue: Optional[QueueType[Union[KernelMessage, None]]]
    win32_interrupt_queue: QueueType[bool] | None

    def close_queues(self) -> None:
        """Close all queues."""
        ...

    def put_control_request(self, request: requests.ControlRequest) -> None:
        """Put a control request in the control queue."""
        ...

    def put_completion_request(
        self, request: requests.CodeCompletionRequest
    ) -> None:
        """Put a code completion request in the completion queue."""
        ...

    def put_input(self, text: str) -> None:
        """Put an input() request in the input queue."""
        ...


class KernelManager(Protocol):
    """Protocol for kernel management."""

    kernel_task: Optional[Union[ProcessLike, threading.Thread]]
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


class Session(Protocol):
    """Protocol for session management."""

    initialization_id: str
    app_file_manager: AppFileManager
    config_manager: MarimoConfigManager
    ttl_seconds: int

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
        request: requests.ControlRequest,
        from_consumer_id: Optional[ConsumerId],
    ) -> None:
        """Put a control request in the control queue."""
        ...

    def put_completion_request(
        self, request: requests.CodeCompletionRequest
    ) -> None:
        """Put a code completion request in the completion queue."""
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

    def get_current_state(self) -> SessionView:
        """Return the current state of the session."""
        ...

    def connection_state(self) -> ConnectionState:
        """Return the connection state of the session."""
        ...

    def write_operation(
        self,
        operation: MessageOperation,
        from_consumer_id: Optional[ConsumerId],
    ) -> None:
        """Write an operation to the session consumer and the session view."""
        ...

    def instantiate(
        self,
        request: Any,
        *,
        http_request: Optional[requests.HTTPRequest],
    ) -> None:
        """Instantiate the app."""
        ...

    def close(self) -> None:
        """Close the session."""
        ...
