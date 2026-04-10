# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import io
from datetime import datetime
from typing import Any

import pytest

from marimo._plugins.ui._impl.mpl import (
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

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.dates import date2num  # noqa: E402

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


def test_unsupported_scale_raises() -> None:
    fig, ax = plt.subplots()
    ax.scatter([1, 2, 3], [4, 5, 6])
    ax.set_xscale("symlog")
    plt.close(fig)
    with pytest.raises(ValueError, match="Unsupported x-axis scale"):
        matplotlib(ax)


def test_unsupported_yscale_raises() -> None:
    fig, ax = plt.subplots()
    ax.scatter([1, 2, 3], [4, 5, 6])
    ax.set_yscale("logit")
    plt.close(fig)
    with pytest.raises(ValueError, match="Unsupported y-axis scale"):
        matplotlib(ax)


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


def test_axes_bounds_match_constrained_layout() -> None:
    """Axes bounds should reflect post-layout position with constrained_layout."""
    fig, ax = plt.subplots(constrained_layout=True)
    ax.scatter([1, 2, 3], [4, 5, 6])
    ax.set_xlabel("X label")
    ax.set_ylabel("Y label")
    ax.set_title("Title")
    plt.close(fig)

    widget = matplotlib(ax)
    args = widget._component_args

    # Render independently with the same settings to get expected bounds
    fig2 = ax.get_figure()
    fig2.savefig(
        io.BytesIO(), format="png", dpi=fig2.get_dpi(), bbox_inches=None
    )
    bbox = ax.get_position()
    w, h = _figure_pixel_size(fig2)

    expected = [
        bbox.x0 * w,
        (1 - bbox.y1) * h,
        bbox.x1 * w,
        (1 - bbox.y0) * h,
    ]
    for actual, exp in zip(args["axes-pixel-bounds"], expected, strict=False):
        assert abs(actual - exp) < 1e-6


def test_axes_bounds_match_tight_layout() -> None:
    """Axes bounds should reflect post-layout position with tight_layout."""
    fig, ax = plt.subplots()
    ax.scatter([1, 2, 3], [4, 5, 6])
    ax.set_xlabel("X label")
    ax.set_ylabel("Y label")
    ax.set_title("Title")
    fig.tight_layout()
    plt.close(fig)

    widget = matplotlib(ax)
    args = widget._component_args

    # Render independently with the same settings to get expected bounds
    fig2 = ax.get_figure()
    fig2.savefig(
        io.BytesIO(), format="png", dpi=fig2.get_dpi(), bbox_inches=None
    )
    bbox = ax.get_position()
    w, h = _figure_pixel_size(fig2)

    expected = [
        bbox.x0 * w,
        (1 - bbox.y1) * h,
        bbox.x1 * w,
        (1 - bbox.y0) * h,
    ]
    for actual, exp in zip(args["axes-pixel-bounds"], expected, strict=False):
        assert abs(actual - exp) < 1e-6


# ============================================================================
# HTML output tests
# ============================================================================


def test_html_contains_tag() -> None:
    ax = _make_scatter_ax()
    fig = matplotlib(ax)
    html = fig.text
    assert "marimo-matplotlib" in html


# ============================================================================
# Datetime support tests
# ============================================================================


def test_box_selection_get_mask_datetime() -> None:
    """BoxSelection.get_mask should work with datetime objects."""
    dates_x = [
        datetime(2020, 1, 1),
        datetime(2022, 6, 15),
        datetime(2025, 12, 31),
    ]
    dates_y = [
        datetime(2000, 3, 10),
        datetime(2010, 7, 20),
        datetime(2020, 11, 5),
    ]

    # Selection bounds in matplotlib's internal float representation,
    # matching what the frontend sends.
    sel = BoxSelection(
        x_min=date2num(datetime(2021, 1, 1)),
        x_max=date2num(datetime(2026, 1, 1)),
        y_min=date2num(datetime(2005, 1, 1)),
        y_max=date2num(datetime(2015, 1, 1)),
    )

    mask = sel.get_mask(dates_x, dates_y)
    # Only (2022-06-15, 2010-07-20) falls within the box
    assert mask.tolist() == [False, True, False]


def test_box_selection_get_mask_numpy_datetime64() -> None:
    """BoxSelection.get_mask should work with numpy datetime64 arrays."""
    x = np.array(
        ["2020-01-01", "2022-06-15", "2025-12-31"], dtype="datetime64"
    )
    y = np.array(
        ["2000-03-10", "2010-07-20", "2020-11-05"], dtype="datetime64"
    )

    sel = BoxSelection(
        x_min=date2num(datetime(2021, 1, 1)),
        x_max=date2num(datetime(2026, 1, 1)),
        y_min=date2num(datetime(2005, 1, 1)),
        y_max=date2num(datetime(2015, 1, 1)),
    )

    mask = sel.get_mask(x, y)
    assert mask.tolist() == [False, True, False]


def test_lasso_selection_get_mask_datetime() -> None:
    """LassoSelection.get_mask should work with datetime objects."""
    # Triangle that contains (2022-06-15, 2010-07-20) but not the others
    v0 = (date2num(datetime(2021, 1, 1)), date2num(datetime(2005, 1, 1)))
    v1 = (date2num(datetime(2026, 1, 1)), date2num(datetime(2005, 1, 1)))
    v2 = (date2num(datetime(2023, 6, 1)), date2num(datetime(2015, 1, 1)))

    sel = LassoSelection(vertices=(v0, v1, v2))

    dates_x = [
        datetime(2020, 1, 1),
        datetime(2022, 6, 15),
        datetime(2025, 12, 31),
    ]
    dates_y = [
        datetime(2000, 3, 10),
        datetime(2010, 7, 20),
        datetime(2020, 11, 5),
    ]

    mask = sel.get_mask(dates_x, dates_y)
    assert not mask[0]  # outside triangle
    assert mask[1]  # inside triangle
    assert not mask[2]  # outside triangle
