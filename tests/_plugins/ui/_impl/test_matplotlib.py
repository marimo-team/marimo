# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

import pytest

mpl = pytest.importorskip("matplotlib")
mpl.use("Agg")  # Non-interactive backend for testing

import matplotlib.pyplot as plt  # noqa: E402

from marimo._plugins.ui._impl.matplotlib import (  # noqa: E402
    _figure_pixel_size,
    _figure_to_base64,
    matplotlib,
)

np = pytest.importorskip("numpy")


# ============================================================================
# Constructor tests
# ============================================================================


def _make_scatter_figure() -> Any:
    fig, ax = plt.subplots()
    ax.scatter([1, 2, 3, 4, 5], [2, 4, 1, 5, 3])
    plt.close(fig)
    return fig


def test_basic_construction() -> None:
    fig = _make_scatter_figure()
    chart = matplotlib(fig)

    assert chart is not None
    assert chart.value is None


def test_construction_with_label() -> None:
    fig = _make_scatter_figure()
    chart = matplotlib(fig, label="My Chart")
    assert chart is not None


def test_construction_with_style_options() -> None:
    fig = _make_scatter_figure()
    chart = matplotlib(
        fig,
        selection_color="#ff0000",
        selection_opacity=0.3,
        stroke_width=4,
    )
    assert chart._component_args["selection-color"] == "#ff0000"
    assert chart._component_args["selection-opacity"] == 0.3
    assert chart._component_args["stroke-width"] == 4


def test_construction_no_axes_raises() -> None:
    fig = plt.figure()
    plt.close(fig)
    with pytest.raises(ValueError, match="at least one axes"):
        matplotlib(fig)


def test_construction_args() -> None:
    fig = _make_scatter_figure()
    chart = matplotlib(fig)

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


def test_on_change_callback() -> None:
    fig = _make_scatter_figure()
    called: list[Any] = []

    def on_change(value: Any) -> None:
        called.append(value)

    chart = matplotlib(fig, on_change=on_change)
    assert chart is not None


# ============================================================================
# _convert_value tests
# ============================================================================


def test_convert_value_empty() -> None:
    fig = _make_scatter_figure()
    chart = matplotlib(fig)
    assert chart._convert_value({}) is None


def test_convert_value_no_selection() -> None:
    fig = _make_scatter_figure()
    chart = matplotlib(fig)
    assert chart._convert_value({"has_selection": False}) is None


def test_convert_value_box() -> None:
    fig = _make_scatter_figure()
    chart = matplotlib(fig)
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
    assert result == {
        "type": "box",
        "data": {
            "x_min": 1.0,
            "x_max": 3.0,
            "y_min": 2.0,
            "y_max": 4.0,
        },
    }


def test_convert_value_lasso() -> None:
    fig = _make_scatter_figure()
    chart = matplotlib(fig)
    value = {
        "type": "lasso",
        "has_selection": True,
        "data": [[1.0, 2.0], [3.0, 4.0], [5.0, 2.0]],
    }
    result = chart._convert_value(value)
    assert result == {
        "type": "lasso",
        "data": [(1.0, 2.0), (3.0, 4.0), (5.0, 2.0)],
    }


# ============================================================================
# get_bounds tests
# ============================================================================


def test_get_bounds_no_selection() -> None:
    fig = _make_scatter_figure()
    chart = matplotlib(fig)
    assert chart.get_bounds() is None


def test_get_bounds_box() -> None:
    fig = _make_scatter_figure()
    chart = matplotlib(fig)
    chart._value = {
        "type": "box",
        "data": {
            "x_min": 1.0,
            "x_max": 3.0,
            "y_min": 2.0,
            "y_max": 4.0,
        },
    }
    assert chart.get_bounds() == (1.0, 3.0, 2.0, 4.0)


def test_get_bounds_lasso() -> None:
    fig = _make_scatter_figure()
    chart = matplotlib(fig)
    chart._value = {
        "type": "lasso",
        "data": [(0.0, 0.0), (4.0, 0.0), (2.0, 3.0)],
    }
    assert chart.get_bounds() == (0.0, 4.0, 0.0, 3.0)


# ============================================================================
# get_vertices tests
# ============================================================================


def test_get_vertices_no_selection() -> None:
    fig = _make_scatter_figure()
    chart = matplotlib(fig)
    assert chart.get_vertices() == []


def test_get_vertices_box() -> None:
    fig = _make_scatter_figure()
    chart = matplotlib(fig)
    chart._value = {
        "type": "box",
        "data": {
            "x_min": 1.0,
            "x_max": 3.0,
            "y_min": 2.0,
            "y_max": 4.0,
        },
    }
    verts = chart.get_vertices()
    assert len(verts) == 4
    assert verts[0] == (1.0, 2.0)
    assert verts[1] == (3.0, 2.0)
    assert verts[2] == (3.0, 4.0)
    assert verts[3] == (1.0, 4.0)


def test_get_vertices_lasso() -> None:
    fig = _make_scatter_figure()
    chart = matplotlib(fig)
    chart._value = {
        "type": "lasso",
        "data": [(1.0, 2.0), (3.0, 4.0), (5.0, 2.0)],
    }
    verts = chart.get_vertices()
    assert len(verts) == 3
    assert verts[0] == (1.0, 2.0)
    assert verts[1] == (3.0, 4.0)
    assert verts[2] == (5.0, 2.0)


# ============================================================================
# contains_point tests
# ============================================================================


def test_contains_point_no_selection() -> None:
    fig = _make_scatter_figure()
    chart = matplotlib(fig)
    assert chart.contains_point(2.0, 3.0) is False


def test_contains_point_box() -> None:
    fig = _make_scatter_figure()
    chart = matplotlib(fig)
    chart._value = {
        "type": "box",
        "data": {
            "x_min": 1.0,
            "x_max": 3.0,
            "y_min": 2.0,
            "y_max": 4.0,
        },
    }
    assert chart.contains_point(2.0, 3.0) is True
    assert chart.contains_point(0.0, 3.0) is False
    assert chart.contains_point(2.0, 5.0) is False


def test_contains_point_lasso() -> None:
    fig = _make_scatter_figure()
    chart = matplotlib(fig)
    # Triangle: (0,0), (4,0), (2,3)
    chart._value = {
        "type": "lasso",
        "data": [(0.0, 0.0), (4.0, 0.0), (2.0, 3.0)],
    }
    # Point inside the triangle
    assert chart.contains_point(2.0, 1.0) is True
    # Point outside the triangle
    assert chart.contains_point(0.0, 3.0) is False
    assert chart.contains_point(5.0, 5.0) is False


# ============================================================================
# get_mask tests
# ============================================================================


def test_get_mask_no_selection() -> None:
    fig = _make_scatter_figure()
    chart = matplotlib(fig)

    x = np.array([1, 2, 3])
    y = np.array([2, 3, 4])
    mask = chart.get_mask(x, y)
    assert mask.sum() == 0


def test_get_mask_box() -> None:
    fig = _make_scatter_figure()
    chart = matplotlib(fig)
    chart._value = {
        "type": "box",
        "data": {
            "x_min": 1.5,
            "x_max": 3.5,
            "y_min": 1.5,
            "y_max": 4.5,
        },
    }

    x = np.array([1, 2, 3, 4, 5])
    y = np.array([2, 4, 1, 5, 3])
    mask = chart.get_mask(x, y)

    # x=2,y=4 is in [1.5,3.5]x[1.5,4.5] -> True
    # x=3,y=1 is NOT in range (y=1 < 1.5) -> False
    assert mask[1] is np.True_  # (2, 4)
    assert not mask[2]  # (3, 1) - y out of range
    assert not mask[0]  # (1, 2) - x out of range


def test_get_mask_lasso() -> None:
    fig = _make_scatter_figure()
    chart = matplotlib(fig)
    # Triangle: (0,0), (10,0), (5,10)
    chart._value = {
        "type": "lasso",
        "data": [(0.0, 0.0), (10.0, 0.0), (5.0, 10.0)],
    }

    x = np.array([5.0, 0.0, 10.0, 5.0])
    y = np.array([1.0, 5.0, 5.0, 5.0])
    mask = chart.get_mask(x, y)

    # (5, 1) is inside the triangle
    assert mask[0]
    # (0, 5) is outside (left edge)
    assert not mask[1]
    # (10, 5) is outside (right edge)
    assert not mask[2]
    # (5, 5) is inside the triangle (center)
    assert mask[3]


# ============================================================================
# get_indices tests
# ============================================================================


def test_get_indices_no_selection() -> None:
    fig = _make_scatter_figure()
    chart = matplotlib(fig)

    x = np.array([1, 2, 3])
    y = np.array([2, 3, 4])
    indices = chart.get_indices(x, y)
    assert len(indices) == 0


def test_get_indices_box() -> None:
    fig = _make_scatter_figure()
    chart = matplotlib(fig)
    chart._value = {
        "type": "box",
        "data": {
            "x_min": 1.5,
            "x_max": 3.5,
            "y_min": 1.5,
            "y_max": 4.5,
        },
    }

    x = np.array([1, 2, 3, 4, 5])
    y = np.array([2, 4, 1, 5, 3])
    indices = chart.get_indices(x, y)
    assert isinstance(indices, np.ndarray)
    # Point (2, 4) at index 1 should be in range
    assert 1 in indices


def test_get_indices_lasso() -> None:
    fig = _make_scatter_figure()
    chart = matplotlib(fig)
    # Triangle: (0,0), (10,0), (5,10)
    chart._value = {
        "type": "lasso",
        "data": [(0.0, 0.0), (10.0, 0.0), (5.0, 10.0)],
    }

    x = np.array([5.0, 0.0, 10.0, 5.0])
    y = np.array([1.0, 5.0, 5.0, 5.0])
    indices = chart.get_indices(x, y)
    assert isinstance(indices, np.ndarray)
    # (5, 1) at index 0 and (5, 5) at index 3 are inside
    assert 0 in indices
    assert 3 in indices
    # (0, 5) at index 1 and (10, 5) at index 2 are outside
    assert 1 not in indices
    assert 2 not in indices


# ============================================================================
# Helper function tests
# ============================================================================


def test_figure_pixel_size() -> None:
    fig = _make_scatter_figure()
    w, h = _figure_pixel_size(fig)
    assert w > 0
    assert h > 0


def test_figure_to_base64() -> None:
    fig = _make_scatter_figure()
    result = _figure_to_base64(fig)
    assert result.startswith("data:image/png;base64,")
    assert len(result) > 50


# ============================================================================
# HTML output tests
# ============================================================================


def test_html_contains_tag() -> None:
    fig = _make_scatter_figure()
    chart = matplotlib(fig)
    html = chart.text
    assert "marimo-matplotlib" in html
