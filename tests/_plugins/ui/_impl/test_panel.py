# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from unittest.mock import Mock

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.from_panel import panel
from marimo._runtime.runtime.kernel import Kernel
from tests.conftest import ExecReqProvider

HAS_DEPS = DependencyManager.panel.has()

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
