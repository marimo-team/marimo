# Copyright 2026 Marimo. All rights reserved.
"""Cell execution runtime.

ExecutionLifecycle: Manages global information prior to execution
Executor: Runs the execution
Evaluator: Composes lifecycles and the executor.
"""

from __future__ import annotations

from marimo._runtime.executor.evaluator import (
    _EXECUTOR_REGISTRY,
    Evaluator,
    resolve_executor,
)
from marimo._runtime.executor.executor import (
    DefaultExecutor,
    Executor,
)
from marimo._runtime.executor.lifecycles import (
    ExecutionLifecycle,
    Skip,
)
from marimo._runtime.executor.lifecycles.debugger import DebuggerLifecycle
from marimo._runtime.executor.lifecycles.strict import StrictLifecycle

__all__ = [
    "_EXECUTOR_REGISTRY",
    "DebuggerLifecycle",
    "DefaultExecutor",
    "Evaluator",
    "ExecutionLifecycle",
    "Executor",
    "Skip",
    "StrictLifecycle",
    "resolve_executor",
]
