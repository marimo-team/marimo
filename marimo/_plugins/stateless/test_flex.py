# Copyright 2023 Marimo. All rights reserved.
from marimo._plugins.stateless.flex import hstack, vstack


def test_vstack() -> None:
    result = vstack(["item1", "item2"], align="center", gap=1)
    assert (
        result.text
        == "<div style='display: flex;flex-direction: column;justify-content: flex-start;align-items: center;flex-wrap: nowrap;gap: 1rem'><div><span>item1</span></div><div><span>item2</span></div></div>"  # noqa: E501
    )


def test_hstack() -> None:
    result = hstack(["item1", "item2"], justify="center", gap=1, wrap=True)
    assert (
        result.text
        == "<div style='display: flex;flex-direction: row;justify-content: center;align-items: normal;flex-wrap: wrap;gap: 1rem'><div><span>item1</span></div><div><span>item2</span></div></div>"  # noqa: E501
    )
