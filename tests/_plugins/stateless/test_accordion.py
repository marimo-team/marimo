# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import gc
import html
import json
import re
import weakref
from typing import TYPE_CHECKING

import pytest

import marimo as mo
from marimo._output.hypertext import Html
from marimo._plugins.stateless.accordion import accordion

if TYPE_CHECKING:
    from collections.abc import Sequence


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


@pytest.mark.parametrize(
    ("expanded", "multiple", "expected"),
    [
        (False, False, []),
        (False, True, []),
        (True, False, ["0"]),
        (True, True, ["0", "1"]),
        ([], False, []),
        (["**Details**"], False, ["1"]),
        (("**Details**", "Summary"), True, ["1", "0"]),
        (["Summary", "Summary"], False, ["0"]),
    ],
)
@pytest.mark.parametrize("lazy", [False, True])
def test_accordion_expanded(
    expanded: bool | Sequence[str],
    multiple: bool,
    expected: list[str],
    lazy: bool,
) -> None:
    result = accordion(
        {"Summary": "Overview", "**Details**": "More information"},
        multiple=multiple,
        lazy=lazy,
        expanded=expanded,
    )
    match = re.search("data-expanded='(.*?)'", result.text)
    assert match is not None
    assert json.loads(html.unescape(match[1])) == expected


@pytest.mark.parametrize("multiple", [False, True])
def test_empty_accordion_expanded(multiple: bool) -> None:
    result = accordion({}, multiple=multiple, expanded=True)
    assert "data-expanded='[]'" in result.text


def test_accordion_default_collapsed() -> None:
    result = accordion({"Summary": "Overview"})
    assert "data-expanded='[]'" in result.text


@pytest.mark.parametrize("multiple", [False, True])
def test_accordion_unknown_expanded_key(multiple: bool) -> None:
    with pytest.raises(
        ValueError, match="Unknown expanded item key: 'Details'"
    ):
        accordion(
            {"Summary": "Overview"}, multiple=multiple, expanded=["Details"]
        )


def test_accordion_multiple_expanded_requires_multiple() -> None:
    with pytest.raises(ValueError, match="requires multiple=True"):
        accordion(
            {"Summary": "Overview", "Details": "More"},
            expanded=["Summary", "Details"],
        )


@pytest.mark.parametrize("expanded", ["Summary", 1, None, {"Summary"}])
def test_accordion_rejects_invalid_expanded_type(expanded: object) -> None:
    with pytest.raises(TypeError, match="sequence of item keys"):
        accordion({"Summary": "Overview"}, expanded=expanded)  # type: ignore[arg-type]
