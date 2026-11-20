# Copyright 2026 Marimo. All rights reserved.
from marimo._messaging.notification import (
    CallbackOutputNotification,
    CompletionResultNotification,
    FocusCellNotification,
    PdbInputNotification,
    PdbOutputNotification,
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


def test_kiosk_receives_callback_output_and_hides_the_debugger() -> None:
    assert not should_filter_operation(
        CallbackOutputNotification.name, is_kiosk=True
    )
    for notification in (PdbInputNotification, PdbOutputNotification):
        assert should_filter_operation(notification.name, is_kiosk=True)
        assert not should_filter_operation(notification.name, is_kiosk=False)
