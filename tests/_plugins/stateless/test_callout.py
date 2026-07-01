# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import gc
import weakref

import marimo as mo
from marimo._output.hypertext import Html
from marimo._plugins.stateless.callout import callout


def test_callout_renders_child() -> None:
    # callout embeds its child (JSON-escaped into the data-html attribute) in a
    # marimo-callout-output component with the given kind.
    result = callout(Html("<p>Important</p>"), kind="warn")
    assert isinstance(result, Html)
    assert "marimo-callout-output" in result.text
    assert "warn" in result.text
    assert "Important" in result.text


def test_callout_retains_strong_reference_to_child() -> None:
    # Regression test: callout() must keep a strong reference to its child so
    # that wrapped UI elements are not garbage collected (the UI registry holds
    # children only weakly).
    child = Html("<span>child</span>")
    child_ref = weakref.ref(child)

    result = callout(child, kind="info")
    assert child_ref() is not None

    del child
    gc.collect()

    assert child_ref() is not None, (
        "callout() did not retain a reference to its child; "
        "the wrapped element can be garbage collected"
    )


def test_callout_child_updates_live() -> None:
    # A mutable child (e.g. mo.status.spinner) re-renders on each access rather
    # than being frozen at construction time.
    with mo.status.spinner(title="Loading") as spinner:
        result = callout(spinner, kind="neutral")
        assert "Loading" in result.text

        spinner.update(title="Done")
        assert "Done" in result.text
        assert "Loading" not in result.text
