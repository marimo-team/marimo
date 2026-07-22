from __future__ import annotations

import gc
import weakref

import pytest

import marimo as mo
from marimo._output.hypertext import Html
from marimo._plugins.stateless.sidebar import sidebar


def test_sidebar_string():
    """Test sidebar with string input."""
    result = sidebar("test content")
    assert isinstance(result, Html)
    assert "width" not in result.text


def test_sidebar_list():
    """Test sidebar with list input."""
    result = sidebar(["item1", "item2"])
    assert isinstance(result, Html)
    assert "width" not in result.text


def test_sidebar_with_footer():
    """Test sidebar with footer."""
    result = sidebar("content", footer="footer text")
    assert isinstance(result, Html)
    assert "width" not in result.text


def test_sidebar_list_both_width_and_footer():
    """Test sidebar with both width and footer."""
    result = sidebar(["item1", "item2"], footer=["footer1", "footer2"])
    assert isinstance(result, Html)
    assert "width" not in result.text


def test_sidebar_with_width():
    """Test sidebar with custom width."""
    result = sidebar("content", width="300px")
    assert isinstance(result, Html)
    assert "data-width='&quot;300px&quot;'" in result.text


def test_sidebar_unsupported_methods():
    """Test that unsupported methods raise TypeError."""
    s = sidebar("content")
    with pytest.raises(TypeError):
        s.batch()
    with pytest.raises(TypeError):
        s.center()
    with pytest.raises(TypeError):
        s.right()
    with pytest.raises(TypeError):
        s.left()
    with pytest.raises(TypeError):
        s.callout()
    with pytest.raises(TypeError):
        s.style()


def test_sidebar_retains_strong_reference_to_item() -> None:
    # Regression test: sidebar() must keep a strong reference to its item so
    # that a wrapped UI element is not garbage collected (the UI registry holds
    # children only weakly).
    child = Html("<span>child</span>")
    child_ref = weakref.ref(child)

    result = sidebar(child)
    assert isinstance(result, Html)
    # the item is rendered, unescaped, inside the sidebar component
    assert "marimo-sidebar" in result.text
    assert "<span>child</span>" in result.text
    assert child_ref() is not None

    del child
    gc.collect()

    assert child_ref() is not None, (
        "sidebar() did not retain a reference to its item; "
        "the wrapped element can be garbage collected"
    )


def test_sidebar_retains_list_items() -> None:
    # The list form wraps items in a vstack; sidebar must retain that wrapper
    # (and thus the items), not freeze its text and drop it.
    a = Html("<span>a</span>")
    b = Html("<span>b</span>")
    refs = [weakref.ref(a), weakref.ref(b)]

    result = sidebar([a, b])
    assert isinstance(result, Html)
    assert "<span>a</span>" in result.text
    assert "<span>b</span>" in result.text

    del a, b
    gc.collect()

    assert all(ref() is not None for ref in refs), (
        "sidebar() did not retain its list items; "
        "at least one was garbage collected"
    )


def test_sidebar_retains_item_and_footer() -> None:
    # With a footer, item and footer are combined in a vstack; sidebar must
    # retain it so neither the item nor the footer is collected.
    item = Html("<span>item</span>")
    footer = Html("<span>footer</span>")
    item_ref = weakref.ref(item)
    footer_ref = weakref.ref(footer)

    result = sidebar(item, footer=footer)
    assert isinstance(result, Html)
    assert "<span>item</span>" in result.text
    assert "<span>footer</span>" in result.text

    del item, footer
    gc.collect()

    assert item_ref() is not None, "sidebar() dropped its item (with footer)"
    assert footer_ref() is not None, "sidebar() dropped its footer"


def test_sidebar_retains_list_footer_items() -> None:
    # A list footer is itself wrapped in a vstack before being combined with
    # the item, so the footer's items must survive too.
    f1 = Html("<span>f1</span>")
    f2 = Html("<span>f2</span>")
    refs = [weakref.ref(f1), weakref.ref(f2)]

    result = sidebar("body", footer=[f1, f2])
    assert isinstance(result, Html)
    assert "<span>f1</span>" in result.text
    assert "<span>f2</span>" in result.text

    del f1, f2
    gc.collect()

    assert all(ref() is not None for ref in refs), (
        "sidebar() did not retain its list footer items; "
        "at least one was garbage collected"
    )


def test_sidebar_item_updates_live() -> None:
    # A mutable item (e.g. mo.status.spinner) re-renders on each access rather
    # than being frozen at construction time.
    with mo.status.spinner(title="Loading") as spinner:
        result = sidebar(spinner)
        assert "Loading" in result.text

        spinner.update(title="Done")
        assert "Done" in result.text
        assert "Loading" not in result.text
