# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import gc
import weakref
from unittest.mock import Mock

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.from_panel import (
    _extract_holoviews_settings,
    panel,
)
from marimo._runtime.commands import DeleteCellCommand
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

    @staticmethod
    def test_extension_served_as_virtual_file(
        executing_kernel: Kernel,
    ) -> None:
        # The extension JS must be served via a `./@file/...` virtual file
        # path rather than inlined as a `data-extension` attribute. This is
        # what lets the frontend refuse to execute attacker-controlled
        # scripts embedded in markdown via raw <marimo-panel> elements.
        del executing_kernel  # fixture installs the runtime context
        slider = pn.widgets.IntSlider(start=0, end=10, value=5)
        element = panel(slider)

        text = element.text
        assert "data-extension-url=" in text
        assert "data-extension=" not in text
        # The extension URL must be a virtual file path; absolute or data:
        # URLs would let raw-HTML attackers load arbitrary JavaScript.
        assert "@file/" in text

    @staticmethod
    async def test_rerun_cleans_previous_panel_view(
        k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        from panel.io.state import state

        await k.run(
            [
                exec_req.get_with_id(
                    "panel_cell",
                    """
import marimo as mo
import panel as pn

slider = pn.widgets.IntSlider(start=0, end=10, value=5)
panel_element = mo.ui.panel(slider)
panel_ref = panel_element._ref
""",
                )
            ]
        )
        first_ref = k.globals["panel_ref"]
        assert first_ref in state._views

        await k.run(
            [
                exec_req.get_with_id(
                    "panel_cell",
                    """
import marimo as mo
import panel as pn

slider = pn.widgets.IntSlider(start=0, end=10, value=6)
panel_element = mo.ui.panel(slider)
panel_ref = panel_element._ref
""",
                )
            ]
        )

        assert first_ref not in state._views
        assert k.globals["panel_ref"] in state._views

    @staticmethod
    async def test_rerun_garbage_collects_old_document_and_pane(
        k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        from panel.io.state import state

        await k.run(
            [
                exec_req.get_with_id(
                    "panel_cell",
                    """
import marimo as mo
import panel as pn

slider = pn.widgets.IntSlider(start=0, end=10, value=5)
panel_element = mo.ui.panel(slider)
panel_ref = panel_element._ref
""",
                )
            ]
        )
        first_ref = k.globals["panel_ref"]
        assert first_ref in state._views
        old_pane = weakref.ref(state._views[first_ref][0])
        old_doc = weakref.ref(state._views[first_ref][2])

        await k.run(
            [
                exec_req.get_with_id(
                    "panel_cell",
                    """
import marimo as mo
import panel as pn

slider = pn.widgets.IntSlider(start=0, end=10, value=6)
panel_element = mo.ui.panel(slider)
panel_ref = panel_element._ref
""",
                )
            ]
        )

        gc.collect()
        assert first_ref not in state._views
        assert old_pane() is None
        assert old_doc() is None

    @staticmethod
    async def test_cell_deletion_removes_panel_view(
        k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        from panel.io.state import state

        cell = exec_req.get_with_id(
            "panel_cell",
            """
import marimo as mo
import panel as pn

slider = pn.widgets.IntSlider(start=0, end=10, value=5)
panel_element = mo.ui.panel(slider)
panel_ref = panel_element._ref
""",
        )
        await k.run([cell])
        panel_ref = k.globals["panel_ref"]
        assert panel_ref in state._views

        await k.delete_cell(DeleteCellCommand(cell_id=cell.cell_id))
        assert panel_ref not in state._views

    @staticmethod
    async def test_cleanup_preserves_shared_widget(
        k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        imports = exec_req.get("import panel as pn\nimport marimo as mo")
        widget = exec_req.get("slider = pn.widgets.IntSlider(value=3)")
        first = exec_req.get("first = mo.ui.panel(slider)")
        second = exec_req.get("second = mo.ui.panel(slider)")
        await k.run([imports, widget, first, second])
        assert not k.errors
        slider = k.globals["slider"]
        second_ref = k.globals["second"]._ref

        await k.run([first])
        assert not k.errors
        first_ref = k.globals["first"]._ref
        slider.value = 7
        assert {
            ref: model.value for ref, (model, _) in slider._models.items()
        } == {first_ref: 7, second_ref: 7}

        await k.delete_cell(DeleteCellCommand(cell_id=first.cell_id))
        slider.value = 8
        assert {
            ref: model.value for ref, (model, _) in slider._models.items()
        } == {second_ref: 8}
        await k.delete_cell(DeleteCellCommand(cell_id=second.cell_id))

    @staticmethod
    async def test_multiple_panels_in_single_cell(
        k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        from panel.io.state import state

        cell = exec_req.get_with_id(
            "multi_cell",
            """
import marimo as mo
import panel as pn

p1 = mo.ui.panel(pn.widgets.IntSlider(value=1))
p2 = mo.ui.panel(pn.widgets.IntSlider(value=2))
refs = [p1._ref, p2._ref]
""",
        )
        await k.run([cell])
        first_refs = list(k.globals["refs"])
        assert all(ref in state._views for ref in first_refs)

        # Re-run cell
        await k.run([cell])
        second_refs = list(k.globals["refs"])
        assert all(ref not in state._views for ref in first_refs)
        assert all(ref in state._views for ref in second_refs)

        # Delete cell
        await k.delete_cell(DeleteCellCommand(cell_id=cell.cell_id))
        assert all(ref not in state._views for ref in second_refs)

    @staticmethod
    async def test_lazy_ancestor_rerun_preserves_descendant(
        lazy_kernel: Kernel, exec_req: ExecReqProvider
    ) -> None:
        from panel.io.state import state

        k = lazy_kernel
        ancestor = exec_req.get_with_id("ancestor", "x = 1")
        descendant = exec_req.get_with_id(
            "descendant",
            """
import marimo as mo
import panel as pn

slider = pn.widgets.IntSlider(value=x)
p = mo.ui.panel(slider)
ref = p._ref
p
""",
        )
        await k.run([ancestor, descendant])
        assert not k.errors
        descendant_ref = k.globals["ref"]
        assert descendant_ref in state._views

        # Re-run ancestor in lazy mode.
        # Descendant should become stale, but its view must NOT be disposed yet.
        ancestor_update = exec_req.get_with_id("ancestor", "x = 2")
        await k.run([ancestor_update])
        assert not k.errors

        assert descendant_ref in state._views

        # Now explicitly re-run descendant.
        # Old view should now be cleaned up and new view registered.
        await k.run([descendant])
        assert not k.errors
        assert descendant_ref not in state._views
        new_ref = k.globals["ref"]
        assert new_ref in state._views

        # Delete descendant
        await k.delete_cell(DeleteCellCommand(cell_id=descendant.cell_id))
        assert new_ref not in state._views


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

    @staticmethod
    async def test_bare_holoviews_output_cleanup(
        k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        from panel.io.state import state

        imports = exec_req.get(
            "import holoviews as hv\nhv.extension('bokeh', logo=False)"
        )
        await k.run([imports])
        assert not k.errors

        baseline = set(state._views)
        plot_cell = exec_req.get_with_id("plot_cell", "hv.Curve([1, 2, 3])")
        await k.run([plot_cell])
        assert not k.errors

        plot_views = set(state._views) - baseline
        assert len(plot_views) == 1
        first_ref = next(iter(plot_views))
        old_pane = weakref.ref(state._views[first_ref][0])
        old_root = weakref.ref(state._views[first_ref][1])
        old_doc = weakref.ref(state._views[first_ref][2])

        other_cell = exec_req.get_with_id("other_cell", "hv.Curve([4, 5, 6])")
        await k.run([other_cell])
        assert not k.errors
        other_views = set(state._views) - baseline - {first_ref}
        assert len(other_views) == 1
        other_ref = next(iter(other_views))
        assert other_ref in state._views

        # Rerun plot_cell: old view, doc, root, and pane are cleaned up and collected
        await k.run([plot_cell])
        assert not k.errors
        gc.collect()

        assert first_ref not in state._views
        assert old_pane() is None
        assert old_root() is None
        assert old_doc() is None
        # other_cell's render remains intact and usable
        assert other_ref in state._views

        new_plot_views = set(state._views) - baseline - {other_ref}
        assert len(new_plot_views) == 1
        second_ref = next(iter(new_plot_views))
        second_pane = weakref.ref(state._views[second_ref][0])
        second_root = weakref.ref(state._views[second_ref][1])
        second_doc = weakref.ref(state._views[second_ref][2])

        # Delete plot_cell: second view, doc, root, and pane are cleaned up and collected
        await k.delete_cell(DeleteCellCommand(cell_id=plot_cell.cell_id))
        gc.collect()

        assert second_ref not in state._views
        assert second_pane() is None
        assert second_root() is None
        assert second_doc() is None
        assert other_ref in state._views

        # Delete other_cell: cleans up remaining view
        await k.delete_cell(DeleteCellCommand(cell_id=other_cell.cell_id))
        assert set(state._views) == baseline
