# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from marimo._runtime.cell_lifecycle_item import CellLifecycleItem

if TYPE_CHECKING:
    from marimo._runtime.context.types import RuntimeContext


class SideEffect(CellLifecycleItem):
    def __init__(self, key: str) -> None:
        self._key = key

    @property
    def key(self) -> str:
        assert self._key is not None
        return self._key

    @property
    def hash(self) -> bytes:
        """Hash the lookup to a consistent size."""
        return hashlib.sha256(self._key.encode()).digest()

    def create(self, context: RuntimeContext | None) -> None:
        """NoOp for side effect.
        Typically hook to expose the object to the context, but the existence of
        the object is enough for side effect tracking.
        """

    def dispose(self, context: RuntimeContext, deletion: bool) -> bool:  # noqa: ARG002
        """Clean up and mark the object for deletion"""
        # Side effects can always be disposed since they are just a cell level
        # marker that some event has occurred.
        return True
