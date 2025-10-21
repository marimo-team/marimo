# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Optional


class MarimoRuntimeException(BaseException):
    """Wrapper for all marimo runtime exceptions."""


class MarimoNameError(NameError):
    """Wrap a name error to rethrow later."""

    def __init__(self, msg: str, ref: str) -> None:
        super().__init__(msg)
        self.ref = ref


class MarimoMissingRefError(BaseException):
    def __init__(
        self, ref: str, name_error: Optional[NameError] = None
    ) -> None:
        super().__init__(ref)
        self.ref = ref
        self.name_error = name_error


class MarimoUnhashableCacheError(BaseException):
    """Raised when cache restoration encounters unhashable variables.

    This exception signals that a cell's cache cannot be restored due to
    unhashable variables (lambdas, nested functions, etc.). The cells that
    define these variables need to be re-executed without attempting cache.

    Args:
        cells_to_rerun: Cell IDs that define the unhashable variables
        variables: Names of unhashable variables encountered
        error_details: Detailed error messages for each variable
    """

    def __init__(
        self,
        cells_to_rerun: set[str],
        variables: list[str],
        error_details: str,
    ) -> None:
        super().__init__(
            f"Cannot restore cache: found unhashable variables {variables} "
            f"defined in cells {cells_to_rerun}"
        )
        self.cells_to_rerun = cells_to_rerun
        self.variables = variables
        self.error_details = error_details
