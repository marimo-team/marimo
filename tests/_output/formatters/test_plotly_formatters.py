from __future__ import annotations

import json

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._output.formatters.formatters import register_formatters
from marimo._output.formatters.plotly_formatters import PlotlyFormatter

HAS_DEPS = DependencyManager.plotly.has()


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
