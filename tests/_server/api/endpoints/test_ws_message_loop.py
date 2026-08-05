# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json

from marimo._messaging.notification import (
    AlertNotification,
    CompletionResultNotification,
    FocusCellNotification,
)
from marimo._messaging.serde import serialize_kernel_message
from marimo._server.api.endpoints.ws.ws_message_loop import (
    prepare_wire_message,
)
from marimo._types.ids import CellId_t, RequestId

FOCUS_CELL = serialize_kernel_message(
    FocusCellNotification(cell_id=CellId_t("Hbol"))
)
COMPLETION_RESULT = serialize_kernel_message(
    CompletionResultNotification(
        completion_id=RequestId("1"), prefix_length=0, options=[]
    )
)
ALERT = serialize_kernel_message(
    AlertNotification(title="title", description="description")
)


def test_editor_filters_kiosk_only_and_keeps_completions() -> None:
    assert prepare_wire_message(FOCUS_CELL, is_kiosk=False) is None
    assert prepare_wire_message(COMPLETION_RESULT, is_kiosk=False) is not None


def test_viewer_keeps_kiosk_only_and_filters_completions() -> None:
    assert prepare_wire_message(FOCUS_CELL, is_kiosk=True) is not None
    assert prepare_wire_message(COMPLETION_RESULT, is_kiosk=True) is None


def test_wire_format() -> None:
    text = prepare_wire_message(ALERT, is_kiosk=False)
    assert text is not None
    message = json.loads(text)
    assert message["op"] == "alert"
    assert message["data"]["title"] == "title"
    assert message["data"]["description"] == "description"
