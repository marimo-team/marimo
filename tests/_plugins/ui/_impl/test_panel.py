# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from unittest.mock import Mock

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.from_panel import (
    _extract_holoviews_settings,
    panel,
)
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider

HAS_DEPS = DependencyManager.panel.has()
HAS_HOLOVIEWS = DependencyManager.holoviews.has()

if HAS_DEPS:
    import panel as pn
else:
    pn = Mock()


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
class TestPanel:
    @staticmethod
    async def test_instances(k: Kernel, exec_req: ExecReqProvider) -> None:
        await k.run(
            [
                exec_req.get(
                    """
import panel as pn
import marimo as mo

slider = pn.widgets.IntSlider(start=0, end=10, value=5)
slider = mo.ui.panel(slider)
"""
                )
            ]
        )

    @staticmethod
    def test_proxy_attributes() -> None:
        slider = pn.widgets.IntSlider(start=0, end=10, value=5)
        wrapped = panel(slider)

        # Test attribute access
        assert (
            wrapped.value == {}
        )  # slider gets wrapped in a row, so it's value is empty
        assert wrapped.start == 0
        assert wrapped.end == 10

        # Test attribute modification
        wrapped.value = 7
        assert (
            wrapped.value == {}
        )  # slider gets wrapped in a row, so it's value is empty
        assert slider.value == 7

    @staticmethod
    def test_layout_components() -> None:
        row = panel(pn.Row("Test"))
        col = panel(pn.Column("Test"))
        tabs = panel(pn.Tabs(("Tab1", "Content")))

        assert isinstance(row, panel)
        assert isinstance(col, panel)
        assert isinstance(tabs, panel)

    @staticmethod
    def test_any_object() -> None:
        assert panel({}) is not None
        assert panel([]) is not None
        assert panel(()) is not None
        assert panel(1) is not None
        assert panel("test") is not None
        assert panel(True) is not None
        assert panel(False) is not None
        assert panel(None) is not None


@pytest.mark.skipif(not HAS_HOLOVIEWS, reason="holoviews not installed")
class TestHoloViewsSettings:
    @staticmethod
    def test_extract_holoviews_settings_with_widget_location() -> None:
        """Test that widget_location is extracted from holoviews renderer."""
        import holoviews as hv

        # Set up holoviews with bokeh backend
        hv.extension("bokeh")
        hv.output(widget_location="top")

        # Create a simple holoviews object
        curve = hv.Curve([1, 2, 3])

        # Extract settings
        settings = _extract_holoviews_settings(curve)

        # Verify widget_location is extracted
        assert "widget_location" in settings
        assert settings["widget_location"] == "top"

    @staticmethod
    def test_extract_holoviews_settings_with_center() -> None:
        """Test that center is extracted from holoviews renderer."""
        import holoviews as hv

        # Set up holoviews with bokeh backend
        hv.extension("bokeh")
        hv.output(center=True)

        # Create a simple holoviews object
        curve = hv.Curve([1, 2, 3])

        # Extract settings
        settings = _extract_holoviews_settings(curve)

        # Verify center is extracted
        assert "center" in settings
        assert settings["center"] is True

    @staticmethod
    def test_extract_holoviews_settings_non_holoviews_object() -> None:
        """Test that non-holoviews objects return empty dict."""
        # Test with regular objects
        assert _extract_holoviews_settings({}) == {}
        assert _extract_holoviews_settings([1, 2, 3]) == {}
        assert _extract_holoviews_settings("test") == {}

    @staticmethod
    def test_extract_holoviews_settings_no_widget_location() -> None:
        """Test extraction when widget_location is not set (None)."""
        import holoviews as hv

        # Set up holoviews with bokeh backend but no widget_location
        hv.extension("bokeh")

        # Get the renderer and ensure widget_location is None
        renderer = hv.renderer("bokeh")
        renderer.widget_location = None

        # Create a simple holoviews object
        curve = hv.Curve([1, 2, 3])

        # Extract settings
        settings = _extract_holoviews_settings(curve)

        # Verify that None values are not included
        assert "widget_location" not in settings


@pytest.mark.skipif(
    not (HAS_DEPS and HAS_HOLOVIEWS),
    reason="panel and holoviews not installed",
)
class TestPanelWithHoloViews:
    @staticmethod
    def test_panel_respects_holoviews_output_settings() -> None:
        """Test that panel() passes holoviews settings to Panel pane."""
        import holoviews as hv

        # Set up holoviews with specific settings
        hv.extension("bokeh")
        hv.output(widget_location="bottom")

        # Create a holoviews object
        curve = hv.Curve([1, 2, 3])

        # Wrap in panel
        wrapped = panel(curve)

        # The wrapped object should be a Panel pane
        # We can't directly check if widget_location was passed,
        # but we can verify the object was created successfully
        assert wrapped is not None
        assert isinstance(wrapped, panel)
