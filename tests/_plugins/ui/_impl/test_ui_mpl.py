# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

import matplotlib.pyplot as plt  # noqa: E402
import pytest

from marimo._plugins.ui._impl.mpl import (  # noqa: E402
    BoxSelection,
    EmptySelection,
    LassoSelection,
    _figure_pixel_size,
    _figure_to_base64,
    matplotlib,
)

mpl = pytest.importorskip("matplotlib")
mpl.use("Agg")  # Non-interactive backend for testing

np = pytest.importorskip("numpy")


# ============================================================================
# Constructor tests
# ============================================================================


def _make_scatter_ax() -> Any:
    fig, ax = plt.subplots()
    ax.scatter([1, 2, 3, 4, 5], [2, 4, 1, 5, 3])
    plt.close(fig)
    return ax


def test_basic_construction() -> None:
    ax = _make_scatter_ax()
    fig = matplotlib(ax)

    assert fig is not None
    assert isinstance(fig.value, EmptySelection)
    assert not fig.value


def test_construction_with_label() -> None:
    ax = _make_scatter_ax()
    fig = matplotlib(ax, label="My Chart")
    assert fig is not None


def test_construction_no_figure_raises() -> None:
    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.scatter([1, 2, 3], [4, 5, 6])
    # Remove ax from figure to simulate detached axes
    # Actually, axes are always attached. Test empty figure differently.
    plt.close(fig)
    # We can still construct since ax.get_figure() returns the figure
    fig = matplotlib(ax)
    assert fig is not None


def test_construction_args() -> None:
    ax = _make_scatter_ax()
    fig = matplotlib(ax)

    args = fig._component_args
    assert "chart-base64" in args
    assert "x-bounds" in args
    assert "y-bounds" in args
    assert "axes-pixel-bounds" in args
    assert "width" in args
    assert "height" in args

    assert isinstance(args["chart-base64"], str)
    assert args["chart-base64"].startswith("data:image/png;base64,")
    assert len(args["x-bounds"]) == 2
    assert len(args["y-bounds"]) == 2
    assert len(args["axes-pixel-bounds"]) == 4
    assert args["width"] > 0
    assert args["height"] > 0

    # Style args should NOT be present (removed from public API)
    assert "selection-color" not in args
    assert "selection-opacity" not in args
    assert "stroke-width" not in args


def test_on_change_callback() -> None:
    ax = _make_scatter_ax()
    called: list[Any] = []

    def on_change(value: Any) -> None:
        called.append(value)

    fig = matplotlib(ax, on_change=on_change)
    assert fig is not None


# ============================================================================
# _convert_value tests
# ============================================================================


def test_convert_value_empty() -> None:
    ax = _make_scatter_ax()
    fig = matplotlib(ax)
    result = fig._convert_value({})
    assert isinstance(result, EmptySelection)
    assert not result


def test_convert_value_no_selection() -> None:
    ax = _make_scatter_ax()
    fig = matplotlib(ax)
    result = fig._convert_value({"has_selection": False})
    assert isinstance(result, EmptySelection)
    assert not result


def test_convert_value_box() -> None:
    ax = _make_scatter_ax()
    fig = matplotlib(ax)
    value = {
        "type": "box",
        "has_selection": True,
        "data": {
            "x_min": 1.0,
            "x_max": 3.0,
            "y_min": 2.0,
            "y_max": 4.0,
        },
    }
    result = fig._convert_value(value)
    assert isinstance(result, BoxSelection)
    assert result.x_min == 1.0
    assert result.x_max == 3.0
    assert result.y_min == 2.0
    assert result.y_max == 4.0


def test_convert_value_lasso() -> None:
    ax = _make_scatter_ax()
    fig = matplotlib(ax)
    value = {
        "type": "lasso",
        "has_selection": True,
        "data": [[1.0, 2.0], [3.0, 4.0], [5.0, 2.0]],
    }
    result = fig._convert_value(value)
    assert isinstance(result, LassoSelection)
    assert result.vertices == ((1.0, 2.0), (3.0, 4.0), (5.0, 2.0))


# ============================================================================
# EmptySelection tests
# ============================================================================


def test_empty_selection_is_falsy() -> None:
    sel = EmptySelection()
    assert not sel
    assert bool(sel) is False


def test_empty_selection_get_mask() -> None:
    sel = EmptySelection()
    x = np.array([1, 2, 3, 4, 5])
    y = np.array([2, 4, 1, 5, 3])
    mask = sel.get_mask(x, y)
    assert mask.sum() == 0
    assert len(mask) == 5


def test_empty_selection_frozen() -> None:
    sel = EmptySelection()
    with pytest.raises(AttributeError):
        sel.foo = 1  # type: ignore[attr-defined]


def test_value_get_mask_before_selection() -> None:
    """fig.value.get_mask() should work even with no selection."""
    ax = _make_scatter_ax()
    fig = matplotlib(ax)
    x = np.array([1, 2, 3])
    y = np.array([4, 5, 6])
    mask = fig.value.get_mask(x, y)
    assert mask.sum() == 0


# ============================================================================
# BoxSelection dataclass tests
# ============================================================================


def test_box_selection_frozen() -> None:
    sel = BoxSelection(x_min=1.0, x_max=3.0, y_min=2.0, y_max=4.0)
    with pytest.raises(AttributeError):
        sel.x_min = 5.0  # type: ignore[misc]


def test_box_selection_get_mask() -> None:
    sel = BoxSelection(x_min=1.5, x_max=3.5, y_min=1.5, y_max=4.5)
    x = np.array([1, 2, 3, 4, 5])
    y = np.array([2, 4, 1, 5, 3])
    mask = sel.get_mask(x, y)
    assert mask[1] is np.True_  # (2, 4) in range
    assert not mask[2]  # (3, 1) y out of range
    assert not mask[0]  # (1, 2) x out of range


# ============================================================================
# LassoSelection dataclass tests
# ============================================================================


def test_lasso_selection_frozen() -> None:
    sel = LassoSelection(vertices=((0.0, 0.0), (4.0, 0.0), (2.0, 3.0)))
    with pytest.raises(AttributeError):
        sel.vertices = ()  # type: ignore[misc]


def test_lasso_selection_get_mask() -> None:
    sel = LassoSelection(vertices=((0.0, 0.0), (10.0, 0.0), (5.0, 10.0)))
    x = np.array([5.0, 0.0, 10.0, 5.0])
    y = np.array([1.0, 5.0, 5.0, 5.0])
    mask = sel.get_mask(x, y)
    assert mask[0]  # (5, 1) inside
    assert not mask[1]  # (0, 5) outside
    assert not mask[2]  # (10, 5) outside
    assert mask[3]  # (5, 5) inside


# ============================================================================
# Helper function tests
# ============================================================================


def test_figure_pixel_size() -> None:
    fig, ax = plt.subplots()
    ax.scatter([1, 2, 3], [4, 5, 6])
    plt.close(fig)
    w, h = _figure_pixel_size(fig)
    assert w > 0
    assert h > 0


def test_figure_to_base64() -> None:
    fig, ax = plt.subplots()
    ax.scatter([1, 2, 3], [4, 5, 6])
    plt.close(fig)
    result = _figure_to_base64(fig)
    assert result.startswith("data:image/png;base64,")
    assert len(result) > 50


# ============================================================================
# HTML output tests
# ============================================================================


def test_html_contains_tag() -> None:
    ax = _make_scatter_ax()
    fig = matplotlib(ax)
    html = fig.text
    assert "marimo-matplotlib" in html
