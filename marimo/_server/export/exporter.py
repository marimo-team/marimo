# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import base64
import io
import mimetypes
import os
from typing import cast

from marimo import __version__
from marimo._ast.cell import Cell, CellConfig, CellImpl
from marimo._config.config import (
    DEFAULT_CONFIG,
    DisplayConfig,
    _deep_copy,
)
from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.utils import build_data_url
from marimo._runtime import dataflow
from marimo._runtime.virtual_file import read_virtual_file
from marimo._server.export.utils import (
    get_app_title,
    get_download_filename,
    get_filename,
    get_markdown_from_cell,
)
from marimo._server.file_manager import AppFileManager
from marimo._server.models.export import ExportAsHTMLRequest
from marimo._server.session.session_view import SessionView
from marimo._server.templates.templates import static_notebook_template
from marimo._server.tokens import SkewProtectionToken
from marimo._utils.paths import import_files

# Root directory for static assets
root = os.path.realpath(str(import_files("marimo").joinpath("_static")))


class Exporter:
    def export_as_html(
        self,
        *,
        file_manager: AppFileManager,
        session_view: SessionView,
        display_config: DisplayConfig,
        request: ExportAsHTMLRequest,
    ) -> tuple[str, str]:
        index_html_file = os.path.join(root, "index.html")

        cell_ids = list(file_manager.app.cell_manager.cell_ids())
        filename = get_filename(file_manager)

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
                cast(KnownMimeType, mime_type),
                base64.b64encode(buffer_contents),
            )

        config = _deep_copy(DEFAULT_CONFIG)
        config["display"] = display_config

        # code and console outputs are grouped together, but
        # we can split them up in the future if desired.
        if request.include_code:
            code = file_manager.to_code()
            codes = file_manager.app.cell_manager.codes()
            configs = file_manager.app.cell_manager.configs()
            console_outputs = session_view.get_cell_console_outputs(cell_ids)
        else:
            code = ""
            codes = ["" for _ in cell_ids]
            configs = [CellConfig() for _ in cell_ids]
            console_outputs = {}

        html = static_notebook_template(
            html=index_html,
            user_config=config,
            server_token=SkewProtectionToken("static"),
            app_config=file_manager.app.config,
            filename=file_manager.filename,
            code=code,
            cell_ids=cell_ids,
            cell_names=list(file_manager.app.cell_manager.names()),
            cell_codes=list(codes),
            cell_configs=list(configs),
            cell_outputs=session_view.get_cell_outputs(cell_ids),
            cell_console_outputs=console_outputs,
            files=files,
            asset_url=request.asset_url,
        )

        download_filename = get_download_filename(file_manager, "html")
        return html, download_filename

    def export_as_script(
        self,
        file_manager: AppFileManager,
    ) -> tuple[str, str]:
        # Check if any code is async, if so, raise an error
        for cell in file_manager.app.cell_manager.cells():
            if not cell:
                continue
            if cell._is_coroutine():
                from click import UsageError

                raise UsageError(
                    "Cannot export a notebook with async code to a flat script"
                )

        graph = file_manager.app.graph
        codes: list[str] = [
            "# %%\n" + graph.cells[cid].code
            for cid in dataflow.topological_sort(graph, graph.cells.keys())
        ]
        code = f'\n__generated_with = "{__version__}"\n\n' + "\n\n".join(codes)

        download_filename = get_download_filename(file_manager, ".script.py")
        return code, download_filename

    def export_as_ipynb(
        self,
        file_manager: AppFileManager,
    ) -> tuple[str, str]:
        import nbformat  # type: ignore

        def create_notebook_cell(cell: CellImpl) -> nbformat.NotebookNode:
            markdown_string = get_markdown_from_cell(
                Cell(_name="__", _cell=cell), cell.code
            )
            if markdown_string is not None:
                return nbformat.v4.new_markdown_cell(  # type: ignore
                    markdown_string, id=cell.cell_id
                )
            else:
                return nbformat.v4.new_code_cell(cell.code, id=cell.cell_id)  # type: ignore

        notebook = nbformat.v4.new_notebook()  # type: ignore
        graph = file_manager.app.graph
        notebook["cells"] = [
            create_notebook_cell(graph.cells[cid])  # type: ignore
            for cid in dataflow.topological_sort(graph, graph.cells.keys())
        ]

        stream = io.StringIO()
        nbformat.write(notebook, stream)  # type: ignore
        stream.seek(0)
        download_filename = get_download_filename(file_manager, ".ipynb")
        return stream.read(), download_filename

    def export_as_md(self, file_manager: AppFileManager) -> tuple[str, str]:
        import yaml

        from marimo._ast.app import _AppConfig
        from marimo._ast.cell import Cell
        from marimo._ast.compiler import compile_cell
        from marimo._cli.convert.markdown import (
            formatted_code_block,
            is_sanitized_markdown,
        )

        # TODO: Provide filter or kernel in yaml header such that markdown
        # documents are executable.

        #  Put data from AppFileManager into the yaml header.
        ignored_keys = {"app_title", "layout_file"}
        metadata = {
            "title": get_app_title(file_manager),
            "marimo-version": __version__,
            "marimo-layout": file_manager.app.config.layout_file,
        }
        # Get values defined in _AppConfig without explicitly extracting keys,
        # as long as it isn't the default.
        metadata.update(
            {
                k: v
                for k, v in file_manager.app.config.asdict().items()
                if k not in ignored_keys and v != _AppConfig.__dict__[k]
            }
        )

        header = yaml.dump(
            {k: v for k, v in metadata.items() if v is not None},
            sort_keys=False,
        )
        document = ["---", header.strip(), "---", ""]
        previous_was_markdown = False
        for cell_data in file_manager.app.cell_manager.cell_data():
            cell = cell_data.cell
            code = cell_data.code
            # Config values are opt in, so only include if they are set.
            attributes = cell_data.config.asdict()
            attributes = {k: "true" for k, v in attributes.items() if v}
            if cell_data.name != "__":
                attributes["name"] = cell_data.name
            # No "cell" typically means not parseable. However newly added
            # cells require compilation before cell is set.
            # TODO: Refactor so it doesn't occur in export (codegen
            # does this too)
            if not cell:
                try:
                    cell_impl = compile_cell(
                        code, cell_id=str(cell_data.cell_id)
                    ).configure(cell_data.config)
                    cell = Cell(
                        _cell=cell_impl,
                        _name=cell_data.name,
                        _app=file_manager.app,
                    )
                    cell_data.cell = cell
                except SyntaxError:
                    pass

            # Definitely no "cell"; as such, treat as code, as everything in
            # marimo is code.
            if cell:
                markdown = get_markdown_from_cell(cell, code)
                # Unsanitized markdown is forced to code.
                if markdown and is_sanitized_markdown(markdown):
                    # Use blank HTML comment to separate markdown codeblocks
                    if previous_was_markdown:
                        document.append("<!---->")
                    previous_was_markdown = True
                    document.append(markdown)
                    continue
            else:
                attributes["unparsable"] = "true"
            # Add a blank line between markdown and code
            if previous_was_markdown:
                document.append("")
            previous_was_markdown = False
            document.append(formatted_code_block(code, attributes))

        download_filename = get_download_filename(file_manager, ".md")
        return "\n".join(document).strip(), download_filename
