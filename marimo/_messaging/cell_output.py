# Copyright 2024 Marimo. All rights reserved.
"""Specification of a cell's visual output"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Union

from marimo._messaging.errors import Error
from marimo._messaging.mimetypes import ConsoleMimeType, KnownMimeType


class CellChannel(str, Enum):
    """The channel of a cell's output."""

    STDOUT = "stdout"
    STDERR = "stderr"
    STDIN = "stdin"
    PDB = "pdb"
    OUTPUT = "output"
    MARIMO_ERROR = "marimo-error"
    MEDIA = "media"

    def __repr__(self) -> str:
        return self.value


@dataclass
class CellOutput:
    # descriptive name about the kind of output: e.g., stdout, stderr, ...
    channel: CellChannel
    mimetype: KnownMimeType
    data: Union[str, list[Error], dict[str, Any]]
    timestamp: float = field(default_factory=lambda: time.time())

    def __repr__(self) -> str:
        return f"CellOutput(channel={self.channel}, mimetype={self.mimetype}, timestamp={self.timestamp})"

    def asdict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def stdout(
        data: str, mimetype: ConsoleMimeType = "text/plain"
    ) -> CellOutput:
        return CellOutput(
            channel=CellChannel.STDOUT,
            mimetype=mimetype,
            data=data,
        )

    @staticmethod
    def stderr(
        data: str, mimetype: ConsoleMimeType = "text/plain"
    ) -> CellOutput:
        return CellOutput(
            channel=CellChannel.STDERR,
            mimetype=mimetype,
            data=data,
        )

    @staticmethod
    def stdin(data: str) -> CellOutput:
        return CellOutput(
            channel=CellChannel.STDIN, mimetype="text/plain", data=data
        )

    @staticmethod
    def empty() -> CellOutput:
        return CellOutput(
            channel=CellChannel.OUTPUT,
            mimetype="text/plain",
            data="",
        )

    @staticmethod
    def errors(data: list[Error]) -> CellOutput:
        return CellOutput(
            channel=CellChannel.MARIMO_ERROR,
            mimetype="application/vnd.marimo+error",
            data=data,
        )
