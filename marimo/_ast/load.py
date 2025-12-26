# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional, Union

from marimo import _loggers
from marimo._ast.app import App, InternalApp
from marimo._ast.parse import (
    MarimoFileError,
    is_non_marimo_python_script,
    parse_notebook,
)
from marimo._schemas.serialization import (
    CellDef,
    NotebookSerialization,
    UnparsableCell,
)

LOGGER = _loggers.marimo_logger()

# Notebooks have 4 entry points:
# 1. edit mode
# 2. run mode
# 3. as a script
# 4. loaded as a module
#
# When being run as a script or module, the expectation is to run _as_ python.
# However for "managed" marimo (i.e. run/ edit), the expectation is to not fail
# on startup and defer errors to the runtime.


@dataclass
class LoadResult:
    """Result of attempting to load a marimo notebook.

    status can be one of:
     - empty: No content, or only comments / a doc string
     - has_errors: Parsed, but has marimo-specific errors (**can load!!**)
     - invalid: Could not be parsed as a marimo notebook (**cannot load**)
     - valid: Parsed and valid marimo notebook
    """

    status: Literal["empty", "has_errors", "invalid", "valid"] = "empty"
    notebook: Optional[NotebookSerialization] = None
    contents: Optional[str] = None


def _maybe_contents(filename: Optional[Union[str, Path]]) -> Optional[str]:
    if filename is None:
        return None

    return Path(filename).read_text(encoding="utf-8").strip()


# Used in tests and current fallback
def _dynamic_load(filename: str | Path) -> Optional[App]:
    """Create and execute a module with the provided filename."""
    contents = _maybe_contents(filename)
    if not contents:
        return None

    spec = importlib.util.spec_from_file_location("marimo_app", filename)
    if spec is None:
        raise RuntimeError("Failed to load module spec")
    marimo_app = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError("Failed to load module spec's loader")
    try:
        sys.modules["marimo_app"] = marimo_app
        spec.loader.exec_module(marimo_app)  # This may throw a SyntaxError
    finally:
        sys.modules.pop("marimo_app", None)
    if not hasattr(marimo_app, "app"):
        return None
    if not isinstance(marimo_app.app, App):
        raise MarimoFileError("`app` attribute must be of type `marimo.App`.")

    app = marimo_app.app
    return app


def _static_load(filepath: Path) -> Optional[App]:
    contents = _maybe_contents(filepath)
    if not contents:
        return None

    notebook = parse_notebook(contents, filepath=str(filepath))

    if notebook and is_non_marimo_python_script(notebook):
        # Should fail instead of overriding contents
        raise MarimoFileError(
            f"Python script {filepath} is not a marimo notebook."
        )

    if notebook is None or not notebook.valid:
        return None

    return load_notebook_ir(notebook, filepath=str(filepath))


def find_cell(filename: str, lineno: int) -> CellDef | None:
    """Find the cell at the given line number in the notebook.

    Args:
        filename: Path to a marimo notebook file (.py or .md)
        lineno: Line number to search for
    """
    load_result = get_notebook_status(filename)
    if load_result.notebook is None:
        raise OSError("Could not resolve notebook.")
    previous = None
    for cell in load_result.notebook.cells:
        if cell.lineno > lineno:
            break
        previous = cell
    return previous


def load_notebook_ir(
    notebook: NotebookSerialization, filepath: Optional[str] = None
) -> App:
    """Load a notebook IR into an App."""
    # Use filepath from notebook if not explicitly provided
    if filepath is None:
        filepath = notebook.filename
    app = App(**notebook.app.options, _filename=filepath)
    for cell in notebook.cells:
        if isinstance(cell, UnparsableCell):
            app._unparsable_cell(cell.code, **cell.options)
            continue
        app._cell_manager.register_ir_cell(cell, InternalApp(app))
    if notebook.header and notebook.header.value:
        app._header = notebook.header.value
    return app


def get_notebook_status(filename: str) -> LoadResult:
    """Attempts to parse an app- should raise SyntaxError on failure.

    Args:
        filename: Path to a marimo notebook file (.py or .md)

    Returns:
        True if a falid code path.

    Raises:
        SyntaxError: If the file contains a syntax error
    """
    path = Path(filename)

    contents = _maybe_contents(filename)
    if not contents:
        return LoadResult(status="empty", contents=contents)

    notebook: Optional[NotebookSerialization] = None
    if path.suffix in (".md", ".qmd"):
        from marimo._convert.markdown.markdown import (
            convert_from_md_to_marimo_ir,
        )

        notebook = convert_from_md_to_marimo_ir(contents)
    elif path.suffix == ".py":
        notebook = parse_notebook(contents, filepath=filename)
    else:
        raise MarimoFileError("File must end with .py, .md, or .qmd.")

    # NB. A invalid notebook can still be opened.
    if notebook is None:
        return LoadResult(status="empty", contents=contents)
    if not notebook.valid:
        return LoadResult(
            status="invalid", notebook=notebook, contents=contents
        )
    if len(notebook.violations) > 0:
        LOGGER.debug(
            "Notebook has violations: \n%s",
            "\n".join(map(repr, notebook.violations)),
        )
        return LoadResult(
            status="has_errors", notebook=notebook, contents=contents
        )
    return LoadResult(status="valid", notebook=notebook, contents=contents)


FAILED_LOAD_NOTEBOOK_MESSAGE = (
    "Static loading of notebook failed; falling back to dynamic loading. "
    "If you can, please report this issue to the marimo team and include your notebook if possible — "
    "https://github.com/marimo-team/marimo/issues/new?template=bug_report.yaml"
)


def load_app(filename: Optional[str | Path]) -> Optional[App]:
    """Load and return app from a marimo-generated module.

    Args:
        filename: Path to a marimo notebook file (.py or .md)

    Returns:
        The marimo App instance if the file exists and contains valid code,
        None if the file is empty or contains only comments.

    Raises:
        MarimoFileError: If the file exists but doesn't define a valid marimo app
        RuntimeError: If there are issues loading the module
        SyntaxError: If the file contains a syntax error
        FileNotFoundError: If the file doesn't exist
    """

    if filename is None:
        return None

    path = Path(filename)

    if path.suffix in (".md", ".qmd"):
        contents = _maybe_contents(filename)
        if not contents:
            return None
        from marimo._convert.markdown.markdown import convert_from_md_to_app

        return convert_from_md_to_app(contents) if contents else None
    elif not path.suffix == ".py":
        raise MarimoFileError("File must end with .py or .md")

    try:
        return _static_load(path)
    except MarimoFileError:
        # Security advantages of static load are lost here, but reasonable
        # fallback for now.
        _app = _dynamic_load(filename)
        LOGGER.warning(FAILED_LOAD_NOTEBOOK_MESSAGE)
        return _app
