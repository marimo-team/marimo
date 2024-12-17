# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional, Union

from marimo._ast.cell import CellId_t
from marimo._runtime.dataflow import EdgeWithVar


@dataclass
class CycleError:
    edges_with_vars: tuple[EdgeWithVar, ...]
    type: Literal["cycle"] = "cycle"

    def describe(self) -> str:
        return "This cell is in a cycle"


@dataclass
class MultipleDefinitionError:
    name: str
    cells: tuple[CellId_t, ...]
    type: Literal["multiple-defs"] = "multiple-defs"

    def describe(self) -> str:
        return f"The variable '{self.name}' was defined by another cell"


@dataclass
class DeleteNonlocalError:
    name: str
    cells: tuple[CellId_t, ...]
    type: Literal["delete-nonlocal"] = "delete-nonlocal"

    def describe(self) -> str:
        return f"The variable '{self.name}' can't be deleted because it was defined by another cell"


@dataclass
class MarimoInterruptionError:
    type: Literal["interruption"] = "interruption"

    def describe(self) -> str:
        return "This cell was interrupted and needs to be re-run"


@dataclass
class MarimoAncestorPreventedError:
    msg: str
    raising_cell: CellId_t
    blamed_cell: Optional[CellId_t]
    type: Literal["ancestor-prevented"] = "ancestor-prevented"

    def describe(self) -> str:
        return self.msg


@dataclass
class MarimoAncestorStoppedError:
    msg: str
    raising_cell: CellId_t
    type: Literal["ancestor-stopped"] = "ancestor-stopped"

    def describe(self) -> str:
        return self.msg


@dataclass
class MarimoExceptionRaisedError:
    msg: str
    exception_type: str
    # None for if raising_cell is the current cell
    raising_cell: Optional[CellId_t]
    type: Literal["exception"] = "exception"

    def describe(self) -> str:
        return self.msg


@dataclass
class MarimoSyntaxError:
    msg: str
    type: Literal["syntax"] = "syntax"

    def describe(self) -> str:
        return self.msg


@dataclass
class UnknownError:
    msg: str
    type: Literal["unknown"] = "unknown"

    def describe(self) -> str:
        return self.msg


@dataclass
class MarimoStrictExecutionError:
    msg: str
    ref: str
    blamed_cell: Optional[CellId_t]
    type: Literal["strict-exception"] = "strict-exception"

    def describe(self) -> str:
        return self.msg


@dataclass
class MarimoInternalError:
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
    CycleError,
    MultipleDefinitionError,
    DeleteNonlocalError,
    MarimoAncestorStoppedError,
    MarimoAncestorPreventedError,
    MarimoExceptionRaisedError,
    MarimoStrictExecutionError,
    MarimoInterruptionError,
    MarimoSyntaxError,
    MarimoInternalError,
    UnknownError,
]
