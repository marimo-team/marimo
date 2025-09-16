# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import abc
import io
from typing import NewType, Optional

from marimo._messaging.mimetypes import ConsoleMimeType
from marimo._types.ids import CellId_t

# A KernelMessage is a bytes object that contains a serialized MessageOperation.
KernelMessage = NewType("KernelMessage", bytes)


class Stream(abc.ABC):
    """
    A stream is a class that can write messages from the kernel to
    some output.
    The `write` method is called by the kernel.
    """

    cell_id: Optional[CellId_t] = None

    @abc.abstractmethod
    def write(self, data: KernelMessage) -> None:
        pass

    def stop(self) -> None:
        """Tear down resources, if any."""
        return


class NoopStream(Stream):
    def write(self, data: KernelMessage) -> None:
        pass


# These streams are not stoppable by users (we don't implement stop).
class Stdout(io.TextIOBase):
    name = "stdout"

    @abc.abstractmethod
    def _write_with_mimetype(
        self, data: str, mimetype: ConsoleMimeType
    ) -> int:
        pass

    def write(self, __s: str) -> int:
        return self._write_with_mimetype(__s, mimetype="text/plain")

    def _stop(self) -> None:
        """Tear down resources, if any."""
        pass


class Stderr(io.TextIOBase):
    name = "stderr"

    @abc.abstractmethod
    def _write_with_mimetype(
        self, data: str, mimetype: ConsoleMimeType
    ) -> int:
        pass

    def write(self, __s: str) -> int:
        return self._write_with_mimetype(__s, mimetype="text/plain")

    def _stop(self) -> None:
        """Tear down resources, if any."""
        pass


class Stdin(io.TextIOBase):
    name = "stdin"

    def _stop(self) -> None:
        """Tear down resources, if any."""
        pass
