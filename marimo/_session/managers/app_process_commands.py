# Copyright 2026 Marimo. All rights reserved.
"""Commands for app process management channel.

These structs are serialized as JSON and sent over ZeroMQ between the main
process and app subprocesses.
"""

from __future__ import annotations

import typing

import msgspec
import msgspec.json

from marimo._ast.cell import CellConfig
from marimo._config.config import MarimoConfig
from marimo._ipc.types import ConnectionInfo
from marimo._runtime.commands import AppMetadata
from marimo._types.ids import CellId_t

# Commands (main -> app process)


class CreateKernelCmd(msgspec.Struct, tag=True):
    """Request the app process to create a new kernel thread."""

    session_id: str
    connection_info: ConnectionInfo
    configs: dict[CellId_t, CellConfig]
    app_metadata: AppMetadata
    user_config: MarimoConfig
    virtual_files_supported: bool
    redirect_console_to_browser: bool
    log_level: int


class StopKernelCmd(msgspec.Struct, tag=True):
    """Request the app process to stop a kernel thread."""

    session_id: str


class ShutdownAppProcessCmd(msgspec.Struct, tag=True):
    """Request the app process to shut down entirely."""


# Responses (app process -> main)


class KernelCreatedResponse(msgspec.Struct, tag=True):
    """Confirms a kernel was created (or reports failure)."""

    session_id: str
    success: bool
    error: typing.Union[str, None] = None


class KernelStoppedResponse(msgspec.Struct, tag=True):
    """Confirms a kernel was stopped."""

    session_id: str


# Union types for tagged deserialization
MgmtCommand = typing.Union[
    CreateKernelCmd, StopKernelCmd, ShutdownAppProcessCmd
]
MgmtResponse = typing.Union[KernelCreatedResponse, KernelStoppedResponse]

_cmd_encoder = msgspec.json.Encoder()
_cmd_decoder = msgspec.json.Decoder(MgmtCommand)
_resp_encoder = msgspec.json.Encoder()
_resp_decoder = msgspec.json.Decoder(MgmtResponse)


def encode_command(cmd: MgmtCommand) -> bytes:
    return _cmd_encoder.encode(cmd)


def decode_command(data: bytes) -> MgmtCommand:
    result: MgmtCommand = _cmd_decoder.decode(data)
    return result


def encode_response(resp: MgmtResponse) -> bytes:
    return _resp_encoder.encode(resp)


def decode_response(data: bytes) -> MgmtResponse:
    result: MgmtResponse = _resp_decoder.decode(data)
    return result
