# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import pytest

from marimo import md
from marimo._output.hypertext import Html
from marimo._plugins import ui


def test_batch_rejects_non_ui_elements() -> None:
    """Test that batch raises ValueError for non-UIElement arguments."""
    with pytest.raises(
        ValueError, match="`.batch` only accepts UIElements as arguments"
    ):
        md("Example {thing}").batch(thing="thing")  # type: ignore

    with pytest.raises(
        ValueError, match="`.batch` only accepts UIElements as arguments"
    ):
        md("Example {thing}").batch(thing=42)  # type: ignore

    with pytest.raises(
        ValueError, match="`.batch` only accepts UIElements as arguments"
    ):
        md("Example {thing}").batch(thing={"key": "value"})  # type: ignore


def test_dictionary_rejects_non_ui_elements() -> None:
    """Test that dictionary raises ValueError for non-UIElement arguments."""
    with pytest.raises(
        ValueError, match="`.batch` only accepts UIElements as arguments"
    ):
        ui.dictionary({"hi": 1})  # type: ignore

    with pytest.raises(
        ValueError, match="`.batch` only accepts UIElements as arguments"
    ):
        ui.dictionary({"text": "string"})  # type: ignore

    with pytest.raises(
        ValueError, match="`.batch` only accepts UIElements as arguments"
    ):
        ui.dictionary({"valid": ui.slider(1, 10), "invalid": "string"})  # type: ignore


def test_update_on_frontend_value_change_only() -> None:
    b = ui.batch(
        Html("{a} {b}"),
        elements={
            "a": ui.button(value=0, on_click=lambda v: v + 1),
            "b": ui.button(value=0, on_click=lambda v: v + 1),
        },
    )
    # Multiple updates with the same value -- should only register once
    b._update({"a": 2})
    b._update({"a": 2})
    b._update({"a": 2})
    b._update({"b": 2})
    b._update({"b": 2})
    b._update({"b": 2})
    assert b.value == {"a": 1, "b": 1}
