# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import base64
import io
import mimetypes
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    Optional,
    cast,
)

from marimo import __version__, _loggers
from marimo._ast.cell import Cell, CellImpl
from marimo._ast.names import DEFAULT_CELL_NAME, is_internal_cell_name
from marimo._ast.visitor import Language
from marimo._config.config import (
    DEFAULT_CONFIG,
    DisplayConfig,
    MarimoConfig,
)
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._config.utils import deep_copy
from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.mimetypes import KnownMimeType
from marimo._runtime import dataflow
from marimo._runtime.virtual_file import read_virtual_file
from marimo._schemas.serialization import NotebookSerializationV1
from marimo._server.export.utils import (
    format_filename_title,
    get_download_filename,
    get_filename,
    get_markdown_from_cell,
    get_sql_options_from_cell,
)
from marimo._server.file_manager import AppFileManager
from marimo._server.models.export import ExportAsHTMLRequest
from marimo._server.session.serialize import (
    serialize_notebook,
    serialize_session_view,
)
from marimo._server.session.session_view import SessionView
from marimo._server.templates.templates import (
    static_notebook_template,
    wasm_notebook_template,
)
from marimo._server.tokens import SkewProtectionToken
from marimo._types.ids import CellId_t
from marimo._utils.data_uri import build_data_url
from marimo._utils.marimo_path import MarimoPath
from marimo._utils.paths import marimo_package_path

LOGGER = _loggers.marimo_logger()

# Root directory for static assets
ROOT = (marimo_package_path() / "_static").resolve()

if TYPE_CHECKING:
    from nbformat.notebooknode import NotebookNode  # type: ignore


class Exporter:
    def export_as_html(
        self,
        *,
        file_manager: AppFileManager,
        session_view: SessionView,
        display_config: DisplayConfig,
        request: ExportAsHTMLRequest,
    ) -> tuple[str, str]:
        index_html = get_html_contents()

        filename = get_filename(file_manager.filename)

        files: dict[str, str] = {}
        for filename_and_length in request.files:
            if filename_and_length.startswith("/@file/"):
                filename = filename_and_length[7:]
            try:
                byte_length, basename = filename.split("-", 1)
                buffer_contents = read_virtual_file(basename, int(byte_length))
            except Exception as e:
                LOGGER.warning(
                    "File not found in export: %s. Error: %s",
                    filename_and_length,
                    e,
                )
                continue
            mime_type = mimetypes.guess_type(basename)[0] or "text/plain"
            files[filename_and_length] = build_data_url(
                cast(KnownMimeType, mime_type),
                base64.b64encode(buffer_contents),
            )

        # We only want pass the display config in the static notebook,
        # since we use:
        # - display.theme
        # - display.cell_output
        config = deep_copy(DEFAULT_CONFIG)
        config["display"] = display_config

        session_snapshot = serialize_session_view(session_view)
        notebook_snapshot = serialize_notebook(
            session_view, file_manager.app.cell_manager
        )
        if not request.include_code:
            code = ""
            # Clear code and console outputs
            for cell in notebook_snapshot["cells"]:
                cell["code"] = ""
                cell["name"] = ""
            for output in session_snapshot["cells"]:
                output["console"] = []
        else:
            code = file_manager.to_code()

        # We include the code hash regardless of whether we include the code
        code_hash = hash_code(file_manager.to_code())

        html = static_notebook_template(
            html=index_html,
            user_config=config,
            config_overrides={},
            server_token=SkewProtectionToken("static"),
            app_config=file_manager.app.config,
            filepath=file_manager.filename,
            code=code,
            code_hash=code_hash,
            session_snapshot=session_snapshot,
            notebook_snapshot=notebook_snapshot,
            files=files,
            asset_url=request.asset_url,
        )

        download_filename = get_download_filename(
            file_manager.filename, "html"
        )
        return html, download_filename

    def export_as_script(
        self,
        file_manager: AppFileManager,
    ) -> tuple[str, str]:
        # Check if any code is async, if so, raise an error
        for cell in file_manager.app.cell_manager.cells():
            if not cell:
                continue
            if cell._is_coroutine:
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

        download_filename = get_download_filename(
            file_manager.filename, "script.py"
        )
        return code, download_filename

    def export_as_ipynb(
        self,
        file_manager: AppFileManager,
        sort_mode: Literal["top-down", "topological"],
        session_view: Optional[SessionView] = None,
    ) -> tuple[str, str]:
        """Export notebook as .ipynb, optionally including outputs if session_view provided."""
        DependencyManager.nbformat.require(
            "to convert marimo notebooks to ipynb"
        )
        import nbformat  # type: ignore[import-not-found]

        notebook = nbformat.v4.new_notebook()  # type: ignore[no-untyped-call]
        graph = file_manager.app.graph

        # Sort cells based on sort_mode
        if sort_mode == "top-down":
            cell_ids = list(file_manager.app.cell_manager.cell_ids())
        else:
            cell_ids = dataflow.topological_sort(graph, graph.cells.keys())

        notebook["cells"] = []
        for cid in cell_ids:
            if cid not in graph.cells:
                LOGGER.warning("Cell %s not found in graph", cid)
                continue
            cell = graph.cells[cid]
            outputs: list[NotebookNode] = []

            if session_view is not None:
                # Get outputs for this cell and convert to IPython format
                cell_output = session_view.get_cell_outputs([cid]).get(
                    cid, None
                )
                cell_console_outputs = session_view.get_cell_console_outputs(
                    [cid]
                ).get(cid, [])
                outputs = _convert_marimo_output_to_ipynb(
                    cell_output, cell_console_outputs
                )

            notebook_cell = _create_notebook_cell(cell, outputs)
            # Add metadata to the cell
            marimo_metadata: dict[str, Any] = {}
            if cell.config.is_different_from_default():
                marimo_metadata["config"] = (
                    cell.config.asdict_without_defaults()
                )
            name = file_manager.app.cell_manager.cell_name(cid)
            if not is_internal_cell_name(name):
                marimo_metadata["name"] = name
            if marimo_metadata:
                notebook_cell["metadata"]["marimo"] = marimo_metadata
            notebook["cells"].append(notebook_cell)

        # notebook.metadata["marimo-version"] = __version__

        stream = io.StringIO()
        nbformat.write(notebook, stream)  # type: ignore[no-untyped-call]
        stream.seek(0)
        download_filename = get_download_filename(
            file_manager.filename, "ipynb"
        )
        return stream.read(), download_filename

    def export_as_md(
        self,
        notebook: NotebookSerializationV1,
        filename: Optional[str],
        previous: Path | None = None,
    ) -> tuple[str, str]:
        from marimo._ast import codegen
        from marimo._ast.app_config import _AppConfig
        from marimo._ast.compiler import compile_cell
        from marimo._convert.markdown.markdown import (
            extract_frontmatter,
            formatted_code_block,
            is_sanitized_markdown,
        )
        from marimo._utils import yaml

        filename = get_filename(filename)
        app_title = notebook.app.options.get("app_title", None)
        if not app_title:
            app_title = format_filename_title(filename)

        metadata: dict[str, str | list[str]] = {}
        metadata.update(
            {
                "title": app_title,
                "marimo-version": __version__,
            }
        )

        # Put data from AppFileManager into the yaml header.
        ignored_keys = {"app_title"}
        default_config = _AppConfig().asdict()

        # Get values defined in _AppConfig without explicitly extracting keys,
        # as long as it isn't the default.
        metadata.update(
            {
                k: v
                for k, v in notebook.app.options.items()
                if k not in ignored_keys and v != default_config.get(k)
            }
        )
        # If previously a markdown file, extract frontmatter.
        # otherwise if it was a python file, extract header.
        if previous and previous.suffix == ".py":
            header = codegen.get_header_comments(previous)
            if header:
                metadata["header"] = header.strip()
        else:
            header_file = previous if previous else filename
            if header_file:
                with open(header_file, encoding="utf-8") as f:
                    _metadata, _ = extract_frontmatter(f.read())
                metadata.update(_metadata)

        # Add the expected qmd filter to the metadata.
        if filename.endswith(".qmd"):
            if "filters" not in metadata:
                metadata["filters"] = []
            if "marimo" not in str(metadata["filters"]):
                if isinstance(metadata["filters"], str):
                    metadata["filters"] = metadata["filters"].split(",")
                if isinstance(metadata["filters"], list):
                    metadata["filters"].append("marimo-team/marimo")
                else:
                    LOGGER.warning(
                        "Unexpected type for filters: %s",
                        type(metadata["filters"]),
                    )

        header = yaml.marimo_compat_dump(
            {
                k: v
                for k, v in metadata.items()
                if v is not None and v != "" and v != []
            },
            sort_keys=False,
        )
        document = ["---", header.strip(), "---", ""]
        previous_was_markdown = False

        for cell in notebook.cells:
            code = cell.code
            # Config values are opt in, so only include if they are set.
            attributes = cell.options
            # Allow for attributes like column index.
            attributes = {
                k: repr(v).lower() for k, v in attributes.items() if v
            }
            if not is_internal_cell_name(cell.name):
                attributes["name"] = cell.name

            # No "cell" typically means not parseable. However newly added
            # cells require compilation before cell is set.
            # TODO: Refactor so it doesn't occur in export (codegen
            # does this too)
            # NB. Also need to recompile in the sql case since sql parsing is
            # cached.
            language: Language = "python"
            cell_impl: CellImpl | None = None
            try:
                cell_impl = compile_cell(code, cell_id=CellId_t("dummy"))
                language = cell_impl.language
            except SyntaxError:
                pass

            if cell_impl:
                # Markdown that starts a column is forced to code.
                column = attributes.get("column", None)
                if not column or column == "0":
                    markdown = get_markdown_from_cell(cell_impl, code)
                    # Unsanitized markdown is forced to code.
                    if markdown and is_sanitized_markdown(markdown):
                        # Use blank HTML comment to separate markdown codeblocks
                        if previous_was_markdown:
                            document.append("<!---->")
                        previous_was_markdown = True
                        document.append(markdown)
                        continue
                attributes["language"] = language
                # Definitely a code cell, but need to determine if it can be
                # formatted as non-python.
                if attributes["language"] == "sql":
                    sql_options: dict[str, str] | None = (
                        get_sql_options_from_cell(code)
                    )
                    if not sql_options:
                        # means not sql.
                        attributes.pop("language")
                    else:
                        # Ignore default query value.
                        if sql_options.get("query") == "_df":
                            sql_options.pop("query")
                        attributes.update(sql_options)
                        code = "\n".join(cell_impl.raw_sqls).strip()

            # Definitely no "cell"; as such, treat as code, as everything in
            # marimo is code.
            else:
                attributes["unparsable"] = "true"
            # Add a blank line between markdown and code
            if previous_was_markdown:
                document.append("")
            previous_was_markdown = False
            document.append(formatted_code_block(code, attributes))

        download_filename = get_download_filename(filename, "md")
        return "\n".join(document).strip(), download_filename

    def export_as_wasm(
        self,
        *,
        file_manager: AppFileManager,
        display_config: DisplayConfig,
        code: str,
        mode: Literal["edit", "run"],
        show_code: bool,
        asset_url: Optional[str] = None,
    ) -> tuple[str, str]:
        """Export notebook as a WASM-powered standalone HTML file."""
        index_html = get_html_contents()
        filename = get_filename(file_manager.filename)

        # We only want to pass the display config in the static notebook
        config: MarimoConfig = deep_copy(DEFAULT_CONFIG)
        config["display"] = display_config
        # Remove autosave
        config["save"]["autosave"] = "off"

        html = wasm_notebook_template(
            html=index_html,
            version=__version__,
            filename=filename,
            mode=mode,
            user_config=config,
            config_overrides={},
            app_config=file_manager.app.config,
            code=code,
            asset_url=asset_url,
            show_code=show_code,
        )

        download_filename = get_download_filename(
            file_manager.filename, "wasm.html"
        )

        return html, download_filename

    def export_assets(
        self, directory: Path, ignore_index_html: bool = False
    ) -> None:
        # Copy assets to the same directory as the notebook
        dirpath = Path(directory)
        LOGGER.debug(f"Copying assets to {dirpath}")
        if not dirpath.exists():
            dirpath.mkdir(parents=True, exist_ok=True)

        import shutil

        shutil.copytree(
            ROOT,
            dirpath,
            dirs_exist_ok=True,
            ignore=(
                shutil.ignore_patterns("index.html")
                if ignore_index_html
                else None
            ),
        )

    def export_public_folder(
        self, directory: Path, marimo_file: MarimoPath
    ) -> bool:
        FOLDER_NAME = "public"
        public_dir = marimo_file.path.parent / FOLDER_NAME

        if public_dir.exists():
            import shutil

            # Copy public folder to the same directory as the notebook
            dirpath = Path(directory)
            if not dirpath.exists():
                dirpath.mkdir(parents=True, exist_ok=True)

            target_dir = dirpath / FOLDER_NAME
            if target_dir == public_dir:
                # Skip if source and target are the same
                return True

            LOGGER.debug(f"Copying public folder to {dirpath}")
            shutil.copytree(
                public_dir,
                target_dir,
                dirs_exist_ok=True,
            )
            return True

        return False


class AutoExporter:
    EXPORT_DIR = "__marimo__"

    def __init__(self) -> None:
        # Cache directories we've already created to avoid redundant checks
        self._created_dirs: set[Path] = set()
        # Thread pool for blocking I/O operations
        self._executor = ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="export"
        )

    async def _save_file(
        self, file_manager: AppFileManager, content: str, extension: str
    ) -> None:
        directory = Path(get_filename(file_manager.filename)).parent
        filename = get_download_filename(file_manager.filename, extension)

        await self._ensure_export_dir_async(directory)
        filepath = directory / self.EXPORT_DIR / filename

        # Run blocking file I/O in thread pool
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self._executor, self._write_file_sync, filepath, content
        )

    async def save_html(self, file_manager: AppFileManager, html: str) -> None:
        await self._save_file(file_manager, html, "html")

    async def save_md(
        self, file_manager: AppFileManager, markdown: str
    ) -> None:
        await self._save_file(file_manager, markdown, "md")

    async def save_ipynb(
        self, file_manager: AppFileManager, ipynb: str
    ) -> None:
        await self._save_file(file_manager, ipynb, "ipynb")

    def _write_file_sync(self, filepath: Path, content: str) -> None:
        """Synchronous file write (runs in thread pool)"""
        if content == "":
            return
        filepath.write_text(content, encoding="utf-8")

    async def _ensure_export_dir_async(self, directory: Path) -> None:
        """Async directory creation with caching to avoid redundant checks"""
        export_dir = directory / self.EXPORT_DIR

        # Fast path: already created this directory
        if export_dir in self._created_dirs:
            return

        if not directory.exists():
            raise FileNotFoundError(f"Directory {directory} does not exist")

        export_dir.mkdir(parents=True, exist_ok=True)

        # Cache that we've created this directory
        self._created_dirs.add(export_dir)

    def cleanup(self) -> None:
        """Cleanup resources"""
        self._executor.shutdown(wait=False)


def hash_code(code: str) -> str:
    import hashlib

    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _create_notebook_cell(
    cell: CellImpl, outputs: list[NotebookNode]
) -> NotebookNode:
    import nbformat

    markdown_string = get_markdown_from_cell(
        Cell(_name=DEFAULT_CELL_NAME, _cell=cell), cell.code
    )
    if markdown_string is not None:
        return cast(
            nbformat.NotebookNode,
            nbformat.v4.new_markdown_cell(markdown_string, id=cell.cell_id),  # type: ignore[no-untyped-call]
        )

    node = cast(
        nbformat.NotebookNode,
        nbformat.v4.new_code_cell(cell.code, id=cell.cell_id),  # type: ignore[no-untyped-call]
    )
    if outputs:
        node.outputs = outputs
    return node


def get_html_contents() -> str:
    if GLOBAL_SETTINGS.DEVELOPMENT_MODE:
        import urllib.request

        # Fetch from a CDN
        LOGGER.info(
            "Fetching index.html from jsdelivr because in development mode"
        )
        url = f"https://cdn.jsdelivr.net/npm/@marimo-team/frontend@{__version__}/dist/index.html"
        with urllib.request.urlopen(url) as response:
            return cast(str, response.read().decode("utf-8"))

    index_html = Path(ROOT) / "index.html"
    return index_html.read_text(encoding="utf-8")


def _convert_marimo_output_to_ipynb(
    output: Optional[CellOutput], console_outputs: list[CellOutput]
) -> list[NotebookNode]:
    """Convert marimo output format to IPython notebook format."""
    import nbformat

    ipynb_outputs: list[NotebookNode] = []

    # Handle stdout/stderr
    for output in console_outputs:
        if output.channel == CellChannel.STDOUT:
            ipynb_outputs.append(
                cast(
                    nbformat.NotebookNode,
                    nbformat.v4.new_output(  # type: ignore[no-untyped-call]
                        "stream",
                        name="stdout",
                        text=output.data,
                    ),
                )
            )
        if output.channel == CellChannel.STDERR:
            ipynb_outputs.append(
                cast(
                    nbformat.NotebookNode,
                    nbformat.v4.new_output(  # type: ignore[no-untyped-call]
                        "stream",
                        name="stderr",
                        text=output.data,
                    ),
                )
            )

    if not output:
        return ipynb_outputs

    if output.data is None:
        return ipynb_outputs

    if output.channel not in (CellChannel.OUTPUT, CellChannel.MEDIA):
        return ipynb_outputs

    if output.mimetype == "text/plain" and (
        output.data == [] or output.data == ""
    ):
        return ipynb_outputs

    # Handle rich output
    data: dict[str, Any] = {}

    if output.mimetype == "application/vnd.marimo+error":
        # Captured by stdout/stderr
        return ipynb_outputs
    elif output.mimetype == "application/vnd.marimo+mimebundle":
        for mime, content in cast(dict[str, Any], output.data).items():
            data[mime] = content
    else:
        if (
            isinstance(output.data, str)
            and output.data.startswith("data:")
            and ";base64," in output.data
        ):
            data[output.mimetype] = output.data.split(";base64,")[1]
        else:
            data[output.mimetype] = output.data

    if data:
        ipynb_outputs.append(
            cast(
                nbformat.NotebookNode,
                nbformat.v4.new_output(  # type: ignore[no-untyped-call]
                    "display_data",
                    data=data,
                    metadata={},
                ),
            )
        )

    return ipynb_outputs
