# Copyright 2026 Marimo. All rights reserved.
"""Mock streams for runtime tests.

`MockStream` inherits the production `ThreadSafe*` types so it slots into
anywhere a real stream is expected.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any, cast

from marimo._messaging.notification import (
    CellNotification,
    NotificationMessage,
)
from marimo._messaging.serde import deserialize_kernel_message
from marimo._messaging.streams import (
    ThreadSafeStderr,
    ThreadSafeStdin,
    ThreadSafeStdout,
    ThreadSafeStream,
)
from marimo._messaging.types import KernelMessage

if TYPE_CHECKING:
    from marimo._messaging.mimetypes import ConsoleMimeType


class MockStream(ThreadSafeStream):
    """Captures `KernelMessage`s written to it and exposes useful views."""

    def __init__(
        self,
        pipe: Any = None,
        input_queue: Any = None,
        redirect_console: bool = False,
        cell_id: Any = None,
    ) -> None:
        # Bypass `ThreadSafeStream.__init__`: no real pipe/input queue and
        # we don't want a buffered-console thread. Accept the same kwargs so
        # callers that clone via `type(stream)(pipe=..., ...)` keep working
        # (e.g. `marimo.Thread`).
        self.pipe = cast(Any, pipe)
        self.input_queue = cast(Any, input_queue)
        self.redirect_console = redirect_console
        self.cell_id = cell_id
        self.messages: list[KernelMessage] = []
        import threading

        self.stream_lock = threading.Lock()

    def write(self, data: KernelMessage) -> None:
        self.messages.append(data)
        deserialize_kernel_message(data)

    @property
    def raw_operations(self) -> list[dict[str, Any]]:
        return [json.loads(op) for op in self.messages]

    @property
    def operations(self) -> list[NotificationMessage]:
        return [deserialize_kernel_message(op) for op in self.messages]

    # Back-compat alias: tests/_messaging/mocks.py:MockStream exposed this name.
    parsed_operations = operations

    @property
    def cell_notifications(self) -> list[CellNotification]:
        return [
            op for op in self.operations if isinstance(op, CellNotification)
        ]


class MockStdout(ThreadSafeStdout):
    """Captures stdout writes as a list of strings."""

    def __init__(self, stream: MockStream) -> None:
        super().__init__(stream)
        self.messages: list[str] = []

    def _write_with_mimetype(
        self, data: str, mimetype: ConsoleMimeType
    ) -> int:
        del mimetype
        self.messages.append(data)
        return len(data)

    def __repr__(self) -> str:
        return "".join(self.messages)


class MockStderr(ThreadSafeStderr):
    """Captures stderr writes; `repr` strips HTML for plain-text comparison."""

    def __init__(self, stream: MockStream) -> None:
        super().__init__(stream)
        self.messages: list[str] = []

    def _write_with_mimetype(
        self, data: str, mimetype: ConsoleMimeType
    ) -> int:
        del mimetype
        self.messages.append(data)
        return len(data)

    def __repr__(self) -> str:
        return re.sub(r"<.*?>", "", "".join(self.messages))


class MockStdin(ThreadSafeStdin):
    """Echoes the prompt back so input() calls don't hang."""

    def __init__(self, stream: MockStream) -> None:
        super().__init__(stream)
        self.messages: list[str] = []

    def _readline_with_prompt(
        self, prompt: str = "", password: bool = False
    ) -> str:
        del password
        return prompt
