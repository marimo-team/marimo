# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import gc
import weakref
from hashlib import md5

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._plugins.ui._impl.from_anywidget import (
    WeakCache,
    anywidget,
    from_anywidget,
    get_anywidget_state,
)
from marimo._runtime.commands import (
    ModelCommand,
    ModelUpdateMessage,
    UpdateUIElementCommand,
)
from marimo._runtime.runtime import Kernel
from marimo._types.ids import WidgetModelId
from tests.conftest import ExecReqProvider

HAS_DEPS = (
    DependencyManager.anywidget.has() and DependencyManager.traitlets.has()
)

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
            UpdateUIElementCommand.from_ids_and_values(
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
        # _initial_value is always a model_id reference
        assert "model_id" in wrapped._initial_value_frontend
        assert len(wrapped._initial_value_frontend) == 1
        assert isinstance(wrapped._initial_value_frontend["model_id"], str)
        assert wrapped._component_args == {
            "css": "",
            "js-url": "",
            "js-hash": md5(b"").hexdigest(),
        }

    @staticmethod
    async def test_initialization_with_dataview() -> None:
        arr = [1, 2, 3]
        wrapped = anywidget(
            Widget(arr={"bytes": bytes(arr), "shape": (len(arr),)})
        )
        # _initial_value is always a model_id reference
        assert "model_id" in wrapped._initial_value_frontend
        assert len(wrapped._initial_value_frontend) == 1
        assert isinstance(wrapped._initial_value_frontend["model_id"], str)
        assert wrapped._component_args == {
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
            non_serializable = traitlets.Instance(object, sync=True)

        wrapped = anywidget(NonSerializableWidget())
        # _initial_value is always a model_id reference
        assert "model_id" in wrapped._initial_value_frontend
        assert len(wrapped._initial_value_frontend) == 1
        assert isinstance(wrapped._initial_value_frontend["model_id"], str)

    @staticmethod
    async def test_skips_non_sync_traits() -> None:
        class NonSyncWidget(_anywidget.AnyWidget):
            _esm = ""
            non_sync = traitlets.Int(1)
            sync = traitlets.Int(2).tag(sync=True)

        wrapped = anywidget(NonSyncWidget())
        # _initial_value is always a model_id reference
        assert "model_id" in wrapped._initial_value_frontend
        assert len(wrapped._initial_value_frontend) == 1
        assert isinstance(wrapped._initial_value_frontend["model_id"], str)

    @staticmethod
    async def test_frontend_changes(
        k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [
                exec_req.get(
                    """
    import marimo as mo
    import traitlets
    import anywidget as _anywidget

    class TestWidget(_anywidget.AnyWidget):
        _esm = ""
        value = traitlets.Int(0).tag(sync=True)

    w = mo.ui.anywidget(TestWidget())
            """
                )
            ]
        )

        ui_element = k.globals["w"]
        assert ui_element.value == {"value": 0}

        # Simulate a change from the frontend
        await k.set_ui_element_value(
            UpdateUIElementCommand.from_ids_and_values(
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

        # _initial_value is always a model_id reference
        assert "model_id" in wrapped._initial_value_frontend
        assert len(wrapped._initial_value_frontend) == 1
        assert isinstance(wrapped._initial_value_frontend["model_id"], str)

        # The value property reads directly from the widget
        assert wrapped.value["array"] == data

        # Test updating the buffer - now updates the widget directly
        new_data = bytes([5, 6, 7, 8])
        wrapped.array = new_data
        assert wrapped.value["array"] == new_data

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

        # Test valid update - now the widget is updated directly
        wrapped.value = 5
        assert wrapped.value == {"value": 5}

        # Test invalid update - should raise ValueError
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

    @staticmethod
    def test_state_merging() -> None:
        class StateWidget(_anywidget.AnyWidget):
            _esm = ""
            a = traitlets.Int(1, allow_none=True).tag(sync=True)
            b = traitlets.Int(2).tag(sync=True)

        wrapped = anywidget(StateWidget())
        assert wrapped.value == {"a": 1, "b": 2}

        # Test partial update merges with existing state
        wrapped._update({"a": 10})
        assert wrapped.value == {"a": 10, "b": 2}

        # Test multiple updates maintain merged state
        wrapped._update({"b": 20})
        assert wrapped.value == {"a": 10, "b": 20}

        # Test unsetting a trait
        wrapped._update({"a": None})
        assert wrapped.value == {"b": 20, "a": None}

    @staticmethod
    def test_state_persistence() -> None:
        class PersistWidget(_anywidget.AnyWidget):
            _esm = ""
            x = traitlets.Int(0).tag(sync=True)
            y = traitlets.Dict().tag(sync=True)

        wrapped = anywidget(PersistWidget())
        initial_state = {"x": 0, "y": {}}
        assert wrapped.value == initial_state

        # Update with partial state
        new_state = {"x": 42}
        wrapped._update(new_state)
        assert wrapped.value == {"x": 42, "y": {}}

        # Update nested state
        nested_state = {"y": {"key": "value"}}
        wrapped._update(nested_state)
        assert wrapped.value == {"x": 42, "y": {"key": "value"}}

    @staticmethod
    def test_unhashable_widget() -> None:
        """Test that unhashable widgets can still be wrapped."""

        # Create a widget with an unhashable trait (list)
        class UnhashableWidget(_anywidget.AnyWidget):
            _esm = ""

            def __hash__(self) -> int:
                raise TypeError("Unhashable widget")

        # This should work without errors despite the widget being unhashable
        widget = UnhashableWidget()
        assert not isinstance(widget, UIElement)

        wrapped = from_anywidget(widget)

        assert isinstance(wrapped, UIElement)
        assert wrapped is from_anywidget(widget)

    @staticmethod
    def test_hashable_widget() -> None:
        class HashableWidget(_anywidget.AnyWidget):
            _esm = ""

        widget = HashableWidget()
        assert not isinstance(widget, UIElement)

        wrapped = from_anywidget(widget)

        assert isinstance(wrapped, UIElement)
        assert wrapped is from_anywidget(widget)

    @staticmethod
    def test_WeakCache() -> None:
        class TestWidget:
            pass

        class TestWrapper:
            def __init__(self, obj):
                self.obj = weakref.ref(obj)

        widget1 = TestWidget()
        widget2 = TestWidget()
        wrapped1 = TestWrapper(widget1)
        wrapped2 = TestWrapper(widget2)

        _cache: WeakCache[TestWidget, TestWrapper] = WeakCache()

        assert _cache.get(widget1) is None
        assert _cache.get(widget2) is None
        assert _cache.get(TestWidget()) is None

        _cache.add(widget1, wrapped1)
        _cache.add(widget2, wrapped2)

        assert _cache.get(widget1) is wrapped1
        assert _cache.get(widget2) is wrapped2

        old_len = len(_cache)
        del widget1
        gc.collect()

        assert len(_cache) == old_len - 1

    @staticmethod
    async def test_get_anywidget_state() -> None:
        """Test get_anywidget_state filters out system traits."""

        class StateWidget(_anywidget.AnyWidget):
            _esm = "export default { render() {} }"
            _css = "button { color: red; }"
            count = traitlets.Int(42).tag(sync=True)
            name = traitlets.Unicode("test").tag(sync=True)

        widget = StateWidget()
        state = get_anywidget_state(widget)

        # Should include user-defined traits
        assert state["count"] == 42
        assert state["name"] == "test"

        # Should NOT include system traits
        assert "_esm" not in state
        assert "_css" not in state
        assert "comm" not in state
        assert "layout" not in state
        assert "_model_module" not in state
        assert "_view_name" not in state

    @staticmethod
    async def test_partial_state_updates() -> None:
        class MultiTraitWidget(_anywidget.AnyWidget):
            _esm = ""
            a = traitlets.Int(1).tag(sync=True)
            b = traitlets.Int(2).tag(sync=True)
            c = traitlets.Int(3).tag(sync=True)

        wrapped = anywidget(MultiTraitWidget())
        assert wrapped.value == {"a": 1, "b": 2, "c": 3}

        # Test partial update
        wrapped._update({"a": 10})
        assert wrapped.value == {"a": 10, "b": 2, "c": 3}

        # Test multiple partial updates
        wrapped._update({"b": 20})
        assert wrapped.value == {"a": 10, "b": 20, "c": 3}

        # Test updating all traits
        wrapped._update({"a": 100, "b": 200, "c": 300})
        assert wrapped.value == {"a": 100, "b": 200, "c": 300}

    @staticmethod
    async def test_getitem_and_contains() -> None:
        """Test that __getitem__ and __contains__ are forwarded to the widget."""
        from typing import Any

        class DictLikeWidget(_anywidget.AnyWidget):
            _esm = ""
            data = traitlets.Dict({"a": 1, "b": 2}).tag(sync=True)

            def __getitem__(self, key: str) -> Any:
                return self.data[key]

            def __contains__(self, key: str) -> bool:
                return key in self.data

        wrapped = anywidget(DictLikeWidget())

        # Test __getitem__ forwarding
        assert wrapped["a"] == 1
        assert wrapped["b"] == 2

        # Test __contains__ forwarding
        assert "a" in wrapped
        assert "b" in wrapped
        assert "c" not in wrapped

        # Test KeyError propagation
        with pytest.raises(KeyError):
            _ = wrapped["nonexistent"]

    @staticmethod
    async def test_model_message_with_observe_and_state(
        k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        """Test that mo.state setters work inside widget observe callbacks.

        Regression test: when a model update message arrives from the
        frontend, the observe callback must run inside an execution
        context so that mo.state setters can trigger downstream re-runs.
        This test does NOT use mo.ui.anywidget() — the model exists
        without a view, verifying the model-to-cell mapping works
        independently of the UIElement path.
        """
        await k.run(
            [
                exec_req.get(
                    """
import anywidget
import traitlets
import marimo as mo

class Counter(anywidget.AnyWidget):
    _esm = ""
    count = traitlets.Int(0).tag(sync=True)

c = Counter()
get_count, set_count = mo.state(c.count)

def _on_count_change(_):
    set_count(c.count)

c.observe(_on_count_change, names="count")
"""
                ),
                exec_req.get("result = get_count()"),
            ]
        )

        assert k.globals["result"] == 0

        widget = k.globals["c"]
        model_id = WidgetModelId(widget._model_id)

        # Simulate a model update from the frontend
        await k.handle_message(
            ModelCommand(
                model_id=model_id,
                message=ModelUpdateMessage(
                    state={"count": 5},
                    buffer_paths=[],
                ),
                buffers=[],
            )
        )

        # The observe callback should have fired set_count,
        # which triggers re-execution of the cell reading get_count()
        assert k.globals["result"] == 5

    @staticmethod
    async def test_nested_model_observe_and_state(
        k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        """Test observe on a child widget nested inside a parent widget.

        Models the lonboard pattern: a Map widget holds Layer children,
        and the user observes trait changes on the inner layer. The
        parent (Map) is displayed via mo.ui.anywidget, but the observe
        callback is on the child layer which has its own model.
        """
        await k.run(
            [
                exec_req.get(
                    """
import anywidget
import traitlets
import marimo as mo

class Layer(anywidget.AnyWidget):
    _esm = ""
    selected_index = traitlets.Int(0).tag(sync=True)

class Map(anywidget.AnyWidget):
    _esm = ""
    layer = traitlets.Instance(Layer).tag(sync=True)

layer = Layer()
m = Map(layer=layer)
w = mo.ui.anywidget(m)

get_selected, set_selected = mo.state(layer.selected_index)
layer.observe(
    lambda _: set_selected(layer.selected_index),
    names="selected_index",
)
"""
                ),
                exec_req.get("result = get_selected()"),
            ]
        )

        assert k.globals["result"] == 0

        layer = k.globals["layer"]
        layer_model_id = WidgetModelId(layer._model_id)

        # Simulate frontend updating the child layer's trait
        await k.handle_message(
            ModelCommand(
                model_id=layer_model_id,
                message=ModelUpdateMessage(
                    state={"selected_index": 42},
                    buffer_paths=[],
                ),
                buffers=[],
            )
        )

        assert k.globals["result"] == 42

    @staticmethod
    async def test_observe_state_no_self_loop(
        k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        """Verify that __external__ sentinel doesn't cause self-loops.

        If a cell both defines and reads a state (get_count), plus has
        an observe callback that calls the setter, the defining cell
        should NOT re-run — only downstream cells should.
        """
        await k.run(
            [
                exec_req.get(
                    """
import anywidget
import traitlets
import marimo as mo

class Counter(anywidget.AnyWidget):
    _esm = ""
    count = traitlets.Int(0).tag(sync=True)

c = Counter()
get_count, set_count = mo.state(c.count)
c.observe(lambda _: set_count(c.count), names="count")

# Read the state in the SAME cell that defines it
same_cell_value = get_count()
run_count = globals().get("run_count", 0) + 1
"""
                ),
                exec_req.get("result = get_count()"),
            ]
        )

        assert k.globals["same_cell_value"] == 0
        assert k.globals["result"] == 0
        initial_run_count = k.globals["run_count"]

        widget = k.globals["c"]
        model_id = WidgetModelId(widget._model_id)

        await k.handle_message(
            ModelCommand(
                model_id=model_id,
                message=ModelUpdateMessage(
                    state={"count": 7},
                    buffer_paths=[],
                ),
                buffers=[],
            )
        )

        # Downstream cell should update
        assert k.globals["result"] == 7
        # The defining cell should NOT have re-run (no self-loop)
        assert k.globals["run_count"] == initial_run_count
