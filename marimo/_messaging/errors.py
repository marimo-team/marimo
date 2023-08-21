# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union

from marimo._ast.cell import CellId_t
from marimo._runtime.dataflow import Edge


@dataclass
class CycleError:
    edges: tuple[Edge, ...]
    type: str = "cycle"


@dataclass
class MultipleDefinitionError:
    name: str
    cells: tuple[CellId_t, ...]
    type: str = "multiple-defs"


@dataclass
class DeleteNonlocalError:
    name: str
    cells: tuple[CellId_t, ...]
    type: str = "delete-nonlocal"


@dataclass
class MarimoInterruptionError:
    type: str = "interruption"


@dataclass
class MarimoAncestorStoppedError:
    msg: str
    raising_cell: CellId_t
    type: str = "ancestor-stopped"


@dataclass
class MarimoExceptionRaisedError:
    msg: str
    exception_type: str
    # None for if raising_cell is the current cell
    raising_cell: Optional[CellId_t]
    type: str = "exception"


@dataclass
class MarimoSyntaxError:
    msg: str
    type: str = "syntax"


@dataclass
class UnknownError:
    msg: str
    type: str = "unknown"


Error = Union[
    CycleError,
    MultipleDefinitionError,
    DeleteNonlocalError,
    MarimoAncestorStoppedError,
    MarimoExceptionRaisedError,
    MarimoInterruptionError,
    MarimoSyntaxError,
    UnknownError,
]
