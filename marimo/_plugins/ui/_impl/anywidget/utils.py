# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.anywidget.types import (
    BufferPaths,
    TypedModelMessage,
    WidgetModelState,
    WidgetModelStateWithoutBuffers,
)

if TYPE_CHECKING:
    from typing_extensions import TypeIs


def extract_buffer_paths(
    message: WidgetModelState,
) -> tuple[WidgetModelStateWithoutBuffers, BufferPaths, list[bytes]]:
    """
    Extract buffer paths from a message.
    """
    DependencyManager.ipywidgets.require("for anywidget support.")
    import ipywidgets  # type: ignore

    _remove_buffers = ipywidgets.widgets.widget._remove_buffers  # type: ignore

    # Get the initial state of the widget
    state, buffer_paths, buffers = _remove_buffers(message)  # type: ignore

    return state, buffer_paths, buffers  # type: ignore


def insert_buffer_paths(
    state: WidgetModelStateWithoutBuffers,
    buffer_paths: BufferPaths,
    buffers: list[bytes],
) -> WidgetModelState:
    """
    Insert buffer paths into a message.
    """
    DependencyManager.ipywidgets.require("for anywidget support.")
    import ipywidgets  # type: ignore

    _put_buffers = ipywidgets.widgets.widget._put_buffers  # type: ignore
    _put_buffers(state, buffer_paths, buffers)
    return state


def is_model_message(message: object) -> TypeIs[TypedModelMessage]:
    """
    Check if a message is a model message.
    """
    if not isinstance(message, dict):
        return False
    keys = ("method", "state", "buffer_paths")
    if not all(key in message for key in keys):
        return False
    return True
