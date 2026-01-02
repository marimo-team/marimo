# Copyright 2026 Marimo. All rights reserved.
"""Public API for rendering marimo notebooks as HTML.

This module provides a clean, public API for rendering marimo notebooks
to HTML without needing to use internal template functions directly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Optional, cast

from marimo._ast.app_config import _AppConfig
from marimo._config.config import MarimoConfig, PartialMarimoConfig
from marimo._convert.converters import MarimoConvert
from marimo._schemas.notebook import NotebookV1
from marimo._schemas.session import NotebookSessionV1
from marimo._server.templates.templates import (
    _custom_css_block,
    notebook_page_template,
    static_notebook_template,
)
from marimo._server.tokens import SkewProtectionToken
from marimo._session.model import SessionMode
from marimo._utils.code import hash_code


def _get_html_template() -> str:
    """Get the base HTML template."""
    from marimo._utils.paths import marimo_package_path

    index_html = Path(marimo_package_path()) / "_static" / "index.html"
    return index_html.read_text(encoding="utf-8")


def _parse_config(config: Optional[dict[str, Any]]) -> MarimoConfig:
    """Parse config dict to MarimoConfig."""
    if config is None:
        return cast(MarimoConfig, {})
    return cast(MarimoConfig, config)


def _parse_partial_config(
    config: Optional[dict[str, Any]],
) -> PartialMarimoConfig:
    """Parse config dict to PartialMarimoConfig."""
    if config is None:
        return cast(PartialMarimoConfig, {})
    return cast(PartialMarimoConfig, config)


def _convert_code_to_notebook(
    code: str,
) -> tuple[NotebookV1, _AppConfig]:
    """Convert Python code to notebook format."""
    try:
        ir = MarimoConvert.from_py(code)
    except Exception:
        # Fallback to non-marimo script conversion
        ir = MarimoConvert.from_non_marimo_python_script(code, aggressive=True)

    app_config = _AppConfig.from_untrusted_dict(ir.ir.app.options)
    notebook = cast(NotebookV1, ir.to_notebook_v1())
    return notebook, app_config


def render_notebook(
    *,
    code: str,
    mode: Literal["edit", "read"],
    filename: str | None = None,
    config: dict[str, Any] | None = None,
    config_overrides: dict[str, Any] | None = None,
    app_config: dict[str, Any] | None = None,
    runtime_config: list[dict[str, Any]] | None = None,
    server_token: str | None = None,
    session_snapshot: NotebookSessionV1 | None = None,
    notebook_snapshot: NotebookV1 | None = None,
    base_url: str = "",
    asset_url: str | None = None,
    custom_css: str | None = None,
) -> str:
    """Render a marimo notebook to HTML.

    Handles all the conversions internally.

    Args:
        code: Raw Python code as a string.
        filename: Display filename.
        mode: Rendering mode - "edit" for editable, "read" for read-only.
        config: User configuration overrides as a dict.
        config_overrides: Notebook-specific configuration overrides as a dict.
        app_config: Notebook-specific configuration as a dict.
        runtime_config: Remote kernel configuration, e.g.,
            [{"url": "wss://...", "authToken": "..."}]
        server_token: Skew protection token.
        session_snapshot: Pre-computed session state.
        notebook_snapshot: Notebook structure/metadata.
        base_url: Base URL for the application (for <base> tag).
        asset_url: CDN URL for static assets (supports {version} placeholder).
        custom_css: CSS string to inject directly into the HTML.

    Returns:
        HTML string of the rendered notebook.

    Example:
        >>> html = render_notebook(
        ...     code="import marimo as mo\\nmo.md('Hello')",
        ...     filename="notebook.py",
        ...     mode="edit",
        ...     runtime_config=[{"url": "wss://kernel.example.com"}],
        ... )
    """

    # Convert code to notebook format if not already provided
    if notebook_snapshot is None or app_config is None:
        converted_notebook, converted_app_config = _convert_code_to_notebook(
            code
        )
        if notebook_snapshot is None:
            notebook_snapshot = converted_notebook
        if app_config is None:
            app_config = converted_app_config.asdict()

    # Parse configs
    user_config = _parse_config(config)
    config_overrides_obj = _parse_partial_config(config_overrides)
    app_config_obj = _AppConfig.from_untrusted_dict(app_config)

    # Get HTML template
    html = _get_html_template()

    result = notebook_page_template(
        html=html,
        base_url=base_url,
        user_config=user_config,
        config_overrides=config_overrides_obj,
        server_token=SkewProtectionToken(server_token or ""),
        app_config=app_config_obj,
        filename=filename,
        mode=_parse_session_mode(mode),
        session_snapshot=session_snapshot,
        notebook_snapshot=notebook_snapshot,
        runtime_config=runtime_config,
        asset_url=asset_url,
    )

    # Add custom CSS if provided
    if custom_css:
        result = _add_custom_css(result, custom_css)

    return result


def render_static_notebook(
    *,
    code: str,
    filename: str | None = None,
    include_code: bool = True,
    session_snapshot: NotebookSessionV1,
    notebook_snapshot: NotebookV1 | None = None,
    files: dict[str, str] | None = None,
    config: dict[str, Any] | None = None,
    app_config: dict[str, Any] | None = None,
    asset_url: str | None = None,
) -> str:
    """Render a static (pre-computed) marimo notebook to HTML.

    Creates a fully self-contained HTML file with pre-computed outputs.
    Ideal for sharing read-only versions of notebooks.

    Args:
        code: Raw Python code as a string.
        filename: Display filename.
        include_code: Whether to include source code in the export.
        session_snapshot: Pre-computed outputs for all cells (required).
        notebook_snapshot: Notebook structure/metadata.
        files: Files to embed (key=path, value=base64 content).
        config: User configuration overrides.
        app_config: Notebook-specific configuration.
        asset_url: CDN URL for assets (default: jsDelivr).

    Returns:
        HTML string of the static notebook.

    Example:
        >>> html = render_static_notebook(
        ...     code=Path("analysis.py").read_text(),
        ...     session_snapshot=precomputed_outputs,
        ...     config={"theme": "dark"},
        ... )
    """

    # Convert code to notebook format if not already provided
    if notebook_snapshot is None or app_config is None:
        converted_notebook, converted_app_config = _convert_code_to_notebook(
            code
        )
        if notebook_snapshot is None:
            notebook_snapshot = converted_notebook
        if app_config is None:
            app_config = converted_app_config.asdict()

    # Parse configs
    user_config = _parse_config(config)
    config_overrides_obj = _parse_partial_config(config or {})
    app_config_obj = _AppConfig.from_untrusted_dict(app_config)

    # Get HTML template
    html = _get_html_template()

    return static_notebook_template(
        html=html,
        user_config=user_config,
        config_overrides=config_overrides_obj,
        server_token=SkewProtectionToken("static"),
        app_config=app_config_obj,
        filepath=filename,
        code=code if include_code else "",
        code_hash=hash_code(code),
        session_snapshot=session_snapshot,
        notebook_snapshot=notebook_snapshot,
        files=files or {},
        asset_url=asset_url,
    )


def _add_custom_css(html: str, custom_css: str) -> str:
    css_block = _custom_css_block(custom_css)
    return html.replace("</head>", f"{css_block}</head>")


def _parse_session_mode(mode: Literal["edit", "read"]) -> SessionMode:
    if mode == "edit":
        return SessionMode.EDIT
    elif mode in ["run", "read"]:
        return SessionMode.RUN
    else:
        raise ValueError(
            f"Invalid session mode: {mode}. Must be 'edit' or 'run'."
        )


__all__ = [
    "render_notebook",
    "render_static_notebook",
]
