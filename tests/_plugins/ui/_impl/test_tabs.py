# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._plugins import ui


def test_tabs_basic() -> None:
    tab = ui.tabs({"Tab 1": "Content 1", "Tab 2": "Content 2"})
    # Default value should be the first tab
    assert tab.value == "Tab 1"


def test_tabs_with_initial_value() -> None:
    tab = ui.tabs({"Tab 1": "Content 1", "Tab 2": "Content 2"}, value="Tab 2")
    assert tab.value == "Tab 2"


def test_tabs_update() -> None:
    tab = ui.tabs({"Tab 1": "Content 1", "Tab 2": "Content 2"})
    assert tab.value == "Tab 1"

    # Simulate selecting the second tab (index 1)
    tab._update("1")
    assert tab.value == "Tab 2"


def test_tabs_empty() -> None:
    # Empty tabs should not raise an error
    tab = ui.tabs({})
    assert tab.value == ""


def test_tabs_with_invalid_initial_value() -> None:
    # Invalid value should default to empty string, which converts to first tab
    tab = ui.tabs(
        {"Tab 1": "Content 1", "Tab 2": "Content 2"}, value="Invalid"
    )
    assert tab.value == "Tab 1"


def test_tabs_lazy() -> None:
    tab = ui.tabs({"Tab 1": "Content 1", "Tab 2": "Content 2"}, lazy=True)
    assert tab.value == "Tab 1"
    # Verify lazy loading is enabled by checking the slotted HTML contains lazy
    assert "marimo-lazy" in tab.text
