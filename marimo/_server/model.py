# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Callable, Protocol

from marimo._types.ids import ConsumerId

if TYPE_CHECKING:
    from marimo._messaging.ops import MessageOperation
    from marimo._messaging.types import KernelMessage


class ConnectionState(Enum):
    """Connection state for a session"""

    CONNECTING = 0
    OPEN = 1
    CLOSED = 2
    ORPHANED = 3


class SessionMode(str, Enum):
    """Session mode for a session"""

    # read-write
    EDIT = "edit"
    # read-only
    RUN = "run"


class SessionConsumer(Protocol):
    """
    Consumer for a session

    This allows use to communicate with a session via different
    connection types. Currently we consume a session via WebSocket
    """

    @property
    def consumer_id(self) -> ConsumerId: ...

    def on_start(
        self,
    ) -> Callable[[KernelMessage], None]:
        """
        Start the session consumer
        and return a subscription function for the session consumer
        """
        ...

    def on_stop(self) -> None: ...

    def write_operation(self, op: MessageOperation) -> None: ...

    def connection_state(self) -> ConnectionState: ...
