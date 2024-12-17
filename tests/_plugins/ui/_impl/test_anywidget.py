# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from hashlib import md5

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
            "js-hash": md5(b"").hexdigest(),
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
            "js-hash": md5(b"").hexdigest(),
        }

    @staticmethod
    async def test_custom_methods_and_attributes() -> None:
        class CustomWidget(_anywidget.AnyWidget):
            _esm = ""
            custom_attr = traitlets.Int(42).tag(sync=True)

            def custom_method(self):
                return self.custom_attr * 2

        wrapped = anywidget(CustomWidget())
        assert wrapped.custom_attr == 42
        assert wrapped.custom_method() == 84

        wrapped.custom_attr = 10
        assert wrapped.custom_attr == 10
        assert wrapped.custom_method() == 20

    @staticmethod
    async def test_non_serializable_traits() -> None:
        class NonSerializableWidget(_anywidget.AnyWidget):
            _esm = ""
            serializable = traitlets.Int(1).tag(sync=True)
            non_serializable = traitlets.Instance(object)

        wrapped = anywidget(NonSerializableWidget())
        assert "serializable" in wrapped._initial_value
        assert wrapped._initial_value["non_serializable"] is None

    @staticmethod
    async def test_frontend_changes(
        k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [
                exec_req.get("""
    import marimo as mo
    import traitlets
    import anywidget as _anywidget

    class TestWidget(_anywidget.AnyWidget):
        _esm = ""
        value = traitlets.Int(0).tag(sync=True)

    w = mo.ui.anywidget(TestWidget())
            """)
            ]
        )

        ui_element = k.globals["w"]
        assert ui_element.value == {"value": 0}

        # Simulate a change from the frontend
        await k.set_ui_element_value(
            SetUIElementValueRequest.from_ids_and_values(
                [(ui_element._id, {"value": 42})]
            )
        )

        assert ui_element.value == {"value": 42}
        assert ui_element.widget.value == 42

    @staticmethod
    async def test_buffers() -> None:
        class BufferWidget(_anywidget.AnyWidget):
            _esm = ""
            array = traitlets.Bytes().tag(sync=True)

        data = bytes([1, 2, 3, 4])
        wrapped = anywidget(BufferWidget(array=data))

        assert wrapped._initial_value == {"array": data}
        assert wrapped._component_args["buffer-paths"] == [["array"]]

        # Test updating the buffer
        new_data = bytes([5, 6, 7, 8])
        wrapped.array = new_data
        assert wrapped.value["array"] == b"\x01\x02\x03\x04"

    @staticmethod
    async def test_error_handling() -> None:
        class ErrorWidget(_anywidget.AnyWidget):
            _esm = ""

            @traitlets.validate("value")
            def _validate_value(self, proposal):
                if proposal["value"] < 0:
                    raise ValueError("Value must be non-negative")
                return proposal["value"]

            value = traitlets.Int(0).tag(sync=True)

        wrapped = anywidget(ErrorWidget())

        # Test invalid update
        wrapped.value = 5
        assert wrapped.value == {"value": 0}

        # Test invalid update
        with pytest.raises(ValueError):
            wrapped.value = -1

    @staticmethod
    async def test_css_handling() -> None:
        class CSSWidget(_anywidget.AnyWidget):
            _esm = ""
            _css = "button { color: red; }"

        wrapped = anywidget(CSSWidget())
        assert wrapped._component_args["css"] == "button { color: red; }"

    @staticmethod
    async def test_js_hash() -> None:
        class JSWidget(_anywidget.AnyWidget):
            _esm = ""
            value = traitlets.Int(0).tag(sync=True)

        wrapped = anywidget(JSWidget())
        assert wrapped._component_args["js-hash"] == md5(b"").hexdigest()

        class JSWidget2(_anywidget.AnyWidget):
            _esm = "function render({ model, el }) { el.innerHTML = 'hello'; }"
            value = traitlets.Int(0).tag(sync=True)

        wrapped2 = anywidget(JSWidget2())
        assert (
            wrapped2._component_args["js-hash"]
            != wrapped._component_args["js-hash"]
        )
