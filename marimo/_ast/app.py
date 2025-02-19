# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import ast
import base64
import inspect
import sys
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from textwrap import dedent
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Iterable,
    Iterator,
    List,
    Literal,
    Mapping,
    Optional,
    TypeVar,
    Union,
    cast,
    overload,
)
from uuid import uuid4

from marimo._types.ids import CellId_t

if sys.version_info < (3, 10):
    from typing_extensions import ParamSpec, TypeAlias
else:
    from typing import ParamSpec, TypeAlias

from marimo import _loggers
from marimo._ast.cell import Cell, CellConfig, CellImpl
from marimo._ast.cell_manager import CellManager
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
    ContextNotInitializedError,
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


P = ParamSpec("P")
R = TypeVar("R")
Fn: TypeAlias = Callable[P, R]
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

    # CSS file, relative to the app file
    css_file: Optional[str] = None

    # HTML head file, relative to the app file
    html_head_file: Optional[str] = None

    # Whether to automatically download the app as HTML and Markdown
    auto_download: List[Literal["html", "markdown"]] = field(
        default_factory=list
    )

    # Experimental top-level cell support
    _toplevel_fn: bool = False

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
        # Used for experimental hooks which start with _
        return {
            k: v for (k, v) in asdict(self).items() if not k.startswith("_")
        }

    def update(self, updates: dict[str, Any]) -> _AppConfig:
        config_dict = asdict(self)
        for key in updates:
            if key in config_dict:
                self.__setattr__(key, updates[key])

        return self


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


class AppKernelRunnerRegistry:
    def __init__(self) -> None:
        # Mapping from thread to its kernel runners, so that app.embed() calls are
        # isolated across run sessions.
        self._runners: dict[int, dict[App, AppKernelRunner]] = {}

    @property
    def size(self) -> int:
        return len(self._runners)

    def get_runner(self, app: App) -> AppKernelRunner:
        app_runners = self._runners.setdefault(threading.get_ident(), {})
        runner = app_runners.get(app, None)
        if runner is None:
            runner = AppKernelRunner(InternalApp(app))
            app_runners[app] = runner
        return runner

    def remove_runner(self, app: App) -> None:
        app_runners = self._runners.get(tid := threading.get_ident(), {})
        if app in app_runners:
            del app_runners[app]
        if tid in self._runners and not (self._runners[tid]):
            del self._runners[tid]

    def shutdown(self) -> None:
        self._runners.clear()


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
        self._config: _AppConfig = _AppConfig.from_untrusted_dict(kwargs)

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

        self._unparsable_code: list[str] = []
        self._unparsable = False
        self._initialized = False
        # injection hook set by contexts like tests such that script traces are
        # deterministic and not dependent on the test itself.
        # Set as a private attribute as not to pollute AppConfig or kwargs.
        self._anonymous_file = False
        # injection hook to rewrite cells for pytest
        self._pytest_rewrite = False

        # Filename is derived from the callsite of the app
        self._filename: str | None = None
        try:
            self._filename = inspect.getfile(inspect.stack()[1].frame)
        except Exception:
            ...

    def __del__(self) -> None:
        try:
            get_context().app_kernel_runner_registry.remove_runner(self)
        except ContextNotInitializedError:
            ...

    def clone(self) -> App:
        """Clone an app to embed multiple copies of it.

        Utility method to clone an app object; use with `embed()` to create
        independent copies of apps.

        Returns:
            A new `app` object with the same code.
        """
        app = App()
        app._cell_manager = CellManager(prefix=str(uuid4()))
        for cell_id, code, name, config in zip(
            self._cell_manager.cell_ids(),
            self._cell_manager.codes(),
            self._cell_manager.names(),
            self._cell_manager.configs(),
        ):
            cell = None
            # If the cell exists, the cell data should be set.
            cell_data = self._cell_manager._cell_data.get(cell_id)
            new_cell_id = app._cell_manager.create_cell_id()
            if cell_data is not None:
                cell = cell_data.cell
                if cell is not None:
                    new_cell = Cell(
                        _name=cell.name,
                        _cell=CellImpl(
                            **{**cell._cell.__dict__, "cell_id": new_cell_id}
                        ),
                        _app=InternalApp(app),
                    )
                    app._cell_manager.register_cell(
                        cell_id=new_cell_id,
                        code=code,
                        name=name,
                        config=config,
                        cell=new_cell,
                    )
        return app

    def cell(
        self,
        func: Fn[P, R] | None = None,
        *,
        column: Optional[int] = None,
        disabled: bool = False,
        hide_code: bool = False,
        **kwargs: Any,
    ) -> Cell | Callable[[Fn[P, R]], Cell]:
        """A decorator to add a cell to the app.

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
            func: The decorated function.
            column: The column number to place this cell in.
            disabled: Whether to disable the cell.
            hide_code: Whether to hide the cell's code.
            **kwargs: For forward-compatibility with future arguments.
        """
        del kwargs

        return cast(
            Union[Cell, Callable[[Fn[P, R]], Cell]],
            self._cell_manager.cell_decorator(
                func, column, disabled, hide_code, app=InternalApp(self)
            ),
        )

    # Overloads are required to preserve the wrapped function's signature.
    # mypy is not smart enough to carry transitive typing in this case.
    @overload
    def function(self, func: Fn[P, R]) -> Fn[P, R]: ...

    @overload
    def function(self, **kwargs: Any) -> Callable[[Fn[P, R]], Fn[P, R]]: ...

    def function(
        self,
        func: Fn[P, R] | None = None,
        *,
        column: Optional[int] = None,
        disabled: bool = False,
        hide_code: bool = False,
        **kwargs: Any,
    ) -> Fn[P, R] | Callable[[Fn[P, R]], Fn[P, R]]:
        """A decorator to wrap a callable function into a cell in the app.

        This decorator can be called with or without parentheses. Each of the
        following is valid:

        ```
        @app.function
        def add(a: int, b: int) -> int:
            return a + b


        @app.function()
        def subtract(a: int, b: int):
            return a - b


        @app.function(disabled=True)
        def multiply(a: int, b: int) -> int:
            return a * b
        ```

        Args:
            func: The decorated function.
            column: The column number to place this cell in.
            disabled: Whether to disable the cell.
            hide_code: Whether to hide the cell's code.
            **kwargs: For forward-compatibility with future arguments.
        """
        del kwargs

        return cast(
            Union[Fn[P, R], Callable[[Fn[P, R]], Fn[P, R]]],
            self._cell_manager.cell_decorator(
                func,
                column,
                disabled,
                hide_code,
                app=InternalApp(self),
                top_level=True,
            ),
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
        self._unparsable_code.append(code)
        self._unparsable = True

    def _maybe_initialize(self) -> None:
        if self._unparsable:
            errors: list[str] = []
            for code in self._unparsable_code:
                try:
                    ast.parse(dedent(code))
                except SyntaxError as e:
                    error_line = e.text
                    error_marker: str = (
                        " " * (e.offset - 1) + "^"
                        if e.offset is not None
                        else ""
                    )
                    err = f"{error_line}{error_marker}\n{e.msg}"
                    errors.append(err)
            syntax_errors = "\n-----\n".join(errors)

            raise UnparsableError(
                f"The notebook '{self._filename}' has cells with syntax errors, "
                + f"so it cannot be initialized:\n {syntax_errors}"
            ) from None

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
        return get_context().app_kernel_runner_registry.get_runner(self)

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
        outputs, glbls = AppScriptRunner(
            InternalApp(self), filename=self._filename
        ).run()
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

        Running `await app.embed()` executes the notebook and results an object
        encapsulating the notebook visual output and its definitions.

        Embedded notebook outputs are interactive: when you interact with
        UI elements in an embedded notebook's output, any cell referring
        to the `app` object other than the one that imported it is marked for
        execution, and its internal state is automatically updated. This lets
        you use notebooks as building blocks or components to create
        higher-level notebooks.

        Multiple levels of nesting are supported: it's possible to embed a
        notebook that in turn embeds another notebook, and marimo will do the
        right thing.

        Example:
            ```python
            from my_notebook import app
            ```

            ```python
            # execute the notebook; app.embed() can't be called in the cell
            # that imported it!
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

        To embed independent copies of same app object, first clone the
        app with `app.clone()`:

            ```python
            from my_notebook import app
            ```

            ```python
            one = app.clone()
            r1 = await one.embed()
            ```

            ```python
            two = app.clone()
            r2 = await two.embed()

        Returns:
            An object `result` with two attributes: `result.output` (visual
            output of the notebook) and `result.defs` (a dictionary mapping
            variable names defined by the notebook to their values).

        """
        from marimo._plugins.stateless.flex import vstack
        from marimo._runtime.context.utils import running_in_notebook

        self._maybe_initialize()

        if running_in_notebook():
            # TODO(akshayka): raise a RuntimeError if called in the cell
            # that defined the name bound to this App, if any
            app_kernel_runner = self._get_kernel_runner()

            outputs: dict[CellId_t, Any]
            glbls: dict[str, Any]
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

    def inline_layout_file(self) -> InternalApp:
        if self.config.layout_file:
            layout_path = Path(self.config.layout_file)
            if self._app._filename:
                # Resolve relative to the current working directory
                layout_path = Path(self._app._filename).parent / layout_path
            layout_file = layout_path.read_bytes()
            data_uri = base64.b64encode(layout_file).decode()
            self.update_config(
                {"layout_file": f"data:application/json;base64,{data_uri}"}
            )
        return self

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
