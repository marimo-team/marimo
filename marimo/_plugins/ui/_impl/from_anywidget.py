# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import base64
import hashlib
import weakref
from copy import deepcopy
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    Optional,
    TypedDict,
    TypeVar,
    cast,
)

import marimo._output.data.data as mo_data
from marimo import _loggers
from marimo._output.rich_help import mddoc
from marimo._plugins.ui._core.ui_element import InitializationArgs, UIElement
from marimo._plugins.ui._impl.anywidget.utils import (
    extract_buffer_paths,
    insert_buffer_paths,
)
from marimo._plugins.ui._impl.comm import MarimoComm
from marimo._runtime.functions import Function


class WireFormat(TypedDict):
    state: dict[str, Any]
    bufferPaths: list[list[str | int]]
    buffers: list[str]


def decode_from_wire(
    wire: WireFormat | dict[str, Any],
) -> dict[str, Any]:
    """Decode wire format { state, bufferPaths, buffers } to plain state with bytes."""
    if "state" not in wire or "bufferPaths" not in wire:
        return wire  # Not wire format, return as-is

    state = wire.get("state", {})
    buffer_paths = wire.get("bufferPaths", [])
    buffers_base64: list[str] = wire.get("buffers", [])

    if buffer_paths and buffers_base64:
        decoded_buffers = [base64.b64decode(b) for b in buffers_base64]
        return insert_buffer_paths(state, buffer_paths, decoded_buffers)

    if buffer_paths or buffers_base64:
        LOGGER.warning(
            "Expected wire format to have buffers, but got %s", wire
        )
        return state

    return state


def encode_to_wire(
    state: dict[str, Any],
) -> WireFormat:
    """Encode plain state with bytes to wire format { state, bufferPaths, buffers }."""
    state_no_buffers, buffer_paths, buffers = extract_buffer_paths(state)

    # Convert bytes to base64
    buffers_base64 = [base64.b64encode(b).decode("utf-8") for b in buffers]

    return WireFormat(
        state=state_no_buffers,
        bufferPaths=buffer_paths,
        buffers=buffers_base64,
    )


if TYPE_CHECKING:
    from anywidget import (  # type: ignore [import-not-found,unused-ignore]  # noqa: E501
        AnyWidget,
    )


LOGGER = _loggers.marimo_logger()

K = TypeVar("K")
V = TypeVar("V")


class WeakCache(Generic[K, V]):
    """A WeakCache "watches" the key and removes its entry if the key is destroyed."""

    def __init__(self) -> None:
        self._data: dict[int, V] = {}
        self._finalizers: dict[int, weakref.finalize[[int], K]] = {}

    def add(self, k: K, v: V) -> None:
        oid: int = id(k)  # finalize will be called before id is reused
        self._data[oid] = v
        self._finalizers[oid] = weakref.finalize(k, self._cleanup, oid)

    def get(self, k: K) -> V | None:
        return self._data.get(id(k))

    def __len__(self) -> int:
        return len(self._data)

    def _cleanup(self, oid: int) -> None:
        self._data.pop(oid, None)
        self._finalizers.pop(oid, None)


# Weak dictionary
# When the widget is deleted, the UIElement will be deleted as well
_cache: WeakCache[AnyWidget, UIElement[Any, Any]] = WeakCache()  # type: ignore[no-untyped-call, unused-ignore, assignment]  # noqa: E501


def from_anywidget(widget: AnyWidget) -> UIElement[Any, Any]:
    """Create a UIElement from an AnyWidget."""
    if not (el := _cache.get(widget)):
        el = anywidget(widget)
        _cache.add(widget, el)  # type: ignore[no-untyped-call, unused-ignore, assignment]  # noqa: E501
    return el


T = dict[str, Any]


@dataclass
class SendToWidgetArgs:
    content: Any
    buffers: Optional[Any] = None


@mddoc
class anywidget(UIElement[WireFormat, T]):
    """Create a UIElement from an AnyWidget.

    This proxies all the widget's attributes and methods, allowing seamless
    integration of AnyWidget instances with Marimo's UI system.

    Examples:
        ```python
        from drawdata import ScatterWidget
        import marimo as mo

        scatter = ScatterWidget()
        scatter = mo.ui.anywidget(scatter)

        # In another cell, access its value
        # This works for all widgets
        scatter.value

        # Or attributes specifically on the ScatterWidget
        scatter.data_as_pandas
        scatter.data_as_polars
        ```

    Attributes:
        value (Dict[str, Any]): The value of the widget's traits as a dictionary.
        widget (AnyWidget): The widget being wrapped.

    Args:
        widget (AnyWidget): The widget to wrap.
    """

    def __init__(self, widget: AnyWidget):
        self.widget = widget
        # This gets set to True in super().__init__()
        self._initialized = False

        # Get state with custom serializers properly applied
        state: dict[str, Any] = widget.get_state()
        _state_no_buffers, buffer_paths, buffers = extract_buffer_paths(state)

        # Remove widget-specific system traits not needed for the frontend
        ignored_traits = [
            "comm",
            "layout",
            "log",
            "tabbable",
            "tooltip",
            "keys",
            "_esm",
            "_css",
            "_anywidget_id",
            "_msg_callbacks",
            "_dom_classes",
            "_model_module",
            "_model_module_version",
            "_model_name",
            "_property_lock",
            "_states_to_send",
            "_view_count",
            "_view_module",
            "_view_module_version",
            "_view_name",
        ]

        # Filter out system traits from the serialized state
        # This should include the binary data,
        # see marimo/_smoke_tests/issues/2366-anywidget-binary.py
        json_args: T = {
            k: v for k, v in state.items() if k not in ignored_traits
        }

        js: str = widget._esm if hasattr(widget, "_esm") else ""  # type: ignore [unused-ignore]  # noqa: E501
        css: str = widget._css if hasattr(widget, "_css") else ""  # type: ignore [unused-ignore]  # noqa: E501

        def on_change(change: dict[str, Any]) -> None:
            # Decode wire format to plain state with bytes
            state = decode_from_wire(change)

            # Only update traits that have actually changed
            current_state: dict[str, Any] = widget.get_state()
            changed_state: dict[str, Any] = {}

            for k, v in state.items():
                if k not in current_state:
                    changed_state[k] = v
                elif current_state[k] != v:
                    changed_state[k] = v

            if changed_state:
                widget.set_state(changed_state)

        js_hash: str = hashlib.md5(
            js.encode("utf-8"), usedforsecurity=False
        ).hexdigest()

        # Store plain state with bytes for merging
        self._prev_state = json_args

        # Initial value is wire format: { state, bufferPaths, buffers }
        initial_wire = encode_to_wire(json_args)

        super().__init__(
            component_name="marimo-anywidget",
            initial_value=initial_wire,
            label="",
            args={
                "js-url": mo_data.js(js).url if js else "",  # type: ignore [unused-ignore]  # noqa: E501
                "js-hash": js_hash,
                "css": css,
            },
            on_change=on_change,
            functions=(
                Function(
                    name="send_to_widget",
                    arg_cls=SendToWidgetArgs,
                    function=self._receive_from_frontend,
                ),
            ),
        )

    def _initialize(
        self,
        initialization_args: InitializationArgs[WireFormat, dict[str, Any]],
    ) -> None:
        super()._initialize(initialization_args)
        # Add the ui_element_id after the widget is initialized
        comm = self.widget.comm
        if isinstance(comm, MarimoComm):
            comm.ui_element_id = self._id

    def _receive_from_frontend(self, args: SendToWidgetArgs) -> None:
        state = decode_from_wire(
            WireFormat(
                state=args.content.get("state", {}),
                bufferPaths=args.content.get("bufferPaths", []),
                buffers=args.buffers or [],
            )
        )
        self.widget._handle_custom_msg(state, args.buffers)

    def _convert_value(self, value: WireFormat) -> T:
        if isinstance(value, dict) and isinstance(self._prev_state, dict):
            # Decode wire format to plain state with bytes
            decoded_state = decode_from_wire(value)

            # Merge with previous state
            merged = {**self._prev_state, **decoded_state}
            self._prev_state = merged

            # Encode back to wire format for frontend
            # NB: This needs to be the wire format to work
            # although the types say it should be the plain state,
            # otherwise the frontend loses some information
            return cast(T, encode_to_wire(merged))

        LOGGER.warning(
            f"Expected anywidget value to be a dict, got {type(value)}"
        )
        self._prev_state = value
        return cast(T, value)

    @property
    def value(self) -> T:
        """The element's current value as a plain dictionary (wire format decoded)."""
        # Get the internal value (which is in wire format)
        internal_value = super().value
        # Decode it to plain state for user-facing code
        return decode_from_wire(internal_value)  # type: ignore[return-value]

    @value.setter
    def value(self, value: T) -> None:
        del value
        raise RuntimeError("Setting the value of a UIElement is not allowed.")

    def __deepcopy__(self, memo: Any) -> Any:
        # Overriding UIElement deepcopy implementation
        widget_deep_copy = deepcopy(self.widget, memo)
        return from_anywidget(widget_deep_copy)  # reuse caching

    # After the widget has been initialized
    # forward all setattr to the widget
    def __setattr__(self, name: str, value: Any) -> None:
        if self._initialized:
            # If the widget has the attribute, set it
            if hasattr(self.widget, name):
                return setattr(self.widget, name, value)
            return super().__setattr__(name, value)
        return super().__setattr__(name, value)

    # After the widget has been initialized
    # forward all getattr to the widget
    def __getattr__(self, name: str) -> Any:
        if name in ("widget", "_initialized"):
            try:
                return self.__getattribute__(name)
            except AttributeError:
                return None
        return getattr(self.widget, name)
