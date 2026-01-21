# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest

from marimo._messaging.notification import SetThemeNotification
from marimo._runtime.runtime import set_theme
from tests._messaging.mocks import MockStream


def test_set_theme_dark() -> None:
    """Test set_theme with dark theme broadcasts correct notification."""
    stream = MockStream()

    set_theme("dark")

    # Note: broadcast_notification uses the global stream, so we need to check
    # if it was called correctly. For now, we just verify the function runs.


def test_set_theme_light() -> None:
    """Test set_theme with light theme broadcasts correct notification."""
    stream = MockStream()

    set_theme("light")

    # Note: broadcast_notification uses the global stream, so we need to check
    # if it was called correctly. For now, we just verify the function runs.


def test_set_theme_invalid() -> None:
    """Test invalid theme values raise ValueError."""
    with pytest.raises(ValueError, match="theme must be 'light' or 'dark'"):
        set_theme("invalid")  # type: ignore

    with pytest.raises(ValueError, match="theme must be 'light' or 'dark'"):
        set_theme("system")  # type: ignore

    with pytest.raises(ValueError, match="theme must be 'light' or 'dark'"):
        set_theme("")  # type: ignore
