# Copyright 2026 Marimo. All rights reserved.
"""Comm backend for the ``comm`` library.

Patches ``comm.create_comm`` so that anywidget's descriptor API
(``MimeBundleDescriptor``) creates comms that broadcast through
marimo's notification system instead of being silent no-ops.
"""

from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4

from marimo._plugins.ui._impl.anywidget.init import (
    WIDGET_COMM_MANAGER,
    CommLifecycleItem,
)
from marimo._plugins.ui._impl.comm import MarimoComm
from marimo._runtime.context import ContextNotInitializedError, get_context
from marimo._types.ids import WidgetModelId


def patch_comm_create() -> None:
    """Replace ``comm.create_comm`` with a marimo-backed implementation.

    This is idempotent -- calling it multiple times is safe.
    """
    try:
        import comm
    except ImportError:
        return

    def _marimo_create_comm(
        *,
        target_name: str = "comm",
        data: Optional[dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
        buffers: Optional[list[Any]] = None,
        comm_id: Optional[str] = None,
        **kwargs: Any,
    ) -> MarimoComm:
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
