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
    assert chart.value == {}


def test_construction_with_label() -> None:
    fig = _make_scatter_figure()
    chart = matplotlib(fig, label="My Chart")
    assert chart is not None


def test_construction_with_modes() -> None:
    fig = _make_scatter_figure()
    chart = matplotlib(fig, modes=["box"])
    assert chart._component_args["modes"] == ["box"]


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
    assert "modes" in args

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
    assert chart._convert_value({}) == {}


def test_convert_value_no_selection() -> None:
    fig = _make_scatter_figure()
    chart = matplotlib(fig)
    assert chart._convert_value({"has_selection": False}) == {}


def test_convert_value_box() -> None:
    fig = _make_scatter_figure()
    chart = matplotlib(fig)
    value = {
        "mode": "box",
        "has_selection": True,
        "selection": {
            "x_min": 1.0,
            "x_max": 3.0,
            "y_min": 2.0,
            "y_max": 4.0,
        },
    }
    result = chart._convert_value(value)
    assert result == value


def test_convert_value_lasso() -> None:
    fig = _make_scatter_figure()
    chart = matplotlib(fig)
    value = {
        "mode": "lasso",
        "has_selection": True,
        "selection": {
            "vertices": [[1.0, 2.0], [3.0, 4.0], [2.0, 1.0]],
        },
    }
    result = chart._convert_value(value)
    assert result == value


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
        "mode": "box",
        "has_selection": True,
        "selection": {
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
        "mode": "lasso",
        "has_selection": True,
        "selection": {
            "vertices": [[1.0, 2.0], [4.0, 5.0], [3.0, 1.0]],
        },
    }
    bounds = chart.get_bounds()
    assert bounds is not None
    assert bounds == (1.0, 4.0, 1.0, 5.0)


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
        "mode": "box",
        "has_selection": True,
        "selection": {
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
        "mode": "lasso",
        "has_selection": True,
        "selection": {
            "vertices": [[1.0, 2.0], [3.0, 4.0], [2.0, 1.0]],
        },
    }
    verts = chart.get_vertices()
    assert len(verts) == 3
    assert verts[0] == (1.0, 2.0)
    assert verts[1] == (3.0, 4.0)
    assert verts[2] == (2.0, 1.0)


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
        "mode": "box",
        "has_selection": True,
        "selection": {
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
    # Triangle: (0,0), (10,0), (5,10)
    chart._value = {
        "mode": "lasso",
        "has_selection": True,
        "selection": {
            "vertices": [[0, 0], [10, 0], [5, 10]],
        },
    }
    assert chart.contains_point(5, 3) is True
    assert chart.contains_point(20, 20) is False


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
        "mode": "box",
        "has_selection": True,
        "selection": {
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
    # Triangle containing points near center
    chart._value = {
        "mode": "lasso",
        "has_selection": True,
        "selection": {
            "vertices": [[1, 1], [5, 1], [3, 6]],
        },
    }

    x = np.array([1, 2, 3, 4, 5])
    y = np.array([2, 4, 1, 5, 3])
    mask = chart.get_mask(x, y)
    assert isinstance(mask, np.ndarray)
    assert mask.dtype == bool


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
        "mode": "box",
        "has_selection": True,
        "selection": {
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
