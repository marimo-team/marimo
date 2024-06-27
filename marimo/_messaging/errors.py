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


@dataclass
class MultipleDefinitionError:
    name: str
    cells: tuple[CellId_t, ...]
    type: Literal["multiple-defs"] = "multiple-defs"


@dataclass
class DeleteNonlocalError:
    name: str
    cells: tuple[CellId_t, ...]
    type: Literal["delete-nonlocal"] = "delete-nonlocal"


@dataclass
class MarimoInterruptionError:
    type: Literal["interruption"] = "interruption"


@dataclass
class MarimoAncestorPreventedError:
    msg: str
    raising_cell: CellId_t
    blamed_cell: Optional[CellId_t]
    type: Literal["ancestor-prevented"] = "ancestor-prevented"


@dataclass
class MarimoAncestorStoppedError:
    msg: str
    raising_cell: CellId_t
    type: Literal["ancestor-stopped"] = "ancestor-stopped"


@dataclass
class MarimoExceptionRaisedError:
    msg: str
    exception_type: str
    # None for if raising_cell is the current cell
    raising_cell: Optional[CellId_t]
    type: Literal["exception"] = "exception"


@dataclass
class MarimoSyntaxError:
    msg: str
    type: Literal["syntax"] = "syntax"


@dataclass
class UnknownError:
    msg: str
    type: Literal["unknown"] = "unknown"


@dataclass
class MarimoStrictExecutionError:
    msg: str
    ref: str
    blamed_cell: Optional[CellId_t]
    type: Literal["strict-exception"] = "strict-exception"


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
