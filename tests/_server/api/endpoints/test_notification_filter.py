# Copyright 2026 Marimo. All rights reserved.
from marimo._messaging.notification import (
    CompletionResultNotification,
    FocusCellNotification,
)
from marimo._server.api.endpoints.ws.notification_filter import (
    should_filter_operation,
)


def test_editor_filters_kiosk_only_and_keeps_completions() -> None:
    assert should_filter_operation(FocusCellNotification.name, is_kiosk=False)
    assert not should_filter_operation(
        CompletionResultNotification.name, is_kiosk=False
    )


def test_viewer_keeps_kiosk_only_and_filters_completions() -> None:
    assert not should_filter_operation(
        FocusCellNotification.name, is_kiosk=True
    )
    assert should_filter_operation(
        CompletionResultNotification.name, is_kiosk=True
    )
