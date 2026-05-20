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
    EvaluatorConfig,
    build_evaluator,
    resolve_executor,
)
from marimo._runtime.executor.executor import (
    DefaultExecutor,
    Executor,
)
from marimo._runtime.executor.lifecycles import (
    ExecutionLifecycle,
    Skip,
    get_lifecycle_class,
)
from marimo._runtime.executor.lifecycles.strict import StrictLifecycle

__all__ = [
    "_EXECUTOR_REGISTRY",
    "DefaultExecutor",
    "Evaluator",
    "EvaluatorConfig",
    "ExecutionLifecycle",
    "Executor",
    "Skip",
    "StrictLifecycle",
    "build_evaluator",
    "get_lifecycle_class",
    "resolve_executor",
]
