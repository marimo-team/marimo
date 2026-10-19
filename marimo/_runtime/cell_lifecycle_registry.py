# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import dataclasses

from marimo._runtime.cell_lifecycle_item import CellLifecycleItem
from marimo._types.ids import CellId_t


@dataclasses.dataclass
class CellLifecycleRegistry:
    registry: dict[CellId_t, set[CellLifecycleItem]] = dataclasses.field(
        default_factory=dict
    )

    def inject(self, cell_id: CellId_t, item: CellLifecycleItem) -> None:
        """Add a provisioned lifecycle item for a specific cell.

        Prefer using `add` to add lifecycle items.
        """
        if cell_id not in self.registry:
            self.registry[cell_id] = set()
        self.registry[cell_id].add(item)

    def add(self, item: CellLifecycleItem) -> None:
        """Add a lifecycle item for the currently running cell.

        Calls the item's create method upon adding. When no cell is running
        on this thread, the owner is the cell whose evaluation spawned the
        current flow of control (an `asyncio` task, or a thread run under a
        copy of that cell's `contextvars` context); the item is then disposed
        when that cell re-runs or is deleted. If there is no such cell, or it
        no longer exists, the item is created with `context=None` and left
        unregistered, as when no runtime context is installed at all.
        """
        from marimo._messaging.context import EXECUTION_CTX
        from marimo._runtime.context import get_context

        ctx = get_context()

        cell_id = ctx.cell_id
        if cell_id is None and (execution := EXECUTION_CTX.get()) is not None:
            spawning_cell = CellId_t(execution.cell_id)
            if spawning_cell in ctx.graph.cells:
                cell_id = spawning_cell
        if cell_id is None:
            item.create(context=None)
            return

        item.create(ctx)
        return self.inject(cell_id, item)

    def dispose(self, cell_id: CellId_t, deletion: bool) -> None:
        """Dispose lifecycle items associated with `cell_id`

        Calls `dispose` hooks and clears items from the registry.

        If `deletion` is `True`, the cell is being removed from the graph.
        """
        from marimo._runtime.context import get_context

        ctx = get_context()
        # LifecycleItems can request that their `dispose` method is retried in
        # the next cell lifecycle; these items are persisted.
        persisted_lifecycle_items = set()
        if cell_id in self.registry:
            for lifecycle_item in self.registry[cell_id]:
                if not lifecycle_item.dispose(context=ctx, deletion=deletion):
                    persisted_lifecycle_items.add(lifecycle_item)

            if persisted_lifecycle_items:
                self.registry[cell_id] = persisted_lifecycle_items
            else:
                del self.registry[cell_id]
