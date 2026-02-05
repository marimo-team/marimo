# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from collections.abc import Sequence

    from marimo._ast.cell import CellImpl
    from marimo._runtime.runner import cell_runner

__all__ = [
    "NotebookCellHooks",
    "Priority",
    "PreparationHook",
    "PreExecutionHook",
    "PostExecutionHook",
    "OnFinishHook",
    "create_default_hooks",
]

# Hook type aliases
PreparationHook = Callable[["cell_runner.Runner"], None]
PreExecutionHook = Callable[["CellImpl", "cell_runner.Runner"], None]
PostExecutionHook = Callable[
    ["CellImpl", "cell_runner.Runner", "cell_runner.RunResult"], None
]
OnFinishHook = Callable[["cell_runner.Runner"], None]


class Priority(IntEnum):
    """Hook execution priority (lower values run first)."""

    EARLY = 0
    NORMAL = 50
    LATE = 90
    FINAL = 100  # Reserved for status updates, cleanup


@dataclass
class _HookEntry:
    """Internal wrapper for a hook with its priority."""

    hook: Callable[..., None]
    priority: Priority = Priority.NORMAL


@dataclass
class NotebookCellHooks:
    """Container for cell execution hooks with priority-based ordering.

    Hook lifecycle:
    1. preparation_hooks: Run once before the runner starts
    2. pre_execution_hooks: Run before each cell executes
    3. post_execution_hooks: Run after each cell executes
    4. on_finish_hooks: Run once after all cells complete
    """

    _preparation: list[_HookEntry] = field(default_factory=list)
    _pre_execution: list[_HookEntry] = field(default_factory=list)
    _post_execution: list[_HookEntry] = field(default_factory=list)
    _on_finish: list[_HookEntry] = field(default_factory=list)

    def add_preparation(
        self, hook: PreparationHook, priority: Priority = Priority.NORMAL
    ) -> None:
        self._preparation.append(_HookEntry(hook, priority))

    def add_pre_execution(
        self, hook: PreExecutionHook, priority: Priority = Priority.NORMAL
    ) -> None:
        self._pre_execution.append(_HookEntry(hook, priority))

    def add_post_execution(
        self, hook: PostExecutionHook, priority: Priority = Priority.NORMAL
    ) -> None:
        self._post_execution.append(_HookEntry(hook, priority))

    def add_on_finish(
        self, hook: OnFinishHook, priority: Priority = Priority.NORMAL
    ) -> None:
        self._on_finish.append(_HookEntry(hook, priority))

    @property
    def preparation_hooks(self) -> Sequence[PreparationHook]:
        return [
            e.hook for e in sorted(self._preparation, key=lambda e: e.priority)
        ]

    @property
    def pre_execution_hooks(self) -> Sequence[PreExecutionHook]:
        return [
            e.hook
            for e in sorted(self._pre_execution, key=lambda e: e.priority)
        ]

    @property
    def post_execution_hooks(self) -> Sequence[PostExecutionHook]:
        return [
            e.hook
            for e in sorted(self._post_execution, key=lambda e: e.priority)
        ]

    @property
    def on_finish_hooks(self) -> Sequence[OnFinishHook]:
        return [
            e.hook for e in sorted(self._on_finish, key=lambda e: e.priority)
        ]

    def copy(self) -> NotebookCellHooks:
        return NotebookCellHooks(
            _preparation=self._preparation.copy(),
            _pre_execution=self._pre_execution.copy(),
            _post_execution=self._post_execution.copy(),
            _on_finish=self._on_finish.copy(),
        )


def create_default_hooks() -> NotebookCellHooks:
    """Create hooks with standard defaults.

    Returns a NotebookCellHooks instance with all standard hooks registered.
    Callers should add mode-specific hooks (e.g., render_toplevel_defs for
    edit mode, attempt_pytest for reactive tests) after calling this.
    """
    from marimo._runtime.runner.hooks_on_finish import (
        _send_cancellation_errors,
        _send_interrupt_errors,
    )
    from marimo._runtime.runner.hooks_post_execution import (
        POST_EXECUTION_HOOKS,
    )
    from marimo._runtime.runner.hooks_pre_execution import (
        PRE_EXECUTION_HOOKS,
    )
    from marimo._runtime.runner.hooks_preparation import (
        PREPARATION_HOOKS,
    )

    hooks = NotebookCellHooks()

    for prep_hook in PREPARATION_HOOKS:
        hooks.add_preparation(prep_hook)

    for pre_hook in PRE_EXECUTION_HOOKS:
        hooks.add_pre_execution(pre_hook)

    for post_hook in POST_EXECUTION_HOOKS:
        hooks.add_post_execution(post_hook)

    hooks.add_on_finish(_send_interrupt_errors)
    hooks.add_on_finish(_send_cancellation_errors)

    return hooks
