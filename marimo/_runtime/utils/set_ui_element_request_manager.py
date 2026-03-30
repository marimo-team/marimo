# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Generic, TypeVar, Union

from marimo._runtime.commands import (
    BatchableCommand,
    ModelCommand,
    ModelCustomMessage,
    ModelUpdateMessage,
    UpdateUIElementCommand,
)
from marimo._session.queue import QueueType
from marimo._types.ids import UIElementId, WidgetModelId

if TYPE_CHECKING:
    import asyncio

A = TypeVar("A")
B = TypeVar("B")


class _RunAccumulator(Generic[A, B]):
    """Merges contiguous runs of same-type commands.

    Uses Generic[A, B] for precise merge function typing. If a third
    command type is needed, this could be generalized to accept a
    dict[type, Callable] instead.

    Example::

        A A A B B B A A B B  →  A(merged) B(merged) A(merged) B(merged)
    """

    def __init__(
        self,
        a: tuple[type[A], Callable[[list[A]], list[A]]],
        b: tuple[type[B], Callable[[list[B]], list[B]]],
    ) -> None:
        self._type_a = a[0]
        self._type_b = b[0]
        self._merge_a = a[1]
        self._merge_b = b[1]
        self._current_run: list[A] | list[B] = []
        self._current_type: type[A | B] | None = None
        self._result: list[A | B] = []

    def push(self, cmd: A | B) -> None:
        cmd_type = (
            self._type_a if isinstance(cmd, self._type_a) else self._type_b
        )
        if (
            self._current_type is not None
            and cmd_type is not self._current_type
        ):
            self._flush()
        self._current_type = cmd_type
        self._current_run.append(cmd)  # type: ignore[arg-type]

    def _flush(self) -> None:
        if not self._current_run:
            return
        if self._current_type is self._type_a:
            self._result.extend(self._merge_a(self._current_run))  # type: ignore[arg-type]
        else:
            self._result.extend(self._merge_b(self._current_run))  # type: ignore[arg-type]
        self._current_run = []
        self._current_type = None

    def finish(self) -> list[A | B]:
        self._flush()
        return self._result


def _merge_ui_commands(
    cmds: list[UpdateUIElementCommand],
) -> list[UpdateUIElementCommand]:
    """Merge UI element commands: last-write-wins per element ID."""
    if not cmds:
        return []

    merged: dict[UIElementId, Any] = {}
    last_cmd = cmds[-1]
    for cmd in cmds:
        for ui_id, value in cmd.ids_and_values:
            merged[ui_id] = value

    return [
        UpdateUIElementCommand(
            object_ids=list(merged.keys()),
            values=list(merged.values()),
            token=last_cmd.token,
            request=last_cmd.request,
        )
    ]


BufferPath = tuple[Union[str, int], ...]


def _merge_model_commands(
    cmds: list[ModelCommand],
) -> list[ModelCommand]:
    """Merge model commands: last-write-wins per model ID on state keys.

    Custom messages pass through without merging. Uses the same merge
    strategy as ModelReplayState.apply_update: when a state key is
    overridden, drop any existing buffers whose root path component
    matches that key.
    """
    result: list[ModelCommand] = []
    model_state: dict[WidgetModelId, dict[str, Any]] = {}
    model_buffers: dict[WidgetModelId, dict[BufferPath, bytes]] = {}

    for cmd in cmds:
        if isinstance(cmd.message, ModelCustomMessage):
            result.append(cmd)
        elif isinstance(cmd.message, ModelUpdateMessage):
            mid = cmd.model_id
            if mid not in model_state:
                model_state[mid] = {}
                model_buffers[mid] = {}

            # Drop buffers whose root key is being overridden
            updated_keys = set(cmd.message.state.keys())
            model_buffers[mid] = {
                path: buf
                for path, buf in model_buffers[mid].items()
                if path[0] not in updated_keys
            }
            # Merge state and buffers
            model_state[mid].update(cmd.message.state)
            for path, buf in zip(cmd.message.buffer_paths, cmd.buffers):
                model_buffers[mid][tuple(path)] = buf

    for mid in model_state:
        paths = list(model_buffers[mid].keys())
        bufs = list(model_buffers[mid].values())
        result.append(
            ModelCommand(
                model_id=mid,
                message=ModelUpdateMessage(
                    state=model_state[mid],
                    buffer_paths=[list(p) for p in paths],
                ),
                buffers=bufs,
            )
        )

    return result


def merge_batchable_commands(
    commands: list[BatchableCommand],
) -> list[BatchableCommand]:
    if not commands:
        return []

    acc = _RunAccumulator(
        a=(UpdateUIElementCommand, _merge_ui_commands),
        b=(ModelCommand, _merge_model_commands),
    )
    for cmd in commands:
        acc.push(cmd)
    return acc.finish()


class SetUIElementRequestManager:
    def __init__(
        self,
        set_ui_element_queue: (
            QueueType[BatchableCommand] | asyncio.Queue[BatchableCommand]
        ),
    ) -> None:
        self._set_ui_element_queue = set_ui_element_queue
        # Token-based dedup for both UI commands and model commands.
        # Each command is placed on both control_queue and
        # set_ui_element_queue; the token tracks which have already
        # been processed via the drain so the control_queue copy
        # can be skipped.
        self._processed_tokens: set[str] = set()

    def _dedup(
        self,
        cmd: BatchableCommand,
        pending: list[BatchableCommand],
    ) -> None:
        token = cmd.token
        if token not in self._processed_tokens:
            pending.append(cmd)
            self._processed_tokens.add(token)
        else:
            self._processed_tokens.discard(token)

    def process_request(
        self, request: BatchableCommand
    ) -> list[BatchableCommand]:
        """Drain the queue and merge pending requests.

        UpdateUIElementCommands are merged by UI element ID
        (last-write-wins).  ModelCommands with update messages are
        merged by model ID (last-write-wins on state keys).  Custom
        model messages pass through without merging.

        Contiguous runs of same-type commands are merged together while
        preserving the relative interleaving order of different types.
        """
        pending: list[BatchableCommand] = []

        # Add the triggering request (with token dedup)
        self._dedup(request, pending)

        # Drain everything currently in the queue
        while not self._set_ui_element_queue.empty():
            self._dedup(self._set_ui_element_queue.get_nowait(), pending)

        return merge_batchable_commands(pending)
