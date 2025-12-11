# Copyright 2024 Marimo. All rights reserved.
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
    decode_from_wire,
    encode_to_wire,
    from_anywidget,
)
from marimo._runtime.requests import SetUIElementValueRequest
from marimo._runtime.runtime import Kernel
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
        assert wrapped._initial_value == {
            "state": {"arr": {"a": 1}},
            "bufferPaths": [],
            "buffers": [],
        }
        assert wrapped._component_args == {
            "css": "",
            "js-url": "",
            "js-hash": md5(b"").hexdigest(),
        }

    @staticmethod
    async def test_initialization_with_dataview() -> None:
        # Create a simple array-like structure without numpy
        import base64

        arr = [1, 2, 3]
        wrapped = anywidget(
            Widget(arr={"bytes": bytes(arr), "shape": (len(arr),)})
        )
        # _initial_value is wire format (buffers are extracted to separate array)
        assert wrapped._initial_value == {
            "state": {"arr": {"shape": (3,)}},
            "bufferPaths": [["arr", "bytes"]],
            "buffers": [base64.b64encode(bytes([1, 2, 3])).decode("utf-8")],
        }
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
        assert wrapped._initial_value == {
            "state": {
                "serializable": 1,
                "non_serializable": None,
            },
            "bufferPaths": [],
            "buffers": [],
        }

    @staticmethod
    async def test_skips_non_sync_traits() -> None:
        class NonSyncWidget(_anywidget.AnyWidget):
            _esm = ""
            non_sync = traitlets.Int(1)
            sync = traitlets.Int(2).tag(sync=True)

        wrapped = anywidget(NonSyncWidget())
        assert wrapped._initial_value == {
            "state": {"sync": 2},
            "bufferPaths": [],
            "buffers": [],
        }

    @staticmethod
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
            SetUIElementValueRequest.from_ids_and_values(
                [(ui_element._id, {"value": 42})]
            )
        )

        assert ui_element.value == {"value": 42}
        assert ui_element.widget.value == 42

    @staticmethod
    async def test_buffers() -> None:
        import base64

        class BufferWidget(_anywidget.AnyWidget):
            _esm = ""
            array = traitlets.Bytes().tag(sync=True)

        data = bytes([1, 2, 3, 4])
        wrapped = anywidget(BufferWidget(array=data))

        # _initial_value is wire format (buffers are extracted to separate array)
        assert wrapped._initial_value == {
            "state": {},
            "bufferPaths": [["array"]],
            "buffers": [base64.b64encode(data).decode("utf-8")],
        }

        # test buffers are inlined as base64 in the wire format
        assert "AQIDBA==" in wrapped.text
        assert "array" in wrapped.text

        # Test updating the buffer
        new_data = bytes([5, 6, 7, 8])
        wrapped.array = new_data
        # value property returns decoded state with buffers re-inserted
        assert wrapped.value["array"] == data

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

        # Test updating with new traits
        wrapped._update({"d": 4})
        assert wrapped.value == {"a": 100, "b": 200, "c": 300, "d": 4}


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
class TestWireFormat:
    """Tests for encode_to_wire and decode_from_wire functions."""

    @staticmethod
    def test_decode_from_wire_not_wire_format() -> None:
        """Test that non-wire format dicts are returned as-is."""
        plain_dict = {"a": 1, "b": 2}
        result = decode_from_wire(plain_dict)
        assert result == plain_dict

        # Test with only state
        partial_wire = {"state": {"a": 1}}
        result = decode_from_wire(partial_wire)
        assert result == partial_wire

    @staticmethod
    def test_decode_from_wire_empty_buffers() -> None:
        """Test decoding wire format with no buffers."""
        wire = {"state": {"a": 1, "b": 2}, "bufferPaths": [], "buffers": []}
        result = decode_from_wire(wire)
        assert result == {"a": 1, "b": 2}

    @staticmethod
    def test_decode_from_wire_with_buffers() -> None:
        """Test decoding wire format with base64 buffers."""
        import base64

        data = b"Hello, World!"
        base64_data = base64.b64encode(data).decode("utf-8")

        wire = {
            "state": {"text": base64_data, "number": 42},
            "bufferPaths": [["text"]],
            "buffers": [base64_data],
        }

        result = decode_from_wire(wire)
        assert result["number"] == 42
        assert result["text"] == data

    @staticmethod
    def test_decode_from_wire_nested_buffers() -> None:
        """Test decoding wire format with nested buffer paths."""
        import base64

        data1 = b"first"
        data2 = b"second"
        base64_1 = base64.b64encode(data1).decode("utf-8")
        base64_2 = base64.b64encode(data2).decode("utf-8")

        wire = {
            "state": {
                "nested": {"buf1": base64_1, "deeper": {"buf2": base64_2}}
            },
            "bufferPaths": [["nested", "buf1"], ["nested", "deeper", "buf2"]],
            "buffers": [base64_1, base64_2],
        }

        result = decode_from_wire(wire)
        assert result["nested"]["buf1"] == data1
        assert result["nested"]["deeper"]["buf2"] == data2

    @staticmethod
    def test_decode_from_wire_array_buffers() -> None:
        """Test decoding wire format with buffers in arrays."""
        import base64

        data = b"test"
        base64_data = base64.b64encode(data).decode("utf-8")

        wire = {
            "state": {"items": [base64_data, "middle", base64_data]},
            "bufferPaths": [["items", 0], ["items", 2]],
            "buffers": [base64_data, base64_data],
        }

        result = decode_from_wire(wire)
        assert result["items"][0] == data
        assert result["items"][1] == "middle"
        assert result["items"][2] == data

    @staticmethod
    def test_encode_to_wire_no_buffers() -> None:
        """Test encoding state without buffers."""
        state = {"a": 1, "b": "text", "c": {"d": True}}
        result = encode_to_wire(state)

        assert result["state"] == state
        assert result["bufferPaths"] == []
        assert result["buffers"] == []

    @staticmethod
    def test_encode_to_wire_with_bytes() -> None:
        """Test encoding state with bytes."""
        import base64

        data = b"Hello, World!"
        state = {"text": data, "number": 42}

        result = encode_to_wire(state)

        assert result["state"]["number"] == 42
        # The buffer should be extracted
        assert len(result["buffers"]) == 1
        assert len(result["bufferPaths"]) == 1
        # Verify the buffer is base64 encoded
        decoded = base64.b64decode(result["buffers"][0])
        assert decoded == data

    @staticmethod
    def test_encode_to_wire_nested_bytes() -> None:
        """Test encoding state with nested bytes."""
        import base64

        data1 = b"first"
        data2 = b"second"
        state = {
            "nested": {"buf1": data1, "deeper": {"buf2": data2}},
            "regular": "value",
        }

        result = encode_to_wire(state)

        assert result["state"]["regular"] == "value"
        assert len(result["buffers"]) == 2
        assert len(result["bufferPaths"]) == 2

        # Verify buffers are base64 encoded
        buffers = [base64.b64decode(b) for b in result["buffers"]]
        assert data1 in buffers
        assert data2 in buffers

    @staticmethod
    def test_round_trip_encoding() -> None:
        """Test that encode -> decode -> encode produces consistent results."""
        original_state = {
            "buffer": b"test data",
            "nested": {"inner_buffer": b"more data"},
            "text": "plain text",
            "number": 123,
        }

        # Encode to wire format
        encoded = encode_to_wire(original_state)

        # Decode back
        decoded = decode_from_wire(encoded)

        # Verify decoded state matches original
        assert decoded["buffer"] == b"test data"
        assert decoded["nested"]["inner_buffer"] == b"more data"
        assert decoded["text"] == "plain text"
        assert decoded["number"] == 123

        # Re-encode
        re_encoded = encode_to_wire(decoded)

        # Verify structure is consistent
        assert len(re_encoded["buffers"]) == len(encoded["buffers"])
        assert len(re_encoded["bufferPaths"]) == len(encoded["bufferPaths"])

        # Verify buffers match (order might differ, so compare sets)
        encoded_buffers = set(encoded["buffers"])
        re_encoded_buffers = set(re_encoded["buffers"])
        assert encoded_buffers == re_encoded_buffers

    @staticmethod
    def test_encode_to_wire_empty_bytes() -> None:
        """Test encoding empty bytes."""
        import base64

        state = {"empty": b"", "data": b"content"}
        result = encode_to_wire(state)

        assert len(result["buffers"]) == 2
        # Verify empty bytes is properly encoded
        assert (
            base64.b64decode(result["buffers"][0]) == b""
            or base64.b64decode(result["buffers"][1]) == b""
        )

    @staticmethod
    def test_decode_from_wire_missing_buffers() -> None:
        """Test decoding when bufferPaths exist but buffers are missing."""
        wire = {
            "state": {"a": 1},
            "bufferPaths": [["a"]],
            # Missing buffers array
        }

        # Should handle gracefully - buffers default to []
        result = decode_from_wire(wire)
        # State should be returned but buffers won't be inserted
        assert "a" in result
