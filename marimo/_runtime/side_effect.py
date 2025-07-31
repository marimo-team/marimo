# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from marimo._runtime.cell_lifecycle_item import CellLifecycleItem

if TYPE_CHECKING:
    from marimo._runtime.context.types import RuntimeContext


class SideEffect(CellLifecycleItem):
    def __init__(self, key: str | bytes) -> None:
        self._key = key

    @property
    def key(self) -> bytes:
        assert self._key is not None
        if isinstance(self._key, bytes):
            return self._key
        return self._key.encode("utf-8")

    @property
    def hash(self) -> bytes:
        """Hash the lookup to a consistent size."""
        return hashlib.sha256(self.key).digest()

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


class CellHash(CellLifecycleItem):
    """Execution as a side effect to prevent the recomputation of a cell for
    recursive or repeated calls.
    """

    def __init__(self, key: str | bytes) -> None:
        self._key = key

    @property
    def key(self) -> bytes:
        assert self._key is not None
        if isinstance(self._key, bytes):
            return self._key
        return self._key.encode("utf-8")

    @property
    def hash(self) -> bytes:
        """Hash the lookup to a consistent size."""
        return hashlib.sha256(self.key).digest()

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
