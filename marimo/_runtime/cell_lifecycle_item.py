# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import abc
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from marimo._runtime.context.types import RuntimeContext


class CellLifecycleItem(abc.ABC):
    @abc.abstractmethod
    def create(self, context: "RuntimeContext") -> None:
        """Create this item

        This method is executed at the beginning of a cell's lifecycle.
        Use it to run side-effects or create state.
        """
        ...

    @abc.abstractmethod
    def dispose(self, context: "RuntimeContext", deletion: bool) -> bool:
        """Dispose this item

        This method is executed at the end of a cell's lifecycle. Use
        it to clean-up side-effects or state associated with the lifecycle
        item.

        The `deletion` flag indicates whether the cell is being removed
        from the graph, which may influence disposal strategy.

        Return True if the disposal is successful and the lifecycle item
        should be removed from the registry. Return False if the disposal
        needs to be retried in the next cell lifecycle (note that `create`
        will not be re-run, only `dispose`).
        """
        ...
