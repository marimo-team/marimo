# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import ast
import dataclasses
import inspect
from typing import TYPE_CHECKING, Any, Literal, Mapping, Optional

from marimo._ast.visitor import ImportData, Name, VariableData
from marimo._data.sql_visitor import SQLVisitor
from marimo._utils.deep_merge import deep_merge

CellId_t = str

if TYPE_CHECKING:
    from collections.abc import Awaitable, Iterable
    from types import CodeType

    from marimo._ast.app import InternalApp
    from marimo._messaging.types import Stream
    from marimo._output.hypertext import Html


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

    def asdict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

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


# States in a cell's runtime state machine
#
# idle: cell has run with latest inputs
# queued: cell is queued to run
# running: cell is running
# disabled-transitively: cell is disabled because a parent is disabled
RuntimeStateType = Literal[
    "idle", "queued", "running", "disabled-transitively"
]


@dataclasses.dataclass
class RuntimeState:
    state: Optional[RuntimeStateType] = None


# Statuses for a cell's attempted execution
#
# cancelled:    an ancestor raised an exception
# marimo-error: cell was prevented from executing
# disabled:     skipped because the cell is disabled
RunResultStatusType = Literal[
    "success",
    "exception",
    "cancelled",
    "interrupted",
    "marimo-error",
    "disabled",
]


@dataclasses.dataclass
class RunResultStatus:
    state: Optional[RunResultStatusType] = None


@dataclasses.dataclass
class ImportWorkspace:
    """A workspace for runtimes to use to manage a cell's imports."""

    # A cell is an import block if all statements are import statements
    is_import_block: bool = False
    # Defs that have been imported by the runtime
    imported_defs: set[Name] = dataclasses.field(default_factory=set)


def _is_coroutine(code: Optional[CodeType]) -> bool:
    if code is None:
        return False
    return inspect.CO_COROUTINE & code.co_flags == inspect.CO_COROUTINE


@dataclasses.dataclass
class CellStaleState:
    state: bool = False


@dataclasses.dataclass
class CellOutput:
    output: Any = None


@dataclasses.dataclass
class ParsedSQLStatements:
    parsed: Optional[list[str]] = None


@dataclasses.dataclass(frozen=True)
class CellImpl:
    # hash of code
    key: int
    code: str
    mod: ast.Module
    defs: set[Name]
    refs: set[Name]
    # metadata about definitions
    variable_data: dict[Name, list[VariableData]]
    deleted_refs: set[Name]
    body: Optional[CodeType]
    last_expr: Optional[CodeType]
    # unique id
    cell_id: CellId_t

    # Mutable fields
    # explicit configuration of cell
    config: CellConfig = dataclasses.field(default_factory=CellConfig)
    # workspace for runtimes to use to store metadata about imports
    import_workspace: ImportWorkspace = dataclasses.field(
        default_factory=ImportWorkspace
    )
    # execution status, inferred at runtime
    _status: RuntimeState = dataclasses.field(default_factory=RuntimeState)
    _run_result_status: RunResultStatus = dataclasses.field(
        default_factory=RunResultStatus
    )
    # whether the cell is stale, inferred at runtime
    _stale: CellStaleState = dataclasses.field(default_factory=CellStaleState)
    # cells can optionally hold a reference to their output
    _output: CellOutput = dataclasses.field(default_factory=CellOutput)
    # parsed sql statements
    _sqls: ParsedSQLStatements = dataclasses.field(
        default_factory=ParsedSQLStatements
    )

    def configure(self, update: dict[str, Any] | CellConfig) -> CellImpl:
        """Update the cell config.

        `update` can be a partial config.
        """
        self.config.configure(update)
        return self

    @property
    def runtime_state(self) -> Optional[RuntimeStateType]:
        return self._status.state

    @property
    def run_result_status(self) -> Optional[RunResultStatusType]:
        return self._run_result_status.state

    @property
    def sqls(self) -> list[str]:
        """Return a list of SQL statements for this cell."""
        if self._sqls.parsed is not None:
            return self._sqls.parsed

        try:
            visitor = SQLVisitor()
            visitor.visit(ast.parse(self.code))
            sqls = visitor.get_sqls()
            self._sqls.parsed = sqls
        except Exception:
            self._sqls.parsed = []

        return self._sqls.parsed

    @property
    def stale(self) -> bool:
        return self._stale.state

    @property
    def disabled_transitively(self) -> bool:
        return self.runtime_state == "disabled-transitively"

    @property
    def imports(self) -> Iterable[ImportData]:
        """Return a set of import data for this cell."""
        import_data = []
        for data in self.variable_data.values():
            import_data.extend(
                [
                    datum.import_data
                    for datum in data
                    if datum.import_data is not None
                ]
            )
        return import_data

    @property
    def imported_namespaces(self) -> set[Name]:
        """Return a set of the namespaces imported by this cell."""
        return set(
            import_data.module.split(".")[0] for import_data in self.imports
        )

    def namespace_to_variable(self, namespace: str) -> Name | None:
        """Returns the variable name corresponding to an imported namespace

        Relevant for imports "as" imports, eg

        import matplotlib.pyplot as plt

        In this case the namespace is "matplotlib" but the name is "plt".
        """
        for import_data in self.imports:
            if import_data.namespace == namespace:
                return import_data.definition
        return None

    def is_coroutine(self) -> bool:
        return _is_coroutine(self.body) or _is_coroutine(self.last_expr)

    def set_runtime_state(
        self, status: RuntimeStateType, stream: Stream | None = None
    ) -> None:
        """Set execution status and broadcast to frontends."""
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
        CellOp.broadcast_status(
            cell_id=self.cell_id, status=status, stream=stream
        )

    def set_run_result_status(
        self, run_result_status: RunResultStatusType
    ) -> None:
        self._run_result_status.state = run_result_status

    def set_stale(self, stale: bool, stream: Stream | None = None) -> None:
        from marimo._messaging.ops import CellOp

        self._stale.state = stale
        CellOp.broadcast_stale(
            cell_id=self.cell_id, stale=stale, stream=stream
        )

    def set_output(self, output: Any) -> None:
        self._output.output = output

    @property
    def output(self) -> Any:
        return self._output.output


@dataclasses.dataclass
class Cell:
    """An executable notebook cell

    A `Cell` object can be executed as a function via its `run()` method, which
    returns the cell's last expression (output) and a mapping from its defined
    names to its values.

    Cells can be named via the marimo editor in the browser, or by
    changing the cell's function name in the notebook file. Named
    cells can then be executed for use in other notebooks, or to test
    in unit tests.

    For example:

    ```python
    from my_notebook import my_cell

    output, definitions = my_cell.run()
    ```

    See the documentation of `run` for info and examples.
    """

    # Function from which this cell was created
    _name: str

    # Internal cell representation
    _cell: CellImpl

    # App to which this cell belongs
    _app: InternalApp | None = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def refs(self) -> set[str]:
        """The references that this cell takes as input"""
        return self._cell.refs

    @property
    def defs(self) -> set[str]:
        """The definitions made by this cell"""
        return self._cell.defs

    def _is_coroutine(self) -> bool:
        """Whether this cell is a coroutine function.

        If True, then this cell's `run` method returns an awaitable.
        """
        if hasattr(self, "_is_coro_cached"):
            return self._is_coro_cached
        assert self._app is not None
        self._is_coro_cached: bool = self._app.runner.is_coroutine(
            self._cell.cell_id
        )
        return self._is_coro_cached

    def _help(self) -> Html:
        from marimo._output.formatting import as_html
        from marimo._output.md import md

        signature_prefix = "Async " if self._is_coroutine() else ""
        execute_str_refs = (
            f"output, defs = await {self.name}.run(**refs)"
            if self._is_coroutine()
            else f"output, defs = {self.name}.run(**refs)"
        )
        execute_str_no_refs = (
            f"output, defs = await {self.name}.run()"
            if self._is_coroutine()
            else f"output, defs = {self.name}.run()"
        )

        return md(
            f"""
            **{signature_prefix}Cell `{self.name}`**

            You can execute this cell using

            `{execute_str_refs}`

            where `refs` is a dictionary mapping a subset of the
            cell's references to values. Missing refs will be automatically
            computed. To automatically compute all refs, simply run with

            `{execute_str_no_refs}`

            **References:**

            {as_html(list(self.refs))}

            **Definitions:**

            {as_html(list(self.defs))}
            """
        )

    def _register_app(self, app: InternalApp) -> None:
        self._app = app

    def run(
        self, **refs: Any
    ) -> (
        tuple[Any, Mapping[str, Any]]
        | Awaitable[tuple[Any, Mapping[str, Any]]]
    ):
        """Run this cell and return its visual output and definitions

        Use this method to run **named cells** and retrieve their output and
        definitions.

        This lets you use reuse cells defined in one notebook in another
        notebook or Python file. It also makes it possible to write and execute
        unit tests for notebook cells using a test framework like `pytest`.

        **Example.** marimo cells can be given names either through the
        editor cell menu or by manually changing the function name in the
        notebook file. For example, consider a notebook `notebook.py`:

        ```python
        import marimo

        app = marimo.App()


        @app.cell
        def __():
            import marimo as mo

            return (mo,)


        @app.cell
        def __():
            x = 0
            y = 1
            return (x, y)


        @app.cell
        def add(mo, x, y):
            z = x + y
            mo.md(f"The value of z is {z}")
            return (z,)


        if __name__ == "__main__":
            app.run()
        ```

        To reuse the `add` cell in another notebook, you'd simply write

        ```python
        from notebook import add

        # `output` is the markdown rendered by `add`
        # defs["z"] == `1`
        output, defs = add.run()
        ```

        When `run` is called without arguments, it automatically computes the
        values that the cell depends on (in this case, `mo`, `x`, and `y`). You
        can override these values by providing any subset of them as keyword
        arguments. For example,

        ```python
        # defs["z"] == 4
        output, defs = add.run(x=2, y=2)
        ```

        **Defined UI Elements.** If the cell's `output` has UI elements
        that are in `defs`, interacting with the output in the frontend will
        trigger reactive execution of cells that reference the `defs` object.
        For example, if `output` has a slider defined by the cell, then
        scrubbing the slider will cause cells that reference `defs` to run.

        **Async cells.** If this cell is a coroutine function (starting with
        `async`), or if any of its ancestors are coroutine functions, then
        you'll need to `await` the result: `output, defs = await cell.run()`.
        You can check whether the result is an awaitable using:

        ```python
        from collections.abc import Awaitable

        ret = cell.run()
        if isinstance(ret, Awaitable):
            output, defs = await ret
        else:
            output, defs = ret
        ```

        **Arguments**:

        - You may pass values for any of this cell's references as keyword
          arguments. marimo will automatically compute values for any refs
          that are not provided by executing the parent cells that compute
          them.

        **Returns**:

        - a tuple `(output, defs)`, or an awaitable of the same, where `output`
          is the cell's last expression and `defs` is a `Mapping` from the
          cell's defined names to their values.
        """
        assert self._app is not None
        if self._is_coroutine():
            return self._app.run_cell_async(cell=self, kwargs=refs)
        else:
            return self._app.run_cell_sync(cell=self, kwargs=refs)

    def __call__(self, *args: Any, **kwargs: Any) -> None:
        del args
        del kwargs
        if self._is_coroutine():
            call_str = f"`outputs, defs = await {self.name}.run()`"
        else:
            call_str = f"`outputs, defs = {self.name}.run()`"

        raise RuntimeError(
            f"Calling marimo cells using `{self.name}()` is not supported. "
            f"Use {call_str} instead. "
        )


@dataclasses.dataclass
class SourcePosition:
    filename: str
    lineno: int
    col_offset: int


def is_ws(char: str) -> bool:
    return char == " " or char == "\n" or char == "\t"
