# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass, replace
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

from marimo import _loggers
from marimo._ast.app import InternalApp
from marimo._ast.errors import CycleError, MultipleDefinitionError
from marimo._ast.load import load_app
from marimo._cli.print import echo
from marimo._config.config import RuntimeConfig
from marimo._config.manager import (
    get_default_config_manager,
)
from marimo._convert.common.filename import get_download_filename
from marimo._convert.converters import MarimoConvert
from marimo._convert.markdown.flavor import (
    markdown_output_filename,
    normalize_markdown_flavor,
)
from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.errors import Error, is_unexpected_error
from marimo._messaging.notification import (
    CellNotification,
    CompletedRunNotification,
)
from marimo._messaging.serde import deserialize_kernel_message
from marimo._messaging.types import KernelMessage
from marimo._output.hypertext import patch_html_for_non_interactive_output
from marimo._runtime.commands import (
    AppMetadata,
    SerializedCLIArgs,
)
from marimo._runtime.patches import extract_docstring_from_header
from marimo._schemas.serialization import NotebookSerialization
from marimo._server.export._status import emit_pdf_export_status
from marimo._server.export.exporter import Exporter
from marimo._server.models.export import (
    ExportAsHTMLRequest,
    ExportPDFPreset,
)
from marimo._server.models.models import InstantiateNotebookRequest
from marimo._session.model import ConnectionState, SessionMode
from marimo._session.notebook import AppFileManager, load_notebook
from marimo._types.ids import ConsumerId
from marimo._utils.inline_script_metadata import (
    pin_pep723_dependencies_for_wasm,
)
from marimo._utils.marimo_path import MarimoPath

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from collections.abc import Mapping

    from marimo._server.export._pdf_raster import PDFRasterizationOptions
    from marimo._server.export._status import PDFExportStatusCallback
    from marimo._session.state.session_view import SessionView
    from marimo._session.types import Session
    from marimo._types.ids import CellId_t


@dataclass
class ExportResult:
    contents: bytes | str
    download_filename: str
    did_error: bool

    @cached_property
    def bytez(self) -> bytes:
        """Return UTF-8 encoded bytes (cached)."""
        if isinstance(self.contents, bytes):
            return self.contents
        return self.contents.encode("utf-8")

    @cached_property
    def text(self) -> str:
        """Return UTF-8 decoded text (cached)."""
        if isinstance(self.contents, str):
            return self.contents
        return self.contents.decode("utf-8")


def _as_ir(path: MarimoPath) -> NotebookSerialization:
    if path.is_python():
        py_contents = path.read_text(encoding="utf-8")
        converter = MarimoConvert.from_py(py_contents)
        return _with_filename(converter.ir, path.short_name)
    elif path.is_markdown():
        md_contents = path.read_text(encoding="utf-8")
        converter = MarimoConvert.from_md(md_contents)
        return _with_filename(converter.ir, path.short_name)
    raise ValueError(f"Unsupported file type: {path.path.suffix}")


def export_as_script(path: MarimoPath) -> ExportResult:
    from marimo._convert.script import convert_from_ir_to_script

    ir = _as_ir(path)
    return ExportResult(
        contents=convert_from_ir_to_script(ir),
        download_filename=get_download_filename(path.short_name, "script.py"),
        did_error=False,
    )


def export_as_md(path: MarimoPath) -> ExportResult:
    ir = _as_ir(path)
    filename = ir.filename or path.short_name
    markdown_flavor = normalize_markdown_flavor(None, filename=filename)
    return ExportResult(
        contents=MarimoConvert.from_ir(ir).to_markdown(
            filename=filename, flavor=markdown_flavor
        ),
        download_filename=markdown_output_filename(filename, markdown_flavor),
        did_error=False,
    )


def export_as_ipynb(
    path: MarimoPath, sort_mode: Literal["top-down", "topological"]
) -> ExportResult:
    app = load_app(path.absolute_name)
    if app is None:
        return ExportResult(
            contents=b"",
            download_filename=get_download_filename(path.short_name, "ipynb"),
            did_error=True,
        )

    # Try the requested sort mode, fall back to top-down if cycles exist
    internal_app = InternalApp(app)
    actual_sort_mode = sort_mode
    if sort_mode == "topological":
        try:
            # Check if graph can be accessed (raises CycleError/MultipleDefinitionError)
            _ = internal_app.graph
        except (CycleError, MultipleDefinitionError):
            echo(
                "Warning: Notebook has errors, "
                "using top-down order instead of topological.",
                err=True,
            )
            actual_sort_mode = "top-down"

    result = Exporter().export_as_ipynb(
        app=internal_app,
        sort_mode=actual_sort_mode,
    )
    return ExportResult(
        contents=result,
        download_filename=get_download_filename(path.short_name, "ipynb"),
        did_error=False,
    )


def export_as_wasm(
    path: MarimoPath,
    mode: Literal["edit", "run"],
    show_code: bool,
    asset_url: str | None = None,
) -> ExportResult:
    _app = load_app(path.absolute_name)
    if _app is None:
        return ExportResult(
            contents=b"",
            download_filename=get_download_filename(
                path.short_name, "wasm.html"
            ),
            did_error=True,
        )
    app = InternalApp(_app)
    # Inline the layout file, if it exists
    app.inline_layout_file()
    config = get_default_config_manager(current_path=path.absolute_name)
    resolved = config.get_config()

    result = Exporter().export_as_wasm(
        filename=path.short_name,
        app=app,
        display_config=resolved["display"],
        mode=mode,
        code=app.to_py(),
        asset_url=asset_url,
        show_code=show_code,
        sharing_config=resolved.get("sharing"),
    )
    return ExportResult(
        contents=result[0],
        download_filename=result[1],
        did_error=False,
    )


def notebook_uses_slides_layout(filepath: MarimoPath) -> bool:
    """Return whether a notebook declares the slides layout."""
    try:
        file_manager = load_notebook(filepath.absolute_name)
        layout_config = file_manager.read_layout_config()
        return layout_config is not None and layout_config.type == "slides"
    except Exception as e:
        LOGGER.debug(
            "Unable to infer notebook layout for %s: %s",
            filepath.absolute_name,
            e,
        )
        return False


async def run_app_then_export_as_ipynb(
    filepath: MarimoPath,
    sort_mode: Literal["top-down", "topological"],
    cli_args: SerializedCLIArgs,
    argv: list[str] | None,
) -> ExportResult:
    file_manager = load_notebook(filepath.absolute_name)

    with patch_html_for_non_interactive_output():
        # Use quiet=True to suppress runtime stdout/stderr since outputs
        # are captured in the session_view and will be included in the ipynb
        (session_view, did_error) = await run_app_until_completion(
            file_manager,
            cli_args,
            argv,
            quiet=True,
        )

    result = Exporter().export_as_ipynb(
        app=file_manager.app,
        sort_mode=sort_mode,
        session_view=session_view,
    )
    return ExportResult(
        contents=result,
        download_filename=get_download_filename(filepath.short_name, "ipynb"),
        did_error=did_error,
    )


async def run_app_then_export_as_pdf(
    filepath: MarimoPath,
    *,
    include_outputs: bool,
    webpdf: bool,
    cli_args: SerializedCLIArgs,
    argv: list[str] | None,
    export_as: ExportPDFPreset | None,
    include_inputs: bool = True,
    rasterization_options: PDFRasterizationOptions | None = None,
    status_callback: PDFExportStatusCallback | None = None,
) -> tuple[bytes | None, bool]:
    file_manager = load_notebook(filepath.absolute_name)

    session_view: SessionView | None = None
    png_fallbacks: Mapping[CellId_t, str] | None = None
    did_error = False

    if include_outputs:
        emit_pdf_export_status(
            status_callback,
            phase="execute",
            message="executing notebook...",
        )
        with patch_html_for_non_interactive_output():
            # Using quiet=True to suppress runtime stdout/stderr since outputs
            # are captured in the session_view and will be included in the PDF
            (session_view, did_error) = await run_app_until_completion(
                file_manager,
                cli_args,
                argv,
                quiet=True,
            )
        emit_pdf_export_status(
            status_callback,
            phase="execute_complete",
            message="notebook execution finished.",
        )

        if (
            session_view is not None
            and rasterization_options is not None
            and rasterization_options.enabled
        ):
            from marimo._server.export._pdf_raster import (
                collect_pdf_png_fallbacks,
            )

            png_fallbacks = await collect_pdf_png_fallbacks(
                app=file_manager.app,
                session_view=session_view,
                filename=filepath.short_name,
                filepath=filepath.absolute_name,
                argv=argv,
                options=rasterization_options,
                status_callback=status_callback,
            )
    emit_pdf_export_status(
        status_callback,
        phase="prepare",
        message="serializing notebook for PDF rendering...",
    )
    exporter = Exporter()
    if export_as == "slides":
        pdf_data = await exporter.export_as_slides_pdf(
            app=file_manager.app,
            session_view=session_view,
            png_fallbacks=png_fallbacks,
            include_inputs=include_inputs,
            status_callback=status_callback,
        )
    else:
        pdf_data = exporter.export_as_pdf(
            app=file_manager.app,
            session_view=session_view,
            png_fallbacks=png_fallbacks,
            include_inputs=include_inputs,
            webpdf=webpdf,
            status_callback=status_callback,
        )
    if pdf_data is not None:
        emit_pdf_export_status(
            status_callback,
            phase="complete",
            message="done.",
        )
    return pdf_data, did_error


async def run_app_then_export_as_html(
    path: MarimoPath,
    include_code: bool,
    cli_args: SerializedCLIArgs,
    argv: list[str],
    *,
    asset_url: str | None = None,
) -> ExportResult:
    file_manager = load_notebook(path.absolute_name)

    # Inline the layout file, if it exists
    file_manager.app.inline_layout_file()

    config = get_default_config_manager(current_path=file_manager.path)
    resolved = config.get_config()
    display_config = resolved["display"]
    session_view, did_error = await run_app_until_completion(
        file_manager,
        cli_args,
        argv=argv,
    )
    # Export the session as HTML
    html, filename = Exporter().export_as_html(
        filename=file_manager.filename,
        app=file_manager.app,
        session_view=session_view,
        display_config=display_config,
        sharing_config=resolved.get("sharing"),
        request=ExportAsHTMLRequest(
            include_code=include_code,
            download=False,
            files=[],
            asset_url=asset_url,
        ),
    )
    return ExportResult(
        contents=html,
        download_filename=filename,
        did_error=did_error,
    )


def bundle_cache_export(notebook_path: MarimoPath, out_dir: Path) -> None:
    """Copy an executed session's cached blobs into `<out_dir>/public/cache/`.

    Reads the per-notebook export manifest the kernel wrote next to the blobs,
    and copies exactly those entries — where the browser store fetches them.
    No manifest (caching off, no caches, or a kernel killed before it flushed)
    means nothing to bundle: the export still works, the browser recomputes.
    """
    import json
    import shutil
    from pathlib import PurePosixPath

    manifest_file = _cache_export_manifest_path(notebook_path)
    cache_src = manifest_file.parent
    if not manifest_file.exists():
        echo("No caches to bundle.")
        return
    try:
        keys: list[str] = json.loads(manifest_file.read_text())
    except (OSError, ValueError) as e:
        LOGGER.warning("Failed to read cache export manifest: %s", e)
        return

    cache_dst = out_dir / "public" / "cache"
    copied = 0
    for key in keys:
        if not isinstance(key, str):
            LOGGER.warning("Skipping non-string cache manifest key: %r", key)
            continue
        # A stale/tampered manifest key could otherwise escape the cache dir.
        rel = PurePosixPath(key)
        if rel.is_absolute() or ".." in rel.parts:
            LOGGER.warning("Skipping unsafe cache manifest key: %r", key)
            continue
        src_file = cache_src / key
        if not src_file.is_file():
            continue
        try:
            dst_file = cache_dst / key
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst_file)
            copied += 1
        except OSError as e:
            LOGGER.warning("Failed to bundle cache file %s: %s", key, e)
    echo(f"Bundled {copied} cache files into {cache_dst}.")


def _cache_export_manifest_path(notebook_path: MarimoPath) -> Path:
    """Path of the export manifest for `notebook_path`.

    Derived identically to the executing kernel's (see `export_manifest_name`)
    so the exporter reads exactly the file the run wrote.
    """
    from marimo._save.stores.file import export_manifest_name
    from marimo._utils.paths import notebook_output_dir

    absolute = notebook_path.absolute_name
    cache_dir = notebook_output_dir(Path(absolute).parent) / "cache"
    return cache_dir / export_manifest_name(absolute)


async def run_app_then_export_as_wasm(
    path: MarimoPath,
    mode: Literal["edit", "run"],
    show_code: bool,
    cli_args: SerializedCLIArgs,
    argv: list[str],
    *,
    asset_url: str | None = None,
    cache_export_dir: Path | None = None,
) -> ExportResult:
    """Execute notebook and export as WASM HTML with embedded session.

    When `cache_export_dir` is set, the caches this run produced are bundled
    into `<cache_export_dir>/public/cache/` so the exported notebook ships
    them and skips recomputation in the browser.
    """
    from marimo._session.state.serialize import (
        serialize_notebook,
        serialize_session_view,
    )

    file_manager = load_notebook(path.absolute_name)
    file_manager.app.inline_layout_file()

    config = get_default_config_manager(current_path=file_manager.path)
    resolved = config.get_config()
    display_config = resolved["display"]

    from marimo._runtime.callbacks.cache import cache_cells_enabled

    # Caching is opt-in: bundle caches only when the notebook enables
    # `cache_cells`. Otherwise export runs fully live, so no cell's output
    # (console included) is served from a warm cache and skips execution.
    cache_dir = (
        cache_export_dir
        if cache_export_dir is not None and cache_cells_enabled(resolved)
        else None
    )

    if cache_dir is not None:
        # NB. drop a prior run's manifest so we never bundle a stale key set.
        _cache_export_manifest_path(path).unlink(missing_ok=True)

    session_view, did_error = await run_app_until_completion(
        file_manager,
        cli_args,
        argv=argv,
        cache_export=cache_dir is not None,
    )
    if cache_dir is not None:
        # NB. the run joined the kernel, which wrote the manifest on shutdown,
        # so it's on disk to read now.
        bundle_cache_export(path, cache_dir)

    session_snapshot = serialize_session_view(
        session_view,
        cell_ids=file_manager.app.cell_manager.cell_ids(),
        drop_virtual_file_outputs=True,
    )
    notebook_snapshot = serialize_notebook(
        session_view, file_manager.app.cell_manager
    )

    code = pin_pep723_dependencies_for_wasm(file_manager.app.to_py(), path)

    html, filename = Exporter().export_as_wasm(
        filename=file_manager.filename,
        app=file_manager.app,
        display_config=display_config,
        code=code,
        mode=mode,
        show_code=show_code,
        asset_url=asset_url,
        session_snapshot=session_snapshot,
        notebook_snapshot=notebook_snapshot,
        sharing_config=resolved.get("sharing"),
    )
    return ExportResult(
        contents=html,
        download_filename=filename,
        did_error=did_error,
    )


async def export_as_html_without_execution(
    path: MarimoPath,
    include_code: bool,
    *,
    asset_url: str | None = None,
) -> ExportResult:
    """Export a notebook to HTML without executing its cells."""
    from marimo._session.state.session_view import SessionView

    file_manager = load_notebook(path.absolute_name)

    # Inline the layout file, if it exists.
    file_manager.app.inline_layout_file()

    view = SessionView()
    for cell_data in file_manager.app.cell_manager.cell_data():
        view.last_executed_code[cell_data.cell_id] = cell_data.code

    config = get_default_config_manager(current_path=file_manager.path)
    display_config = config.get_config()["display"]

    html, filename = Exporter().export_as_html(
        filename=file_manager.filename,
        app=file_manager.app,
        session_view=view,
        display_config=display_config,
        request=ExportAsHTMLRequest(
            include_code=include_code,
            download=False,
            files=[],
            asset_url=asset_url,
        ),
    )
    return ExportResult(
        contents=html,
        download_filename=filename,
        did_error=False,
    )


async def run_app_then_export_as_reactive_html(
    path: MarimoPath,
    include_code: bool,
) -> ExportResult:
    from marimo._islands._island_generator import MarimoIslandGenerator

    generator = MarimoIslandGenerator.from_file(
        path.absolute_name, display_code=include_code
    )
    await generator.build()
    html = generator.render_html()
    basename = os.path.basename(path.absolute_name)
    filename = f"{os.path.splitext(basename)[0]}.html"
    return ExportResult(
        contents=html,
        download_filename=filename,
        did_error=False,
    )


async def run_app_until_completion(
    file_manager: AppFileManager,
    cli_args: SerializedCLIArgs,
    argv: list[str] | None,
    quiet: bool = False,
    persist_session: bool = True,
    cache_export: bool = False,
) -> tuple[SessionView, bool]:
    from marimo._session.consumer import SessionConsumer
    from marimo._session.events import SessionEventBus
    from marimo._session.session import SessionImpl

    instantiated_event = asyncio.Event()

    class RunUntilCompletionSessionConsumer(SessionConsumer):
        def __init__(self) -> None:
            self.did_error = False

        @property
        def consumer_id(self) -> ConsumerId:
            return ConsumerId("default")

        def notify(self, notification: KernelMessage) -> None:
            data = deserialize_kernel_message(notification)
            # Print errors to stderr (unless quiet mode)
            if isinstance(data, CellNotification):
                output = data.output
                console_output = data.console
                if output and output.channel == CellChannel.MARIMO_ERROR:
                    errors = cast(list[Error], output.data)
                    for err in errors:
                        # Not all errors are fatal
                        if is_unexpected_error(err):
                            if not quiet:
                                echo(
                                    f"{err.__class__.__name__}: {err.describe()}",
                                    file=sys.stderr,
                                )
                            self.did_error = True

                if console_output and not quiet:
                    console_as_list: list[CellOutput] = (
                        console_output
                        if isinstance(console_output, list)
                        else [console_output]
                    )
                    try:
                        for line in console_as_list:
                            # We print to stderr to not interfere with the
                            # piped output
                            mimetype = line.mimetype
                            if mimetype == "text/plain":
                                echo(line.data, file=sys.stderr, nl=False)
                    except Exception:
                        LOGGER.warning("Error printing console output")

            if isinstance(data, CompletedRunNotification):
                instantiated_event.set()

        def on_attach(
            self, session: Session, event_bus: SessionEventBus
        ) -> None:
            del session
            del event_bus

        def on_detach(self) -> None:
            return None

        def connection_state(self) -> ConnectionState:
            return ConnectionState.OPEN

    runtime_overrides: dict[str, Any] = {
        "on_cell_change": "autorun",
        "auto_instantiate": True,
        "auto_reload": "off",
        "watcher_on_save": "lazy",
    }
    if cache_export:
        # Cache every executed cell so the export can bundle the results;
        # this same flag gates the kernel's export-manifest dump on teardown.
        runtime_overrides["cache_cells"] = True
    config_manager = get_default_config_manager(
        current_path=file_manager.path
    ).with_overrides(
        # We cast because we don't want to override the other config values.
        {"runtime": cast(RuntimeConfig, runtime_overrides)}
    )

    # Create a session
    session_consumer = RunUntilCompletionSessionConsumer()
    session = SessionImpl.create(
        # Any initialization ID will do
        initialization_id="_any_",
        session_consumer=session_consumer,
        # Run in EDIT mode so that console outputs are captured
        mode=SessionMode.EDIT,
        app_metadata=AppMetadata(
            query_params={},
            filename=file_manager.path,
            cli_args=cli_args,
            argv=argv,
            app_config=file_manager.app.config,
            docstring=extract_docstring_from_header(
                file_manager.app._app._header
            ),
        ),
        app_file_manager=file_manager,
        config_manager=config_manager,
        virtual_file_storage=None,
        redirect_console_to_browser=False,
        ttl_seconds=None,
        auto_instantiate=True,
    )

    # Run the notebook to completion once
    session.instantiate(
        InstantiateNotebookRequest(object_ids=[], values=[]),
        http_request=None,
    )
    await instantiated_event.wait()
    # Hack: yield to give the session view a chance to process the incoming
    # console operations.
    await asyncio.sleep(0.1)

    if persist_session:
        from marimo._server.export._session_cache import (
            persist_session_view_to_cache,
        )

        try:
            persist_session_view_to_cache(
                view=session.session_view,
                notebook_path=file_manager.path,
                cell_ids=file_manager.app.cell_manager.cell_ids(),
            )
        except Exception as e:
            LOGGER.warning(
                "Failed to persist session snapshot for %s: %s",
                file_manager.path,
                e,
            )

    # Stop distributor, terminate kernel process, etc -- all information is
    # captured by the session view. When exporting caches, close gracefully so
    # the kernel flushes the cache manifest that bundle_cache_export reads next.
    session.close(graceful=cache_export)

    return session.session_view, session_consumer.did_error


def _with_filename(
    ir: NotebookSerialization, filename: str
) -> NotebookSerialization:
    return replace(ir, filename=filename)
