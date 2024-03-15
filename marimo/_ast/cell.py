# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import ast
import dataclasses
import inspect
from collections.abc import Awaitable
from types import CodeType
from typing import TYPE_CHECKING, Any, Callable, Literal, Mapping, Optional

from marimo._ast.visitor import Name, VariableData
from marimo._utils.deep_merge import deep_merge

CellId_t = str

if TYPE_CHECKING:
    from marimo._ast.app import InternalApp
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

    def module_to_variable(self, module: str) -> Name | None:
        """Returns the variable name corresponding to an imported module

        Relevant for imports "as" imports, eg

        import matplotlib.pyplot as plt

        In this case the module is "matplotlib" but the name is "plt".
        """
        for name, data in self.variable_data.items():
            if data.module == module:
                return name
        return None

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
    _f: Callable[..., Any]

    # Internal cell representation
    _cell: CellImpl

    # App to which this cell belongs
    _app: InternalApp | None = None

    @property
    def name(self) -> str:
        return self._f.__name__

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
