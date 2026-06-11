# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import abc
import dataclasses
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

    def flush_console(self) -> None:
        """Flush buffered console output, if any."""
        return

    def stop(self) -> None:
        """Tear down resources, if any."""
        return

    def copy_for_thread(self) -> Stream:
        raise RuntimeError("Unsupported stream type " + str(type(self)))


class NoopStream(Stream):
    def write(self, data: KernelMessage) -> None:
        pass

    def copy_for_thread(self) -> Stream:
        return NoopStream()


def _ensure_plain_str(s: str) -> str:
    """Coerce str subclasses to plain `str`.

    Some libraries (e.g. loguru) emit str subclasses whose `__slots__`
    carry extra metadata (loguru's `Message.record`).  When such an
    object reaches msgspec serialization the encoder may serialize the
    slots/attributes instead of the string value, corrupting console output.
    Converting to a bare `str` strips those attributes cheaply and is
    a no-op for regular strings (`type(s) is str` fast-path).

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
class Stdout(io.TextIOBase, abc.ABC):
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


class Stderr(io.TextIOBase, abc.ABC):
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


class Stdin(io.TextIOBase, abc.ABC):
    name = "stdin"

    @abc.abstractmethod
    def _readline_with_prompt(
        self, prompt: str = "", password: bool = False
    ) -> str:
        """Send a prompt to the frontend and return the user's bare response.

        Subclasses implement the transport. Returns the user-typed text
        without a trailing newline (matches Python's input() contract).
        """

    # `size` and `hint` are accepted for sys.stdin API compatibility but
    # ignored: marimo's stdin is a single-prompt pseudofile.

    def readline(self, size: int | None = -1) -> str:  # type: ignore[override]
        del size
        # Trailing "\n" is required so a blank submission doesn't look like
        # EOF to builtin input() (used by rich, click, getpass, pdb, etc.).
        return self._readline_with_prompt(prompt="") + "\n"

    def readlines(self, hint: int | None = -1) -> list[str]:  # type: ignore[override]
        del hint
        return [self.readline()]

    def _stop(self) -> None:
        """Tear down resources, if any."""


@dataclasses.dataclass(kw_only=True)
class KernelStreams:
    """The four I/O channels the kernel uses to communicate with the host."""

    stream: Stream
    stdout: Stdout | None
    stderr: Stderr | None
    stdin: Stdin | None
