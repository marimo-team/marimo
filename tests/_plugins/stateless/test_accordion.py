# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import gc
import weakref

import marimo as mo
from marimo._output.hypertext import Html
from marimo._plugins.stateless.accordion import accordion


def test_accordion_retains_strong_references() -> None:
    # Regression test: accordion() must keep a strong reference to its children
    # so that wrapped UI elements are not garbage collected (the UI registry
    # holds children only weakly).
    tabs = {f"label {n}": Html(f"<span>tab {n}</span>") for n in range(3)}
    tab_refs = {label: weakref.ref(tab) for label, tab in tabs.items()}

    result = accordion(tabs)
    assert isinstance(result, Html)
    assert all(ref() is not None for ref in tab_refs.values())

    del tabs
    gc.collect()

    assert all(ref() is not None for ref in tab_refs.values()), (
        "accordion() did not retain a reference to all its children; "
        "at least one child was garbage collected"
    )


def test_lazy_accordion_retains_strong_references() -> None:
    tabs = {f"label {n}": Html(f"<span>tab {n}</span>") for n in range(3)}
    factories = {label: (lambda tab=tab: tab) for label, tab in tabs.items()}
    tab_refs = {label: weakref.ref(tab) for label, tab in tabs.items()}

    result = accordion(factories, lazy=True)
    assert isinstance(result, Html)
    assert all(ref() is not None for ref in tab_refs.values())

    del tabs
    del factories
    gc.collect()

    assert all(ref() is not None for ref in tab_refs.values()), (
        "accordion() did not retain a reference to all its (lazily created) children; "
        "at least one child was garbage collected"
    )


def test_accordion_child_updates_live() -> None:
    # A mutable child (e.g. mo.status.spinner) re-renders on each access rather
    # than being frozen at construction time.
    with mo.status.spinner(title="Loading") as spinner:
        result = accordion({"label": spinner})
        assert "Loading" in result.text

        spinner.update(title="Done")
        assert "Done" in result.text
        assert "Loading" not in result.text
