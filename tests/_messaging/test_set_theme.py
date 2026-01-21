# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._messaging.notification import SetThemeNotification
from marimo._messaging.notification_utils import broadcast_notification
from marimo._utils.parse_dataclass import parse_raw
from tests._messaging.mocks import MockStream


def test_set_theme_notification_creation_light() -> None:
    """Test SetThemeNotification creation with light theme."""
    notification = SetThemeNotification(theme="light")
    assert notification.name == "set-theme"
    assert notification.theme == "light"


def test_set_theme_notification_creation_dark() -> None:
    """Test SetThemeNotification creation with dark theme."""
    notification = SetThemeNotification(theme="dark")
    assert notification.name == "set-theme"
    assert notification.theme == "dark"


def test_set_theme_notification_broadcast() -> None:
    """Test broadcasting SetThemeNotification."""
    stream = MockStream()
    notification = SetThemeNotification(theme="dark")

    broadcast_notification(notification, stream)

    assert len(stream.messages) == 1
    assert stream.operations[0] == {
        "op": "set-theme",
        "theme": "dark",
    }


def test_set_theme_notification_serialization() -> None:
    """Test serialization/deserialization roundtrip."""
    stream = MockStream()
    notification = SetThemeNotification(theme="light")

    broadcast_notification(notification, stream)

    assert len(stream.messages) == 1
    parsed = parse_raw(stream.operations[0], SetThemeNotification)
    assert isinstance(parsed, SetThemeNotification)
    assert parsed.theme == "light"
    assert parsed.name == "set-theme"
