# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._plugins.stateless.flex import hstack, vstack


def test_vstack() -> None:
    result = vstack(["item1", "item2"], align="center", gap=1)
    assert (
        result.text
        == "<div style='display: flex;flex: 1;flex-direction: column;justify-content: flex-start;align-items: center;flex-wrap: nowrap;gap: 1rem'><span>item1</span><span>item2</span></div>"
    )

    result = vstack(["item1", "item2"], justify="center", heights=[1, 2])
    assert (
        result.text
        == "<div style='display: flex;flex: 1;flex-direction: column;justify-content: center;align-items: normal;flex-wrap: nowrap;gap: 0.5rem'><div style='flex: 1'><span>item1</span></div><div style='flex: 2'><span>item2</span></div></div>"
    )


def test_hstack() -> None:
    result = hstack(["item1", "item2"], justify="center", gap=1, wrap=True)
    assert (
        result.text
        == "<div style='display: flex;flex: 1;flex-direction: row;justify-content: center;align-items: normal;flex-wrap: wrap;gap: 1rem'><span>item1</span><span>item2</span></div>"
    )

    result = hstack(["item1", "item2"], align="center", widths=[1, 2])
    assert (
        result.text
        == "<div style='display: flex;flex: 1;flex-direction: row;justify-content: space-between;align-items: center;flex-wrap: nowrap;gap: 0.5rem'><div style='flex: 1'><span>item1</span></div><div style='flex: 2'><span>item2</span></div></div>"
    )

    result = hstack(["item1", "item2"], align="center", widths="equal")
    assert (
        result.text
        == "<div style='display: flex;flex: 1;flex-direction: row;justify-content: space-between;align-items: center;flex-wrap: nowrap;gap: 0.5rem'><div style='flex: 1'><span>item1</span></div><div style='flex: 1'><span>item2</span></div></div>"
    )


def test_nested_stacks_preserve_flex_wrapper() -> None:
    # Nested stacks must get display:flex wrapper so their flex/justify work
    inner = vstack(["a", "b"])
    result = hstack([inner, "plain"], widths="equal")
    assert "display: flex;min-width: 0;min-height: 0" in result.text
    # First wrapper (around nested vstack) is a flex container
    assert (
        "<div style='flex: 1;display: flex;min-width: 0;min-height: 0'>"
        in result.text
    )
    # Second wrapper (around "plain") is block only so content fills width
    assert "<div style='flex: 1'><span>plain</span></div>" in result.text
