# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import dataclasses

from marimo._messaging.context import EXECUTION_CTX
from marimo._runtime.cell_lifecycle_item import CellLifecycleItem
from marimo._runtime.scratch import SCRATCH_CELL_ID
from marimo._types.ids import CellId_t


class NoOwningCellError(RuntimeError):
    """No cell can own a lifecycle item, so marimo refuses to create it."""


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
        """Create `item` and register it with the cell that owns it.

        The owner is the cell whose evaluation created `item`, directly or
        from a task or thread it spawned, or else the cell running on this
        context. Raises `NoOwningCellError` when there is neither.
        """
        from marimo._runtime.context import get_context

        ctx = get_context()

        execution = EXECUTION_CTX.get()
        if execution is None:
            cell_id = ctx.cell_id
            if cell_id is None:
                raise NoOwningCellError(
                    "No cell is running on this thread, so marimo cannot clean "
                    "up. Start background work with mo.Thread within a cell."
                )
        else:
            # The tag is task-local, so it names the spawning cell even when
            # another cell runs on the shared context, and it outlives the
            # cell body, so that cell can already be deleted. The scratchpad
            # cell runs on a graph of its own.
            cell_id = CellId_t(execution.cell_id)
            if cell_id not in ctx.graph.cells and cell_id != SCRATCH_CELL_ID:
                raise NoOwningCellError(
                    "Since the cell that started this background work was deleted, "
                    "marimo cannot provide clean up. Start background work with "
                    "mo.Thread within a cell."
                )

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
