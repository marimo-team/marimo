# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import html
import json
import os
from textwrap import dedent
from typing import Any, Literal, Optional, Union, cast

from marimo import __version__
from marimo._ast.app_config import _AppConfig
from marimo._config.config import MarimoConfig, PartialMarimoConfig
from marimo._output.utils import uri_encode_component
from marimo._schemas.notebook import NotebookV1
from marimo._schemas.session import NotebookSessionV1
from marimo._server.api.utils import parse_title
from marimo._server.file_manager import read_css_file, read_html_head_file
from marimo._server.model import SessionMode
from marimo._server.tokens import SkewProtectionToken
from marimo._utils.versions import is_editable

MOUNT_CONFIG_TEMPLATE = "'{{ mount_config }}'"


def _html_escape(text: str) -> str:
    """Escape HTML special characters."""
    return html.escape(text, quote=True)


def _get_mount_config(
    *,
    filename: Optional[str],
    mode: Literal["edit", "home", "read"],
    server_token: SkewProtectionToken,
    user_config: MarimoConfig,
    config_overrides: PartialMarimoConfig,
    app_config: Optional[_AppConfig],
    version: Optional[str] = None,
    show_app_code: bool = True,
    session_snapshot: Optional[NotebookSessionV1] = None,
    notebook_snapshot: Optional[NotebookV1] = None,
) -> str:
    """
    Return a JSON string with custom indentation and sorting.
    """

    options: dict[str, Any] = {
        "filename": filename or "",
        "mode": mode,
        "version": version or get_version(),
        "server_token": str(server_token),
        "user_config": user_config,
        "config_overrides": config_overrides,
        "app_config": _del_none_or_empty(app_config.asdict())
        if app_config
        else {},
        "view": {
            "showAppCode": show_app_code,
        },
        "notebook": notebook_snapshot,
        "session": session_snapshot,
    }

    return """{{
            "filename": {filename},
            "mode": {mode},
            "version": {version},
            "serverToken": {server_token},
            "config": {user_config},
            "configOverrides": {config_overrides},
            "appConfig": {app_config},
            "view": {view},
            "notebook": {notebook},
            "session": {session},
        }}
""".format(
        **{k: json.dumps(v, sort_keys=True) for k, v in options.items()}
    ).strip()


def home_page_template(
    html: str,
    base_url: str,
    user_config: MarimoConfig,
    config_overrides: PartialMarimoConfig,
    server_token: SkewProtectionToken,
) -> str:
    html = html.replace("{{ base_url }}", base_url)
    html = html.replace("{{ title }}", "marimo")
    html = html.replace("{{ filename }}", "")

    html = html.replace(
        MOUNT_CONFIG_TEMPLATE,
        _get_mount_config(
            filename=None,
            mode="home",
            server_token=server_token,
            user_config=user_config,
            config_overrides=config_overrides,
            app_config=None,
        ),
    )

    # Add custom CSS from display config
    html = _inject_custom_css_for_config(html, user_config)
    html = _inject_custom_css_for_config(html, config_overrides)
    return html


def notebook_page_template(
    html: str,
    base_url: str,
    user_config: MarimoConfig,
    config_overrides: PartialMarimoConfig,
    server_token: SkewProtectionToken,
    app_config: _AppConfig,
    filename: Optional[str],
    mode: SessionMode,
) -> str:
    html = html.replace("{{ base_url }}", base_url)

    html = html.replace("{{ filename }}", _html_escape(filename or ""))
    html = html.replace(
        MOUNT_CONFIG_TEMPLATE,
        _get_mount_config(
            filename=filename,
            mode="read" if mode == SessionMode.RUN else "edit",
            server_token=server_token,
            user_config=user_config,
            config_overrides=config_overrides,
            app_config=app_config,
        ),
    )

    html = html.replace(
        "{{ title }}",
        _html_escape(
            parse_title(filename)
            if app_config.app_title is None
            else app_config.app_title
        ),
    )

    # If has custom css, inline the css and add to the head
    if app_config.css_file:
        css_contents = read_css_file(app_config.css_file, filename=filename)
        if css_contents:
            css_contents = _custom_css_block(css_contents)
            # Append to head
            html = html.replace("</head>", f"{css_contents}</head>")

    # Add custom CSS from display config
    html = _inject_custom_css_for_config(html, user_config, filename)
    html = _inject_custom_css_for_config(html, config_overrides, filename)

    # Add HTML head file contents if specified
    if app_config.html_head_file:
        head_contents = read_html_head_file(
            app_config.html_head_file, filename=filename
        )
        if head_contents:
            # Append to head
            html = html.replace("</head>", f"{head_contents}</head>")

    return html


def static_notebook_template(
    html: str,
    user_config: MarimoConfig,
    config_overrides: PartialMarimoConfig,
    server_token: SkewProtectionToken,
    app_config: _AppConfig,
    filepath: Optional[str],
    code: str,
    code_hash: str,
    session_snapshot: NotebookSessionV1,
    notebook_snapshot: NotebookV1,
    files: dict[str, str],
    asset_url: Optional[str] = None,
) -> str:
    if asset_url is None:
        asset_url = f"https://cdn.jsdelivr.net/npm/@marimo-team/frontend@{__version__}/dist"

    html = html.replace("{{ base_url }}", "")
    filename = os.path.basename(filepath or "")
    html = html.replace("{{ filename }}", _html_escape(filename))

    # We don't need all this user config when we export the notebook,
    # but we do need some:
    # - display.theme
    # - display.cell_output
    html = html.replace(
        MOUNT_CONFIG_TEMPLATE,
        _get_mount_config(
            filename=filename,
            mode="read",
            server_token=server_token,
            user_config=user_config,
            config_overrides=config_overrides,
            app_config=app_config,
            session_snapshot=session_snapshot,
            notebook_snapshot=notebook_snapshot,
        ),
    )

    html = html.replace(
        "{{ title }}",
        _html_escape(
            parse_title(filepath)
            if app_config.app_title is None
            else app_config.app_title
        ),
    )

    static_block = dedent(
        f"""
    <script data-marimo="true">
        window.__MARIMO_STATIC__ = {{}};
        window.__MARIMO_STATIC__.files = {json.dumps(files)};
    </script>
    """
    )

    # Add HTML head file contents if specified
    if app_config.html_head_file:
        head_contents = read_html_head_file(
            app_config.html_head_file, filename=filepath
        )
        if head_contents:
            static_block += dedent(
                f"""
            {head_contents}
            """
            )

    # If has custom css, inline the css and add to the head
    if app_config.css_file:
        css_contents = read_css_file(app_config.css_file, filename=filepath)
        if css_contents:
            static_block += _custom_css_block(css_contents)

    # Add custom CSS from display config
    static_block = _inject_custom_css_for_config(
        static_block, user_config, filepath
    )
    static_block = _inject_custom_css_for_config(
        static_block, config_overrides, filepath
    )

    code_block = dedent(
        f"""
    <marimo-code hidden="">
        {uri_encode_component(code)}
    </marimo-code>
    """
    )
    if not code:
        code_block = '<marimo-code hidden=""></marimo-code>'

    # Add a 256-bit hash of the code, for cache busting or CI checks
    code_block += (
        f'\n<marimo-code-hash hidden="">{code_hash}</marimo-code-hash>\n'
    )

    # Replace all relative href and src with absolute URL
    html = (
        html.replace("href='./", f"crossorigin='anonymous' href='{asset_url}/")
        .replace("src='./", f"crossorigin='anonymous' src='{asset_url}/")
        .replace('href="./', f'crossorigin="anonymous" href="{asset_url}/')
        .replace('src="./', f'crossorigin="anonymous" src="{asset_url}/')
    )

    # Append to head
    html = html.replace("</head>", f"{static_block}</head>")
    # Append to body
    html = html.replace("</body>", f"{code_block}</body>")

    html = _inject_custom_css_for_config(html, user_config, filepath)
    html = _inject_custom_css_for_config(html, config_overrides, filepath)
    return html


def wasm_notebook_template(
    *,
    html: str,
    version: str,
    filename: str,
    user_config: MarimoConfig,
    config_overrides: PartialMarimoConfig,
    app_config: _AppConfig,
    mode: Literal["edit", "run"],
    code: str,
    show_code: bool,
    asset_url: Optional[str] = None,
    show_save: bool = False,
) -> str:
    """Template for WASM notebooks."""
    import re

    body = html

    if asset_url is not None:
        body = re.sub(r'="./assets/', f'="{asset_url}/assets/', body)

    body = body.replace("{{ base_url }}", "")
    body = body.replace(
        "{{ title }}",
        _html_escape(
            parse_title(filename)
            if app_config.app_title is None
            else app_config.app_title
        ),
    )

    body = body.replace("{{ filename }}", _html_escape("notebook.py"))
    body = body.replace(
        MOUNT_CONFIG_TEMPLATE,
        _get_mount_config(
            # WASM runtime currently expect this to be notebook.py instead of the actual filename
            filename="notebook.py",
            mode="edit" if mode == "edit" else "read",
            server_token=SkewProtectionToken("unused"),
            user_config=user_config,
            config_overrides=config_overrides,
            app_config=app_config,
            version=version,
            show_app_code=show_code,
        ),
    )

    body = body.replace(
        "</head>", '<marimo-wasm hidden=""></marimo-wasm>\n</head>'
    )

    warning_script = """
    <script>
        if (window.location.protocol === 'file:') {
            alert('Warning: This file must be served by an HTTP server to function correctly.');
        }
    </script>
    """
    body = body.replace("</head>", f"{warning_script}</head>")

    wasm_styles = """
    <style>
        #save-button {
            display: none !important;
        }
        #filename-input {
            display: none !important;
        }
    </style>
    """
    # Hide save button in WASM mode unless explicitly requested to show
    if not show_save:
        body = body.replace("</head>", f"{wasm_styles}</head>")

    # If has custom css, inline the css and add to the head
    if app_config.css_file:
        css_contents = read_css_file(app_config.css_file, filename=filename)
        if css_contents:
            css_contents = _custom_css_block(css_contents)
            # Append to head
            body = body.replace("</head>", f"{css_contents}</head>")

    # Add custom CSS from display config
    body = _inject_custom_css_for_config(body, user_config, filename)
    body = _inject_custom_css_for_config(body, config_overrides, filename)

    # Add HTML head file contents if specified
    if app_config.html_head_file:
        head_contents = read_html_head_file(
            app_config.html_head_file, filename=filename
        )
        if head_contents:
            # Append to head
            body = body.replace("</head>", f"{head_contents}</head>")

    body = body.replace(
        "</head>",
        f'<marimo-code hidden="">{uri_encode_component(code)}</marimo-code></head>',
    )

    return body


def inject_script(html: str, script: str) -> str:
    """Inject a script into the HTML before the closing body tag."""
    script_tag = f"<script>{script}</script>"
    return html.replace("</body>", f"{script_tag}\n</body>")


def _del_none_or_empty(d: Any) -> Any:
    return {
        key: (
            _del_none_or_empty(cast(Any, value))
            if isinstance(value, dict)
            else value
        )
        for key, value in d.items()
        if value is not None and value != []
    }


def get_version() -> str:
    return (
        f"{__version__} (editable)" if is_editable("marimo") else __version__
    )


def _custom_css_block(css_contents: str) -> str:
    # marimo-custom is used by the frontend to identify this stylesheet
    # comes from marimo
    return f"<style title='marimo-custom'>{css_contents}</style>"


def _inject_custom_css_for_config(
    html: str,
    config: Union[MarimoConfig, PartialMarimoConfig],
    filename: Optional[str] = None,
) -> str:
    """Inject custom CSS from display config into HTML."""
    custom_css = config.get("display", {}).get("custom_css", [])
    if not custom_css:
        return html

    css_contents: list[str] = []
    for css_path in custom_css:
        css_content = read_css_file(css_path, filename=filename)
        if css_content:
            css_contents.append(_custom_css_block(css_content))

    if not css_contents:
        return html

    css_block = "\n".join(css_contents)
    return html.replace("</head>", f"{css_block}</head>")
