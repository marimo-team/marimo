# Copyright 2026 Marimo. All rights reserved.
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


def test_on_change_preserved_through_nested_cloning() -> None:
    """Test that on_change handlers on child elements work correctly
    when elements are nested in containers (batch inside array).

    Regression test for https://github.com/marimo-team/marimo/issues/6435
    """
    from dataclasses import dataclass

    @dataclass
    class Model:
        id: int
        state: bool = False

        def set_state(self, new_val: bool) -> None:
            self.state = new_val

    models = [Model(i) for i in range(3)]

    # checkbox in batch in array: the on_change (m.set_state) must
    # still reference the original Model, not a deep-copied one
    view = ui.array(
        [
            ui.batch(
                Html("{box}"),
                elements={
                    "box": ui.checkbox(on_change=m.set_state),
                },
            )
            for m in models
        ]
    )

    # Simulate checking the first checkbox
    view._update({"0": {"box": True}})
    assert view.value[0] == {"box": True}
    # The on_change should have mutated the ORIGINAL model
    assert models[0].state is True
    assert models[1].state is False
    assert models[2].state is False

    # Simulate checking the third checkbox
    view._update({"2": {"box": True}})
    assert models[2].state is True


def test_on_change_preserved_through_single_cloning() -> None:
    """Test that on_change handlers work when elements are nested
    in just a single container (batch only, no array wrapping)."""
    from dataclasses import dataclass

    @dataclass
    class Model:
        id: int
        state: bool = False

        def set_state(self, new_val: bool) -> None:
            self.state = new_val

    m = Model(0)
    b = ui.batch(
        Html("{box}"),
        elements={"box": ui.checkbox(on_change=m.set_state)},
    )
    b._update({"box": True})
    assert b.value == {"box": True}
    assert m.state is True
