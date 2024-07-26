# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import random
import string
from dataclasses import asdict, dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Iterable,
    Iterator,
    Mapping,
    Optional,
)
from uuid import uuid4

from marimo import _loggers
from marimo._ast.cell import Cell, CellConfig, CellId_t
from marimo._ast.compiler import cell_factory
from marimo._ast.errors import (
    CycleError,
    DeleteNonlocalError,
    MultipleDefinitionError,
    UnparsableError,
)
from marimo._config.config import WidthType
from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._runtime import dataflow
from marimo._runtime.app.kernel_runner import AppKernelRunner
from marimo._runtime.app.script_runner import AppScriptRunner
from marimo._runtime.context.types import (
    get_context,
    runtime_context_installed,
)
from marimo._runtime.requests import (
    FunctionCallRequest,
    SetUIElementValueRequest,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from marimo._messaging.ops import HumanReadableStatus
    from marimo._plugins.core.web_component import JSONType
    from marimo._runtime.context.types import ExecutionContext

LOGGER = _loggers.marimo_logger()


@dataclass
class _AppConfig:
    """Program-specific configuration.

    Configuration for frontends or runtimes that is specific to
    a single marimo program.
    """

    width: WidthType = "compact"
    app_title: Optional[str] = None

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
    def __init__(
        self, dictionary: dict[str, object], owner: Cell | App
    ) -> None:
        self._dict = dictionary
        self._owner = owner

    def __getitem__(self, item: str) -> object:
        return self._dict[item]

    def __iter__(self) -> Iterator[str]:
        return iter(self._dict)

    def __len__(self) -> int:
        return len(self._dict)

    def _mime_(self) -> tuple[KnownMimeType, str]:
        from marimo._plugins.stateless.tree import tree

        return tree(self._dict)._mime_()


@dataclass
class AppEmbedResult:
    output: Html
    defs: Mapping[str, object]


@mddoc
class App:
    """A marimo notebook.

    A marimo notebook is a dataflow graph, with each node computing a Python
    function.
    """

    def __init__(self, **kwargs: Any) -> None:
        # Take `AppConfig` as kwargs for forward/backward compatibility;
        # unrecognized settings will just be dropped, instead of raising
        # a TypeError.
        self._config = _AppConfig.from_untrusted_dict(kwargs)

        if runtime_context_installed():
            # nested applications get a unique cell prefix to disambiguate
            # their graph from other graphs
            get_context()
            cell_prefix = str(uuid4())
        else:
            cell_prefix = ""

        self._cell_manager = CellManager(prefix=cell_prefix)
        self._graph = dataflow.DirectedGraph()
        self._execution_context: ExecutionContext | None = None
        self._runner = dataflow.Runner(self._graph)

        self._unparsable = False
        self._initialized = False
        # injection hook set by contexts like tests such that script traces are
        # deterministic and not dependent on the test itself.
        # Set as a private attribute as not to pollute AppConfig or kwargs.
        self._anonymous_file = False

        self._app_kernel_runner: AppKernelRunner | None = None

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
            raise UnparsableError(
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
            multiply_defined_names = self._graph.get_multiply_defined()
            if multiply_defined_names:
                raise MultipleDefinitionError(
                    "This app can't be run because it has multiple "
                    f"definitions of the name {multiply_defined_names[0]}"
                )
            deleted_nonlocal_refs = self._graph.get_deleted_nonlocal_ref()
            if deleted_nonlocal_refs:
                raise DeleteNonlocalError(
                    "This app can't be run because at least one cell "
                    "deletes one of its refs (the ref's name is "
                    f"{deleted_nonlocal_refs[0]})"
                )
            self._execution_order = dataflow.topological_sort(
                self._graph, list(self._cell_manager.valid_cell_ids())
            )
        finally:
            self._initialized = True

    def _get_kernel_runner(self) -> AppKernelRunner:
        if self._app_kernel_runner is None:
            self._app_kernel_runner = AppKernelRunner(InternalApp(self))
        return self._app_kernel_runner

    def _flatten_outputs(self, outputs: dict[CellId_t, Any]) -> Sequence[Any]:
        return tuple(
            outputs[cid]
            for cid in self._cell_manager.valid_cell_ids()
            if not self._graph.is_disabled(cid) and cid in outputs
        )

    def _globals_to_defs(self, glbls: dict[str, Any]) -> _Namespace:
        return _Namespace(
            dictionary={
                name: glbls[name] for name in self._defs if name in glbls
            },
            owner=self,
        )

    def run(
        self,
    ) -> tuple[Sequence[Any], Mapping[str, Any]]:
        self._maybe_initialize()
        outputs, glbls = AppScriptRunner(InternalApp(self)).run()
        return (self._flatten_outputs(outputs), self._globals_to_defs(glbls))

    async def _run_cell_async(
        self, cell: Cell, kwargs: dict[str, Any]
    ) -> tuple[Any, _Namespace]:
        self._maybe_initialize()
        output, defs = await self._runner.run_cell_async(
            cell._cell.cell_id, kwargs
        )
        return output, _Namespace(defs, owner=self)

    def _run_cell_sync(
        self, cell: Cell, kwargs: dict[str, Any]
    ) -> tuple[Any, _Namespace]:
        self._maybe_initialize()
        output, defs = self._runner.run_cell_sync(cell._cell.cell_id, kwargs)
        return output, _Namespace(defs, owner=self)

    async def _set_ui_element_value(
        self, request: SetUIElementValueRequest
    ) -> bool:
        app_kernel_runner = self._get_kernel_runner()
        return await app_kernel_runner.set_ui_element_value(request)

    async def _function_call(
        self, request: FunctionCallRequest
    ) -> tuple[HumanReadableStatus, JSONType, bool]:
        app_kernel_runner = self._get_kernel_runner()
        return await app_kernel_runner.function_call(request)

    @mddoc
    async def embed(self) -> AppEmbedResult:
        """Embed a notebook into another notebook.

        The `embed` method lets you embed the output of a notebook
        into another notebook and access the values of its variables.

        **Example.**

        ```python
        from my_notebook import app
        ```

        ```python
        # execute the notebook
        result = await app.embed()
        ```

        ```python
        # view the notebook's visual output
        result.output
        ```

        ```python
        # access the notebook's defined variables
        result.defs
        ```

        Running `await app.embed()` executes the notebook and results an object
        encapsulating the notebook visual output and its definitions.

        Embedded notebook outputs are interactive: when you interact with
        UI elements in an embedded notebook's output, any cell referring
        to the `app` object is marked for execution, and its internal state
        is automatically updated. This lets you notebooks as building blocks or
        components to create higher-level notebooks.

        Multiple levels of nesting are supported: it's possible to embed a
        notebook that in turn embeds another notebook, and marimo will do the
        right thing.

        **Returns.**

        - An object `result` with two attributes: `result.output` (visual
          output of the notebook) and `result.defs` (a dictionary mapping
          variable names defined by the notebook to their values).
        """
        from marimo._plugins.stateless.flex import vstack
        from marimo._runtime.context.utils import running_in_notebook

        self._maybe_initialize()

        if running_in_notebook():
            app_kernel_runner = self._get_kernel_runner()

            if not app_kernel_runner.outputs:
                outputs, glbls = await app_kernel_runner.run(
                    set(self._execution_order)
                )
            else:
                outputs, glbls = (
                    app_kernel_runner.outputs,
                    app_kernel_runner.globals,
                )
            return AppEmbedResult(
                output=vstack(
                    [
                        o
                        for o in self._flatten_outputs(outputs)
                        if o is not None
                    ]
                ),
                defs=self._globals_to_defs(glbls),
            )
        else:
            flat_outputs, defs = self.run()
            return AppEmbedResult(
                output=vstack([o for o in flat_outputs if o is not None]),
                defs=defs,
            )


class CellManager:
    """
    A manager for cells.

    This holds the cells that have been registered with the app, and
    provides methods to access them.
    """

    def __init__(self, prefix: str = "") -> None:
        self._cell_data: dict[CellId_t, CellData] = {}
        self.prefix = prefix
        self.unparsable = False
        self.random_seed = random.Random(42)

    def create_cell_id(self) -> CellId_t:
        # 4 random letters
        return self.prefix + "".join(
            self.random_seed.choices(string.ascii_letters, k=4)
        )

    def cell_decorator(
        self,
        func: Callable[..., Any] | None,
        disabled: bool,
        hide_code: bool,
        app: InternalApp | None = None,
    ) -> Cell | Callable[..., Cell]:
        cell_config = CellConfig(disabled=disabled, hide_code=hide_code)

        def _register(func: Callable[..., Any]) -> Cell:
            cell = cell_factory(
                func,
                cell_id=self.create_cell_id(),
                anonymous_file=app._app._anonymous_file if app else False,
            )
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

    def get_cell_id_by_code(self, code: str) -> Optional[CellId_t]:
        """
        Finds the first cell with the given code and returns its cell ID.
        """
        for cell_id, cell_data in self._cell_data.items():
            if cell_data.code == code:
                return cell_id
        return None


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
    def graph(self) -> dataflow.DirectedGraph:
        self._app._maybe_initialize()
        return self._app._graph

    @property
    def execution_order(self) -> list[CellId_t]:
        self._app._maybe_initialize()
        return self._app._execution_order

    @property
    def execution_context(self) -> ExecutionContext | None:
        return self._app._execution_context

    def set_execution_context(
        self, execution_context: ExecutionContext | None
    ) -> None:
        self._app._execution_context = execution_context

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
            cell = None
            # If the cell exists, the cell data should be set.
            cell_data = self._app._cell_manager._cell_data.get(cell_id)
            if cell_data is not None:
                cell = cell_data.cell
            new_cell_manager.register_cell(
                cell_id=cell_id,
                code=code,
                name=name,
                config=config,
                cell=cell,
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

    async def set_ui_element_value(
        self, request: SetUIElementValueRequest
    ) -> bool:
        return await self._app._set_ui_element_value(request)

    async def function_call(
        self, request: FunctionCallRequest
    ) -> tuple[HumanReadableStatus, JSONType, bool]:
        return await self._app._function_call(request)
