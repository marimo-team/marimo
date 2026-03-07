# Copyright 2026 Marimo. All rights reserved.
"""Picklable commands for worker process management channel.

These dataclasses are sent over multiprocessing.Queue between the main
process and worker subprocesses.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from marimo._ast.cell import CellConfig
    from marimo._config.config import MarimoConfig
    from marimo._ipc.types import ConnectionInfo
    from marimo._runtime.commands import AppMetadata
    from marimo._types.ids import CellId_t


# Commands (main -> worker)


@dataclasses.dataclass
class CreateKernelCmd:
    """Request the worker to create a new kernel thread."""

    session_id: str
    connection_info: ConnectionInfo
    configs: dict[CellId_t, CellConfig]
    app_metadata: AppMetadata
    user_config: MarimoConfig
    virtual_files_supported: bool
    redirect_console_to_browser: bool
    log_level: int


@dataclasses.dataclass
class StopKernelCmd:
    """Request the worker to stop a kernel thread."""

    session_id: str


@dataclasses.dataclass
class ShutdownWorkerCmd:
    """Request the worker to shut down entirely."""


# Responses (worker -> main)


@dataclasses.dataclass
class KernelCreatedResponse:
    """Confirms a kernel was created (or reports failure)."""

    session_id: str
    success: bool
    error: Optional[str] = None


@dataclasses.dataclass
class KernelStoppedResponse:
    """Confirms a kernel was stopped."""

    session_id: str
