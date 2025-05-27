# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import hashlib
import weakref
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

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

if TYPE_CHECKING:
    from anywidget import (  # type: ignore [import-not-found,unused-ignore]  # noqa: E501
        AnyWidget,
    )

LOGGER = _loggers.marimo_logger()


# Weak dictionary
# When the widget is deleted, the UIElement will be deleted as well
cache: dict[Any, UIElement[Any, Any]] = weakref.WeakKeyDictionary()  # type: ignore[no-untyped-call, unused-ignore, assignment]  # noqa: E501


def from_anywidget(widget: AnyWidget) -> UIElement[Any, Any]:
    """Create a UIElement from an AnyWidget."""
    try:
        if widget not in cache:
            cache[widget] = anywidget(widget)  # type: ignore[no-untyped-call, unused-ignore, assignment]  # noqa: E501
        return cache[widget]
    except TypeError as e:
        # Unhashable widgets can't be used as keys in a WeakKeyDictionary
        LOGGER.warning(e)
        return anywidget(widget)


T = dict[str, Any]


@dataclass
class SendToWidgetArgs:
    content: Any
    buffers: Optional[Any] = None


@mddoc
class anywidget(UIElement[T, T]):
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

        def on_change(change: T) -> None:
            insert_buffer_paths(change, buffer_paths, buffers)
            current_state: dict[str, Any] = widget.get_state()
            changed_state: dict[str, Any] = {}
            for k, v in change.items():
                if k not in current_state:
                    changed_state[k] = v
                elif current_state[k] != v:
                    changed_state[k] = v
            widget.set_state(changed_state)

        js_hash: str = hashlib.md5(
            js.encode("utf-8"), usedforsecurity=False
        ).hexdigest()

        self._prev_state = json_args

        super().__init__(
            component_name="marimo-anywidget",
            initial_value=self._prev_state,
            label="",
            args={
                "js-url": mo_data.js(js).url if js else "",  # type: ignore [unused-ignore]  # noqa: E501
                "js-hash": js_hash,
                "css": css,
                "buffer-paths": buffer_paths,
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
        initialization_args: InitializationArgs[
            dict[str, Any], dict[str, Any]
        ],
    ) -> None:
        super()._initialize(initialization_args)
        # Add the ui_element_id after the widget is initialized
        comm = self.widget.comm
        if isinstance(comm, MarimoComm):
            comm.ui_element_id = self._id

    def _receive_from_frontend(self, args: SendToWidgetArgs) -> None:
        self.widget._handle_custom_msg(args.content, args.buffers)

    def _convert_value(self, value: T) -> T:
        if isinstance(value, dict) and isinstance(self._prev_state, dict):
            merged = {**self._prev_state, **value}
            self._prev_state = merged
            return merged

        LOGGER.warning(
            f"Expected anywidget value to be a dict, got {type(value)}"
        )
        self._prev_state = value
        return value

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
