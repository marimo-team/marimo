# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import weakref
from copy import deepcopy
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    TypeAlias,
    TypedDict,
    TypeVar,
    cast,
)

import marimo._output.data.data as mo_data
from marimo import _loggers
from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.rich_help import mddoc
from marimo._plugins.ui._core.ui_element import InitializationArgs, UIElement
from marimo._plugins.ui._impl.comm import MarimoComm
from marimo._types.ids import WidgetModelId
from marimo._utils.code import hash_code
from marimo._utils.methods import getcallable

AnyWidgetState: TypeAlias = dict[str, Any]


class WireFormat(TypedDict):
    """Wire format for anywidget state with binary buffers."""

    state: AnyWidgetState
    bufferPaths: list[list[str | int]]
    buffers: list[str]


class ModelIdRef(TypedDict):
    """Reference to a model by its ID. The frontend retrieves state from the open message."""

    model_id: WidgetModelId


if TYPE_CHECKING:
    from anywidget import (  # type: ignore [import-not-found,unused-ignore]
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
_cache: WeakCache[AnyWidget, UIElement[Any, Any]] = WeakCache()  # type: ignore[no-untyped-call, unused-ignore, assignment]


def from_anywidget(widget: AnyWidget) -> UIElement[Any, Any]:
    """Create a UIElement from an AnyWidget."""
    el = _cache.get(widget)
    if el is None:
        el = anywidget(widget)
        _cache.add(widget, el)  # type: ignore[no-untyped-call, unused-ignore, assignment]
    return el


def _sync_widget_state(widget: AnyWidget) -> None:
    """Call _repr_mimebundle_ to sync widget state if available.

    Plotly's FigureWidget (and subclasses like plotly-resampler's
    FigureWidgetResampler) maintain a split internal model: the figure's
    data lives in _data/_layout_obj, but the widget traits (_widget_data,
    _widget_layout) are only updated during _repr_mimebundle_(). This call
    ensures the widget traits reflect the current figure state before the
    comm sends state to the frontend.
    """
    repr_mimebundle = getcallable(widget, "_repr_mimebundle_")
    if repr_mimebundle is not None:
        try:
            repr_mimebundle()
        except Exception:
            # Not critical — widget may still work without this sync
            LOGGER.debug(
                "Failed to call _repr_mimebundle_ on %s",
                type(widget).__name__,
            )


_WIDGET_REF_PREFIX = "anywidget:"


def _try_get_widget_model_id(value: Any) -> str | None:
    """Return the `_model_id` of a value if it looks like an anywidget.

    Detects two shapes:
    - ipywidgets-derived `AnyWidget` instances (have `_model_id` set by
      `init_marimo_widget` on construction).
    - Protocol-based widgets (RFC 0001) that expose a `MimeBundleDescriptor`
      with a resolved `model_id`. We don't have a stable hook for those yet,
      so for now we only catch the ipywidgets path — extending detection to
      the protocol shape can land alongside `WidgetTrait` support.
    """
    model_id = getattr(value, "_model_id", None)
    if isinstance(model_id, str) and model_id:
        return model_id
    return None


def _replace_widget_refs(value: Any) -> Any:
    """Recursively replace nested anywidget instances with `anywidget:<id>`.

    Walks dicts, lists, and tuples so widget refs can live anywhere in the
    state tree (e.g. `{"layout": {"left": <widget>, "right": None}}`).
    Any value with an `_model_id` attribute is replaced with the wire-format
    string the frontend's `host.getWidget(ref)` expects.

    Returns a new container if any replacement occurred, otherwise the
    original value (so untouched state can pass through without a copy).
    """
    model_id = _try_get_widget_model_id(value)
    if model_id is not None:
        return f"{_WIDGET_REF_PREFIX}{model_id}"
    if isinstance(value, dict):
        replaced = {k: _replace_widget_refs(v) for k, v in value.items()}
        # Preserve identity when nothing changed — avoids a needless copy
        # on the hot serialization path for widgets without nested refs.
        if all(replaced[k] is value[k] for k in value):
            return value
        return replaced
    if isinstance(value, list):
        replaced_list = [_replace_widget_refs(v) for v in value]
        if all(a is b for a, b in zip(replaced_list, value)):
            return value
        return replaced_list
    if isinstance(value, tuple):
        replaced_tuple = tuple(_replace_widget_refs(v) for v in value)
        if all(a is b for a, b in zip(replaced_tuple, value)):
            return value
        return replaced_tuple
    return value


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
    filtered = {k: v for k, v in state.items() if k not in ignored_traits}

    # Replace nested AnyWidget values with `anywidget:<model_id>` strings
    # so the frontend can resolve them via `host.getWidget(ref)`. Children
    # already have their comms opened (ipywidgets'
    # `Widget.on_widget_constructed` fires `init_marimo_widget` on
    # construction), so the frontend has the model registered by the time
    # the parent's state arrives.
    return cast(AnyWidgetState, _replace_widget_refs(filtered))


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
                "js-url": mo_data.js(js).url if js else "",  # type: ignore [unused-ignore]
                "js-hash": js_hash,
                "model-id": model_id,
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

    def _ensure_widget_synced(self) -> None:
        """Sync widget state lazily on first access (idempotent).

        Some widgets (e.g. plotly FigureWidget, plotly-resampler) only sync
        their internal data to widget traits during _repr_mimebundle_().
        This ensures the sync happens once, the first time the element is
        rendered.

        NOTE: @once cannot be used here because Html is a @dataclass with
        eq=True/frozen=False, making instances unhashable (WeakKeyDictionary
        requires hashable keys).

        NOTE: If you are a widget author and need to sync state from your
        widget, do not do this in the repr_mimebundle method.
        This is not a supported pattern and may break in the future.
        """
        # Use object.__dict__ directly to bypass anywidget's
        # custom __getattr__/__setattr__
        if self.__dict__.get("_widget_synced", False):
            return
        object.__setattr__(self, "_widget_synced", True)
        _sync_widget_state(self.widget)

    @property
    def text(self) -> str:
        self._ensure_widget_synced()
        return super().text

    def _mime_(self) -> tuple[KnownMimeType, str]:
        self._ensure_widget_synced()
        return super()._mime_()

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
