# Copyright 2024 Marimo. All rights reserved.
import abc
import io
from typing import Any, Dict, Optional, Tuple

from marimo._ast.cell import CellId_t
from marimo._messaging.mimetypes import KnownMimeType

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


class NoopStream(Stream):
    def write(self, op: str, data: Dict[Any, Any]) -> None:
        pass


class Stdout(io.TextIOBase):
    name = "stdout"

    @abc.abstractmethod
    def _write_with_mimetype(self, data: str, mimetype: KnownMimeType) -> int:
        pass

    def write(self, __s: str) -> int:
        return self._write_with_mimetype(__s, mimetype="text/plain")


class Stderr(io.TextIOBase):
    name = "stderr"

    @abc.abstractmethod
    def _write_with_mimetype(self, data: str, mimetype: KnownMimeType) -> int:
        pass

    def write(self, __s: str) -> int:
        return self._write_with_mimetype(__s, mimetype="text/plain")


class Stdin(io.TextIOBase):
    name = "stdin"

    pass
