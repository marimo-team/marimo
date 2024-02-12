# Copyright 2024 Marimo. All rights reserved.
import abc
from typing import Any, Dict, Optional, Tuple

from marimo._ast.cell import CellId_t

# The message from the kernel is a tuple of message type
# and a json representation of the message
KernelMessage = Tuple[str, Any]


class Stream(abc.ABC):
    """
    A stream is a class that can write messages from the kernel to
    some output.
    The `write` method is called by the kernel.
    """

    cell_id: Optional[CellId_t] = None

    @abc.abstractmethod
    def write(self, op: str, data: Dict[Any, Any]) -> None:
        pass


class Stdout:
    @abc.abstractmethod
    def start(self) -> None:
        pass

    @abc.abstractmethod
    def stop(self) -> None:
        pass

    @abc.abstractmethod
    def pause(self) -> None:
        pass

    @abc.abstractmethod
    def write(self, __s: str) -> int:
        pass


class Stderr:
    @abc.abstractmethod
    def start(self) -> None:
        pass

    @abc.abstractmethod
    def stop(self) -> None:
        pass

    @abc.abstractmethod
    def pause(self) -> None:
        pass

    @abc.abstractmethod
    def write(self, __s: str) -> int:
        pass


class Stdin:
    pass
