# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from collections.abc import Sequence

    from marimo._ast.cell import CellImpl
    from marimo._runtime.runner import cell_runner
    from marimo._runtime.runner.hook_context import (
        OnFinishHookContext,
        PostExecutionHookContext,
        PreExecutionHookContext,
        PreparationHookContext,
    )

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
PreparationHook = Callable[["PreparationHookContext"], None]
PreExecutionHook = Callable[["CellImpl", "PreExecutionHookContext"], None]
PostExecutionHook = Callable[
    ["CellImpl", "PostExecutionHookContext", "cell_runner.RunResult"], None
]
OnFinishHook = Callable[["OnFinishHookContext"], None]


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
class _HookList:
    """A list of hook entries with cached priority-sorted access."""

    _entries: list[_HookEntry] = field(default_factory=list)
    _sorted: list[Callable[..., None]] | None = field(
        default=None, init=False, repr=False
    )

    def add(self, hook: Callable[..., None], priority: Priority) -> None:
        self._entries.append(_HookEntry(hook, priority))
        self._sorted = None

    @property
    def sorted_hooks(self) -> Sequence[Callable[..., None]]:
        if self._sorted is None:
            self._sorted = [
                e.hook for e in sorted(self._entries, key=lambda e: e.priority)
            ]
        return self._sorted

    def copy(self) -> _HookList:
        return _HookList(self._entries.copy())


class NotebookCellHooks:
    """Container for cell execution hooks with priority-based ordering.

    Hook lifecycle:
    1. preparation_hooks: Run once before the runner starts
    2. pre_execution_hooks: Run before each cell executes
    3. post_execution_hooks: Run after each cell executes
    4. on_finish_hooks: Run once after all cells complete
    """

    def __init__(
        self,
        _preparation: _HookList | None = None,
        _pre_execution: _HookList | None = None,
        _post_execution: _HookList | None = None,
        _on_finish: _HookList | None = None,
    ) -> None:
        self._preparation = _preparation or _HookList()
        self._pre_execution = _pre_execution or _HookList()
        self._post_execution = _post_execution or _HookList()
        self._on_finish = _on_finish or _HookList()

    def add_preparation(
        self, hook: PreparationHook, priority: Priority = Priority.NORMAL
    ) -> None:
        self._preparation.add(hook, priority)

    def add_pre_execution(
        self, hook: PreExecutionHook, priority: Priority = Priority.NORMAL
    ) -> None:
        self._pre_execution.add(hook, priority)

    def add_post_execution(
        self, hook: PostExecutionHook, priority: Priority = Priority.NORMAL
    ) -> None:
        self._post_execution.add(hook, priority)

    def add_on_finish(
        self, hook: OnFinishHook, priority: Priority = Priority.NORMAL
    ) -> None:
        self._on_finish.add(hook, priority)

    @property
    def preparation_hooks(self) -> Sequence[PreparationHook]:
        return self._preparation.sorted_hooks

    @property
    def pre_execution_hooks(self) -> Sequence[PreExecutionHook]:
        return self._pre_execution.sorted_hooks

    @property
    def post_execution_hooks(self) -> Sequence[PostExecutionHook]:
        return self._post_execution.sorted_hooks

    @property
    def on_finish_hooks(self) -> Sequence[OnFinishHook]:
        return self._on_finish.sorted_hooks

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
    from marimo._runtime.runner.hooks_on_finish import ON_FINISH_HOOKS
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

    for finish_hook in ON_FINISH_HOOKS:
        hooks.add_on_finish(finish_hook)

    return hooks
