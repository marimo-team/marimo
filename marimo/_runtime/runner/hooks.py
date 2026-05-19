# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import TYPE_CHECKING, cast

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
    "HookPhase",
    "NotebookCellHooks",
    "OnFinishHook",
    "PostExecutionHook",
    "PreExecutionHook",
    "PreparationHook",
    "Priority",
    "create_default_hooks",
]

# Hook type aliases
PreparationHook = Callable[["PreparationHookContext"], None]
PreExecutionHook = Callable[["CellImpl", "PreExecutionHookContext"], None]
PostExecutionHook = Callable[
    ["CellImpl", "PostExecutionHookContext", "cell_runner.RunResult"], None
]
OnFinishHook = Callable[["OnFinishHookContext"], None]


class HookPhase(str, Enum):
    """Lifecycle phases a hook may register against."""

    PREPARATION = "preparation"
    PRE_EXECUTION = "pre_execution"
    POST_EXECUTION = "post_execution"
    ON_FINISH = "on_finish"


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
        self, _lists: dict[HookPhase, _HookList] | None = None
    ) -> None:
        self._lists: dict[HookPhase, _HookList] = _lists or {
            phase: _HookList() for phase in HookPhase
        }

    def _add(
        self,
        phase: HookPhase,
        hook: Callable[..., None],
        priority: Priority,
    ) -> None:
        self._lists[phase].add(hook, priority)

    def _get(self, phase: HookPhase) -> Sequence[Callable[..., None]]:
        return self._lists[phase].sorted_hooks

    def add_preparation(
        self, hook: PreparationHook, priority: Priority = Priority.NORMAL
    ) -> None:
        self._add(HookPhase.PREPARATION, hook, priority)

    def add_pre_execution(
        self, hook: PreExecutionHook, priority: Priority = Priority.NORMAL
    ) -> None:
        self._add(HookPhase.PRE_EXECUTION, hook, priority)

    def add_post_execution(
        self, hook: PostExecutionHook, priority: Priority = Priority.NORMAL
    ) -> None:
        self._add(HookPhase.POST_EXECUTION, hook, priority)

    def add_on_finish(
        self, hook: OnFinishHook, priority: Priority = Priority.NORMAL
    ) -> None:
        self._add(HookPhase.ON_FINISH, hook, priority)

    @property
    def preparation_hooks(self) -> Sequence[PreparationHook]:
        return cast(
            "Sequence[PreparationHook]", self._get(HookPhase.PREPARATION)
        )

    @property
    def pre_execution_hooks(self) -> Sequence[PreExecutionHook]:
        return cast(
            "Sequence[PreExecutionHook]", self._get(HookPhase.PRE_EXECUTION)
        )

    @property
    def post_execution_hooks(self) -> Sequence[PostExecutionHook]:
        return cast(
            "Sequence[PostExecutionHook]", self._get(HookPhase.POST_EXECUTION)
        )

    @property
    def on_finish_hooks(self) -> Sequence[OnFinishHook]:
        return cast("Sequence[OnFinishHook]", self._get(HookPhase.ON_FINISH))

    def copy(self) -> NotebookCellHooks:
        return NotebookCellHooks(
            {phase: lst.copy() for phase, lst in self._lists.items()}
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
    defaults: list[tuple[HookPhase, Sequence[Callable[..., None]]]] = [
        (HookPhase.PREPARATION, PREPARATION_HOOKS),
        (HookPhase.PRE_EXECUTION, PRE_EXECUTION_HOOKS),
        (HookPhase.POST_EXECUTION, POST_EXECUTION_HOOKS),
        (HookPhase.ON_FINISH, ON_FINISH_HOOKS),
    ]
    for phase, hook_list in defaults:
        for hook in hook_list:
            hooks._add(phase, hook, Priority.NORMAL)
    return hooks
