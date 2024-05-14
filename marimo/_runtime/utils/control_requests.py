# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

from marimo._plugins.ui._core.registry import UIElementId
from marimo._runtime.requests import SetUIElementValueRequest


def merge_set_ui_element_requests(
    requests: list[SetUIElementValueRequest],
) -> SetUIElementValueRequest:
    merged: dict[UIElementId, Any] = {}
    for request in requests:
        for ui_id, value in request.ids_and_values:
            merged[ui_id] = value
    return SetUIElementValueRequest(
        ids_and_values=[(ui_id, value) for ui_id, value in merged.items()]
    )
