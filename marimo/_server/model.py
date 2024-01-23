# Copyright 2024 Marimo. All rights reserved.
import abc
from enum import Enum
from multiprocessing.connection import Connection
from typing import Any, Callable


class ConnectionState(Enum):
    """Connection state for a session"""

    OPEN = 0
    CLOSED = 1


class SessionMode(Enum):
    """Session mode for a session"""

    # read-write
    EDIT = 0
    # read-only
    RUN = 1


class SessionHandler(metaclass=abc.ABCMeta):
    """
    Handler for a session

    This allows use to communicate with a session via different
    connection types.
    """

    @abc.abstractmethod
    def on_start(
        self,
        connection: Connection,
        check_alive: Callable[[], None],
    ) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def on_stop(self, connection: Connection) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def write_operation(self, op: str, data: Any) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def connection_state(self) -> ConnectionState:
        raise NotImplementedError
