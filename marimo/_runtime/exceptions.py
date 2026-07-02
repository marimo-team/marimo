# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from marimo._runtime.dataflow import DirectedGraph
    from marimo._types.ids import CellId_t


class MarimoRuntimeException(BaseException):
    """Wrapper for all marimo runtime exceptions."""


class MarimoNameError(NameError):
    """Wrap a name error to rethrow later."""

    def __init__(self, msg: str, ref: str) -> None:
        super().__init__(msg)
        self.ref = ref


class MarimoMissingRefError(BaseException):
    def __init__(self, ref: str, name_error: NameError | None = None) -> None:
        super().__init__(ref)
        self.ref = ref
        self.name_error = name_error


class MarimoCancelCellError(BaseException):
    """Soft-cancel signal raised by a lifecycle.

    Subclasses BaseException (not Exception) so user-code `except Exception`
    blocks don't swallow the control-flow signal.
    """

    cells_to_rerun: set[CellId_t]

    def __init__(
        self,
        *args: object,
        cells_to_rerun: set[CellId_t] | None = None,
    ) -> None:
        super().__init__(*args)
        self.cells_to_rerun = cells_to_rerun or set()


class MarimoUnhashableCacheError(MarimoCancelCellError):
    """Raised when cell-level caching encounters a value that cannot be
    hashed/serialized for cache restoration."""

    def __init__(
        self,
        cells_to_rerun: set[CellId_t],
        variables: list[str],
        error_details: str,
    ) -> None:
        super().__init__(error_details, cells_to_rerun=cells_to_rerun)
        self.variables = variables
        self.error_details = error_details


def unwrap_user_exception(
    exc: MarimoRuntimeException,
    graph: DirectedGraph | None = None,
) -> BaseException | None:
    """Extract the user exception from a `MarimoRuntimeException`."""
    cause = exc.__cause__
    if graph is not None and isinstance(cause, NameError):
        name = getattr(cause, "name", None)
        if name and name in graph.definitions:
            return MarimoMissingRefError(name, cause)
    return cause
