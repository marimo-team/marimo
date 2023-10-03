# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import dataclasses

from marimo._ast.cell import CellId_t
from marimo._runtime.cell_lifecycle_item import CellLifecycleItem


@dataclasses.dataclass
class CellLifecycleRegistry:
    registry: dict[CellId_t, set[CellLifecycleItem]] = dataclasses.field(
        default_factory=dict
    )

    def add(self, item: CellLifecycleItem) -> None:
        """Add a lifecycle item for the currently running cell.

        Calls the item's create method upon adding. No-op if no cell
        is running.
        """
        from marimo._runtime.context import get_context

        ctx = get_context()
        cell_id = ctx.cell_id
        if cell_id is None:
            return

        if cell_id not in self.registry:
            self.registry[cell_id] = set()
        item.create(ctx)
        self.registry[cell_id].add(item)

    def dispose(self, cell_id: CellId_t) -> None:
        """Dispose lifecycle items associated with `cell_id`

        Calls `dispose` hooks and clears items from the registry.
        """
        from marimo._runtime.context import get_context

        ctx = get_context()
        if cell_id in self.registry:
            for lifecycle_item in self.registry[cell_id]:
                lifecycle_item.dispose(context=ctx)
            del self.registry[cell_id]
