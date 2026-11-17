# Copyright 2026 Marimo. All rights reserved.
# ruff: noqa: E402
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._runtime._wasm import ensure_wasm_runtime_bootstrapped

ensure_wasm_runtime_bootstrapped()

from marimo._config.config import merge_config
from marimo._runtime.commands import AppMetadata, SerializedQueryParams
from marimo._runtime.patches import extract_docstring_from_header
from marimo._server.app_defaults import AppDefaults
from marimo._session.model import SessionMode
from marimo._session.notebook import AppFileManager

if TYPE_CHECKING:
    from marimo._config.config_schema import MarimoConfig
    from marimo._pyodide.pyodide_session import PyodideBridge, PyodideSession


def instantiate(
    session: PyodideSession, auto_instantiate: bool = True
) -> None:
    """
    Instantiate the marimo app in the session.

    This function is called by the WebAssembly frontend.
    """
    session.instantiate(auto_run=auto_instantiate)


def create_session(
    filename: str,
    query_params: SerializedQueryParams,
    user_config: MarimoConfig,
) -> tuple[PyodideSession, PyodideBridge]:
    """
    Create a session with the given filename and query parameters.

    Args:
        filename: The filename of the app.
        query_params: The query parameters from the URL.
        user_config: The user configuration.

    Returns:
        A tuple of (session, bridge)

    This function is called by the WebAssembly frontend.
    """
    ensure_wasm_runtime_bootstrapped()

    # Lazy import to decrease startup time
    from marimo._config.config import merge_default_config
    from marimo._config.manager import ScriptConfigReader

    # Add default config
    user_config = merge_default_config(user_config)
    script_config = ScriptConfigReader(filename).read()
    # Merge with inline script-metadata config
    user_config = merge_config(user_config, script_config)

    app_file_manager = AppFileManager(
        filename=filename,
        defaults=AppDefaults(
            width=user_config.display.default_width,
            sql_output=user_config.runtime.default_sql_output,
        ),
    )
    app = app_file_manager.app

    from marimo._pyodide.pyodide_session import PyodideBridge, PyodideSession

    session = PyodideSession(
        app_file_manager,
        SessionMode.EDIT,
        AppMetadata(
            query_params=query_params,
            filename=filename,
            cli_args={},
            argv=[],
            app_config=app.config,
            docstring=extract_docstring_from_header(
                app_file_manager.app._app._header
            ),
        ),
        user_config,
    )

    bridge = PyodideBridge(session)

    return session, bridge
