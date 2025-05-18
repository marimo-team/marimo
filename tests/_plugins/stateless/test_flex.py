# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._plugins.stateless.flex import hstack, vstack


def test_vstack() -> None:
    result = vstack(["item1", "item2"], align="center", gap=1)
    assert (
        result.text
        == "<div style='display: flex;flex: 1;flex-direction: column;justify-content: flex-start;align-items: center;flex-wrap: nowrap;gap: 1rem'><span>item1</span><span>item2</span></div>"  # noqa: E501
    )

    result = vstack(["item1", "item2"], justify="center", heights=[1, 2])
    assert (
        result.text
        == "<div style='display: flex;flex: 1;flex-direction: column;justify-content: center;align-items: normal;flex-wrap: nowrap;gap: 0.5rem'><div style='flex: 1'><span>item1</span></div><div style='flex: 2'><span>item2</span></div></div>"  # noqa: E501
    )


def test_hstack() -> None:
    result = hstack(["item1", "item2"], justify="center", gap=1, wrap=True)
    assert (
        result.text
        == "<div style='display: flex;flex: 1;flex-direction: row;justify-content: center;align-items: normal;flex-wrap: wrap;gap: 1rem'><span>item1</span><span>item2</span></div>"  # noqa: E501
    )

    result = hstack(["item1", "item2"], align="center", widths=[1, 2])
    assert (
        result.text
        == "<div style='display: flex;flex: 1;flex-direction: row;justify-content: space-between;align-items: center;flex-wrap: nowrap;gap: 0.5rem'><div style='flex: 1'><span>item1</span></div><div style='flex: 2'><span>item2</span></div></div>"  # noqa: E501
    )

    result = hstack(["item1", "item2"], align="center", widths="equal")
    assert (
        result.text
        == "<div style='display: flex;flex: 1;flex-direction: row;justify-content: space-between;align-items: center;flex-wrap: nowrap;gap: 0.5rem'><div style='flex: 1'><span>item1</span></div><div style='flex: 1'><span>item2</span></div></div>"  # noqa: E501
    )
