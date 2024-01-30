# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import random
import string
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import (
    Any,
    Callable,
    Iterable,
    Literal,
    Optional,
    Union,
    cast,
)

from marimo import _loggers
from marimo._ast.cell import (
    CellConfig,
    CellFunction,
    CellFuncType,
    CellFuncTypeBound,
    CellId_t,
    execute_cell,
)
from marimo._ast.compiler import cell_factory
from marimo._ast.errors import (
    CycleError,
    DeleteNonlocalError,
    MultipleDefinitionError,
    UnparsableError,
)
from marimo._output.rich_help import mddoc
from marimo._runtime.dataflow import DirectedGraph, topological_sort

LOGGER = _loggers.marimo_logger()


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

    def update(self, updates: dict[str, Any]) -> _AppConfig:
        config_dict = asdict(self)
        for key in updates:
            if key in config_dict:
                self.__setattr__(key, updates[key])

        return self


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

        self._cell_manager = CellManager()
        self._graph = DirectedGraph()

        self._unparsable = False
        self._initialized = False

    def cell(
        self,
        func: Optional[CellFuncTypeBound] = None,
        *,
        disabled: bool = False,
        hide_code: bool = False,
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

        return self._cell_manager.cell_decorator(func, disabled, hide_code)

    def _unparsable_cell(
        self,
        code: str,
        name: Optional[str] = None,
        **config: Any,
    ) -> None:
        self._cell_manager.register_unparsable_cell(
            code,
            name,
            CellConfig.from_dict(config),
        )
        self._unparsable = True

    def _maybe_initialize(self) -> None:
        assert not self._unparsable

        if self._initialized:
            LOGGER.warning(
                "App was initialized twice. This is probably a bug in marimo."
            )
            return

        # Add cells to graph
        for cell_id, cell_fn in self._cell_manager.valid_cells():
            self._graph.register_cell(cell_id, cell_fn.cell)
        self._defs = self._graph.definitions.keys()

        try:
            # Check for cycles, multiply defined names, and deleted nonlocal
            if self._graph.cycles:
                raise CycleError(
                    "This app can't be run because it has cycles."
                )
            name = self._graph.get_multiply_defined()
            if name is not None:
                raise MultipleDefinitionError(
                    "This app can't be run because it has multiple "
                    f"definitions of the name {name}"
                )
            ref = self._graph.get_deleted_nonlocal_ref()
            if ref is not None:
                raise DeleteNonlocalError(
                    "This app can't be run because at least one cell "
                    f"deletes one of its refs (the ref's name is {ref})"
                )
            self._execution_order = topological_sort(
                self._graph, list(self._cell_manager.valid_cell_ids())
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

        # Execute cells and collect outputs
        outputs: dict[CellId_t, Any] = {}
        for cid in self._execution_order:
            cell_function = self._cell_manager.cell_data_at(cid).cell_function
            if cell_function is not None:
                outputs[cid] = execute_cell(cell_function.cell, glbls)

        # Return
        # - the outputs, sorted in the order that cells were added to the
        #   graph
        # - dict of defs -> values
        return (
            tuple(outputs[cid] for cid in self._cell_manager.valid_cell_ids()),
            # omit defs that were never defined at runtime, eg due to
            # conditional definitions like
            #
            # if cond:
            #   x = 0
            {name: glbls[name] for name in self._defs if name in glbls},
        )


class CellManager:
    """
    A manager for cells.

    This holds the cells that have been registered with the app, and
    provides methods to access them.
    """

    def __init__(self) -> None:
        self._cell_data: dict[CellId_t, CellData] = {}
        self.unparsable = False
        self.random_seed = random.Random(42)

    def create_cell_id(self) -> CellId_t:
        # 4 random letters
        return "".join(self.random_seed.choices(string.ascii_letters, k=4))

    def cell_decorator(
        self,
        func: Optional[CellFuncTypeBound],
        disabled: bool,
        hide_code: bool,
    ) -> Union[
        Callable[[CellFuncType], CellFunction[CellFuncTypeBound]],
        CellFunction[CellFuncTypeBound],
    ]:
        cell_config = CellConfig(disabled=disabled, hide_code=hide_code)

        if func is None:
            # If the decorator was used with parentheses, func will be None,
            # and we return a decorator that takes the decorated function as an
            # argument
            def decorator(
                func: CellFuncTypeBound,
            ) -> CellFunction[CellFuncTypeBound]:
                cell_function = cell_factory(
                    func, cell_id=self.create_cell_id()
                )
                cell_function.cell.configure(cell_config)
                self._register_cell_function(cell_function)
                return cell_function

            return cast(
                Callable[[CellFuncType], CellFunction[CellFuncTypeBound]],
                decorator,
            )

        # If the decorator was used without parentheses, func will be the
        # decorated function
        cell_function = cell_factory(func, cell_id=self.create_cell_id())
        cell_function.cell.configure(cell_config)
        self._register_cell_function(cell_function)
        return cell_function

    def _register_cell_function(
        self, cell_function: CellFunction[CellFuncTypeBound]
    ) -> None:
        self.register_cell(
            cell_id=cell_function.cell.cell_id,
            code=cell_function.cell.code,
            name=cell_function.__name__,
            config=cell_function.cell.config,
            cell_function=cast(CellFunction[CellFuncType], cell_function),
        )

    def register_cell(
        self,
        cell_id: Optional[CellId_t],
        code: str,
        config: Optional[CellConfig],
        name: str = "__",
        cell_function: Optional[CellFunction[CellFuncType]] = None,
    ) -> None:
        if cell_id is None:
            cell_id = self.create_cell_id()

        self._cell_data[cell_id] = CellData(
            cell_id=cell_id,
            code=code,
            name=name,
            config=config or CellConfig(),
            cell_function=cell_function,
        )

    def register_unparsable_cell(
        self,
        code: str,
        name: Optional[str],
        cell_config: CellConfig,
    ) -> None:
        # - code.split("\n")[1:-1] disregards first and last lines, which are
        #   empty
        # - line[4:] removes leading indent in multiline string
        # - replace(...) unescapes double quotes
        # - rstrip() removes an extra newline
        code = "\n".join(
            [line[4:].replace('\\"', '"') for line in code.split("\n")[1:-1]]
        )

        self.register_cell(
            cell_id=self.create_cell_id(),
            code=code,
            config=cell_config,
            name=name or "__",
            cell_function=None,
        )

    def names(self) -> Iterable[str]:
        for cell_data in self._cell_data.values():
            yield cell_data.name

    def codes(self) -> Iterable[str]:
        for cell_data in self._cell_data.values():
            yield cell_data.code

    def configs(self) -> Iterable[CellConfig]:
        for cell_data in self._cell_data.values():
            yield cell_data.config

    def valid_cells(
        self,
    ) -> Iterable[tuple[CellId_t, CellFunction[CellFuncType]]]:
        """Return cells and functions for each valid cell."""
        for cell_data in self._cell_data.values():
            if cell_data.cell_function is not None:
                yield (cell_data.cell_id, cell_data.cell_function)

    def valid_cell_ids(self) -> Iterable[CellId_t]:
        for cell_data in self._cell_data.values():
            if cell_data.cell_function is not None:
                yield cell_data.cell_id

    def cell_ids(self) -> Iterable[CellId_t]:
        """Cell IDs in the order they were registered."""
        return self._cell_data.keys()

    def cell_functions(
        self,
    ) -> Iterable[Optional[CellFunction[CellFuncType]]]:
        for cell_data in self._cell_data.values():
            yield cell_data.cell_function

    def config_map(self) -> dict[CellId_t, CellConfig]:
        return {cid: cd.config for cid, cd in self._cell_data.items()}

    def cell_data(self) -> Iterable[CellData]:
        return self._cell_data.values()

    def cell_data_at(self, cell_id: CellId_t) -> CellData:
        return self._cell_data[cell_id]


class InternalApp:
    """
    Internal representation of an app.

    This exposes private APIs that are used by the server and other
    internal components.
    """

    def __init__(self, app: App) -> None:
        self._app = app

    @property
    def config(self) -> _AppConfig:
        return self._app._config

    @property
    def cell_manager(self) -> CellManager:
        return self._app._cell_manager

    def update_config(self, updates: dict[str, Any]) -> _AppConfig:
        return self.config.update(updates)

    def with_data(
        self,
        *,
        cell_ids: Iterable[CellId_t],
        codes: Iterable[str],
        names: Iterable[str],
        configs: Iterable[CellConfig],
    ) -> InternalApp:
        new_cell_manager = CellManager()
        for cell_id, code, name, config in zip(
            cell_ids, codes, names, configs
        ):
            new_cell_manager.register_cell(
                cell_id=cell_id,
                code=code,
                name=name,
                config=config,
            )
        self._app._cell_manager = new_cell_manager
        return self
