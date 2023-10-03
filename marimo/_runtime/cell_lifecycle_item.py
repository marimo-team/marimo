# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import abc
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from marimo._runtime.context import RuntimeContext


class CellLifecycleItem(abc.ABC):
    @abc.abstractmethod
    def create(self, context: "RuntimeContext") -> None:
        ...

    @abc.abstractmethod
    def dispose(self, context: "RuntimeContext") -> None:
        ...
