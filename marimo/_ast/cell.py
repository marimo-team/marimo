# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import ast
import dataclasses
import inspect
from types import CodeType
from typing import Any, Callable, Literal, Optional

from marimo._ast.visitor import Name, VariableData
from marimo._utils.deep_merge import deep_merge

CellId_t = str


@dataclasses.dataclass
class CellConfig:
    # If True, the cell and its descendants cannot be executed,
    # but they can still be added to the graph.
    disabled: bool = False

    # If True, the cell is hidden from the editor.
    hide_code: bool = False

    @classmethod
    def from_dict(cls, kwargs: dict[str, Any]) -> CellConfig:
        return cls(**{k: v for k, v in kwargs.items() if k in CellConfigKeys})

    def configure(self, update: dict[str, Any] | CellConfig) -> None:
        """Update the config in-place.

        `update` can be a partial config or a CellConfig
        """
        if isinstance(update, CellConfig):
            update = dataclasses.asdict(update)
        new_config = dataclasses.asdict(
            CellConfig.from_dict(deep_merge(dataclasses.asdict(self), update))
        )
        for key, value in new_config.items():
            self.__setattr__(key, value)


CellConfigKeys = frozenset(
    {field.name for field in dataclasses.fields(CellConfig)}
)


# Cell Statuses
#
# idle: cell has run with latest inputs
# queued: cell is queued to run
# running: cell is running
# stale: cell hasn't run with latest inputs, and can't run (disabled)
# disabled-transitively: cell is disabled because a parent is disabled
CellStatusType = Literal[
    "idle", "queued", "running", "stale", "disabled-transitively"
]


@dataclasses.dataclass
class CellStatus:
    state: Optional[CellStatusType] = None


def _is_coroutine(code: Optional[CodeType]) -> bool:
    if code is None:
        return False
    return inspect.CO_COROUTINE & code.co_flags == inspect.CO_COROUTINE


@dataclasses.dataclass(frozen=True)
class CellImpl:
    # hash of code
    key: int
    code: str
    mod: ast.Module
    defs: set[Name]
    refs: set[Name]
    # metadata about definitions
    variable_data: dict[Name, VariableData]
    deleted_refs: set[Name]
    body: Optional[CodeType]
    last_expr: Optional[CodeType]
    # unique id
    cell_id: CellId_t

    # Mutable fields
    # config: explicit configuration of cell
    config: CellConfig = dataclasses.field(default_factory=CellConfig)
    # status: status, inferred at runtime
    _status: CellStatus = dataclasses.field(default_factory=CellStatus)

    def configure(self, update: dict[str, Any] | CellConfig) -> CellImpl:
        """Update the cel config.

        `update` can be a partial config.
        """
        self.config.configure(update)
        return self

    @property
    def status(self) -> Optional[CellStatusType]:
        return self._status.state

    @property
    def stale(self) -> bool:
        return self.status == "stale"

    @property
    def disabled_transitively(self) -> bool:
        return self.status == "disabled-transitively"

    @property
    def imported_modules(self) -> set[Name]:
        """Return a set of the modules imported by this cell."""
        return set(
            data.module
            for _, data in self.variable_data.items()
            if data.module is not None
        )

    def is_coroutine(self) -> bool:
        return _is_coroutine(self.body) or _is_coroutine(self.last_expr)

    def set_status(self, status: CellStatusType) -> None:
        from marimo._messaging.ops import CellOp
        from marimo._runtime.context import (
            ContextNotInitializedError,
            get_context,
        )

        self._status.state = status
        try:
            get_context()
        except ContextNotInitializedError:
            return

        assert self.cell_id is not None
        CellOp.broadcast_status(cell_id=self.cell_id, status=status)

    def run(self, **kwargs: Any) -> Any:
        raise NotImplementedError


@dataclasses.dataclass(frozen=True)
class Cell:
    _f: Callable[..., Any]
    _cell: CellImpl

    @property
    def name(self) -> str:
        return self._f.__name__

    def run(self, **kwargs: Any) -> tuple[Any, dict[str, Any]]:
        # TODO(akshayka): implement
        raise NotImplementedError

    def __call__(self, *args, **kwargs) -> None:
        del args
        del kwargs
        raise RuntimeError(
            f"Calling marimo cell's using `{self.name}()` is not supported. "
            f"Use {self.name}.run() instead. See the docs more for info."
        )


def is_ws(char: str) -> bool:
    return char == " " or char == "\n" or char == "\t"


async def execute_cell_async(cell: CellImpl, glbls: dict[Any, Any]) -> Any:
    if cell.body is None:
        return None
    assert cell.last_expr is not None

    if _is_coroutine(cell.body):
        await eval(cell.body, glbls)
    else:
        exec(cell.body, glbls)

    if _is_coroutine(cell.last_expr):
        return await eval(cell.last_expr, glbls)
    else:
        return eval(cell.last_expr, glbls)


def execute_cell(cell: CellImpl, glbls: dict[Any, Any]) -> Any:
    if cell.body is None:
        return None
    assert cell.last_expr is not None
    exec(cell.body, glbls)
    return eval(cell.last_expr, glbls)
