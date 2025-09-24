# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Optional, Union

import msgspec

from marimo._runtime.dataflow import EdgeWithVar
from marimo._types.ids import CellId_t


class SetupRootError(msgspec.Struct, tag="setup-refs"):
    edges_with_vars: tuple[EdgeWithVar, ...]

    def describe(self) -> str:
        return "The setup cell cannot have references"


class CycleError(msgspec.Struct, tag="cycle"):
    edges_with_vars: tuple[EdgeWithVar, ...]

    def describe(self) -> str:
        return "This cell is in a cycle"


class MultipleDefinitionError(msgspec.Struct, tag="multiple-defs"):
    name: str
    cells: tuple[CellId_t, ...]

    def describe(self) -> str:
        return f"The variable '{self.name}' was defined by another cell"


class ImportStarError(msgspec.Struct, tag="import-star"):
    msg: str

    def describe(self) -> str:
        return self.msg


class MarimoInterruptionError(msgspec.Struct, tag="interruption"):
    def describe(self) -> str:
        return "This cell was interrupted and needs to be re-run"


class MarimoAncestorPreventedError(msgspec.Struct, tag="ancestor-prevented"):
    msg: str
    raising_cell: CellId_t
    blamed_cell: Optional[CellId_t]

    def describe(self) -> str:
        return self.msg


class MarimoAncestorStoppedError(msgspec.Struct, tag="ancestor-stopped"):
    msg: str
    raising_cell: CellId_t

    def describe(self) -> str:
        return self.msg


class MarimoExceptionRaisedError(msgspec.Struct, tag="exception"):
    msg: str
    exception_type: str
    # None for if raising_cell is the current cell
    raising_cell: Optional[CellId_t]

    def describe(self) -> str:
        return self.msg


class MarimoSyntaxError(msgspec.Struct, tag="syntax"):
    msg: str

    def describe(self) -> str:
        return self.msg


class UnknownError(msgspec.Struct, tag="unknown"):
    msg: str
    error_type: Optional[str] = None

    def describe(self) -> str:
        return self.msg


class MarimoStrictExecutionError(msgspec.Struct, tag="strict-exception"):
    msg: str
    ref: str
    blamed_cell: Optional[CellId_t]

    def describe(self) -> str:
        return self.msg


class MarimoInternalError(msgspec.Struct, tag="internal"):
    """
    An internal error that should be hidden from the user.
    The error is logged to the console and then a new error is broadcasted
    such that the data is hidden.

    They can be linked back to the original error by the error_id.
    """

    error_id: str
    msg: str = ""

    def __post_init__(self) -> None:
        self.msg = f"An internal error occurred: {self.error_id}"

    def describe(self) -> str:
        return self.msg


class MarimoSQLError(msgspec.Struct, tag="sql-error"):
    """
    SQL-specific error with enhanced metadata for debugging.
    """

    msg: str
    sql_statement: str
    hint: Optional[str] = (
        None  # Helpful hints like "Did you mean?" or "Candidate bindings"
    )
    sql_line: Optional[int] = None  # 0-based line within SQL
    sql_col: Optional[int] = None  # 0-based column within SQL
    node_lineno: int = 0
    node_col_offset: int = 0

    def describe(self) -> str:
        return self.msg


def is_unexpected_error(error: Error) -> bool:
    """
    These errors are unexpected, in that they are not intentional.
    mo.stop and interrupt are intentional.
    """
    return not isinstance(
        error,
        (
            MarimoAncestorPreventedError,
            MarimoAncestorStoppedError,
            MarimoInterruptionError,
        ),
    )


def is_sensitive_error(error: Error) -> bool:
    """
    These errors are sensitive, in that they are intentional.
    """
    return not isinstance(
        error,
        (
            MarimoAncestorPreventedError,
            MarimoAncestorStoppedError,
            MarimoInternalError,
        ),
    )


Error = Union[
    SetupRootError,
    CycleError,
    MultipleDefinitionError,
    ImportStarError,
    MarimoAncestorStoppedError,
    MarimoAncestorPreventedError,
    MarimoExceptionRaisedError,
    MarimoStrictExecutionError,
    MarimoInterruptionError,
    MarimoSyntaxError,
    MarimoInternalError,
    MarimoSQLError,
    UnknownError,
]
