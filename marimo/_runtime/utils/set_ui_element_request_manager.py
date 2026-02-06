# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Union

from marimo._runtime.commands import (
    ModelCommand,
    ModelCustomMessage,
    ModelUpdateMessage,
    UpdateUIElementCommand,
)
from marimo._session.queue import QueueType
from marimo._types.ids import UIElementId, WidgetModelId

if TYPE_CHECKING:
    import asyncio

BatchableCommand = Union[UpdateUIElementCommand, ModelCommand]


class SetUIElementRequestManager:
    def __init__(
        self,
        set_ui_element_queue: (
            QueueType[BatchableCommand] | asyncio.Queue[BatchableCommand]
        ),
    ) -> None:
        self._set_ui_element_queue = set_ui_element_queue
        self._processed_request_tokens: set[str] = set()

    def process_request(
        self, request: BatchableCommand
    ) -> list[BatchableCommand]:
        """Drain the queue and merge pending requests.

        UpdateUIElementCommands are merged by UI element ID
        (last-write-wins).  ModelCommands with update messages are
        merged by model ID (last-write-wins on state keys).  Custom
        model messages pass through without merging.
        """
        pending: list[BatchableCommand] = []

        # Add the triggering request (with token dedup for UI elements)
        if isinstance(request, UpdateUIElementCommand):
            if request.token not in self._processed_request_tokens:
                pending.append(request)
                self._processed_request_tokens.add(request.token)
            else:
                self._processed_request_tokens.remove(request.token)
        else:
            pending.append(request)

        # Drain everything currently in the queue
        while not self._set_ui_element_queue.empty():
            r = self._set_ui_element_queue.get_nowait()
            if isinstance(r, UpdateUIElementCommand):
                if r.token not in self._processed_request_tokens:
                    pending.append(r)
                    self._processed_request_tokens.add(r.token)
                else:
                    self._processed_request_tokens.remove(r.token)
            else:
                pending.append(r)

        return self._merge(pending)

    @staticmethod
    def _merge(
        commands: list[BatchableCommand],
    ) -> list[BatchableCommand]:
        if not commands:
            return []

        result: list[BatchableCommand] = []

        # --- UI element merging (last-write-wins per element ID) ---
        ui_merged: dict[UIElementId, Any] = {}
        last_ui_request: UpdateUIElementCommand | None = None
        for cmd in commands:
            if isinstance(cmd, UpdateUIElementCommand):
                for ui_id, value in cmd.ids_and_values:
                    ui_merged[ui_id] = value
                last_ui_request = cmd

        if last_ui_request is not None:
            result.append(
                UpdateUIElementCommand(
                    object_ids=list(ui_merged.keys()),
                    values=list(ui_merged.values()),
                    token=last_ui_request.token,
                    request=last_ui_request.request,
                )
            )

        # --- Model command merging (last-write-wins per model ID) ---
        # Uses the same merge strategy as ModelReplayState.apply_update:
        # when a state key is overridden, drop any existing buffers whose
        # root path component matches that key.
        BufferPath = tuple[Union[str, int], ...]
        model_state: dict[WidgetModelId, dict[str, Any]] = {}
        model_buffers: dict[WidgetModelId, dict[BufferPath, bytes]] = {}

        for cmd in commands:
            if not isinstance(cmd, ModelCommand):
                continue
            if isinstance(cmd.message, ModelCustomMessage):
                # Custom messages are not mergeable
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
