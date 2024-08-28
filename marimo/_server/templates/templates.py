# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import base64
import json
from textwrap import dedent
from typing import Any, List, Optional, cast

from marimo import __version__
from marimo._ast.app import _AppConfig
from marimo._ast.cell import CellConfig, CellId_t
from marimo._config.config import MarimoConfig
from marimo._messaging.cell_output import CellOutput
from marimo._output.utils import uri_encode_component
from marimo._server.api.utils import parse_title
from marimo._server.file_manager import read_css_file
from marimo._server.model import SessionMode
from marimo._server.tokens import SkewProtectionToken


def home_page_template(
    html: str,
    base_url: str,
    user_config: MarimoConfig,
    server_token: SkewProtectionToken,
) -> str:
    html = html.replace("{{ base_url }}", base_url)
    html = html.replace("{{ user_config }}", json.dumps(user_config))
    html = html.replace("{{ server_token }}", str(server_token))
    html = html.replace("{{ version }}", __version__)

    html = html.replace("{{ title }}", "marimo")
    html = html.replace("{{ app_config }}", json.dumps({}))
    html = html.replace("{{ filename }}", "")
    html = html.replace("{{ mode }}", "home")

    return html


def notebook_page_template(
    html: str,
    base_url: str,
    user_config: MarimoConfig,
    server_token: SkewProtectionToken,
    app_config: _AppConfig,
    filename: Optional[str],
    mode: SessionMode,
) -> str:
    html = html.replace("{{ base_url }}", base_url)
    html = html.replace("{{ user_config }}", json.dumps(user_config))
    html = html.replace("{{ server_token }}", str(server_token))
    html = html.replace("{{ version }}", __version__)

    html = html.replace(
        "{{ title }}",
        parse_title(filename)
        if app_config.app_title is None
        else app_config.app_title,
    )
    html = html.replace(
        "{{ app_config }}", json.dumps(_del_none(app_config.asdict()))
    )
    html = html.replace("{{ filename }}", filename or "")
    html = html.replace(
        "{{ mode }}",
        "read" if mode == SessionMode.RUN else "edit",
    )
    return html


def static_notebook_template(
    html: str,
    user_config: MarimoConfig,
    server_token: SkewProtectionToken,
    app_config: _AppConfig,
    filename: Optional[str],
    code: str,
    cell_ids: list[str],
    cell_names: list[str],
    cell_codes: list[str],
    cell_configs: list[CellConfig],
    cell_outputs: dict[CellId_t, CellOutput],
    cell_console_outputs: dict[CellId_t, List[CellOutput]],
    files: dict[str, str],
    asset_url: Optional[str] = None,
) -> str:
    if asset_url is None:
        asset_url = f"https://cdn.jsdelivr.net/npm/@marimo-team/frontend@{__version__}/dist"

    html = html.replace("{{ base_url }}", "")
    # We don't need all this user config when we export the notebook,
    # but we do need some:
    # - display.theme
    # - display.cell_output
    html = html.replace(
        "{{ user_config }}", json.dumps(user_config, sort_keys=True)
    )
    html = html.replace("{{ server_token }}", str(server_token))
    html = html.replace("{{ version }}", __version__)

    html = html.replace(
        "{{ title }}",
        parse_title(filename)
        if app_config.app_title is None
        else app_config.app_title,
    )
    html = html.replace(
        "{{ app_config }}",
        json.dumps(_del_none(app_config.asdict()), sort_keys=True),
    )
    html = html.replace("{{ filename }}", filename or "")
    html = html.replace("{{ mode }}", "read")

    serialized_cell_outputs = {
        cell_id: _serialize_to_base64(json.dumps(output.asdict()))
        for cell_id, output in cell_outputs.items()
    }
    serialized_cell_console_outputs = {
        cell_id: [_serialize_to_base64(json.dumps(o.asdict())) for o in output]
        for cell_id, output in cell_console_outputs.items()
        if output
    }

    static_block = dedent(f"""
    <script data-marimo="true">
        window.__MARIMO_STATIC__ = {{}};
        window.__MARIMO_STATIC__.version = "{__version__}";
        window.__MARIMO_STATIC__.notebookState = {json.dumps({
          "cellIds": cell_ids,
          "cellNames": _serialize_list_to_base64(cell_names),
          "cellCodes": _serialize_list_to_base64(cell_codes),
          "cellConfigs": _serialize_list_to_base64([
            json.dumps(config.asdict())
            for config in cell_configs
          ]),
          "cellOutputs": serialized_cell_outputs,
          "cellConsoleOutputs": serialized_cell_console_outputs,
        })};
        window.__MARIMO_STATIC__.assetUrl = "{asset_url}";
        window.__MARIMO_STATIC__.files = {json.dumps(files)};
    </script>
    """)

    # If has custom css, inline the css and add to the head
    if app_config.css_file:
        css_contents = read_css_file(app_config.css_file, filename=filename)
        if css_contents:
            static_block += dedent(f"""
            <style>
                {css_contents}
            </style>
            """)

    code_block = f"""
    <marimo-code hidden="">
        {uri_encode_component(code)}
    </marimo-code>
    """
    if not code:
        code_block = '<marimo-code hidden=""></marimo-code>'

    # Replace all relative href and src with absolute URL
    html = (
        html.replace("href='./", f"crossorigin='anonymous' href='{asset_url}/")
        .replace("src='./", f"crossorigin='anonymous' src='{asset_url}/")
        .replace('href="./', f'crossorigin="anonymous" href="{asset_url}/')
        .replace('src="./', f'crossorigin="anonymous" src="{asset_url}/')
    )

    # Append to body
    html = html.replace("</head>", f"{static_block}</head>")
    # Append to body
    html = html.replace("</body>", f"{code_block}</body>")

    return html


def _serialize_to_base64(value: str) -> str:
    # Encode the JSON string to URL-encoded format
    url_encoded = uri_encode_component(value)
    # Encode the URL-encoded string to Base64
    base64_encoded = base64.b64encode(url_encoded.encode()).decode()
    return base64_encoded


def _serialize_list_to_base64(value: list[str]) -> list[str]:
    return [_serialize_to_base64(v) for v in value]


def _del_none(d: Any) -> Any:
    return {
        key: _del_none(cast(Any, value)) if isinstance(value, dict) else value
        for key, value in d.items()
        if value is not None
    }
