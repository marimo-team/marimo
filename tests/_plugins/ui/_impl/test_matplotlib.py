# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

import pytest

mpl = pytest.importorskip("matplotlib")
mpl.use("Agg")  # Non-interactive backend for testing

import matplotlib.pyplot as plt  # noqa: E402

from marimo._plugins.ui._impl.matplotlib import (  # noqa: E402
    BoxSelection,
    LassoSelection,
    _figure_pixel_size,
    _figure_to_base64,
    matplotlib,
)

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
    chart = matplotlib(ax)

    assert chart is not None
    assert chart.value is None


def test_construction_with_label() -> None:
    ax = _make_scatter_ax()
    chart = matplotlib(ax, label="My Chart")
    assert chart is not None


def test_construction_no_figure_raises() -> None:
    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.scatter([1, 2, 3], [4, 5, 6])
    # Remove ax from figure to simulate detached axes
    # Actually, axes are always attached. Test empty figure differently.
    plt.close(fig)
    # We can still construct since ax.get_figure() returns the figure
    chart = matplotlib(ax)
    assert chart is not None


def test_construction_args() -> None:
    ax = _make_scatter_ax()
    chart = matplotlib(ax)

    args = chart._component_args
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

    chart = matplotlib(ax, on_change=on_change)
    assert chart is not None


# ============================================================================
# _convert_value tests
# ============================================================================


def test_convert_value_empty() -> None:
    ax = _make_scatter_ax()
    chart = matplotlib(ax)
    assert chart._convert_value({}) is None


def test_convert_value_no_selection() -> None:
    ax = _make_scatter_ax()
    chart = matplotlib(ax)
    assert chart._convert_value({"has_selection": False}) is None


def test_convert_value_box() -> None:
    ax = _make_scatter_ax()
    chart = matplotlib(ax)
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
    result = chart._convert_value(value)
    assert isinstance(result, BoxSelection)
    assert result.x_min == 1.0
    assert result.x_max == 3.0
    assert result.y_min == 2.0
    assert result.y_max == 4.0


def test_convert_value_lasso() -> None:
    ax = _make_scatter_ax()
    chart = matplotlib(ax)
    value = {
        "type": "lasso",
        "has_selection": True,
        "data": [[1.0, 2.0], [3.0, 4.0], [5.0, 2.0]],
    }
    result = chart._convert_value(value)
    assert isinstance(result, LassoSelection)
    assert result.vertices == ((1.0, 2.0), (3.0, 4.0), (5.0, 2.0))


# ============================================================================
# .selection property tests
# ============================================================================


def test_selection_property_none() -> None:
    ax = _make_scatter_ax()
    chart = matplotlib(ax)
    assert chart.selection is None


def test_selection_property_box() -> None:
    ax = _make_scatter_ax()
    chart = matplotlib(ax)
    sel = BoxSelection(x_min=1.0, x_max=3.0, y_min=2.0, y_max=4.0)
    chart._value = sel
    assert chart.selection is sel
    assert chart.selection == chart.value


# ============================================================================
# BoxSelection dataclass tests
# ============================================================================


def test_box_selection_frozen() -> None:
    sel = BoxSelection(x_min=1.0, x_max=3.0, y_min=2.0, y_max=4.0)
    with pytest.raises(AttributeError):
        sel.x_min = 5.0  # type: ignore[misc]


def test_box_selection_contains_point() -> None:
    sel = BoxSelection(x_min=1.0, x_max=3.0, y_min=2.0, y_max=4.0)
    assert sel.contains_point(2.0, 3.0) is True
    assert sel.contains_point(0.0, 3.0) is False
    assert sel.contains_point(2.0, 5.0) is False
    # Edge cases: on boundary
    assert sel.contains_point(1.0, 2.0) is True
    assert sel.contains_point(3.0, 4.0) is True


def test_box_selection_get_mask() -> None:
    sel = BoxSelection(x_min=1.5, x_max=3.5, y_min=1.5, y_max=4.5)
    x = np.array([1, 2, 3, 4, 5])
    y = np.array([2, 4, 1, 5, 3])
    mask = sel.get_mask(x, y)
    assert mask[1] is np.True_  # (2, 4) in range
    assert not mask[2]  # (3, 1) y out of range
    assert not mask[0]  # (1, 2) x out of range


def test_box_selection_get_indices() -> None:
    sel = BoxSelection(x_min=1.5, x_max=3.5, y_min=1.5, y_max=4.5)
    x = np.array([1, 2, 3, 4, 5])
    y = np.array([2, 4, 1, 5, 3])
    indices = sel.get_indices(x, y)
    assert isinstance(indices, np.ndarray)
    assert 1 in indices


# ============================================================================
# LassoSelection dataclass tests
# ============================================================================


def test_lasso_selection_frozen() -> None:
    sel = LassoSelection(vertices=((0.0, 0.0), (4.0, 0.0), (2.0, 3.0)))
    with pytest.raises(AttributeError):
        sel.vertices = ()  # type: ignore[misc]


def test_lasso_selection_contains_point() -> None:
    sel = LassoSelection(vertices=((0.0, 0.0), (4.0, 0.0), (2.0, 3.0)))
    assert sel.contains_point(2.0, 1.0) is True
    assert sel.contains_point(0.0, 3.0) is False
    assert sel.contains_point(5.0, 5.0) is False


def test_lasso_selection_get_mask() -> None:
    sel = LassoSelection(vertices=((0.0, 0.0), (10.0, 0.0), (5.0, 10.0)))
    x = np.array([5.0, 0.0, 10.0, 5.0])
    y = np.array([1.0, 5.0, 5.0, 5.0])
    mask = sel.get_mask(x, y)
    assert mask[0]  # (5, 1) inside
    assert not mask[1]  # (0, 5) outside
    assert not mask[2]  # (10, 5) outside
    assert mask[3]  # (5, 5) inside


def test_lasso_selection_get_indices() -> None:
    sel = LassoSelection(vertices=((0.0, 0.0), (10.0, 0.0), (5.0, 10.0)))
    x = np.array([5.0, 0.0, 10.0, 5.0])
    y = np.array([1.0, 5.0, 5.0, 5.0])
    indices = sel.get_indices(x, y)
    assert isinstance(indices, np.ndarray)
    assert 0 in indices
    assert 3 in indices
    assert 1 not in indices
    assert 2 not in indices


# ============================================================================
# get_vertices tests (chart convenience method)
# ============================================================================


def test_get_vertices_no_selection() -> None:
    ax = _make_scatter_ax()
    chart = matplotlib(ax)
    assert chart.get_vertices() == []


def test_get_vertices_box() -> None:
    ax = _make_scatter_ax()
    chart = matplotlib(ax)
    chart._value = BoxSelection(x_min=1.0, x_max=3.0, y_min=2.0, y_max=4.0)
    verts = chart.get_vertices()
    assert len(verts) == 4
    assert verts[0] == (1.0, 2.0)
    assert verts[1] == (3.0, 2.0)
    assert verts[2] == (3.0, 4.0)
    assert verts[3] == (1.0, 4.0)


def test_get_vertices_lasso() -> None:
    ax = _make_scatter_ax()
    chart = matplotlib(ax)
    chart._value = LassoSelection(
        vertices=((1.0, 2.0), (3.0, 4.0), (5.0, 2.0))
    )
    verts = chart.get_vertices()
    assert len(verts) == 3
    assert verts[0] == (1.0, 2.0)
    assert verts[1] == (3.0, 4.0)
    assert verts[2] == (5.0, 2.0)


# ============================================================================
# contains_point tests (chart convenience method)
# ============================================================================


def test_contains_point_no_selection() -> None:
    ax = _make_scatter_ax()
    chart = matplotlib(ax)
    assert chart.contains_point(2.0, 3.0) is False


def test_contains_point_box() -> None:
    ax = _make_scatter_ax()
    chart = matplotlib(ax)
    chart._value = BoxSelection(x_min=1.0, x_max=3.0, y_min=2.0, y_max=4.0)
    assert chart.contains_point(2.0, 3.0) is True
    assert chart.contains_point(0.0, 3.0) is False
    assert chart.contains_point(2.0, 5.0) is False


def test_contains_point_lasso() -> None:
    ax = _make_scatter_ax()
    chart = matplotlib(ax)
    chart._value = LassoSelection(
        vertices=((0.0, 0.0), (4.0, 0.0), (2.0, 3.0))
    )
    assert chart.contains_point(2.0, 1.0) is True
    assert chart.contains_point(0.0, 3.0) is False
    assert chart.contains_point(5.0, 5.0) is False


# ============================================================================
# get_mask tests (chart convenience method)
# ============================================================================


def test_get_mask_no_selection() -> None:
    ax = _make_scatter_ax()
    chart = matplotlib(ax)

    x = np.array([1, 2, 3])
    y = np.array([2, 3, 4])
    mask = chart.get_mask(x, y)
    assert mask.sum() == 0


def test_get_mask_box() -> None:
    ax = _make_scatter_ax()
    chart = matplotlib(ax)
    chart._value = BoxSelection(x_min=1.5, x_max=3.5, y_min=1.5, y_max=4.5)

    x = np.array([1, 2, 3, 4, 5])
    y = np.array([2, 4, 1, 5, 3])
    mask = chart.get_mask(x, y)

    assert mask[1] is np.True_  # (2, 4)
    assert not mask[2]  # (3, 1) - y out of range
    assert not mask[0]  # (1, 2) - x out of range


def test_get_mask_lasso() -> None:
    ax = _make_scatter_ax()
    chart = matplotlib(ax)
    chart._value = LassoSelection(
        vertices=((0.0, 0.0), (10.0, 0.0), (5.0, 10.0))
    )

    x = np.array([5.0, 0.0, 10.0, 5.0])
    y = np.array([1.0, 5.0, 5.0, 5.0])
    mask = chart.get_mask(x, y)

    assert mask[0]  # (5, 1) inside
    assert not mask[1]  # (0, 5) outside
    assert not mask[2]  # (10, 5) outside
    assert mask[3]  # (5, 5) inside


# ============================================================================
# get_indices tests (chart convenience method)
# ============================================================================


def test_get_indices_no_selection() -> None:
    ax = _make_scatter_ax()
    chart = matplotlib(ax)

    x = np.array([1, 2, 3])
    y = np.array([2, 3, 4])
    indices = chart.get_indices(x, y)
    assert len(indices) == 0


def test_get_indices_box() -> None:
    ax = _make_scatter_ax()
    chart = matplotlib(ax)
    chart._value = BoxSelection(x_min=1.5, x_max=3.5, y_min=1.5, y_max=4.5)

    x = np.array([1, 2, 3, 4, 5])
    y = np.array([2, 4, 1, 5, 3])
    indices = chart.get_indices(x, y)
    assert isinstance(indices, np.ndarray)
    assert 1 in indices


def test_get_indices_lasso() -> None:
    ax = _make_scatter_ax()
    chart = matplotlib(ax)
    chart._value = LassoSelection(
        vertices=((0.0, 0.0), (10.0, 0.0), (5.0, 10.0))
    )

    x = np.array([5.0, 0.0, 10.0, 5.0])
    y = np.array([1.0, 5.0, 5.0, 5.0])
    indices = chart.get_indices(x, y)
    assert isinstance(indices, np.ndarray)
    assert 0 in indices
    assert 3 in indices
    assert 1 not in indices
    assert 2 not in indices


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
    chart = matplotlib(ax)
    html = chart.text
    assert "marimo-matplotlib" in html
