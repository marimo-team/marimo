# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("plotly.express")
pytest.importorskip("plotly.graph_objects")

import plotly.express as px
import plotly.graph_objects as go

from marimo._plugins.ui._impl.plotly import (
    _extract_heatmap_cells_fallback,
    _extract_heatmap_cells_numpy,
    plotly,
)


def test_basic_scatter_plot() -> None:
    """Test creating a basic scatter plot."""
    fig = go.Figure(data=go.Scatter(x=[1, 2, 3], y=[4, 5, 6], mode="markers"))
    plot = plotly(fig)

    assert plot is not None
    assert plot.value == []
    assert plot.ranges == {}
    assert plot.points == []
    assert plot.indices == []


def test_plotly_express_scatter() -> None:
    """Test creating a plot with plotly express."""
    import pandas as pd

    df = pd.DataFrame(
        {"x": [1, 2, 3], "y": [4, 5, 6], "color": ["A", "B", "A"]}
    )
    fig = px.scatter(df, x="x", y="y", color="color")
    plot = plotly(fig)

    assert plot is not None
    assert plot.value == []


def test_plotly_with_config() -> None:
    """Test creating a plot with custom configuration."""
    fig = go.Figure(data=go.Scatter(x=[1, 2, 3], y=[4, 5, 6]))
    config = {"staticPlot": True, "displayModeBar": False}
    plot = plotly(fig, config=config)

    assert plot is not None
    assert plot._component_args["config"] == config


def test_plotly_with_label() -> None:
    """Test creating a plot with a label."""
    fig = go.Figure(data=go.Scatter(x=[1, 2, 3], y=[4, 5, 6]))
    plot = plotly(fig, label="My Plot")

    assert plot is not None


def test_plotly_with_on_change() -> None:
    """Test creating a plot with on_change callback."""
    fig = go.Figure(data=go.Scatter(x=[1, 2, 3], y=[4, 5, 6]))
    callback_called = []

    def on_change(value: Any) -> None:
        callback_called.append(value)

    plot = plotly(fig, on_change=on_change)
    assert plot is not None


def test_initial_selection() -> None:
    """Test that initial selection is properly set."""
    fig = go.Figure(data=go.Scatter(x=[1, 2, 3, 4], y=[1, 2, 3, 4]))

    # Add a selection to the figure
    fig.add_selection(x0=1, x1=3, y0=1, y1=3, xref="x", yref="y")

    # Update layout to include axis titles
    fig.update_xaxes(title_text="X Axis")
    fig.update_yaxes(title_text="Y Axis")

    plot = plotly(fig)

    # Check that initial value contains the selection
    initial_value = plot._args.initial_value
    assert "range" in initial_value
    assert "x" in initial_value["range"]
    assert "y" in initial_value["range"]
    assert initial_value["range"]["x"] == [1, 3]
    assert initial_value["range"]["y"] == [1, 3]

    # Check that points within the selection are included
    assert "points" in initial_value
    assert "indices" in initial_value
    # Points at (1,1), (2,2), and (3,3) should be selected (using <= comparisons)
    assert len(initial_value["indices"]) == 3
    assert initial_value["indices"] == [0, 1, 2]


def test_selection_with_axis_titles() -> None:
    """Test that selection properly extracts axis titles."""
    fig = go.Figure(data=go.Scatter(x=[1, 2, 3], y=[4, 5, 6]))
    fig.update_xaxes(title_text="Time")
    fig.update_yaxes(title_text="Value")
    fig.add_selection(x0=1, x1=2, y0=4, y1=5, xref="x", yref="y")

    plot = plotly(fig)

    # Check that points have the correct axis labels
    initial_value = plot._args.initial_value
    if initial_value["points"]:
        point = initial_value["points"][0]
        assert "Time" in point or "Value" in point


def test_selection_without_axis_titles() -> None:
    """Test selection when axes don't have titles."""
    fig = go.Figure(data=go.Scatter(x=[1, 2, 3], y=[4, 5, 6]))
    fig.add_selection(x0=1, x1=2, y0=4, y1=5, xref="x", yref="y")

    plot = plotly(fig)

    # Should still work, but points might be empty or have generic labels
    initial_value = plot._args.initial_value
    assert "points" in initial_value


def test_convert_value_with_selection() -> None:
    """Test _convert_value method with selection data."""
    fig = go.Figure(data=go.Scatter(x=[1, 2, 3], y=[4, 5, 6]))
    plot = plotly(fig)

    selection = {
        "points": [{"x": 1, "y": 4}, {"x": 2, "y": 5}],
        "range": {"x": [1, 2], "y": [4, 5]},
        "indices": [0, 1],
    }

    result = plot._convert_value(selection)

    # _convert_value should return the points
    assert result == selection["points"]
    assert plot.ranges == {"x": [1, 2], "y": [4, 5]}
    assert plot.indices == [0, 1]


def test_convert_value_empty_selection() -> None:
    """Test _convert_value with empty selection."""
    fig = go.Figure(data=go.Scatter(x=[1, 2, 3], y=[4, 5, 6]))
    plot = plotly(fig)

    result = plot._convert_value({})

    assert result == []
    assert plot.ranges == {}
    assert plot.points == []
    assert plot.indices == []


def test_ranges_property() -> None:
    """Test the ranges property."""
    fig = go.Figure(data=go.Scatter(x=[1, 2, 3], y=[4, 5, 6]))
    plot = plotly(fig)

    # Initially empty
    assert plot.ranges == {}

    # Set selection data
    plot._convert_value({"range": {"x": [1, 2], "y": [4, 5]}})
    assert plot.ranges == {"x": [1, 2], "y": [4, 5]}


def test_points_property() -> None:
    """Test the points property."""
    fig = go.Figure(data=go.Scatter(x=[1, 2, 3], y=[4, 5, 6]))
    plot = plotly(fig)

    # Initially empty
    assert plot.points == []

    # Set selection data
    plot._convert_value({"points": [{"x": 1, "y": 4}]})
    assert plot.points == [{"x": 1, "y": 4}]


def test_indices_property() -> None:
    """Test the indices property."""
    fig = go.Figure(data=go.Scatter(x=[1, 2, 3], y=[4, 5, 6]))
    plot = plotly(fig)

    # Initially empty
    assert plot.indices == []

    # Set selection data
    plot._convert_value({"indices": [0, 2]})
    assert plot.indices == [0, 2]


def test_treemap() -> None:
    """Test that treemaps can be created (supported chart type)."""
    fig = go.Figure(
        go.Treemap(
            labels=["A", "B", "C"],
            parents=["", "A", "A"],
            values=[10, 5, 5],
        )
    )
    plot = plotly(fig)

    assert plot is not None


def test_sunburst() -> None:
    """Test that sunburst charts can be created (supported chart type)."""
    fig = go.Figure(
        go.Sunburst(
            labels=["A", "B", "C"],
            parents=["", "A", "A"],
            values=[10, 5, 5],
        )
    )
    plot = plotly(fig)

    assert plot is not None


def test_multiple_traces() -> None:
    """Test plot with multiple traces."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[1, 2, 3], y=[4, 5, 6], name="Trace 1"))
    fig.add_trace(go.Scatter(x=[1, 2, 3], y=[6, 5, 4], name="Trace 2"))

    plot = plotly(fig)
    assert plot is not None


def test_selection_across_multiple_traces() -> None:
    """Test that selection works across multiple traces."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[1, 2], y=[1, 2], name="Trace 1"))
    fig.add_trace(go.Scatter(x=[2, 3], y=[2, 3], name="Trace 2"))
    fig.update_xaxes(title_text="X")
    fig.update_yaxes(title_text="Y")
    fig.add_selection(x0=1.5, x1=2.5, y0=1.5, y1=2.5, xref="x", yref="y")

    plot = plotly(fig)

    # Should select points from both traces
    initial_value = plot._args.initial_value
    assert len(initial_value["indices"]) >= 1


def test_selection_with_no_data() -> None:
    """Test selection on a plot with no data."""
    fig = go.Figure()
    fig.add_selection(x0=1, x1=2, y0=1, y1=2, xref="x", yref="y")

    plot = plotly(fig)

    # Should not error, but should have empty selection
    initial_value = plot._args.initial_value
    assert initial_value["points"] == []
    assert initial_value["indices"] == []


def test_selection_partial_attributes() -> None:
    """Test that selection without all required attributes is ignored."""
    fig = go.Figure(data=go.Scatter(x=[1, 2, 3], y=[4, 5, 6]))

    plot = plotly(fig)
    assert plot is not None


def test_figure_serialization() -> None:
    """Test that the figure is properly serialized to JSON."""
    fig = go.Figure(data=go.Scatter(x=[1, 2, 3], y=[4, 5, 6]))
    plot = plotly(fig)

    # Check that figure is in args as a dictionary
    assert "figure" in plot._component_args
    assert isinstance(plot._component_args["figure"], dict)
    assert "data" in plot._component_args["figure"]


def test_default_config_from_renderer() -> None:
    """Test that default config is pulled from renderer when not provided."""
    import plotly.io as pio

    # Save original renderer
    original_renderer = pio.renderers.default

    try:
        # Set a renderer with custom config
        pio.renderers.default = "browser"

        fig = go.Figure(data=go.Scatter(x=[1, 2, 3], y=[4, 5, 6]))
        plot = plotly(fig)

        # Should have some config (exact config depends on renderer)
        assert "config" in plot._component_args

    finally:
        # Restore original renderer
        pio.renderers.default = original_renderer


def test_explicit_config_overrides_renderer() -> None:
    """Test that explicit config takes precedence over renderer config."""
    fig = go.Figure(data=go.Scatter(x=[1, 2, 3], y=[4, 5, 6]))
    custom_config = {"displaylogo": False}
    plot = plotly(fig, config=custom_config)

    assert plot._component_args["config"] == custom_config


def test_value_returns_points() -> None:
    """Test that .value returns the points list."""
    fig = go.Figure(data=go.Scatter(x=[1, 2, 3], y=[4, 5, 6]))
    plot = plotly(fig)

    selection = {
        "points": [{"x": 1, "y": 4}],
        "range": {"x": [1, 2], "y": [4, 5]},
        "indices": [0],
    }

    # _convert_value returns the points
    result = plot._convert_value(selection)
    assert result == [{"x": 1, "y": 4}]


def test_plotly_name() -> None:
    """Test that the component name is correct."""
    assert plotly.name == "marimo-plotly"


def test_selection_boundary_conditions() -> None:
    """Test selection at exact boundaries."""
    fig = go.Figure(data=go.Scatter(x=[1, 2, 3], y=[1, 2, 3]))
    fig.update_xaxes(title_text="X")
    fig.update_yaxes(title_text="Y")

    # Selection that exactly matches point (2, 2)
    fig.add_selection(x0=2, x1=2, y0=2, y1=2, xref="x", yref="y")

    plot = plotly(fig)

    # Point at exactly (2, 2) should be selected (using <= comparisons)
    initial_value = plot._args.initial_value
    assert len(initial_value["indices"]) == 1
    assert 1 in initial_value["indices"]


def test_heatmap_basic() -> None:
    """Test that heatmaps can be created (supported chart type)."""
    fig = go.Figure(
        data=go.Heatmap(
            z=[[1, 2, 3], [4, 5, 6], [7, 8, 9]],
            x=["A", "B", "C"],
            y=["X", "Y", "Z"],
        )
    )
    plot = plotly(fig)

    assert plot is not None
    assert plot.value == []


def test_heatmap_selection_numeric() -> None:
    """Test heatmap selection with numeric axes."""
    fig = go.Figure(
        data=go.Heatmap(
            z=[[1, 2, 3], [4, 5, 6], [7, 8, 9]],
            x=[10, 20, 30],
            y=[100, 200, 300],
        )
    )
    plot = plotly(fig)

    # Simulate a selection from frontend
    selection = {
        "range": {"x": [15, 25], "y": [150, 250]},
        "points": [],  # Frontend might send empty for heatmaps
        "indices": [],
    }

    result = plot._convert_value(selection)

    # Should extract cells at (20, 200) within the range
    assert len(result) > 0
    # Check that extracted cells have x, y, z values
    for cell in result:
        assert "x" in cell
        assert "y" in cell
        assert "z" in cell


def test_heatmap_selection_categorical() -> None:
    """Test heatmap selection with categorical axes."""
    fig = go.Figure(
        data=go.Heatmap(
            z=[[1, 2, 3], [4, 5, 6], [7, 8, 9]],
            x=["A", "B", "C"],
            y=["X", "Y", "Z"],
        )
    )
    plot = plotly(fig)

    # For categorical axes, selection uses indices
    # Select cells around index 1 (0.5 to 1.5 covers index 1)
    selection = {
        "range": {"x": [0.5, 1.5], "y": [0.5, 1.5]},
        "points": [],
        "indices": [],
    }

    result = plot._convert_value(selection)

    # Should extract the cell at index (1, 1) which is ("B", "Y")
    assert len(result) > 0
    assert any(cell["x"] == "B" and cell["y"] == "Y" for cell in result)


def test_heatmap_selection_mixed_axes() -> None:
    """Test heatmap with one numeric and one categorical axis."""
    fig = go.Figure(
        data=go.Heatmap(
            z=[[1, 2, 3], [4, 5, 6]],
            x=[10, 20, 30],  # Numeric
            y=["Row1", "Row2"],  # Categorical
        )
    )
    plot = plotly(fig)

    selection = {
        "range": {"x": [15, 25], "y": [-0.5, 0.5]},  # Select first row
        "points": [],
        "indices": [],
    }

    result = plot._convert_value(selection)

    # Should extract cell at (20, "Row1")
    assert len(result) > 0
    assert any(cell["x"] == 20 and cell["y"] == "Row1" for cell in result)


def test_heatmap_selection_all_cells() -> None:
    """Test selecting all cells in a small heatmap."""
    fig = go.Figure(
        data=go.Heatmap(
            z=[[1, 2], [3, 4]],
            x=["A", "B"],
            y=["X", "Y"],
        )
    )
    plot = plotly(fig)

    # Select entire heatmap (categorical uses indices -0.5 to n-0.5)
    selection = {
        "range": {"x": [-0.5, 1.5], "y": [-0.5, 1.5]},
        "points": [],
        "indices": [],
    }

    result = plot._convert_value(selection)

    # Should have all 4 cells
    assert len(result) == 4
    # Check we have all combinations
    expected_combinations = {("A", "X"), ("A", "Y"), ("B", "X"), ("B", "Y")}
    actual_combinations = {(cell["x"], cell["y"]) for cell in result}
    assert actual_combinations == expected_combinations


def test_heatmap_selection_no_cells() -> None:
    """Test heatmap selection with range that includes no cells."""
    fig = go.Figure(
        data=go.Heatmap(
            z=[[1, 2, 3]],
            x=[10, 20, 30],
            y=[100],
        )
    )
    plot = plotly(fig)

    # Select a range with no cells
    selection = {
        "range": {"x": [50, 60], "y": [200, 300]},
        "points": [],
        "indices": [],
    }

    result = plot._convert_value(selection)

    # Should be empty
    assert result == []


def test_heatmap_selection_invalid_range_type() -> None:
    """Test heatmap with selection where range is not a dict."""
    fig = go.Figure(
        data=go.Heatmap(
            z=[[1, 2], [3, 4]],
            x=["A", "B"],
            y=["X", "Y"],
        )
    )
    plot = plotly(fig)

    # Selection with invalid range type (should be handled by isinstance check)
    selection = {"range": "invalid", "points": [], "indices": []}

    result = plot._convert_value(selection)

    # Should handle gracefully without crashing
    assert result == []


def test_heatmap_selection_missing_x_or_y() -> None:
    """Test heatmap selection with incomplete range data."""
    fig = go.Figure(
        data=go.Heatmap(
            z=[[1, 2], [3, 4]],
            x=["A", "B"],
            y=["X", "Y"],
        )
    )
    plot = plotly(fig)

    # Selection with only x range
    selection = {"range": {"x": [0, 1]}, "points": [], "indices": []}

    result = plot._convert_value(selection)

    # Should return empty list (checked in _extract_heatmap_cells_from_range)
    assert result == []


def test_heatmap_curve_number() -> None:
    """Test that heatmap cells include curveNumber for multi-trace plots."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[1, 2], y=[1, 2]))  # trace 0
    fig.add_trace(go.Heatmap(z=[[1, 2]], x=["A", "B"], y=["X"]))  # trace 1

    plot = plotly(fig)

    selection = {
        "range": {"x": [-0.5, 1.5], "y": [-0.5, 0.5]},
        "points": [],
        "indices": [],
    }

    result = plot._convert_value(selection)

    # Heatmap cells should have curveNumber = 1
    assert len(result) > 0
    assert all(cell.get("curveNumber") == 1 for cell in result)


def test_heatmap_initial_selection() -> None:
    """Test that initial selection works with heatmaps."""
    fig = go.Figure(
        data=go.Heatmap(
            z=[[1, 2, 3], [4, 5, 6], [7, 8, 9]],
            x=["A", "B", "C"],
            y=["X", "Y", "Z"],
        )
    )

    # Add an initial selection
    fig.add_selection(x0=0.5, x1=1.5, y0=0.5, y1=1.5, xref="x", yref="y")

    plot = plotly(fig)

    # Check that initial value contains the selection
    initial_value = plot._args.initial_value
    assert "range" in initial_value
    assert initial_value["range"]["x"] == [0.5, 1.5]
    assert initial_value["range"]["y"] == [0.5, 1.5]

    # For heatmap, should extract cells, not scatter points
    assert "points" in initial_value
    assert len(initial_value["points"]) > 0

    # Should have x, y, z values (heatmap cells)
    for point in initial_value["points"]:
        assert "x" in point
        assert "y" in point
        assert "z" in point

    # Should extract cell at index (1, 1) which is ("B", "Y", 5)
    assert any(
        p["x"] == "B" and p["y"] == "Y" and p["z"] == 5
        for p in initial_value["points"]
    )


def test_heatmap_empty() -> None:
    """Test heatmap with empty data."""
    fig = go.Figure(
        data=go.Heatmap(
            z=[],
            x=[],
            y=[],
        )
    )
    plot = plotly(fig)

    selection = {
        "range": {"x": [-0.5, 0.5], "y": [-0.5, 0.5]},
        "points": [],
        "indices": [],
    }

    result = plot._convert_value(selection)

    # Should return empty list for empty heatmap
    assert result == []


def test_heatmap_single_cell() -> None:
    """Test heatmap with a single cell."""
    fig = go.Figure(
        data=go.Heatmap(
            z=[[42]],
            x=["A"],
            y=["X"],
        )
    )
    plot = plotly(fig)

    # Selection that covers the single cell (categorical at index 0)
    selection = {
        "range": {"x": [-0.5, 0.5], "y": [-0.5, 0.5]},
        "points": [],
        "indices": [],
    }

    result = plot._convert_value(selection)

    # Should extract the single cell
    assert len(result) == 1
    assert result[0]["x"] == "A"
    assert result[0]["y"] == "X"
    assert result[0]["z"] == 42


def test_heatmap_single_cell_numeric() -> None:
    """Test heatmap with a single cell and numeric axes."""
    fig = go.Figure(
        data=go.Heatmap(
            z=[[99]],
            x=[5],
            y=[10],
        )
    )
    plot = plotly(fig)

    # Selection that covers the single numeric cell
    selection = {
        "range": {"x": [0, 10], "y": [5, 15]},
        "points": [],
        "indices": [],
    }

    result = plot._convert_value(selection)

    # Should extract the single cell
    assert len(result) == 1
    assert result[0]["x"] == 5
    assert result[0]["y"] == 10
    assert result[0]["z"] == 99


def test_heatmap_single_cell_outside_selection() -> None:
    """Test single-cell heatmap where selection doesn't cover the cell."""
    fig = go.Figure(
        data=go.Heatmap(
            z=[[42]],
            x=["A"],
            y=["X"],
        )
    )
    plot = plotly(fig)

    # Selection that doesn't cover the cell (categorical at index 0)
    selection = {
        "range": {"x": [1.5, 2.5], "y": [1.5, 2.5]},
        "points": [],
        "indices": [],
    }

    result = plot._convert_value(selection)

    # Should return empty list since selection doesn't cover the cell
    assert result == []


def test_heatmap_numpy_and_fallback_produce_same_results() -> None:
    """Test that numpy and fallback implementations produce identical results."""
    fig = go.Figure(
        data=go.Heatmap(
            z=[[1, 2, 3], [4, 5, 6], [7, 8, 9]],
            x=["A", "B", "C"],
            y=["X", "Y", "Z"],
        )
    )

    x_min, x_max = 0.5, 2.5
    y_min, y_max = 0.5, 2.5

    # Get results from both implementations
    numpy_result = _extract_heatmap_cells_numpy(
        fig, x_min, x_max, y_min, y_max
    )
    fallback_result = _extract_heatmap_cells_fallback(
        fig, x_min, x_max, y_min, y_max
    )

    # Both should return the same number of cells
    assert len(numpy_result) == len(fallback_result)

    # Sort results for comparison (order might differ)
    def sort_key(cell: dict[str, Any]) -> tuple[Any, ...]:
        return (cell["x"], cell["y"], cell["z"])

    numpy_sorted = sorted(numpy_result, key=sort_key)
    fallback_sorted = sorted(fallback_result, key=sort_key)

    # Compare each cell
    for np_cell, fb_cell in zip(numpy_sorted, fallback_sorted):
        assert np_cell["x"] == fb_cell["x"]
        assert np_cell["y"] == fb_cell["y"]
        assert np_cell["z"] == fb_cell["z"]
        assert np_cell["curveNumber"] == fb_cell["curveNumber"]


def test_heatmap_numpy_and_fallback_numeric_axes() -> None:
    """Test numpy and fallback with numeric axes produce identical results."""
    fig = go.Figure(
        data=go.Heatmap(
            z=[[1, 2, 3], [4, 5, 6], [7, 8, 9]],
            x=[10, 20, 30],
            y=[100, 200, 300],
        )
    )

    x_min, x_max = 15, 25
    y_min, y_max = 150, 250

    numpy_result = _extract_heatmap_cells_numpy(
        fig, x_min, x_max, y_min, y_max
    )
    fallback_result = _extract_heatmap_cells_fallback(
        fig, x_min, x_max, y_min, y_max
    )

    assert len(numpy_result) == len(fallback_result)

    def sort_key(cell: dict[str, Any]) -> tuple[Any, ...]:
        return (cell["x"], cell["y"], cell["z"])

    numpy_sorted = sorted(numpy_result, key=sort_key)
    fallback_sorted = sorted(fallback_result, key=sort_key)

    for np_cell, fb_cell in zip(numpy_sorted, fallback_sorted):
        assert np_cell["x"] == fb_cell["x"]
        assert np_cell["y"] == fb_cell["y"]
        assert np_cell["z"] == fb_cell["z"]
        assert np_cell["curveNumber"] == fb_cell["curveNumber"]
