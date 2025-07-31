# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Literal, NewType, TypedDict, Union

# AnyWidget model id
WidgetModelId = NewType("WidgetModelId", str)

# Buffer paths
BufferPaths = list[list[Union[str, int]]]

# Widget model state
WidgetModelState = dict[str, Any]

# Widget model state without buffers
WidgetModelStateWithoutBuffers = dict[str, Any]


# AnyWidget model message
class TypedModelMessage(TypedDict):
    """
    A typed message for AnyWidget models.

    Args:
        state: The state of the model.
        buffer_paths: The buffer paths to update.
    """

    state: WidgetModelStateWithoutBuffers
    buffer_paths: BufferPaths


class TypedModelAction(TypedModelMessage):
    """
    A typed message for AnyWidget models.

    Args:
        method: The method to call on the model.
        state: The state of the model.
        buffer_paths: The buffer paths to update.
    """

    method: Literal["open", "update", "custom", "echo_update"]


class TypedModelMessageContent(TypedDict):
    """A typed payload for AnyWidget models."""

    data: TypedModelAction


class TypedModelMessagePayload(TypedDict):
    """
    A typed payload for AnyWidget models.

    This interface is what AnyWidget's comm.handle_msg expects
    """

    content: TypedModelMessageContent
    buffers: list[bytes]
