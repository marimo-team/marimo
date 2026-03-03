# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, cast
from uuid import uuid4

if TYPE_CHECKING:
    import ipywidgets  # type: ignore

    from marimo._runtime.context.types import RuntimeContext

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.comm import (  # pyright: ignore[reportMissingTypeStubs]
    BufferType,
    MarimoComm,
    MarimoCommManager,
)
from marimo._runtime.cell_lifecycle_item import CellLifecycleItem
from marimo._runtime.context import ContextNotInitializedError, get_context


class CommLifecycleItem(CellLifecycleItem):
    def __init__(self, comm: MarimoComm) -> None:
        self._comm = comm

    def create(self, context: RuntimeContext) -> None:
        del context

    def dispose(self, context: RuntimeContext, deletion: bool) -> bool:
        del context, deletion
        self._comm.close()
        return True


# Initialize ipywidgets using a MarimoComm
def init_marimo_widget(w: ipywidgets.Widget) -> None:
    DependencyManager.ipywidgets.require("for anywidget support.")
    import ipywidgets  # type: ignore

    __protocol_version__ = ipywidgets._version.__protocol_version__
    from marimo._plugins.ui._impl.anywidget.utils import extract_buffer_paths

    # Get the initial state of the widget
    state, buffer_paths, buffers = extract_buffer_paths(w.get_state())

    # Generate a random model_id so we can assign the same id to the comm
    if getattr(w, "_model_id", None) is None:
        w._model_id = uuid4().hex

    # Initialize the comm...this will also send the initial state of the widget
    w.comm = MarimoComm(
        comm_id=w._model_id,  # pyright: ignore
        comm_manager=WIDGET_COMM_MANAGER,
        target_name="jupyter.widgets",
        data={"state": state, "buffer_paths": buffer_paths, "method": "open"},
        buffers=cast(BufferType, buffers),
        metadata={"version": __protocol_version__},
    )

    # Register ipywidgets' message handler so it can process incoming messages
    # with proper buffer handling via _put_buffers and serializer support
    w.comm.on_msg(w._handle_msg)

    # Register lifecycle item so the comm is closed when the cell is
    # re-executed or deleted (sends ModelClose to the frontend).
    try:
        ctx = get_context()
        ctx.cell_lifecycle_registry.add(CommLifecycleItem(w.comm))
    except ContextNotInitializedError:
        pass


WIDGET_COMM_MANAGER = MarimoCommManager()
