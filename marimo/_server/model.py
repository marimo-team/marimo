# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import abc
from enum import Enum
from typing import TYPE_CHECKING, Callable

from marimo._server.ids import ConsumerId

if TYPE_CHECKING:
    from marimo._messaging.ops import MessageOperation
    from marimo._messaging.types import KernelMessage


class ConnectionState(Enum):
    """Connection state for a session"""

    OPEN = 0
    CLOSED = 1
    ORPHANED = 2


class SessionMode(str, Enum):
    """Session mode for a session"""

    # read-write
    EDIT = "edit"
    # read-only
    RUN = "run"


class SessionConsumer(metaclass=abc.ABCMeta):
    """
    Consumer for a session

    This allows use to communicate with a session via different
    connection types. Currently we consume a session via WebSocket
    """

    def __init__(self, consumer_id: ConsumerId) -> None:
        self.consumer_id = consumer_id

    @abc.abstractmethod
    def on_start(
        self,
    ) -> Callable[[KernelMessage], None]:
        """
        Start the session consumer
        and return a subscription function for the session consumer
        """
        raise NotImplementedError

    @abc.abstractmethod
    def on_stop(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def write_operation(self, op: MessageOperation) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def connection_state(self) -> ConnectionState:
        raise NotImplementedError
