# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import builtins
import itertools
import textwrap
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any, Callable, Iterable, Literal, Optional, Union, cast

from marimo._ast.cell import (
    CellConfig,
    CellFunction,
    CellFuncType,
    CellFuncTypeBound,
    CellId_t,
    cell_factory,
    execute_cell,
)
from marimo._ast.errors import (
    CycleError,
    DeleteNonlocalError,
    MultipleDefinitionError,
    UnparsableError,
)
from marimo._output.rich_help import mddoc
from marimo._runtime.dataflow import DirectedGraph, topological_sort


@dataclass
class _AppConfig:
    """Program-specific configuration.

    Configuration for frontends or runtimes that is specific to
    a single marimo program.
    """

    width: Literal["normal", "full"] = "normal"

    # The file path of the layout file, relative to the app file.
    layout_file: Optional[str] = None

    def asdict(self) -> dict[str, Any]:
        return asdict(self)

    def update(self, updates: dict[str, Any]) -> None:
        config_dict = asdict(self)
        for key in updates:
            if key in config_dict:
                self.__setattr__(key, updates[key])


@dataclass
class CellData:
    """A cell together with some metadata"""

    cell_id: CellId_t
    # User code comprising the cell
    code: str
    # User-provided name for cell (or default)
    name: str
    # Cell config
    config: CellConfig

    # Callable cell, or None if cell was not parsable
    cell_function: Optional[CellFunction[CellFuncType]]


@mddoc
class App:
    """A marimo app.

    A marimo app is a dataflow graph, with each node computing a Python
    function.

    This class has no public API, but this may change in the future.
    """

    def __init__(self, **kwargs: Any) -> None:
        # Take `AppConfig` as kwargs for forward/backward compatibility;
        # unrecognized settings will just be dropped, instead of raising
        # a TypeError.
        self._config = _AppConfig()
        for key in asdict(self._config):
            if key in kwargs:
                self._config.__setattr__(key, kwargs.pop(key))

        self._cell_data: dict[CellId_t, CellData] = {}
        self._registration_order: list[CellId_t] = []

        self._cell_id_counter = 0
        self._unparsable = False
        self._initialized = False

    def _create_cell_id(
        self, cell_function: Optional[CellFunction[CellFuncTypeBound]]
    ) -> CellId_t:
        del cell_function
        cell_id = str(self._cell_id_counter)
        self._registration_order.append(cell_id)
        self._cell_id_counter += 1
        return str(cell_id)

    def cell(
        self,
        func: Optional[CellFuncTypeBound] = None,
        *,
        disabled: bool = False,
        **kwargs: Any,
    ) -> Union[
        Callable[[CellFuncType], CellFunction[CellFuncTypeBound]],
        CellFunction[CellFuncTypeBound],
    ]:
        """A decorator to add a cell to the app

        This decorator can be called with or without parentheses. Each of the
        following is valid:

        ```
        @app.cell
        def __(mo):
            # ...

        @app.cell()
        def __(mo):
            # ...

        @app.cell(disabled=True)
        def __(mo):
            # ...
        ```

        Args:
        - func: The decorated function
        - disabled: Whether to disable the cell
        - kwargs: For forward-compatibility with future arguments
        """
        del kwargs

        if func is None:
            # If the decorator was used with parentheses, func will be None,
            # and we return a decorator that takes the decorated function as an
            # argument
            def decorator(
                func: CellFuncTypeBound,
            ) -> CellFunction[CellFuncTypeBound]:
                cell_function = cell_factory(func)
                cell_function.cell.configure(CellConfig(disabled=disabled))
                self._register_cell(cell_function)
                return cell_function

            return cast(
                Callable[[CellFuncType], CellFunction[CellFuncTypeBound]],
                decorator,
            )
        else:
            # If the decorator was used without parentheses, func will be the
            # decorated function
            cell_function = cell_factory(func)
            cell_function.cell.configure(CellConfig(disabled=disabled))
            self._register_cell(cell_function)
            return cell_function

    def _register_cell(
        self, cell_function: CellFunction[CellFuncTypeBound]
    ) -> None:
        cell_id = self._create_cell_id(cell_function)
        self._cell_data[cell_id] = CellData(
            cell_id=cell_id,
            code=cell_function.cell.code,
            name=cell_function.__name__,
            config=cell_function.cell.config,
            cell_function=cast(CellFunction[CellFuncType], cell_function),
        )

    def _names(self) -> Iterable[str]:
        return (cell_data.name for cell_data in self._cell_data.values())

    def _codes(self) -> Iterable[str]:
        return (cell_data.code for cell_data in self._cell_data.values())

    def _configs(self) -> Iterable[CellConfig]:
        return (cell_data.config for cell_data in self._cell_data.values())

    def _cell_functions(
        self,
    ) -> Iterable[Optional[CellFunction[CellFuncType]]]:
        return (
            cell_data.cell_function for cell_data in self._cell_data.values()
        )

    def _validate_args(self) -> None:
        """Validate the args of each cell function.

        Args should match cell.refs, excluding builtins that haven't been
        shadowed by other cells.

        This function must be called after all cells have been parsed, because
        it's only then that we know the set of unshadowed builtins.

        Raises: ValueError if a cell has an invalid arg set.
        """
        defs = set(
            itertools.chain.from_iterable(
                f.cell.defs for f in self._cell_functions() if f is not None
            )
        )
        unshadowed_builtins = set(builtins.__dict__.keys()).difference(defs)
        for f in self._cell_functions():
            if f is None:
                continue
            expected_args = f.cell.refs - unshadowed_builtins
            if f.args != expected_args:
                suggested_sig = (
                    f"def {f.__name__}({', '.join(sorted(expected_args))}):"
                )
                raise ValueError(
                    "A cell must take all its refs as args. "
                    "This rule is violated by the following function:\n\n"
                    + textwrap.indent(f.code, prefix="    ")
                    + "\n"
                    f"Fix: Make '{suggested_sig}' this function's signature."
                )

    def _unparsable_cell(
        self,
        code: str,
        name: Optional[str] = None,
        **config: Any,
    ) -> None:
        cell_id = self._create_cell_id(None)
        name = name if name is not None else "__"
        # - code.split("\n")[1:-1] disregards first and last lines, which are
        #   empty
        # - line[4:] removes leading indent in multiline string
        # - replace(...) unescapes double quotes
        # - rstrip() removes an extra newline
        code = "\n".join(
            [line[4:].replace('\\"', '"') for line in code.split("\n")[1:-1]]
        )
        self._cell_data[cell_id] = CellData(
            cell_id=cell_id,
            code=code,
            name=name,
            config=CellConfig.from_dict(config),
            cell_function=None,
        )
        self._unparsable = True

    def _maybe_initialize(self) -> None:
        assert not self._unparsable
        if not self._initialized:
            # ids of cells to add to the graph, in the order that they
            # were registered with the app
            self._cell_ids = [
                # exclude unparseable cells from graph
                cell_data.cell_id
                for cell_data in self._cell_data.values()
                if cell_data.cell_function is not None
            ]
            self._graph = DirectedGraph()
            for cell_id in self._cell_ids:
                cell_function = self._cell_data[cell_id].cell_function
                assert cell_function is not None
                self._graph.register_cell(cell_id, cell_function.cell)
            self._defs = self._graph.definitions.keys()

            # these two helper functions could be written as concise
            # `any` expressions using assignment expressions, but
            # that's a silly reason to make Python < 3.8 incompatible
            # with marimo.
            def get_multiply_defined() -> Optional[str]:
                for name, definers in self._graph.definitions.items():
                    if len(definers) > 1:
                        return name
                return None

            def get_deleted_nonlocal_ref() -> Optional[str]:
                for cell in self._graph.cells.values():
                    for ref in cell.deleted_refs:
                        if ref in self._graph.definitions:
                            return ref
                return None

            try:
                if self._graph.cycles:
                    raise CycleError(
                        "This app can't be run because it has cycles."
                    )
                name = get_multiply_defined()
                if name is not None:
                    raise MultipleDefinitionError(
                        "This app can't be run because it has multiple "
                        f"definitions of the name {name}"
                    )
                ref = get_deleted_nonlocal_ref()
                if ref is not None:
                    raise DeleteNonlocalError(
                        "This app can't be run because at least one cell "
                        f"deletes one of its refs (the ref's name is {ref})"
                    )
                self._execution_order = topological_sort(
                    self._graph, self._cell_ids
                )
            finally:
                self._initialized = True

    def run(self) -> tuple[Sequence[Any], dict[str, Any]]:
        if self._unparsable:
            raise UnparsableError(
                "This app can't be run because it has unparsable cells."
            )

        self._maybe_initialize()
        glbls: dict[Any, Any] = {}
        outputs = {
            cid: execute_cell(cell_function.cell, glbls)
            for cid in self._execution_order
            if (cell_function := self._cell_data[cid].cell_function)
            is not None
        }
        # Return
        # - the outputs, sorted in the order that cells were added to the
        #   graph
        # - dict of defs -> values
        return (
            tuple(
                outputs[cid]
                for cid in self._registration_order
                # exclude unparseable cells
                if cid in outputs
            ),
            {name: glbls[name] for name in self._defs},
        )
