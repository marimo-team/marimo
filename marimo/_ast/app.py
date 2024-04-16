# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import random
import string
from dataclasses import asdict, dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Iterable,
    Iterator,
    Literal,
    Mapping,
    Optional,
)

from marimo import _loggers
from marimo._ast.cell import Cell, CellConfig, CellId_t, execute_cell_async
from marimo._ast.compiler import cell_factory
from marimo._ast.errors import (
    CycleError,
    DeleteNonlocalError,
    MultipleDefinitionError,
    UnparsableError,
)
from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.rich_help import mddoc
from marimo._runtime import dataflow
from marimo._runtime.patches import patch_main_module_context

if TYPE_CHECKING:
    from collections.abc import Sequence

LOGGER = _loggers.marimo_logger()


@dataclass
class _AppConfig:
    """Program-specific configuration.

    Configuration for frontends or runtimes that is specific to
    a single marimo program.
    """

    width: Literal["normal", "medium", "full"] = "normal"

    # The file path of the layout file, relative to the app file.
    layout_file: Optional[str] = None

    @staticmethod
    def from_untrusted_dict(updates: dict[str, Any]) -> _AppConfig:
        config = _AppConfig()
        for key in updates:
            if hasattr(config, key):
                config.__setattr__(key, updates[key])
            else:
                LOGGER.warning(
                    f"Unrecognized key '{key}' in app config. Ignoring."
                )
        return config

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

    # The original cell, or None if cell was not parsable
    cell: Optional[Cell]


class _Namespace(Mapping[str, object]):
    def __init__(self, dictionary: dict[str, object]) -> None:
        self._dict = dictionary

    def __getitem__(self, item: str) -> object:
        return self._dict[item]

    def __iter__(self) -> Iterator[str]:
        return iter(self._dict)

    def __len__(self) -> int:
        return len(self._dict)

    def _mime_(self) -> tuple[KnownMimeType, str]:
        from marimo._plugins.stateless.tree import tree

        return tree(self._dict)._mime_()


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
        self._config = _AppConfig.from_untrusted_dict(kwargs)

        self._cell_manager = CellManager()
        self._graph = dataflow.DirectedGraph()
        self._runner = dataflow.Runner(self._graph)

        self._unparsable = False
        self._initialized = False

    def cell(
        self,
        func: Callable[..., Any] | None = None,
        *,
        disabled: bool = False,
        hide_code: bool = False,
        **kwargs: Any,
    ) -> Cell | Callable[[Callable[..., Any]], Cell]:
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

        return self._cell_manager.cell_decorator(
            func, disabled, hide_code, app=InternalApp(self)
        )

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
        if self._unparsable:
            raise RuntimeError(
                "This notebook has cells with syntax errors, "
                "so it cannot be initialized."
            )

        if self._initialized:
            return

        # Add cells to graph
        for cell_id, cell in self._cell_manager.valid_cells():
            self._graph.register_cell(cell_id, cell._cell)
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
            self._execution_order = dataflow.topological_sort(
                self._graph, list(self._cell_manager.valid_cell_ids())
            )
        finally:
            self._initialized = True

    async def _run_async(self) -> tuple[Sequence[Any], dict[str, Any]]:
        # TODO: We'll maybe expose this in the future
        if self._unparsable:
            raise UnparsableError(
                "This app can't be run because it has unparsable cells."
            )

        self._maybe_initialize()

        # No need to provide `file`, `input_override` here, since this
        # function is only called when running as a script
        with patch_main_module_context() as module:
            glbls = module.__dict__
            # Execute cells and collect outputs
            outputs: dict[CellId_t, Any] = {}
            for cid in self._execution_order:
                cell = self._cell_manager.cell_data_at(cid).cell
                if cell is not None:
                    outputs[cid] = await execute_cell_async(cell._cell, glbls)

            # Return
            # - the outputs, sorted in the order that cells were added to the
            #   graph
            # - dict of defs -> values
            return (
                tuple(
                    outputs[cid] for cid in self._cell_manager.valid_cell_ids()
                ),
                # omit defs that were never defined at runtime, eg due to
                # conditional definitions like
                #
                # if cond:
                #   x = 0
                {name: glbls[name] for name in self._defs if name in glbls},
            )

    def run(self) -> tuple[Sequence[Any], dict[str, Any]]:
        # formatters aren't automatically registered when running as a script
        from marimo._output.formatters.formatters import (
            register_formatters,
        )
        from marimo._output.formatting import FORMATTERS

        if not FORMATTERS:
            register_formatters()

        return asyncio.run(self._run_async())

    async def _run_cell_async(
        self, cell: Cell, kwargs: dict[str, Any]
    ) -> tuple[Any, _Namespace]:
        self._maybe_initialize()
        output, defs = await self._runner.run_cell_async(
            cell._cell.cell_id, kwargs
        )
        return output, _Namespace(defs)

    def _run_cell_sync(
        self, cell: Cell, kwargs: dict[str, Any]
    ) -> tuple[Any, _Namespace]:
        self._maybe_initialize()
        output, defs = self._runner.run_cell_sync(cell._cell.cell_id, kwargs)
        return output, _Namespace(defs)


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
        func: Callable[..., Any] | None,
        disabled: bool,
        hide_code: bool,
        app: InternalApp | None = None,
    ) -> Cell | Callable[..., Cell]:
        cell_config = CellConfig(disabled=disabled, hide_code=hide_code)

        def _register(func: Callable[..., Any]) -> Cell:
            cell = cell_factory(func, cell_id=self.create_cell_id())
            cell._cell.configure(cell_config)
            self._register_cell(cell, app=app)
            return cell

        if func is None:
            # If the decorator was used with parentheses, func will be None,
            # and we return a decorator that takes the decorated function as an
            # argument
            def decorator(func: Callable[..., Any]) -> Cell:
                return _register(func)

            return decorator
        else:
            return _register(func)

    def _register_cell(
        self, cell: Cell, app: InternalApp | None = None
    ) -> None:
        if app is not None:
            cell._register_app(app)
        cell_impl = cell._cell
        self.register_cell(
            cell_id=cell_impl.cell_id,
            code=cell_impl.code,
            name=cell.name,
            config=cell_impl.config,
            cell=cell,
        )

    def register_cell(
        self,
        cell_id: Optional[CellId_t],
        code: str,
        config: Optional[CellConfig],
        name: str = "__",
        cell: Optional[Cell] = None,
    ) -> None:
        if cell_id is None:
            cell_id = self.create_cell_id()

        self._cell_data[cell_id] = CellData(
            cell_id=cell_id,
            code=code,
            name=name,
            config=config or CellConfig(),
            cell=cell,
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
            cell=None,
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
    ) -> Iterable[tuple[CellId_t, Cell]]:
        """Return cells and functions for each valid cell."""
        for cell_data in self._cell_data.values():
            if cell_data.cell is not None:
                yield (cell_data.cell_id, cell_data.cell)

    def valid_cell_ids(self) -> Iterable[CellId_t]:
        for cell_data in self._cell_data.values():
            if cell_data.cell is not None:
                yield cell_data.cell_id

    def cell_ids(self) -> Iterable[CellId_t]:
        """Cell IDs in the order they were registered."""
        return self._cell_data.keys()

    def cells(
        self,
    ) -> Iterable[Optional[Cell]]:
        for cell_data in self._cell_data.values():
            yield cell_data.cell

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

    @property
    def runner(self) -> dataflow.Runner:
        self._app._maybe_initialize()
        return self._app._runner

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

    async def run_cell_async(
        self, cell: Cell, kwargs: dict[str, Any]
    ) -> tuple[Any, _Namespace]:
        return await self._app._run_cell_async(cell, kwargs)

    def run_cell_sync(
        self, cell: Cell, kwargs: dict[str, Any]
    ) -> tuple[Any, _Namespace]:
        return self._app._run_cell_sync(cell, kwargs)
