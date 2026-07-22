# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import gc
import weakref

import marimo as mo
from marimo._output.hypertext import Html
from marimo._plugins.stateless.carousel import carousel


def test_carousel_renders_items() -> None:
    # carousel embeds each item's HTML, unescaped, inside a marimo-carousel
    # component.
    result = carousel([Html("<p>First</p>"), Html("<p>Second</p>")])
    assert isinstance(result, Html)
    assert "marimo-carousel" in result.text
    assert "<p>First</p>" in result.text
    assert "<p>Second</p>" in result.text


def test_carousel_retains_strong_references() -> None:
    # Regression test: carousel() must keep a strong reference to its children
    # so that wrapped UI elements are not garbage collected (the UI registry
    # holds children only weakly).
    items = [Html(f"<span>item {n}</span>") for n in range(3)]
    item_refs = [weakref.ref(item) for item in items]

    result = carousel(items)
    assert isinstance(result, Html)
    assert all(ref() is not None for ref in item_refs)

    del items
    gc.collect()

    assert all(ref() is not None for ref in item_refs), (
        "carousel() did not retain a reference to all its children; "
        "at least one child was garbage collected"
    )


def test_carousel_child_updates_live() -> None:
    # A mutable child (e.g. mo.status.spinner) re-renders on each access rather
    # than being frozen at construction time.
    with mo.status.spinner(title="Loading") as spinner:
        result = carousel([spinner])
        assert "Loading" in result.text

        spinner.update(title="Done")
        assert "Done" in result.text
        assert "Loading" not in result.text
