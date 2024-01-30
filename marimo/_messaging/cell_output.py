# Copyright 2024 Marimo. All rights reserved.
"""Specification of a cell's visual output
"""


from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence, Union

from marimo._messaging.errors import Error
from marimo._messaging.mimetypes import KnownMimeType


class CellChannel(str, Enum):
    """The channel of a cell's output."""

    STDOUT = "stdout"
    STDERR = "stderr"
    STDIN = "stdin"
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
    data: Union[str, Sequence[Error]]
    timestamp: float = field(default_factory=lambda: time.time())

    @staticmethod
    def stdout(data: str) -> CellOutput:
        return CellOutput(
            channel=CellChannel.STDOUT, mimetype="text/plain", data=data
        )

    @staticmethod
    def stderr(data: str) -> CellOutput:
        return CellOutput(
            channel=CellChannel.STDERR, mimetype="text/plain", data=data
        )

    @staticmethod
    def stdin(data: str) -> CellOutput:
        return CellOutput(
            channel=CellChannel.STDIN, mimetype="text/plain", data=data
        )
