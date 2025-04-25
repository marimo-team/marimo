# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import importlib.util
import sys
from typing import Optional

from marimo import _loggers
from marimo._ast.app import App, InternalApp
from marimo._ast.parse import MarimoFileError, parse_notebook
from marimo._schemas.serialization import UnparsableCell

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


def _maybe_contents(filename: Optional[str]) -> Optional[str]:
    if filename is None:
        return None

    with open(filename, encoding="utf-8") as f:
        contents = f.read().strip()

    return contents


# Used in tests and current fallback
def _dynamic_load(filename: str) -> Optional[App]:
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


def _static_load(filename: str) -> Optional[App]:
    notebook = parse_notebook(filename)
    if notebook is None or not notebook.valid:
        return None
    app = App(**notebook.app.options, _filename=filename)
    for cell in notebook.cells:
        if isinstance(cell, UnparsableCell):
            app._unparsable_cell(cell.code, **cell.options)
            continue
        app._cell_manager.register_ir_cell(cell, InternalApp(app))
    return app


def load_app(filename: Optional[str]) -> Optional[App]:
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

    if filename.endswith(".md"):
        contents = _maybe_contents(filename)
        if not contents:
            return None
        from marimo._cli.convert.markdown import convert_from_md_to_app

        return convert_from_md_to_app(contents) if contents else None

    if not filename.endswith(".py"):
        raise MarimoFileError("File must end with .py or .md")

    try:
        return _static_load(filename)
    except MarimoFileError:
        # Security advantages of static load are lost here, but reasonable
        # fallback for now.
        _app = _dynamic_load(filename)
        LOGGER.warning(
            "Static loading of notebook failed; "
            "falling back to dynamic loading. "
            "If you can, please report this issue to the marimo team — "
            "https://github.com/marimo-team/marimo/issues/new?template=bug_report.yaml"
        )
        return _app
