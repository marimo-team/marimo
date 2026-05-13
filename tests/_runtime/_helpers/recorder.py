# Copyright 2026 Marimo. All rights reserved.
"""Hook spy/recorder for `NotebookCellHooks`.

Lets tests assert on hook invocation order, args, and counts without
threading manual `order.append(...)` lambdas through their setup.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, Literal

from marimo._runtime.runner.hooks import NotebookCellHooks, Priority

if TYPE_CHECKING:
    from collections.abc import Sequence

HookPhase = Literal[
    "preparation", "pre_execution", "post_execution", "on_finish"
]


@dataclasses.dataclass
class HookEvent:
    """A single hook invocation captured by `HookRecorder`."""

    phase: HookPhase
    args: tuple[Any, ...]


class HookRecorder:
    """Spy that records every invocation across all four hook phases.

    Usage::

        hooks = create_default_hooks()
        recorder = HookRecorder(hooks)
        # ... run cells through a kernel using `hooks` ...
        assert recorder.phases == ["preparation", "pre_execution", ...]
    """

    def __init__(
        self,
        hooks: NotebookCellHooks,
        *,
        priority: Priority = Priority.FINAL,
    ) -> None:
        # Record at FINAL priority by default so we see what other hooks
        # observed/produced before us.
        self._events: list[HookEvent] = []

        def _make_recorder(
            phase: HookPhase,
        ) -> Any:
            def _record(*args: Any) -> None:
                self._events.append(HookEvent(phase=phase, args=args))

            return _record

        hooks.add_preparation(_make_recorder("preparation"), priority)
        hooks.add_pre_execution(_make_recorder("pre_execution"), priority)
        hooks.add_post_execution(_make_recorder("post_execution"), priority)
        hooks.add_on_finish(_make_recorder("on_finish"), priority)

    @property
    def events(self) -> Sequence[HookEvent]:
        return tuple(self._events)

    @property
    def phases(self) -> list[HookPhase]:
        return [e.phase for e in self._events]

    def events_in_phase(self, phase: HookPhase) -> list[HookEvent]:
        return [e for e in self._events if e.phase == phase]

    def reset(self) -> None:
        self._events.clear()
