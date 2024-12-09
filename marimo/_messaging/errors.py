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
    UnknownError,
]
