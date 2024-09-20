# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.from_anywidget import anywidget
from marimo._runtime.requests import SetUIElementValueRequest
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider

HAS_DEPS = DependencyManager.anywidget.has()

if HAS_DEPS:
    import anywidget as _anywidget
    import traitlets

    class CounterWidget(_anywidget.AnyWidget):
        _esm = """
        function render({ model, el }) {
            let getCount = () => model.get("count");
            let button = document.createElement("button");
            button.innerHTML = `count is ${getCount()}`;
            el.appendChild(button);
        }
        export default { render };
        """
        _css = """button { padding: 5px !important; }"""
        count = traitlets.Int(0).tag(sync=True)

    class Widget(_anywidget.AnyWidget):
        _esm = ""
        arr = traitlets.Dict().tag(sync=True)


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
class TestAnywidget:
    @staticmethod
    async def test_instances(k: Kernel, exec_req: ExecReqProvider) -> None:
        import anywidget as _anywidget

        await k.run(
            [
                exec_req.get(
                    """
import anywidget
import traitlets
import marimo as mo

class CounterWidget(anywidget.AnyWidget):
    _esm = \"\"\"
    function render({ model, el }) {
        let getCount = () => model.get("count");
        let button = document.createElement("button");
        button.innerHTML = `count is ${getCount()}`;
        el.appendChild(button);
    }
    export default { render };
    \"\"\"
    _css = \"\"\"button { padding: 5px !important; }\"\"\"
    count = traitlets.Int(10).tag(sync=True)

base_widget = CounterWidget()

are_same = mo.as_html(base_widget).text == mo.as_html(base_widget).text
are_different = mo.as_html(CounterWidget()) is not mo.as_html(CounterWidget())
as_marimo_element = mo.ui.anywidget(base_widget)
x = as_marimo_element.count
"""
                )
            ]
        )
        assert k.globals["are_same"] is True
        assert k.globals["are_different"] is True
        assert k.globals["x"] == 10
        assert isinstance(k.globals["base_widget"], _anywidget.AnyWidget)
        assert "marimo-anywidget" in k.globals["as_marimo_element"].text

    @staticmethod
    async def test_value(k: Kernel, exec_req: ExecReqProvider) -> None:
        await k.run(
            [
                exec_req.get(
                    """
                    import anywidget
                    import traitlets

                    class CounterWidget(anywidget.AnyWidget):
                        _esm = \"\"\"
                        function render({ model, el }) {
                            let getCount = () => model.get("count");
                            let button = document.createElement("button");
                            button.innerHTML = `count is ${getCount()}`;
                            el.appendChild(button);
                        }
                        export default { render };
                        \"\"\"
                        _css = \"\"\"button { padding: 5px !important; }\"\"\"
                        count = traitlets.Int(10).tag(sync=True)
                    """
                ),
                exec_req.get(
                    """
                    import marimo as mo
                    w = mo.ui.anywidget(CounterWidget())
                    """
                ),
                exec_req.get(
                    """
                    w_value = w.value
                    w_count = w.count
                    """
                ),
            ]
        )

        ui_element = k.globals["w"]
        assert isinstance(ui_element, anywidget)
        assert k.globals["w_value"]["count"] == 10
        assert k.globals["w_count"] == 10
        assert ui_element.value == {"count": 10}

        await k.set_ui_element_value(
            SetUIElementValueRequest.from_ids_and_values(
                [(ui_element._id, {"count": 5})]
            )
        )

        assert k.globals["w_value"]["count"] == 5
        assert k.globals["w_count"] == 5
        assert ui_element.value == {"count": 5}

    @staticmethod
    async def test_getters_setters() -> None:
        # Test on wrapped
        wrapped = anywidget(CounterWidget())
        assert wrapped.count == 0
        wrapped.count = 10
        assert wrapped.count == 10

        # Test on wrapped, with initialization
        wrapped = anywidget(CounterWidget(count=5))
        assert wrapped.count == 5
        wrapped.count = 10
        assert wrapped.count == 10

        # Test on wrapped.widget, with initialization
        wrapped = anywidget(CounterWidget(count=7))
        assert wrapped.widget.count == 7  # type: ignore
        wrapped.widget.count = 10  # type: ignore
        assert wrapped.count == 10

        assert wrapped._initialized is True

    @staticmethod
    async def test_set_trait() -> None:
        # Test on wrapped
        wrapped = anywidget(CounterWidget())
        assert wrapped.count == 0
        wrapped.set_trait("count", 10)
        assert wrapped.count == 10
        assert wrapped.widget.count == 10  # type: ignore
        wrapped.widget.set_trait("count", 7)
        assert wrapped.count == 7
        assert wrapped.widget.count == 7  # type: ignore

        assert wrapped._initialized is True

    @staticmethod
    async def test_can_set_value() -> None:
        wrapped = anywidget(CounterWidget())
        assert wrapped.value == {"count": 0}
        wrapped._update({"count": 10})
        assert wrapped.value == {"count": 10}

    @staticmethod
    async def test_initialization() -> None:
        wrapped = anywidget(Widget(arr={"a": 1}))
        assert wrapped._initial_value == {"arr": {"a": 1}}
        assert wrapped._component_args == {
            "buffer-paths": [],
            "css": "",
            "js-url": "",
        }

    @staticmethod
    async def test_initialization_with_dataview() -> None:
        # Create a simple array-like structure without numpy
        arr = [1, 2, 3]
        wrapped = anywidget(
            Widget(arr={"bytes": bytes(arr), "shape": (len(arr),)})
        )
        assert wrapped._initial_value == {
            "arr": {"bytes": bytes([1, 2, 3]), "shape": (3,)}
        }
        assert wrapped._component_args == {
            "buffer-paths": [["arr", "bytes"]],
            "css": "",
            "js-url": "",
        }
