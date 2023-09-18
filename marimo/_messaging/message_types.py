# Copyright 2023 Marimo. All rights reserved.
"""Message Types

Messages that the kernel sends to the frontend.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import ClassVar, Dict, Optional, Union, cast

from marimo._ast.cell import CellConfig, CellId_t, CellStatusType
from marimo._messaging.cell_output import CellOutput
from marimo._messaging.completion_option import CompletionOption
from marimo._plugins.core.web_component import JSONType
from marimo._server.layout import LayoutConfig


# A cell-op's data has three optional fields:
#
# output  - a CellOutput
# console - a CellOutput (console message to append), or a list of CellOutputs
# status  - execution status
#
# NB: omitting a field means that its value should be unchanged
#
# and one required field:
#
# cell_id - the cell id
@dataclass
class CellOp:
    name: ClassVar[str] = "cell-op"
    cell_id: CellId_t
    output: Optional[CellOutput] = None
    console: Optional[Union[CellOutput, list[CellOutput]]] = None
    status: Optional[CellStatusType] = None
    timestamp: float = field(default_factory=lambda: time.time())


@dataclass
class RemoveUIElements:
    name: ClassVar[str] = "remove-ui-elements"
    cell_id: CellId_t


@dataclass
class Interrupted:
    name: ClassVar[str] = "interrupted"


@dataclass
class CompletedRun:
    name: ClassVar[str] = "completed-run"


@dataclass
class KernelReady:
    name: ClassVar[str] = "kernel-ready"
    codes: tuple[str, ...]
    names: tuple[str, ...]
    layout: Optional[LayoutConfig]
    configs: tuple[CellConfig, ...]


@dataclass
class CompletionResult:
    name: ClassVar[str] = "completion-result"
    completion_id: str
    prefix_length: int
    options: list[CompletionOption]


MessageType = Union[
    CellOp,
    RemoveUIElements,
    Interrupted,
    CompletedRun,
    KernelReady,
    CompletionResult,
]


# TODO(akshayka): fix typing once mypy/dataclasses has stricter
# typing for asdict
def serialize(message: MessageType) -> dict[str, JSONType]:
    return cast(Dict[str, JSONType], asdict(message))
