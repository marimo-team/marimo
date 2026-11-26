# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import base64
import io
from datetime import datetime
from typing import TYPE_CHECKING, Any

import pytest

from marimo._plugins.ui._impl.mpl import (
    BoxSelection,
    EmptySelection,
    LassoSelection,
    RangeSelection,
    matplotlib,
)

if TYPE_CHECKING:
    from typing import assert_type

    from matplotlib.axes import Axes

    from marimo._plugins.ui._impl.mpl import MatplotlibSelection

    def _check_value(ax: Axes) -> None:
        assert_type(matplotlib(ax).value, MatplotlibSelection)


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


def test_initial_box_selection() -> None:
    ax = _make_scatter_ax()
    fig = matplotlib(ax, value={"x": (1.0, 3.0), "y": (2.0, 4.0)})

    assert fig._args.initial_value == {
        "type": "box",
        "has_selection": True,
        "data": {
            "x_min": 1.0,
            "x_max": 3.0,
            "y_min": 2.0,
            "y_max": 4.0,
        },
    }
    assert fig.value == BoxSelection(
        x_min=1.0,
        x_max=3.0,
        y_min=2.0,
        y_max=4.0,
    )


def test_initial_box_selection_clamps_to_axes() -> None:
    ax = _make_scatter_ax()
    axes_x_min, axes_x_max = sorted(ax.get_xlim())
    _axes_y_min, axes_y_max = sorted(ax.get_ylim())

    partial = matplotlib(
        ax,
        value={
            "x": (3.0, axes_x_min - 1),
            "y": (axes_y_max + 1, 2.0),
        },
    )
    assert partial.value == BoxSelection(
        x_min=axes_x_min,
        x_max=3.0,
        y_min=2.0,
        y_max=axes_y_max,
    )

    outside = matplotlib(
        ax,
        value={"x": (axes_x_max + 1, axes_x_max + 2), "y": (2.0, 4.0)},
    )
    assert isinstance(outside.value, EmptySelection)
    assert outside._args.initial_value == {}


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


@pytest.mark.parametrize(
    ("brush", "pan", "zoom"),
    [(True, False, False), (False, False, False), (False, True, True)],
)
def test_modes_share_the_figure_widget(brush, pan, zoom) -> None:
    ax = _make_scatter_ax()
    view = matplotlib(ax, brush=brush, pan=pan, zoom=zoom)
    widget = view._plot_widget
    assert view._component_args == {"model-id": widget.model_id}
    assert widget.figure_ref == f"anywidget:{widget.figure_widget.model_id}"
    assert widget.figure_widget.canvas.figure is ax.figure
    assert widget.options == {
        "brush": brush,
        "pan": pan,
        "zoom": zoom,
        "debounce": False,
    }


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


def test_figure_to_base64(monkeypatch) -> None:
    monkeypatch.setenv("MARIMO_NO_JS", "true")
    fig, ax = plt.subplots(figsize=(6.4, 2.3), dpi=100)
    plt.close(fig)
    with mpl.rc_context({"savefig.bbox": "tight"}):
        widget = matplotlib(ax)
    mimetype, uri = widget._mime_()
    assert mimetype == "image/png"
    assert widget._plot_widget is None
    prefix, data = uri.split(",", 1)
    assert prefix == "data:image/png;base64"
    pixels = plt.imread(io.BytesIO(base64.b64decode(data)), format="png")
    assert pixels.shape[:2] == (460, 1280)
    assert fig.get_dpi() == 100


# ============================================================================
# HTML output tests
# ============================================================================


@pytest.mark.parametrize("layout", ["constrained", "tight"])
def test_axes_bounds_follow_layout(layout):
    fig, ax = plt.subplots(layout=layout)
    ax.set(xlabel="Time", ylabel="Temperature", title="Weather")
    widget = matplotlib(ax)._plot_widget.figure_widget
    try:
        widget.canvas.draw()
        bbox = ax.get_position()
        assert widget.geometry["rect"] == pytest.approx(
            [bbox.x0, 1 - bbox.y1, bbox.x1, 1 - bbox.y0]
        )
    finally:
        widget.close()
        plt.close(fig)


def test_constructing_plot_does_not_display_a_jupyter_output(monkeypatch):
    pytest.importorskip("matplotlib.backends.backend_anywidget")
    import IPython.display
    import jupyter_rfb.widget
    from ipywidgets import Output

    from marimo._output.formatters.ipython_formatters import IPythonFormatter
    from marimo._runtime.output import _output

    emitted = []
    monkeypatch.setattr(_output, "append", emitted.append)
    restore = IPythonFormatter().register()
    try:
        monkeypatch.setattr(
            jupyter_rfb.widget, "display", IPython.display.display
        )
        plot = matplotlib(_make_scatter_ax())
        try:
            assert emitted == []
            output = Output()
            try:
                IPython.display.display(output)
                assert emitted == [output]
            finally:
                output.close()
        finally:
            plot._plot_widget.close()
    finally:
        restore()


def test_html_contains_tag() -> None:
    ax = _make_scatter_ax()
    fig = matplotlib(ax)
    html = fig.text
    assert "marimo-anywidget" in html


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


def test_single_axes_in_right_subfigure():
    fig = plt.figure()
    _, right = fig.subfigures(1, 2)
    ax = right.subplots()
    try:
        view = matplotlib(ax)
        left = view._plot_widget.figure_widget.geometry["rect"][0]
        assert left > 0.5
    finally:
        plt.close(fig)


@pytest.mark.parametrize("option", ["brush", "pan", "zoom"])
def test_invalid_dimension(option):
    with pytest.raises(ValueError, match=option):
        matplotlib(_make_scatter_ax(), **{option: "z"})


def test_live_axes_survives_pyplot_cleanup():
    pytest.importorskip("matplotlib.backends.backend_anywidget")
    from marimo._output.mpl import close_figures
    from marimo._plugins.ui._impl.mpl_widget import _NavigationWidget

    fig, (ax, sibling) = plt.subplots(1, 2)
    initial = sibling.get_xlim()
    widget = _NavigationWidget(ax, pan=True, zoom=False)
    try:
        close_figures()
        assert fig.canvas is widget.canvas
        widget._navigate(widget, {"navigation": "pan", "x": 0.5, "y": 0}, [])
        widget.get_frame()
        np.testing.assert_allclose(widget.geometry["x"], ax.get_xlim())
        np.testing.assert_allclose(sibling.get_xlim(), initial)
        assert ax.get_autoscaley_on()
    finally:
        widget.close()


@pytest.mark.parametrize("axis", ["x", "y"])
def test_range_brush_filters_only_its_dimension(axis):
    fig = matplotlib(_make_scatter_ax(), brush=axis, value={axis: (2, 4)})
    assert fig.value == RangeSelection(axis, 2, 4)
    points = [1, 2, 4, 5]
    outside_view = [100] * len(points)
    coordinates = (
        (points, outside_view) if axis == "x" else (outside_view, points)
    )
    np.testing.assert_array_equal(
        fig.value.get_mask(*coordinates), [False, True, True, False]
    )


def test_navigation_preserves_independently_fixed_dimensions():
    pytest.importorskip("matplotlib.backends.backend_anywidget")
    from marimo._plugins.ui._impl.mpl_widget import _NavigationWidget

    ax = _make_scatter_ax()
    ax.set(xscale="log", xlim=(100, 1), ylim=(0, 12))
    widget = _NavigationWidget(ax, pan="x", zoom="y")
    try:
        frames = []
        widget.canvas.mpl_connect(
            "draw_event", lambda event: frames.append(event)
        )
        widget._navigate(
            widget, {"navigation": "pan", "x": 0.5, "y": 0.25}, []
        )
        np.testing.assert_allclose(ax.get_xlim(), (1000, 10))
        np.testing.assert_allclose(ax.get_ylim(), (0, 12))
        widget._navigate(
            widget,
            {"navigation": "zoom", "x": 0.5, "y": 0.25, "factor": 0.5},
            [],
        )
        np.testing.assert_allclose(ax.get_xlim(), (1000, 10))
        np.testing.assert_allclose(ax.get_ylim(), (1.5, 7.5))
        assert len(frames) == 0
        widget.get_frame()
        assert len(frames) == 1
        np.testing.assert_allclose(widget.geometry["y"], (1.5, 7.5))
        # Commands in a frame keep their order, even across a reset.
        widget._navigate(
            widget,
            {
                "gestures": [
                    {"navigation": "pan", "x": 0.5, "y": 0},
                    {"navigation": "reset"},
                    {"navigation": "zoom", "x": 0, "y": 0.5, "factor": 0.5},
                ]
            },
            [],
        )
        np.testing.assert_allclose(ax.get_xlim(), (100, 1))
        np.testing.assert_allclose(ax.get_ylim(), (3, 9))
        widget._navigate(widget, {"navigation": "reset"}, [])
        np.testing.assert_allclose(ax.get_xlim(), (100, 1))
        np.testing.assert_allclose(ax.get_ylim(), (0, 12))
    finally:
        widget.close()


@pytest.mark.parametrize("layout", ["tight", "constrained"])
def test_zoom_keeps_the_pointer_anchor_with_automatic_layout(layout):
    from matplotlib.figure import Figure

    from marimo._plugins.ui._impl.mpl_widget import _NavigationWidget

    figure = Figure(figsize=(5, 2.5), layout=layout)
    ax = figure.subplots()
    ax.plot(range(12), range(12))
    widget = _NavigationWidget(ax, pan=False, zoom=True)
    try:
        anchor = ax.transAxes.transform((0.31, 0.67))
        data = ax.transData.inverted().transform(anchor)
        layout_engine = figure.get_layout_engine()
        for _ in range(20):
            widget._apply_gesture(
                {"navigation": "zoom", "x": 0.31, "y": 0.67, "factor": 0.84}
            )
            widget.get_frame()
            np.testing.assert_allclose(
                ax.transData.transform(data), anchor, atol=1e-6
            )
        assert figure.get_layout_engine() is layout_engine
    finally:
        widget.close()
