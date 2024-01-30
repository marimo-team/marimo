# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import ast
import dataclasses
import functools
import inspect
from types import CodeType
from typing import (
    Any,
    Callable,
    Literal,
    Optional,
    Protocol,
    Tuple,
    TypeVar,
    cast,
)

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

"""
idle: cell has run with latest inputs
queued: cell is queued to run
running: cell is running
stale: cell hasn't run with latest inputs, and can't run (disabled)
disabled-transitively: cell is disabled because a parent is disabled
"""
CellStatusType = Literal[
    "idle", "queued", "running", "stale", "disabled-transitively"
]


@dataclasses.dataclass
class CellStatus:
    state: Optional[CellStatusType] = None


@dataclasses.dataclass(frozen=True)
class Cell:
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

    def configure(self, update: dict[str, Any] | CellConfig) -> Cell:
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


CellFuncType = Callable[..., Optional[Tuple[Any, ...]]]
# Cumbersome, but used to ensure function types don't get erased in decorators
# or creation of CellFunction
CellFuncTypeBound = TypeVar(
    "CellFuncTypeBound",
    bound=Callable[..., Optional[Tuple[Any, ...]]],
)


class CellFunction(Protocol[CellFuncTypeBound]):
    """Wraps a function from which a Cell object was created."""

    cell: Cell
    # function name
    __name__: str
    # function code
    code: str
    # arg names of wrapped function
    args: set[str]
    __call__: CellFuncTypeBound


def cell_function(
    cell: Cell, args: set[str], code: str, f: CellFuncTypeBound
) -> CellFunction[CellFuncTypeBound]:
    signature = inspect.signature(f)

    n_args = 0
    defaults = {}
    for name, value in signature.parameters.items():
        if value.default != inspect.Parameter.empty:
            defaults[name] = value.default
        else:
            n_args += 1

    parameters = list(signature.parameters.keys())
    return_names = sorted(defn for defn in cell.defs)

    @functools.wraps(f)
    def func(*args: Any, **kwargs: Any) -> tuple[Any, ...]:
        """Wrapper for executing cell using the function's signature.

        Alternative for passing a globals dict
        """
        glbls = {}
        glbls.update(defaults)
        pos = 0
        for arg in args:
            glbls[parameters[pos]] = arg
            pos += 1
        if pos < n_args:
            raise TypeError(
                f.__name__
                + f"() missing {n_args - pos} required arguments: "
                + " and ".join(f"'{p}'" for p in parameters[pos:n_args])
            )

        for kwarg, value in kwargs.items():
            if kwarg not in parameters:
                raise TypeError(
                    f.__name__
                    + "() got an unexpected keyword argument '{kwarg}'"
                )
            else:
                glbls[kwarg] = value

        # we use execute_cell instead of calling `f` directly because
        # we want to obtain the cell's HTML output, which is the last
        # expression in the cell body.
        #
        # TODO: stash output if mo.collect_outputs() context manager is active
        #       ... or just make cell execution return the output in addition
        #       to the defs, which might be weird because that doesn't
        #       match the function signature
        _ = execute_cell(cell, glbls)
        return tuple(glbls[name] for name in return_names)

    cell_func = cast(CellFunction[CellFuncTypeBound], func)
    cell_func.cell = cell
    cell_func.args = args
    cell_func.code = code
    return cell_func


def is_ws(char: str) -> bool:
    return char == " " or char == "\n" or char == "\t"


def execute_cell(cell: Cell, glbls: dict[Any, Any]) -> Any:
    if cell.body is None:
        return None
    assert cell.last_expr is not None
    exec(cell.body, glbls)
    return eval(cell.last_expr, glbls)
