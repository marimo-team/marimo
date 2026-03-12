from __future__ import annotations

import json

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._output.formatters.formatters import register_formatters
from marimo._output.formatters.plotly_formatters import PlotlyFormatter
from marimo._output.formatting import get_formatter

HAS_DEPS = DependencyManager.plotly.has()
HAS_ANYWIDGET = DependencyManager.anywidget.has()


@pytest.mark.skipif(not HAS_DEPS, reason="plotly not installed")
def test_plotly_config_forwarding():
    """Test that config parameter is properly forwarded"""
    register_formatters()

    import plotly.graph_objects as go
    import plotly.io as pio

    fig = go.Figure(data=[go.Scatter(x=[1, 2, 3], y=[4, 5, 6])])

    json_str = pio.to_json(fig)
    json_dict = json.loads(json_str)

    config = {"displayModeBar": False, "responsive": True}
    result = PlotlyFormatter.render_plotly_dict(json_dict, config=config)

    assert "marimo-plotly" in result.text
    assert "data-config=" in result.text
    assert "displayModeBar" in result.text
    assert "responsive" in result.text


@pytest.mark.skipif(
    not (HAS_DEPS and HAS_ANYWIDGET),
    reason="plotly and anywidget not installed",
)
def test_plotly_figure_widget_uses_anywidget_formatter():
    """Test that FigureWidget uses the anywidget formatter, not the static
    plotly formatter.

    FigureWidget is an anywidget.AnyWidget subclass and should go through
    the anywidget formatter path for interactive widget features (like
    plotly-resampler's dynamic resampling) to work.

    Regression test for https://github.com/marimo-team/marimo/issues/4091
    """
    register_formatters()

    import plotly.graph_objects as go

    fig_widget = go.FigureWidget(data=[go.Scatter(x=[1, 2, 3], y=[4, 5, 6])])

    # get_formatter walks the MRO; for FigureWidget, the first match
    # should be the anywidget formatter (not the plotly Figure formatter)
    formatter = get_formatter(fig_widget)
    assert formatter is not None

    # Call the formatter and verify it goes through the anywidget path
    mimetype, data = formatter(fig_widget)
    assert mimetype == "text/html"
    assert "marimo-anywidget" in data
    assert "marimo-plotly" not in data
