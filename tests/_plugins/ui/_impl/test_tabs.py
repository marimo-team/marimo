# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import gc

from marimo._plugins import ui
from marimo._runtime.context import get_context
from marimo._runtime.runtime import Kernel


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


def test_tabs_default_orientation_is_horizontal() -> None:
    tab = ui.tabs({"Tab 1": "Content 1", "Tab 2": "Content 2"})
    assert tab._component_args["orientation"] == "horizontal"  # pyright: ignore[reportPrivateUsage]


def test_tabs_vertical_orientation() -> None:
    tab = ui.tabs(
        {"Tab 1": "Content 1", "Tab 2": "Content 2"},
        orientation="vertical",
    )
    assert tab._component_args["orientation"] == "vertical"  # pyright: ignore[reportPrivateUsage]
    # Orientation should not affect selection behavior
    assert tab.value == "Tab 1"


def test_tabs_keeps_ui_element_registered(executing_kernel: Kernel) -> None:
    # Regression test: a UIElement placed in a tab (e.g. returned from a
    # helper) must stay alive and registered. mo.ui.tabs freezes each tab's
    # rendered HTML and keeps only the tab keys, so it must retain the tab
    # contents; otherwise the weak registry entry is reaped on garbage
    # collection and the element loses interactivity.
    del executing_kernel

    registry = get_context().ui_element_registry
    slider = ui.slider(1, 10)
    object_id = slider._id
    assert registry.get_object(object_id) is slider

    result = ui.tabs({"Tab": slider})
    assert object_id in result.text  # the slider is rendered into the tab

    del slider
    gc.collect()

    assert object_id in registry._objects, (
        "mo.ui.tabs let a tab's UI element be garbage collected; "
        "it was removed from the registry and is no longer interactive"
    )
    assert registry._objects[object_id]() is not None
