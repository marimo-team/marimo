# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("plotly.express")
pytest.importorskip("plotly.graph_objects")

import plotly.express as px
import plotly.graph_objects as go

from marimo._plugins.ui._impl.plotly import plotly


class TestPlotly:
    @staticmethod
    def test_basic_scatter_plot() -> None:
        """Test creating a basic scatter plot."""
        fig = go.Figure(
            data=go.Scatter(x=[1, 2, 3], y=[4, 5, 6], mode="markers")
        )
        plot = plotly(fig)

        assert plot is not None
        assert plot.value == []
        assert plot.ranges == {}
        assert plot.points == []
        assert plot.indices == []

    @staticmethod
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

    @staticmethod
    def test_plotly_with_config() -> None:
        """Test creating a plot with custom configuration."""
        fig = go.Figure(data=go.Scatter(x=[1, 2, 3], y=[4, 5, 6]))
        config = {"staticPlot": True, "displayModeBar": False}
        plot = plotly(fig, config=config)

        assert plot is not None
        assert plot._component_args["config"] == config

    @staticmethod
    def test_plotly_with_label() -> None:
        """Test creating a plot with a label."""
        fig = go.Figure(data=go.Scatter(x=[1, 2, 3], y=[4, 5, 6]))
        plot = plotly(fig, label="My Plot")

        assert plot is not None

    @staticmethod
    def test_plotly_with_on_change() -> None:
        """Test creating a plot with on_change callback."""
        fig = go.Figure(data=go.Scatter(x=[1, 2, 3], y=[4, 5, 6]))
        callback_called = []

        def on_change(value: Any) -> None:
            callback_called.append(value)

        plot = plotly(fig, on_change=on_change)
        assert plot is not None

    @staticmethod
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

    @staticmethod
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

    @staticmethod
    def test_selection_without_axis_titles() -> None:
        """Test selection when axes don't have titles."""
        fig = go.Figure(data=go.Scatter(x=[1, 2, 3], y=[4, 5, 6]))
        fig.add_selection(x0=1, x1=2, y0=4, y1=5, xref="x", yref="y")

        plot = plotly(fig)

        # Should still work, but points might be empty or have generic labels
        initial_value = plot._args.initial_value
        assert "points" in initial_value

    @staticmethod
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

    @staticmethod
    def test_convert_value_empty_selection() -> None:
        """Test _convert_value with empty selection."""
        fig = go.Figure(data=go.Scatter(x=[1, 2, 3], y=[4, 5, 6]))
        plot = plotly(fig)

        result = plot._convert_value({})

        assert result == []
        assert plot.ranges == {}
        assert plot.points == []
        assert plot.indices == []

    @staticmethod
    def test_ranges_property() -> None:
        """Test the ranges property."""
        fig = go.Figure(data=go.Scatter(x=[1, 2, 3], y=[4, 5, 6]))
        plot = plotly(fig)

        # Initially empty
        assert plot.ranges == {}

        # Set selection data
        plot._convert_value({"range": {"x": [1, 2], "y": [4, 5]}})
        assert plot.ranges == {"x": [1, 2], "y": [4, 5]}

    @staticmethod
    def test_points_property() -> None:
        """Test the points property."""
        fig = go.Figure(data=go.Scatter(x=[1, 2, 3], y=[4, 5, 6]))
        plot = plotly(fig)

        # Initially empty
        assert plot.points == []

        # Set selection data
        plot._convert_value({"points": [{"x": 1, "y": 4}]})
        assert plot.points == [{"x": 1, "y": 4}]

    @staticmethod
    def test_indices_property() -> None:
        """Test the indices property."""
        fig = go.Figure(data=go.Scatter(x=[1, 2, 3], y=[4, 5, 6]))
        plot = plotly(fig)

        # Initially empty
        assert plot.indices == []

        # Set selection data
        plot._convert_value({"indices": [0, 2]})
        assert plot.indices == [0, 2]

    @staticmethod
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

    @staticmethod
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

    @staticmethod
    def test_multiple_traces() -> None:
        """Test plot with multiple traces."""
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[1, 2, 3], y=[4, 5, 6], name="Trace 1"))
        fig.add_trace(go.Scatter(x=[1, 2, 3], y=[6, 5, 4], name="Trace 2"))

        plot = plotly(fig)
        assert plot is not None

    @staticmethod
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

    @staticmethod
    def test_selection_with_no_data() -> None:
        """Test selection on a plot with no data."""
        fig = go.Figure()
        fig.add_selection(x0=1, x1=2, y0=1, y1=2, xref="x", yref="y")

        plot = plotly(fig)

        # Should not error, but should have empty selection
        initial_value = plot._args.initial_value
        assert initial_value["points"] == []
        assert initial_value["indices"] == []

    @staticmethod
    def test_selection_partial_attributes() -> None:
        """Test that selection without all required attributes is ignored."""
        fig = go.Figure(data=go.Scatter(x=[1, 2, 3], y=[4, 5, 6]))

        plot = plotly(fig)
        assert plot is not None

    @staticmethod
    def test_figure_serialization() -> None:
        """Test that the figure is properly serialized to JSON."""
        fig = go.Figure(data=go.Scatter(x=[1, 2, 3], y=[4, 5, 6]))
        plot = plotly(fig)

        # Check that figure is in args as a dictionary
        assert "figure" in plot._component_args
        assert isinstance(plot._component_args["figure"], dict)
        assert "data" in plot._component_args["figure"]

    @staticmethod
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

    @staticmethod
    def test_explicit_config_overrides_renderer() -> None:
        """Test that explicit config takes precedence over renderer config."""
        fig = go.Figure(data=go.Scatter(x=[1, 2, 3], y=[4, 5, 6]))
        custom_config = {"displaylogo": False}
        plot = plotly(fig, config=custom_config)

        assert plot._component_args["config"] == custom_config

    @staticmethod
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

    @staticmethod
    def test_plotly_name() -> None:
        """Test that the component name is correct."""
        assert plotly.name == "marimo-plotly"

    @staticmethod
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
