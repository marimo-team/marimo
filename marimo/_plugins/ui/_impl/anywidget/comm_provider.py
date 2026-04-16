# Copyright 2026 Marimo. All rights reserved.
"""Comm backend for the ``comm`` library.

Patches ``comm.create_comm`` so that anywidget's descriptor API
(``MimeBundleDescriptor``) creates comms that broadcast through
marimo's notification system instead of being silent no-ops.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from marimo._loggers import marimo_logger
from marimo._plugins.ui._impl.anywidget.init import (
    WIDGET_COMM_MANAGER,
    CommLifecycleItem,
)
from marimo._plugins.ui._impl.comm import MarimoComm
from marimo._runtime.context import ContextNotInitializedError, get_context
from marimo._types.ids import WidgetModelId

LOGGER = marimo_logger()


def _is_anywidget_comm(target_name: str, data: dict[str, Any] | None) -> bool:
    """Check if this comm is being opened by anywidget.

    anywidget's ``open_comm`` always uses ``target_name="jupyter.widget"``
    and includes ``_model_module: "anywidget"`` in the state.
    """
    if target_name != "jupyter.widget":
        return False
    if data is None:
        return False
    state = data.get("state", {})
    return bool(state.get("_model_module") == "anywidget")


def patch_comm_create() -> None:
    """Replace ``comm.create_comm`` with a marimo-backed implementation.

    Only intercepts comms created by anywidget (identified by
    ``target_name`` and ``_model_module``). All other comms fall
    through to a no-op ``DummyComm``.

    This is idempotent -- calling it multiple times is safe.
    """
    try:
        import comm
        from comm import DummyComm
    except ImportError:
        return

    def _marimo_create_comm(
        *,
        target_name: str = "comm",
        data: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        buffers: list[Any] | None = None,
        comm_id: str | None = None,
        **kwargs: Any,
    ) -> MarimoComm | DummyComm:
        if not _is_anywidget_comm(target_name, data):
            LOGGER.warning(
                "comm.create_comm called with target_name=%r but "
                "not recognized as anywidget; returning no-op comm",
                target_name,
            )
            return DummyComm(
                target_name=target_name,
                data=data,
                metadata=metadata,
                buffers=buffers,
                comm_id=comm_id,
                **kwargs,
            )

        resolved_id = WidgetModelId(comm_id or uuid4().hex)

        if data is not None:
            # Tag with method="open" so MarimoComm._broadcast creates a
            # ModelOpen (not ModelUpdate) on first send.
            data = {**data, "method": "open"}

        c = MarimoComm(
            comm_id=resolved_id,
            comm_manager=WIDGET_COMM_MANAGER,
            target_name=target_name,
            data=data,
            metadata=metadata,
            buffers=buffers,
            **kwargs,
        )
        # Register lifecycle cleanup so the comm is closed when
        # the cell is re-run or deleted.
        try:
            ctx = get_context()
            ctx.cell_lifecycle_registry.add(CommLifecycleItem(c))
        except ContextNotInitializedError:
            pass
        return c

    comm.create_comm = _marimo_create_comm  # type: ignore[assignment]
