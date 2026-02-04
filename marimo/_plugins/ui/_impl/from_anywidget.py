# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import weakref
from copy import deepcopy
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    TypedDict,
    TypeVar,
    cast,
)

import marimo._output.data.data as mo_data
from marimo import _loggers
from marimo._output.rich_help import mddoc
from marimo._plugins.ui._core.ui_element import InitializationArgs, UIElement
from marimo._plugins.ui._impl.comm import MarimoComm
from marimo._types.ids import WidgetModelId
from marimo._utils.code import hash_code

AnyWidgetState = TypeAlias = dict[str, Any]


class WireFormat(TypedDict):
    """Wire format for anywidget state with binary buffers."""

    state: AnyWidgetState
    bufferPaths: list[list[str | int]]
    buffers: list[str]


class ModelIdRef(TypedDict):
    """Reference to a model by its ID. The frontend retrieves state from the open message."""

    model_id: WidgetModelId


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


def get_anywidget_state(widget: AnyWidget) -> AnyWidgetState:
    """Get the state of an AnyWidget."""
    # Remove widget-specific system traits not needed for the frontend
    ignored_traits = {
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
    }

    state: dict[str, Any] = widget.get_state()

    # Filter out system traits from the serialized state
    # This should include the binary data,
    # see marimo/_smoke_tests/issues/2366-anywidget-binary.py
    return {k: v for k, v in state.items() if k not in ignored_traits}


def get_anywidget_model_id(widget: AnyWidget) -> WidgetModelId:
    """Get the model_id of an AnyWidget."""
    model_id = getattr(widget, "_model_id", None)
    if not model_id:
        raise RuntimeError("Widget model_id is not set")
    return WidgetModelId(model_id)


@mddoc
class anywidget(UIElement[ModelIdRef, AnyWidgetState]):
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

        js: str = getattr(widget, "_esm", "")  # type: ignore [unused-ignore]
        js_hash = hash_code(js)

        # Trigger comm initialization early to ensure _model_id is set
        _ = widget.comm

        # Get the model_id from the widget (should always be set after comm init)
        model_id = get_anywidget_model_id(widget)

        # Initial value is just the model_id reference
        # The frontend retrieves the actual state from the 'open' message
        super().__init__(
            component_name="marimo-anywidget",
            initial_value=ModelIdRef(model_id=model_id),
            label=None,
            args={
                "js-url": mo_data.js(js).url if js else "",  # type: ignore [unused-ignore]  # noqa: E501
                "js-hash": js_hash,
            },
            on_change=None,
        )

    def _initialize(
        self,
        initialization_args: InitializationArgs[ModelIdRef, AnyWidgetState],
    ) -> None:
        super()._initialize(initialization_args)
        # Add the ui_element_id after the widget is initialized
        comm = self.widget.comm
        if isinstance(comm, MarimoComm):
            comm.ui_element_id = self._id

    def _convert_value(
        self, value: ModelIdRef | AnyWidgetState
    ) -> AnyWidgetState:
        if not isinstance(value, dict):
            raise ValueError(f"Expected dict, got {type(value)}")

        # Check if this is a ModelIdRef (initial value from frontend)
        model_id = value.get("model_id")
        if model_id and len(value) == 1:
            # Initial value - just return empty, the widget manages its own state
            return {}

        # Otherwise, it's a state update from the frontend
        # Update the widget's state
        self.widget.set_state(value)
        return cast(AnyWidgetState, value)

    @property
    def value(self) -> AnyWidgetState:
        """The element's current value as a plain dictionary (wire format decoded)."""
        return get_anywidget_state(self.widget)

    @value.setter
    def value(self, value: AnyWidgetState) -> None:
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

    def __getitem__(self, key: Any) -> Any:
        """Forward __getitem__ to the wrapped widget."""
        return self.widget[key]

    def __contains__(self, key: Any) -> bool:
        """Forward __contains__ to the wrapped widget."""
        return key in self.widget
