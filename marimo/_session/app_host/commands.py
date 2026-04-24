# Copyright 2026 Marimo. All rights reserved.
"""Commands and responses."""

from __future__ import annotations

import enum
import typing

import msgspec
import msgspec.json

from marimo._ast.cell import CellConfig
from marimo._config.config import MarimoConfig
from marimo._runtime.commands import AppMetadata
from marimo._runtime.virtual_file import VirtualFileStorageType
from marimo._types.ids import CellId_t


# ---------------- Management commands ---------------------
class CreateKernelCmd(msgspec.Struct, tag=True):
    """Request the app host to create a new kernel thread."""

    session_id: str
    configs: dict[CellId_t, CellConfig]
    app_metadata: AppMetadata
    user_config: MarimoConfig
    virtual_file_storage: VirtualFileStorageType | None
    redirect_console_to_browser: bool
    log_level: int


class StopKernelCmd(msgspec.Struct, tag=True):
    """Request the app host to stop a kernel thread."""

    session_id: str


class ShutdownAppHostCmd(msgspec.Struct, tag=True):
    """Request the app host to shut down entirely."""


# ---------------- Management responses ---------------------
class AppHostReadyResponse(msgspec.Struct, tag=True):
    """Signals that the app host has started and is ready."""


class KernelCreatedResponse(msgspec.Struct, tag=True):
    """Confirms a kernel was created (or reports failure)."""

    session_id: str
    success: bool
    error: str | None = None


# ---------------- Management encoders and decoders ---------------------
MgmtCommand = typing.Union[CreateKernelCmd, StopKernelCmd, ShutdownAppHostCmd]
MgmtResponse = typing.Union[AppHostReadyResponse, KernelCreatedResponse]

_cmd_decoder = msgspec.json.Decoder(MgmtCommand)
_resp_decoder = msgspec.json.Decoder(MgmtResponse)


def encode_mgmt_command(cmd: MgmtCommand) -> bytes:
    return msgspec.json.encode(cmd)


def decode_mgmt_command(data: bytes) -> MgmtCommand:
    result: MgmtCommand = _cmd_decoder.decode(data)
    return result


def encode_mgmt_response(resp: MgmtResponse) -> bytes:
    return msgspec.json.encode(resp)


def decode_mgmt_response(data: bytes) -> MgmtResponse:
    result: MgmtResponse = _resp_decoder.decode(data)
    return result


# ---------------- AppHost initialization ----------------
class AppHostArgs(msgspec.Struct):
    """Args sent to the AppHost process."""

    # ZMQ PULL address for receiving management commands
    mgmt_addr: str
    # ZMQ PUSH address for sending management responses
    response_addr: str
    # ZMQ PULL address for receiving kernel commands
    cmd_addr: str
    # ZMQ PUSH address for sending kernel output
    stream_addr: str
    # Notebook file path, for debug logs
    file_path: str
    log_level: int
    parent_pid: int | None

    def encode_json(self) -> bytes:
        return msgspec.json.encode(self)

    @classmethod
    def decode_json(cls, buf: bytes) -> AppHostArgs:
        return msgspec.json.decode(buf, type=cls)


# ---------------- Kernel ----------------
class Channel(enum.Enum):
    """Command channels."""

    CONTROL = b"control"
    UI_ELEMENT = b"ui_element"
    COMPLETION = b"completion"
    INPUT = b"input"


# Sentinel sent on the stream channel when a kernel thread exits.
class KernelExited:
    """Signals that a kernel thread has exited."""
