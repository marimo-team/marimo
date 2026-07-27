# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from marimo import _loggers
from marimo._ast.app import InternalApp
from marimo._ast.errors import CycleError, MultipleDefinitionError
from marimo._ast.load import load_app
from marimo._config.config import RuntimeConfig
from marimo._config.manager import (
    get_default_config_manager,
)
from marimo._convert.common.filename import get_download_filename
from marimo._convert.converters import MarimoConvert
from marimo._export._status import emit_pdf_export_status
from marimo._export.exporter import (
    Exporter,
    export_markdown as render_markdown,
    export_script as render_script,
    render_pdf,
)
from marimo._export.requests import (
    CacheBundleRequest,
    ExportResult,
    HTMLExportRequest,
    HTMLFileExportRequest,
    IPYNBExportRequest,
    IPYNBFileExportRequest,
    MarkdownExportRequest,
    MarkdownFileExportRequest,
    PDFExportRequest,
    PDFFileExportRequest,
    PDFRasterizationRequest,
    ReactiveHTMLFileExportRequest,
    RunNotebookRequest,
    ScriptExportRequest,
    ScriptFileExportRequest,
    WASMExportRequest,
    WASMFileExportRequest,
)
from marimo._export.serialization import serialize_notebook_snapshot
from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.errors import Error, is_unexpected_error
from marimo._messaging.notification import (
    CellNotification,
    CompletedRunNotification,
)
from marimo._messaging.serde import deserialize_kernel_message
from marimo._messaging.types import KernelMessage
from marimo._output.hypertext import patch_html_for_non_interactive_output
from marimo._runtime.commands import AppMetadata
from marimo._runtime.patches import extract_docstring_from_header
from marimo._schemas.export_options import (
    IPYNBExportOptions,
)
from marimo._schemas.serialization import NotebookSerialization
from marimo._session.model import ConnectionState, SessionMode
from marimo._session.notebook import load_notebook
from marimo._session.requests import InstantiateNotebookRequest
from marimo._types.ids import ConsumerId
from marimo._utils.inline_script_metadata import (
    pin_pep723_dependencies_for_wasm,
)
from marimo._utils.marimo_path import MarimoPath

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from collections.abc import Mapping

    from marimo._session.state.session_view import SessionView
    from marimo._session.types import Session
    from marimo._types.ids import CellId_t


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


def export_script(request: ScriptFileExportRequest) -> ExportResult:
    return render_script(
        ScriptExportRequest(
            notebook=_as_ir(request.path),
        )
    )


def export_markdown(request: MarkdownFileExportRequest) -> ExportResult:
    return render_markdown(
        MarkdownExportRequest(
            notebook=_as_ir(request.path),
            options=request.options,
        )
    )


async def export_ipynb(
    request: IPYNBFileExportRequest,
) -> ExportResult:
    if request.execution is None:
        app = load_app(request.path.absolute_name)
        if app is None:
            return ExportResult(
                contents=b"",
                download_filename=get_download_filename(
                    request.path.short_name, "ipynb"
                ),
                did_error=True,
            )

        # Try the requested sort mode, fall back to top-down if cycles exist
        internal_app = InternalApp(app)
        options = request.options
        if options.sort_mode == "topological":
            try:
                # Check if graph can be accessed (raises CycleError/MultipleDefinitionError)
                _ = internal_app.graph
            except (CycleError, MultipleDefinitionError):
                stderr = request.stderr or sys.stderr
                stderr.write(
                    "Warning: Notebook has errors, "
                    "using top-down order instead of topological.\n"
                )
                options = IPYNBExportOptions(sort_mode="top-down")

        result = Exporter().export_as_ipynb(
            IPYNBExportRequest(
                app=internal_app,
                options=options,
            )
        )
        return ExportResult(
            contents=result,
            download_filename=get_download_filename(
                request.path.short_name, "ipynb"
            ),
            did_error=False,
        )

    file_manager = load_notebook(request.path.absolute_name)
    with patch_html_for_non_interactive_output():
        # Use quiet=True to suppress runtime stdout/stderr since outputs
        # are captured in the session_view and will be included in the ipynb
        session_view, did_error = await run_notebook(
            RunNotebookRequest(
                file_manager=file_manager,
                options=replace(request.execution, quiet=True),
            )
        )

    result = Exporter().export_as_ipynb(
        IPYNBExportRequest(
            app=file_manager.app,
            options=request.options,
            session_view=session_view,
        )
    )
    return ExportResult(
        contents=result,
        download_filename=get_download_filename(
            request.path.short_name, "ipynb"
        ),
        did_error=did_error,
    )


async def export_wasm(
    request: WASMFileExportRequest,
) -> ExportResult:
    if request.execution is None:
        _app = load_app(request.path.absolute_name)
        if _app is None:
            return ExportResult(
                contents=b"",
                download_filename=get_download_filename(
                    request.path.short_name, "wasm.html"
                ),
                did_error=True,
            )
        app = InternalApp(_app)
        # Inline the layout file, if it exists
        app.inline_layout_file()
        config = get_default_config_manager(
            current_path=request.path.absolute_name
        )
        resolved = config.get_config()

        code = app.to_py()
        if request.code_transform is not None:
            code = request.code_transform(code)

        result = Exporter().export_as_wasm(
            WASMExportRequest(
                filename=request.path.short_name,
                app_config=app.config,
                display_config=resolved["display"],
                code=code,
                options=request.options,
                sharing_config=resolved.get("sharing"),
            )
        )
        return ExportResult(
            contents=result[0],
            download_filename=result[1],
            did_error=False,
        )

    return await _export_wasm_with_execution(request)


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


async def export_pdf(
    request: PDFFileExportRequest,
) -> ExportResult | None:
    file_manager = load_notebook(request.path.absolute_name)

    session_view: SessionView | None = None
    png_fallbacks: Mapping[CellId_t, str] | None = None
    did_error = False

    if request.execution is not None:
        emit_pdf_export_status(
            request.status_callback,
            phase="execute",
            message="executing notebook...",
        )
        with patch_html_for_non_interactive_output():
            # Using quiet=True to suppress runtime stdout/stderr since outputs
            # are captured in the session_view and will be included in the PDF
            session_view, did_error = await run_notebook(
                RunNotebookRequest(
                    file_manager=file_manager,
                    options=replace(request.execution, quiet=True),
                )
            )
        emit_pdf_export_status(
            request.status_callback,
            phase="execute_complete",
            message="notebook execution finished.",
        )

        if (
            session_view is not None
            and request.rasterization is not None
            and request.rasterization.enabled
        ):
            from marimo._export._pdf_raster import (
                collect_pdf_png_fallbacks,
            )

            png_fallbacks = await collect_pdf_png_fallbacks(
                PDFRasterizationRequest(
                    app=file_manager.app,
                    session_view=session_view,
                    filename=request.path.short_name,
                    filepath=request.path.absolute_name,
                    options=request.rasterization,
                    live_page_url=request.live_page_url,
                    status_callback=request.status_callback,
                )
            )
    emit_pdf_export_status(
        request.status_callback,
        phase="prepare",
        message="serializing notebook for PDF rendering...",
    )
    render_request = PDFExportRequest(
        app=file_manager.app,
        session_view=session_view,
        png_fallbacks=png_fallbacks,
        options=request.options,
        status_callback=request.status_callback,
    )
    pdf_data = await render_pdf(render_request)
    if pdf_data is not None:
        emit_pdf_export_status(
            request.status_callback,
            phase="complete",
            message="done.",
        )
    else:
        return None

    return ExportResult(
        contents=pdf_data,
        download_filename=get_download_filename(
            request.path.short_name, "pdf"
        ),
        did_error=did_error,
    )


async def export_html(
    request: HTMLFileExportRequest,
) -> ExportResult:
    file_manager = load_notebook(request.path.absolute_name)

    # Inline the layout file, if it exists
    file_manager.app.inline_layout_file()

    if request.execution is None:
        from marimo._session.state.session_view import SessionView

        session_view = SessionView()
        for cell_data in file_manager.app.cell_manager.cell_data():
            session_view.last_executed_code[cell_data.cell_id] = cell_data.code
        did_error = False
    else:
        session_view, did_error = await run_notebook(
            RunNotebookRequest(
                file_manager=file_manager,
                options=request.execution,
            )
        )

    config = get_default_config_manager(current_path=file_manager.path)
    resolved = config.get_config()
    display_config = resolved["display"]
    # Export the session as HTML
    html, filename = Exporter().export_as_html(
        HTMLExportRequest(
            filename=file_manager.filename,
            app_code=file_manager.app.to_py(),
            app_config=file_manager.app.config,
            snapshot=serialize_notebook_snapshot(
                file_manager.app,
                session_view,
                drop_virtual_file_outputs=False,
                include_model_notifications=True,
            ),
            display_config=display_config,
            options=request.options,
            sharing_config=(
                resolved.get("sharing")
                if request.execution is not None
                else None
            ),
        )
    )
    return ExportResult(
        contents=html,
        download_filename=filename,
        did_error=did_error,
    )


def bundle_cache_export(request: CacheBundleRequest) -> None:
    """Copy an executed session's cached blobs into `<out_dir>/public/cache/`.

    Reads the per-notebook export manifest the kernel wrote next to the blobs,
    and copies exactly those entries — where the browser store fetches them.
    No manifest (caching off, no caches, or a kernel killed before it flushed)
    means nothing to bundle: the export still works, the browser recomputes.
    """
    import json
    import shutil
    from pathlib import PurePosixPath

    manifest_file = _cache_export_manifest_path(request.notebook_path)
    cache_src = manifest_file.parent
    stdout = request.stdout or sys.stdout
    if not manifest_file.exists():
        stdout.write("No caches to bundle.\n")
        return
    try:
        keys: list[str] = json.loads(manifest_file.read_text())
    except (OSError, ValueError) as e:
        LOGGER.warning("Failed to read cache export manifest: %s", e)
        return

    cache_dst = request.output_directory / "public" / "cache"
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
    stdout.write(f"Bundled {copied} cache files into {cache_dst}.\n")


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


async def _export_wasm_with_execution(
    request: WASMFileExportRequest,
) -> ExportResult:
    """Execute notebook and export as WASM HTML with embedded session.

    When `cache_export_dir` is set, the caches this run produced are bundled
    into `<cache_export_dir>/public/cache/` so the exported notebook ships
    them and skips recomputation in the browser.
    """
    if request.execution is None:
        raise ValueError("Execution options are required.")

    file_manager = load_notebook(request.path.absolute_name)
    file_manager.app.inline_layout_file()

    config = get_default_config_manager(current_path=file_manager.path)
    resolved = config.get_config()
    display_config = resolved["display"]

    from marimo._runtime.callbacks.cache import cache_cells_enabled

    # Caching is opt-in: bundle caches only when the notebook enables
    # `cache_cells`. Otherwise export runs fully live, so no cell's output
    # (console included) is served from a warm cache and skips execution.
    cache_dir = (
        request.cache_export_dir
        if request.cache_export_dir is not None
        and cache_cells_enabled(resolved)
        else None
    )

    if cache_dir is not None:
        # NB. drop a prior run's manifest so we never bundle a stale key set.
        _cache_export_manifest_path(request.path).unlink(missing_ok=True)

    session_view, did_error = await run_notebook(
        RunNotebookRequest(
            file_manager=file_manager,
            options=replace(
                request.execution,
                cache_export=cache_dir is not None,
            ),
        )
    )
    if cache_dir is not None:
        # NB. the run joined the kernel, which wrote the manifest on shutdown,
        # so it's on disk to read now.
        bundle_cache_export(
            CacheBundleRequest(
                notebook_path=request.path,
                output_directory=cache_dir,
                stdout=request.stdout,
            )
        )

    snapshot = serialize_notebook_snapshot(
        file_manager.app,
        session_view,
        drop_virtual_file_outputs=True,
    )

    code = pin_pep723_dependencies_for_wasm(
        file_manager.app.to_py(), request.path
    )
    if request.code_transform is not None:
        code = request.code_transform(code)

    html, filename = Exporter().export_as_wasm(
        WASMExportRequest(
            filename=file_manager.filename,
            app_config=file_manager.app.config,
            display_config=display_config,
            code=code,
            options=request.options,
            session_snapshot=snapshot.session,
            notebook_snapshot=snapshot.notebook,
            sharing_config=resolved.get("sharing"),
        )
    )
    return ExportResult(
        contents=html,
        download_filename=filename,
        did_error=did_error,
    )


async def export_reactive_html(
    request: ReactiveHTMLFileExportRequest,
) -> ExportResult:
    from marimo._islands._island_generator import MarimoIslandGenerator

    generator = MarimoIslandGenerator.from_file(
        request.path.absolute_name,
        display_code=request.include_code,
    )
    await generator.build()
    html = generator.render_html()
    basename = os.path.basename(request.path.absolute_name)
    filename = f"{os.path.splitext(basename)[0]}.html"
    return ExportResult(
        contents=html,
        download_filename=filename,
        did_error=False,
    )


async def run_notebook(
    request: RunNotebookRequest,
) -> tuple[SessionView, bool]:
    from marimo._session.consumer import SessionConsumer
    from marimo._session.events import SessionEventBus
    from marimo._session.session import SessionImpl

    file_manager = request.file_manager
    options = request.options
    stderr = options.stderr or sys.stderr
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
                            if not options.quiet:
                                stderr.write(
                                    f"{err.__class__.__name__}: "
                                    f"{err.describe()}\n"
                                )
                            self.did_error = True

                if console_output and not options.quiet:
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
                                stderr.write(str(line.data))
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
    if options.cache_export:
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
            cli_args=options.cli_args,
            argv=options.argv,
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

    if options.persist_session:
        from marimo._export._session_cache import (
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
    session.close(graceful=options.cache_export)

    return session.session_view, session_consumer.did_error


def _with_filename(
    ir: NotebookSerialization, filename: str
) -> NotebookSerialization:
    return replace(ir, filename=filename)
