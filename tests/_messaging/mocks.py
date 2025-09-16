from __future__ import annotations

from typing import Any, Optional

from marimo._messaging.mimetypes import ConsoleMimeType
from marimo._messaging.ops import CellOp, MessageOperation
from marimo._messaging.types import KernelMessage, Stderr, Stream
from marimo._utils.parse_dataclass import parse_raw


class MockStream(Stream):
    def __init__(self, stream: Optional[Stream] = None) -> None:
        self.messages: list[KernelMessage] = []

        if stream is not None and hasattr(stream, "messages"):
            self.messages = stream.messages

    def write(self, data: KernelMessage) -> None:
        self.messages.append(data)

    @property
    def operations(self) -> list[dict[str, Any]]:
        import json

        return [json.loads(op_data) for op_data in self.messages]

    @property
    def parsed_operations(self) -> list[MessageOperation]:
        return [
            parse_raw(op_data, MessageOperation) for op_data in self.messages
        ]

    @property
    def cell_ops(self) -> list[CellOp]:
        return [op for op in self.parsed_operations if isinstance(op, CellOp)]


class MockStderr(Stderr):
    def __init__(self, stream: Optional[Stderr] = None) -> None:
        self.messages: list[str] = []

        if stream is not None and hasattr(stream, "messages"):
            self.messages = stream.messages

    def _write_with_mimetype(
        self, data: str, mimetype: ConsoleMimeType
    ) -> int:
        del mimetype
        self.messages.append(data)
        return len(data)
