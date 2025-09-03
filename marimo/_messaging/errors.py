# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Literal, Optional, Union

import msgspec

from marimo._runtime.dataflow import EdgeWithVar
from marimo._types.ids import CellId_t


class SetupRootError(msgspec.Struct, rename="camel"):
    edges_with_vars: tuple[EdgeWithVar, ...]
    type: Literal["setup-refs"] = "setup-refs"

    def describe(self) -> str:
        return "The setup cell cannot have references"


class CycleError(msgspec.Struct, rename="camel"):
    edges_with_vars: tuple[EdgeWithVar, ...]
    type: Literal["cycle"] = "cycle"

    def describe(self) -> str:
        return "This cell is in a cycle"


class MultipleDefinitionError(msgspec.Struct, rename="camel"):
    name: str
    cells: tuple[CellId_t, ...]
    type: Literal["multiple-defs"] = "multiple-defs"

    def describe(self) -> str:
        return f"The variable '{self.name}' was defined by another cell"


class ImportStarError(msgspec.Struct, rename="camel"):
    msg: str
    type: Literal["import-star"] = "import-star"

    def describe(self) -> str:
        return self.msg


class MarimoInterruptionError(msgspec.Struct, rename="camel"):
    type: Literal["interruption"] = "interruption"

    def describe(self) -> str:
        return "This cell was interrupted and needs to be re-run"


class MarimoAncestorPreventedError(msgspec.Struct, rename="camel"):
    msg: str
    raising_cell: CellId_t
    blamed_cell: Optional[CellId_t]
    type: Literal["ancestor-prevented"] = "ancestor-prevented"

    def describe(self) -> str:
        return self.msg


class MarimoAncestorStoppedError(msgspec.Struct, rename="camel"):
    msg: str
    raising_cell: CellId_t
    type: Literal["ancestor-stopped"] = "ancestor-stopped"

    def describe(self) -> str:
        return self.msg


class MarimoExceptionRaisedError(msgspec.Struct, rename="camel"):
    msg: str
    exception_type: str
    # None for if raising_cell is the current cell
    raising_cell: Optional[CellId_t]
    type: Literal["exception"] = "exception"

    def describe(self) -> str:
        return self.msg


class MarimoSyntaxError(msgspec.Struct, rename="camel"):
    msg: str
    type: Literal["syntax"] = "syntax"

    def describe(self) -> str:
        return self.msg


class UnknownError(msgspec.Struct, rename="camel"):
    msg: str
    type: Literal["unknown"] = "unknown"

    def describe(self) -> str:
        return self.msg


class MarimoStrictExecutionError(msgspec.Struct, rename="camel"):
    msg: str
    ref: str
    blamed_cell: Optional[CellId_t]
    type: Literal["strict-exception"] = "strict-exception"

    def describe(self) -> str:
        return self.msg


class MarimoInternalError(msgspec.Struct, rename="camel"):
    """
    An internal error that should be hidden from the user.
    The error is logged to the console and then a new error is broadcasted
    such that the data is hidden.

    They can be linked back to the original error by the error_id.
    """

    error_id: str
    type: Literal["internal"] = "internal"
    msg: str = ""

    def __post_init__(self) -> None:
        self.msg = f"An internal error occurred: {self.error_id}"

    def describe(self) -> str:
        return self.msg


def is_unexpected_error(error: Error) -> bool:
    """
    These errors are unexpected, in that they are not intentional.
    mo.stop and interrupt are intentional.
    """
    return error.type not in [
        "ancestor-prevented",
        "ancestor-stopped",
        "interruption",
    ]


def is_sensitive_error(error: Error) -> bool:
    """
    These errors are sensitive, in that they are intentional.
    """
    return error.type not in [
        "ancestor-prevented",
        "ancestor-stopped",
        "internal",
    ]


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
    UnknownError,
]
