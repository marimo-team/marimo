# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Literal, Optional, cast

from marimo import _loggers
from marimo._ast.app import InternalApp
from marimo._ast.load import load_app
from marimo._cli.print import echo
from marimo._config.config import RuntimeConfig
from marimo._config.manager import (
    get_default_config_manager,
)
from marimo._convert.converters import MarimoConvert
from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.errors import Error, is_unexpected_error
from marimo._messaging.notification import (
    CellNotification,
    CompletedRunNotification,
)
from marimo._messaging.serde import deserialize_kernel_message
from marimo._messaging.types import KernelMessage
from marimo._output.hypertext import patch_html_for_non_interactive_output
from marimo._runtime.commands import AppMetadata, SerializedCLIArgs
from marimo._schemas.serialization import NotebookSerialization
from marimo._server.export.exporter import Exporter
from marimo._server.export.utils import get_download_filename
from marimo._server.file_router import AppFileRouter
from marimo._server.models.export import ExportAsHTMLRequest
from marimo._server.models.models import InstantiateNotebookRequest
from marimo._session.model import ConnectionState, SessionMode
from marimo._session.notebook import AppFileManager
from marimo._types.ids import ConsumerId
from marimo._utils.marimo_path import MarimoPath

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from marimo._session.state.session_view import SessionView
    from marimo._session.types import Session


@dataclass
class ExportResult:
    contents: str
    download_filename: str
    did_error: bool


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
    return ExportResult(
        contents=MarimoConvert.from_ir(ir).to_markdown(),
        download_filename=get_download_filename(path.short_name, "md"),
        did_error=False,
    )


def export_as_ipynb(
    path: MarimoPath, sort_mode: Literal["top-down", "topological"]
) -> ExportResult:
    app = load_app(path.absolute_name)
    if app is None:
        return ExportResult(
            contents="",
            download_filename=get_download_filename(path.short_name, "ipynb"),
            did_error=True,
        )

    result = Exporter().export_as_ipynb(
        app=InternalApp(app),
        sort_mode=sort_mode,
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
    asset_url: Optional[str] = None,
) -> ExportResult:
    _app = load_app(path.absolute_name)
    if _app is None:
        return ExportResult(
            contents="",
            download_filename=get_download_filename(
                path.short_name, "wasm.html"
            ),
            did_error=True,
        )
    app = InternalApp(_app)
    # Inline the layout file, if it exists
    app.inline_layout_file()
    config = get_default_config_manager(current_path=path.absolute_name)

    result = Exporter().export_as_wasm(
        filename=path.short_name,
        app=app,
        display_config=config.get_config()["display"],
        mode=mode,
        code=app.to_py(),
        asset_url=asset_url,
        show_code=show_code,
    )
    return ExportResult(
        contents=result[0],
        download_filename=result[1],
        did_error=False,
    )


async def run_app_then_export_as_ipynb(
    filepath: MarimoPath,
    sort_mode: Literal["top-down", "topological"],
    cli_args: SerializedCLIArgs,
    argv: list[str] | None,
) -> ExportResult:
    file_router = AppFileRouter.from_filename(filepath)
    file_key = file_router.get_unique_file_key()
    assert file_key is not None
    file_manager = file_router.get_file_manager(file_key)

    with patch_html_for_non_interactive_output():
        (session_view, did_error) = await run_app_until_completion(
            file_manager,
            cli_args,
            argv,
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


async def run_app_then_export_as_html(
    path: MarimoPath,
    include_code: bool,
    cli_args: SerializedCLIArgs,
    argv: list[str],
) -> ExportResult:
    # Create a file router and file manager
    file_router = AppFileRouter.from_filename(path)
    file_key = file_router.get_unique_file_key()
    assert file_key is not None
    file_manager = file_router.get_file_manager(file_key)

    # Inline the layout file, if it exists
    file_manager.app.inline_layout_file()

    config = get_default_config_manager(current_path=file_manager.path)
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
        display_config=config.get_config()["display"],
        request=ExportAsHTMLRequest(
            include_code=include_code,
            download=False,
            files=[],
        ),
    )
    return ExportResult(
        contents=html,
        download_filename=filename,
        did_error=did_error,
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
            # Print errors to stderr
            if isinstance(data, CellNotification):
                output = data.output
                console_output = data.console
                if output and output.channel == CellChannel.MARIMO_ERROR:
                    errors = cast(list[Error], output.data)
                    for err in errors:
                        # Not all errors are fatal
                        if is_unexpected_error(err):
                            echo(
                                f"{err.__class__.__name__}: {err.describe()}",
                                file=sys.stderr,
                            )
                            self.did_error = True

                if console_output:
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

    config_manager = get_default_config_manager(
        current_path=file_manager.path
    ).with_overrides(
        {
            "runtime": cast(
                RuntimeConfig,
                {
                    "on_cell_change": "autorun",
                    "auto_instantiate": True,
                    "auto_reload": "off",
                    "watcher_on_save": "lazy",
                    # We cast because we don't want to override the other
                    # config values
                },
            ),
        }
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
        ),
        app_file_manager=file_manager,
        config_manager=config_manager,
        virtual_files_supported=False,
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
    # Process console messages
    #
    # TODO(akshayka): A timing issue with the console output worker
    # might still exist; the better thing to do would be to flush
    # the worker, then ask it to quit and join on it. If we have an
    # issue with some outputs being missed, that's what we should do.
    session.flush_messages()
    # Hack: yield to give the session view a chance to process the incoming
    # console operations.
    await asyncio.sleep(0.1)
    # Stop distributor, terminate kernel process, etc -- all information is
    # captured by the session view.
    session.close()

    return session.session_view, session_consumer.did_error


def _with_filename(
    ir: NotebookSerialization, filename: str
) -> NotebookSerialization:
    return replace(ir, filename=filename)
