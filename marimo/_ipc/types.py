# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import msgspec
import msgspec.json

from marimo._ast.cell import CellConfig
from marimo._config.config import MarimoConfig
from marimo._messaging.msgspec_encoder import encode_json_bytes
from marimo._runtime.requests import AppMetadata
from marimo._types.ids import CellId_t


class LaunchKernelArgs(msgspec.Struct):
    """Args to send to the kernel."""

    configs: dict[CellId_t, CellConfig]
    app_metadata: AppMetadata
    user_config: MarimoConfig
    log_level: int
    profile_path: str | None

    def encode_json(self) -> bytes:
        """Encode kernel args as JSON."""
        return encode_json_bytes(self)

    @classmethod
    def decode_json(cls, buf: bytes | str) -> LaunchKernelArgs:
        """Encode kernel args as JSON."""
        return msgspec.json.decode(buf, type=cls)


class ConnectionInfo(msgspec.Struct):
    """ZeroMQ socket connection info."""

    control: int
    ui_element: int
    completion: int
    win32_interrupt: int | None

    input: int
    stream: int

    def encode_json(self) -> bytes:
        """Encode ConnectionInfo as JSON."""
        return encode_json_bytes(self)

    @classmethod
    def decode_json(cls, buf: bytes | str) -> ConnectionInfo:
        """Decode JSON connection info."""
        return msgspec.json.decode(buf, type=cls)
