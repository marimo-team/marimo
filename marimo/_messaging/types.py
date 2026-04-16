# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import abc
import io
from typing import NewType

from marimo._messaging.mimetypes import ConsoleMimeType
from marimo._types.ids import CellId_t

# A KernelMessage is a bytes object that contains a serialized NotificationMessage.
KernelMessage = NewType("KernelMessage", bytes)


class Stream(abc.ABC):
    """
    A stream is a class that can write messages from the kernel to
    some output.
    The `write` method is called by the kernel.
    """

    cell_id: CellId_t | None = None

    @abc.abstractmethod
    def write(self, data: KernelMessage) -> None:
        pass

    def stop(self) -> None:
        """Tear down resources, if any."""
        return


class NoopStream(Stream):
    def write(self, data: KernelMessage) -> None:
        pass


def _ensure_plain_str(s: str) -> str:
    """Coerce str subclasses to plain ``str``.

    Some libraries (e.g. loguru) emit str subclasses whose ``__slots__``
    carry extra metadata (loguru's ``Message.record``).  When such an
    object reaches msgspec serialization the encoder may serialize the
    slots/attributes instead of the string value, corrupting console output.
    Converting to a bare ``str`` strips those attributes cheaply and is
    a no-op for regular strings (``type(s) is str`` fast-path).

    Raises TypeError for non-str inputs to preserve io.TextIOBase.write()
    semantics.
    """
    if type(s) is not str:
        if not isinstance(s, str):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError(  # pyright: ignore[reportUnreachable]
                f"write() argument must be a str, not {type(s).__name__}"
            )
        return str(s)
    return s


# These streams are not stoppable by users (we don't implement stop).
class Stdout(io.TextIOBase):
    name = "stdout"

    @abc.abstractmethod
    def _write_with_mimetype(
        self, data: str, mimetype: ConsoleMimeType
    ) -> int:
        pass

    def write(self, __s: str) -> int:
        return self._write_with_mimetype(
            _ensure_plain_str(__s), mimetype="text/plain"
        )

    def _stop(self) -> None:
        """Tear down resources, if any."""


class Stderr(io.TextIOBase):
    name = "stderr"

    @abc.abstractmethod
    def _write_with_mimetype(
        self, data: str, mimetype: ConsoleMimeType
    ) -> int:
        pass

    def write(self, __s: str) -> int:
        return self._write_with_mimetype(
            _ensure_plain_str(__s), mimetype="text/plain"
        )

    def _stop(self) -> None:
        """Tear down resources, if any."""


class Stdin(io.TextIOBase):
    name = "stdin"

    def _stop(self) -> None:
        """Tear down resources, if any."""
