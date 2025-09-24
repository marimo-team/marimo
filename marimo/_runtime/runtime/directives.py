# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import dataclasses
import pathlib

from marimo._ast.cell import CellConfig
from marimo._ast.variables import BUILTINS
from marimo._output.rich_help import mddoc
from marimo._runtime.app_meta import AppMeta
from marimo._runtime.context import ContextNotInitializedError, get_context
from marimo._runtime.params import CLIArgs, QueryParams
from marimo._utils.platform import is_pyodide


@mddoc
def defs() -> tuple[str, ...]:
    """Get the definitions of the currently executing cell.

    Returns:
        tuple[str, ...]: A tuple of the currently executing cell's defs.
    """
    try:
        ctx = get_context()
    except ContextNotInitializedError:
        return tuple()

    if ctx.execution_context is not None:
        return tuple(
            sorted(
                defn
                for defn in ctx.graph.cells[ctx.execution_context.cell_id].defs
            )
        )
    return tuple()


@mddoc
def refs() -> tuple[str, ...]:
    """Get the references of the currently executing cell.

    Returns:
        tuple[str, ...]: A tuple of the currently executing cell's refs.
    """
    try:
        ctx = get_context()
    except ContextNotInitializedError:
        return tuple()

    # builtins that have not been shadowed by the user
    unshadowed_builtins = BUILTINS.difference(
        set(ctx.graph.definitions.keys())
    )

    if ctx.execution_context is not None:
        return tuple(
            sorted(
                defn
                for defn in ctx.graph.cells[ctx.execution_context.cell_id].refs
                # exclude builtins that have not been shadowed
                if defn not in unshadowed_builtins
            )
        )
    return tuple()


@mddoc
def query_params() -> QueryParams:
    """Get the query parameters of a marimo app.

    Examples:
        Keep the text input in sync with the URL query parameters:

        ```python3
        # In its own cell
        query_params = mo.query_params()

        # In another cell
        search = mo.ui.text(
            value=query_params["search"] or "",
            on_change=lambda value: query_params.set("search", value),
        )
        search
        ```

        You can also set the query parameters reactively:

        ```python3
        toggle = mo.ui.switch(label="Toggle me")
        toggle

        # In another cell
        query_params["is_enabled"] = toggle.value
        ```

    Returns:
        QueryParams: A QueryParams object containing the query parameters.
            You can directly interact with this object like a dictionary.
            If you mutate this object, changes will be persisted to the frontend
            query parameters and any other cells referencing the query parameters
            will automatically re-run.
    """
    return get_context().query_params


@mddoc
def app_meta() -> AppMeta:
    """Get the metadata of a marimo app.

    The `AppMeta` class provides access to runtime metadata about a marimo app,
    such as its display theme and execution mode.

    Examples:
        Get the current theme and conditionally set a plotting library's theme:

        ```python
        import altair as alt

        # Enable dark theme for Altair when marimo is in dark mode
        alt.themes.enable(
            "dark" if mo.app_meta().theme == "dark" else "default"
        )
        ```

        Show content only in edit mode:

        ```python
        # Only show this content when editing the notebook
        mo.md("# Developer Notes") if mo.app_meta().mode == "edit" else None
        ```

        Get the current request headers or user info:

        ```python
        request = mo.app_meta().request
        print(request.headers)
        print(request.user)
        ```

    Returns:
        AppMeta: An AppMeta object containing the app's metadata.
    """
    return AppMeta()


@mddoc
def cli_args() -> CLIArgs:
    """Get the command line arguments of a marimo notebook.

    Examples:
        `marimo edit notebook.py -- -size 10`

        ```python3
        # Access the command line arguments
        size = mo.cli_args().get("size") or 100

        for i in range(size):
            print(i)
        ```

    Returns:
        CLIArgs: A dictionary containing the command line arguments.
            This dictionary is read-only and cannot be mutated.
    """
    return get_context().cli_args


@mddoc
def notebook_dir() -> pathlib.Path | None:
    """Get the directory of the currently executing notebook.

    Returns:
        pathlib.Path | None: A pathlib.Path object representing the directory of the current
            notebook, or None if the notebook's directory cannot be determined.

    Examples:
        ```python
        data_file = mo.notebook_dir() / "data" / "example.csv"
        # Use the directory to read a file
        if data_file.exists():
            print(f"Found data file: {data_file}")
        else:
            print("No data file found")
        ```
    """
    try:
        ctx = get_context()
    except ContextNotInitializedError:
        # If we are not running in a notebook (e.g. exported to Jupyter),
        # return the current working directory
        return pathlib.Path().absolute()

    # NB: __file__ is patched by runner, so always bound to be correct.
    filename = ctx.globals.get("__file__", None) or ctx.filename
    if filename is not None:
        path = pathlib.Path(filename).resolve()
        while not path.is_dir():
            path = path.parent
        return path

    return None


class URLPath(pathlib.PurePosixPath):
    """
    Wrapper around pathlib.Path that preserves the "://" in the URL protocol.
    """

    def __str__(self) -> str:
        return super().__str__().replace(":/", "://")


@mddoc
def notebook_location() -> pathlib.PurePath | None:
    """Get the location of the currently executing notebook.

    In WASM, this is the URL of webpage, for example, `https://my-site.com`.
    For nested paths, this is the URL including the origin and pathname.
    `https://<my-org>.github.io/<my-repo>/folder`.

    In non-WASM, this is the directory of the notebook, which is the same as
    `mo.notebook_dir()`.

    Examples:
        In order to access data both locally and when a notebook runs via
        WebAssembly (e.g. hosted on GitHub Pages), you can use this
        approach to fetch data from the notebook's location.

        ```python
        import polars as pl

        data_path = mo.notebook_location() / "public" / "data.csv"
        df = pl.read_csv(str(data_path))
        df.head()
        ```

    Returns:
        Path | None: A Path object representing the URL or directory of the current
            notebook, or None if the notebook's directory cannot be determined.
    """
    if is_pyodide():
        from js import location  # type: ignore

        path_location = pathlib.Path(str(location))
        # The location looks like https://marimo-team.github.io/marimo-gh-pages-template/notebooks/assets/worker-BxJ8HeOy.js
        # We want to crawl out of the assets/ folder
        if "assets" in path_location.parts:
            return URLPath(str(path_location.parent.parent))
        return URLPath(str(path_location))

    else:
        return notebook_dir()


@dataclasses.dataclass
class CellMetadata:
    """CellMetadata class for storing cell metadata.

    Metadata the kernel needs to persist, even when a cell is removed
    from the graph or when a cell can't be formed from user code due to syntax
    errors.

    Attributes:
        config (CellConfig): Configuration for the cell.
    """

    config: CellConfig = dataclasses.field(default_factory=CellConfig)
