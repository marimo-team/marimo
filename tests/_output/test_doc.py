# Copyright 2026 Marimo. All rights reserved.
"""Tests for `marimo._output.doc.doc` / `mo.doc`."""

from __future__ import annotations

import marimo as mo
from marimo._output.doc import doc
from marimo._output.hypertext import Html


def test_doc_on_mddoc_decorated_function_does_not_raise() -> None:
    """Regression test for https://github.com/marimo-team/marimo/issues/9316.

    `mo.doc` renders `_rich_help_` output (which contains a ```python fenced
    code block with the object's signature) through pymdown-extensions +
    pygments. pymdown-extensions <10.21.2 passed `filename=None` to pygments'
    `HtmlFormatter`, and pygments >=2.20 crashed with
    `AttributeError: 'NoneType' object has no attribute 'replace'`.

    This test exercises the full pipeline end-to-end on each `@mddoc`-decorated
    object used by the Layout tutorial so a regression in the pinned dependency
    range is caught immediately.
    """
    for obj in (mo.hstack, mo.vstack, mo.accordion, mo.callout, mo.tree):
        result = doc(obj)
        assert isinstance(result, Html), (
            f"doc({obj.__name__}) returned {result!r}"
        )
        # The highlighted signature block should be present in the output.
        assert "codehilite" in result.text
        assert obj.__name__ in result.text


def test_doc_on_mddoc_decorated_method_does_not_raise() -> None:
    for method in (mo.Html.center, mo.Html.right, mo.Html.left):
        result = doc(method)
        assert isinstance(result, Html)
        assert "codehilite" in result.text


def test_doc_on_object_without_rich_help_returns_none() -> None:
    """When the target object doesn't implement `_rich_help_`, `doc` should
    fall back to `help(obj)` and return `None`."""

    class Plain:
        """A plain class without `_rich_help_`."""

    assert doc(Plain) is None
