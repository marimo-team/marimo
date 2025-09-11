# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import msgspec
import msgspec.json

from marimo._ast.cell import CellConfig
from marimo._config.config import MarimoConfig
from marimo._messaging.msgspec_encoder import encode_json_bytes
from marimo._runtime.requests import AppMetadata
from marimo._types.ids import CellId_t


class ConnectionInfo(msgspec.Struct):
    """ZeroMQ socket connection info."""

    control: int
    ui_element: int
    completion: int
    win32_interrupt: int | None

    input: int
    stream: int


class KernelArgs(msgspec.Struct):
    """Args to send to the kernel."""

    configs: dict[CellId_t, CellConfig]
    app_metadata: AppMetadata
    user_config: MarimoConfig
    log_level: int
    profile_path: str | None

    connection_info: ConnectionInfo


def encode_kernel_args(args: KernelArgs) -> bytes:
    return encode_json_bytes(args)


def decode_kernel_args(buf: bytes) -> KernelArgs:
    return msgspec.json.decode(buf, type=KernelArgs)
