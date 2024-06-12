# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from marimo._plugins.ui._core.registry import UIElementId
from marimo._runtime.requests import SetUIElementValueRequest
from marimo._server.types import QueueType

if TYPE_CHECKING:
    import asyncio


class SetUIElementRequestManager:
    def __init__(
        self,
        set_ui_element_queue: QueueType[SetUIElementValueRequest]
        | asyncio.Queue[SetUIElementValueRequest],
    ) -> None:
        self._set_ui_element_queue = set_ui_element_queue
        self._processed_request_tokens: set[str] = set()

    def process_request(
        self, request: SetUIElementValueRequest
    ) -> SetUIElementValueRequest | None:
        request_batch: list[SetUIElementValueRequest] = []
        if request.token not in self._processed_request_tokens:
            request_batch.append(request)
            self._processed_request_tokens.add(request.token)
        else:
            self._processed_request_tokens.remove(request.token)

        while not self._set_ui_element_queue.empty():
            r = self._set_ui_element_queue.get_nowait()
            if r.token not in self._processed_request_tokens:
                request_batch.append(r)
                self._processed_request_tokens.add(r.token)
            else:
                self._processed_request_tokens.remove(r.token)

        return self._merge_set_ui_element_requests(request_batch)

    def _merge_set_ui_element_requests(
        self,
        requests: list[SetUIElementValueRequest],
    ) -> SetUIElementValueRequest | None:
        if not requests:
            return None

        merged: dict[UIElementId, Any] = {}
        for request in requests:
            for ui_id, value in request.ids_and_values:
                merged[ui_id] = value
        return SetUIElementValueRequest(
            object_ids=list(merged.keys()),
            values=list(merged.values()),
            token="",
        )
