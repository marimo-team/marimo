# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from marimo._output.hypertext import Html
from marimo._plugins import ui


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
