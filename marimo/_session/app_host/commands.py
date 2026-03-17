# Copyright 2026 Marimo. All rights reserved.
"""Commands for the app host management channel."""

from __future__ import annotations

import typing

import msgspec
import msgspec.json

from marimo._ast.cell import CellConfig
from marimo._config.config import MarimoConfig
from marimo._runtime.commands import AppMetadata
from marimo._types.ids import CellId_t

# Channel names for multiplexed command routing.
# Shared between host.py (main process) and main.py (subprocess).
CHANNEL_CONTROL = "control"
CHANNEL_UI_ELEMENT = "ui_element"
CHANNEL_COMPLETION = "completion"
CHANNEL_INPUT = "input"


# Commands (main -> app host)
class CreateKernelCmd(msgspec.Struct, tag=True):
    """Request the app host to create a new kernel thread."""

    session_id: str
    configs: dict[CellId_t, CellConfig]
    app_metadata: AppMetadata
    user_config: MarimoConfig
    virtual_files_supported: bool
    redirect_console_to_browser: bool
    log_level: int


class StopKernelCmd(msgspec.Struct, tag=True):
    """Request the app host to stop a kernel thread."""

    session_id: str


class ShutdownAppHostCmd(msgspec.Struct, tag=True):
    """Request the app host to shut down entirely."""


# Responses (app host -> main)
class AppHostReadyResponse(msgspec.Struct, tag=True):
    """Signals that the app host has started and is ready."""


class KernelCreatedResponse(msgspec.Struct, tag=True):
    """Confirms a kernel was created (or reports failure)."""

    session_id: str
    success: bool
    error: str | None = None


# Sentinel sent on the stream channel when a kernel thread exits.
class KernelExited:
    """Signals that a kernel thread has exited (normally or via crash)."""


# Union types for tagged deserialization
MgmtCommand = typing.Union[CreateKernelCmd, StopKernelCmd, ShutdownAppHostCmd]
MgmtResponse = typing.Union[AppHostReadyResponse, KernelCreatedResponse]

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


class AppHostArgs(msgspec.Struct):
    """Args sent to the AppHost process."""

    mgmt_addr: str  # ZMQ PULL address for receiving management commands
    response_addr: str  # ZMQ PUSH address for sending management responses
    cmd_addr: str  # ZMQ PULL address for receiving kernel commands
    stream_addr: str  # ZMQ PUSH address for sending kernel output
    file_path: str
    log_level: int

    def encode_json(self) -> bytes:
        return msgspec.json.encode(self)

    @classmethod
    def decode_json(cls, buf: bytes) -> AppHostArgs:
        return msgspec.json.decode(buf, type=cls)
