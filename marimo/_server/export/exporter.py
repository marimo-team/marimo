from __future__ import annotations

import mimetypes
import os
from typing import cast

from marimo._config.config import (
    DEFAULT_CONFIG,
    DisplayConfig,
)
from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.utils import build_data_url
from marimo._runtime.virtual_file import read_virtual_file
from marimo._server.file_manager import AppFileManager
from marimo._server.models.export import ExportAsHTMLRequest
from marimo._server.session.session_view import SessionView
from marimo._server.templates.templates import static_notebook_template
from marimo._utils.paths import import_files

# Root directory for static assets
root = os.path.realpath(str(import_files("marimo").joinpath("_static")))


class Exporter:
    def export_as_html(
        self,
        file_manager: AppFileManager,
        session_view: SessionView,
        display_config: DisplayConfig,
        request: ExportAsHTMLRequest,
    ) -> tuple[str, str]:
        index_html_file = os.path.join(root, "index.html")

        cell_ids = list(file_manager.app.cell_manager.cell_ids())
        filename = file_manager.filename
        if not filename:
            filename = "notebook.py"

        with open(index_html_file, "r") as f:  # noqa: ASYNC101
            index_html = f.read()

        files: dict[str, str] = {}
        for filename_and_length in request.files:
            if filename_and_length.startswith("/@file/"):
                filename = filename_and_length[7:]
            byte_length, basename = filename.split("-", 1)
            buffer_contents = read_virtual_file(basename, int(byte_length))
            mime_type, _ = mimetypes.guess_type(basename) or (
                "text/plain",
                None,
            )
            files[filename_and_length] = build_data_url(
                cast(KnownMimeType, mime_type), buffer_contents
            )

        config = DEFAULT_CONFIG.copy()
        config["display"] = display_config

        code = file_manager.to_code() if request.include_code else ""
        codes = (
            file_manager.app.cell_manager.codes()
            if request.include_code
            else ["" for _ in cell_ids]
        )

        html = static_notebook_template(
            html=index_html,
            user_config=config,
            server_token="static",
            app_config=file_manager.app.config,
            filename=file_manager.filename,
            code=code,
            cell_ids=cell_ids,
            cell_names=list(file_manager.app.cell_manager.names()),
            cell_codes=list(codes),
            cell_configs=list(file_manager.app.cell_manager.configs()),
            cell_outputs=session_view.get_cell_outputs(cell_ids),
            cell_console_outputs=session_view.get_cell_console_outputs(
                cell_ids
            ),
            files=files,
            asset_url=request.asset_url,
        )

        basename = os.path.basename(filename)
        download_filename = f"{os.path.splitext(basename)[0]}.html"

        return html, download_filename
