# Copyright 2026 Marimo. All rights reserved.
"""Shared test helpers for `tests/_runtime/` (and any test that needs a kernel)."""

from tests._runtime._helpers.factories import (
    default_app_metadata,
    default_user_config,
)
from tests._runtime._helpers.loop import LoopDriver
from tests._runtime._helpers.recorder import HookEvent, HookPhase, HookRecorder
from tests._runtime._helpers.session import TestKernel, mocked_kernel_session
from tests._runtime._helpers.streams import (
    MockStderr,
    MockStdin,
    MockStdout,
    MockStream,
)

__all__ = [
    "HookEvent",
    "HookPhase",
    "HookRecorder",
    "LoopDriver",
    "MockStderr",
    "MockStdin",
    "MockStdout",
    "MockStream",
    "TestKernel",
    "default_app_metadata",
    "default_user_config",
    "mocked_kernel_session",
]
