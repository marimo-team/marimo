# Copyright 2026 Marimo. All rights reserved.
"""Shared test helpers for kernel-based tests."""

from tests._runtime._helpers.factories import default_app_metadata
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
    "mocked_kernel_session",
]
