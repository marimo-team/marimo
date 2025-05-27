# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Literal, Optional, Union, cast

from marimo import _loggers
from marimo._cli.print import echo
from marimo._config.config import RuntimeConfig
from marimo._config.manager import (
    get_default_config_manager,
)
from marimo._messaging.cell_output import CellChannel
from marimo._messaging.errors import Error, is_unexpected_error
from marimo._messaging.ops import MessageOperation
from marimo._messaging.types import KernelMessage
from marimo._output.hypertext import patch_html_for_non_interactive_output
from marimo._runtime.requests import AppMetadata, SerializedCLIArgs
from marimo._server.export.exporter import Exporter
from marimo._server.file_manager import AppFileManager
from marimo._server.file_router import AppFileRouter
from marimo._server.model import ConnectionState, SessionConsumer, SessionMode
from marimo._server.models.export import ExportAsHTMLRequest
from marimo._server.models.models import InstantiateRequest
from marimo._server.session.session_view import SessionView
from marimo._types.ids import ConsumerId
from marimo._utils.marimo_path import MarimoPath
from marimo._utils.parse_dataclass import parse_raw

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class ExportResult:
    contents: str
    download_filename: str
    did_error: bool


def export_as_script(
    path: MarimoPath,
) -> ExportResult:
    file_router = AppFileRouter.from_filename(path)
    file_key = file_router.get_unique_file_key()
    assert file_key is not None
    file_manager = file_router.get_file_manager(file_key)

    result = Exporter().export_as_script(file_manager)
    return ExportResult(
        contents=result[0],
        download_filename=result[1],
        did_error=False,
    )


def export_as_md(
    path: MarimoPath,
    new_filename: Optional[Path] = None,
) -> ExportResult:
    file_router = AppFileRouter.from_filename(path)
    file_key = file_router.get_unique_file_key()
    assert file_key is not None
    file_manager = file_router.get_file_manager(file_key)

    # py -> md
    if new_filename:
        file_manager.filename = str(new_filename)
    result = Exporter().export_as_md(file_manager, previous=path.path)
    return ExportResult(
        contents=result[0],
        download_filename=result[1],
        did_error=False,
    )


def export_as_ipynb(
    path: MarimoPath,
    sort_mode: Literal["top-down", "topological"],
) -> ExportResult:
    file_router = AppFileRouter.from_filename(path)
    file_key = file_router.get_unique_file_key()
    assert file_key is not None
    file_manager = file_router.get_file_manager(file_key)

    result = Exporter().export_as_ipynb(file_manager, sort_mode=sort_mode)
    return ExportResult(
        contents=result[0],
        download_filename=result[1],
        did_error=False,
    )


def export_as_wasm(
    path: MarimoPath,
    mode: Literal["edit", "run"],
    show_code: bool,
    asset_url: Optional[str] = None,
) -> ExportResult:
    file_router = AppFileRouter.from_filename(path)
    file_key = file_router.get_unique_file_key()
    assert file_key is not None
    file_manager = file_router.get_file_manager(file_key)
    # Inline the layout file, if it exists
    file_manager.app.inline_layout_file()
    config = get_default_config_manager(current_path=file_manager.path)

    result = Exporter().export_as_wasm(
        file_manager=file_manager,
        display_config=config.get_config()["display"],
        mode=mode,
        code=file_manager.to_code(),
        asset_url=asset_url,
        show_code=show_code,
    )
    return ExportResult(
        contents=result[0],
        download_filename=result[1],
        did_error=False,
    )


async def run_app_then_export_as_ipynb(
    path_or_file_manager: Union[MarimoPath, AppFileManager],
    sort_mode: Literal["top-down", "topological"],
    cli_args: SerializedCLIArgs,
    argv: list[str] | None,
) -> ExportResult:
    if isinstance(path_or_file_manager, AppFileManager):
        file_manager = path_or_file_manager
    else:
        file_router = AppFileRouter.from_filename(path_or_file_manager)
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
        file_manager, sort_mode=sort_mode, session_view=session_view
    )
    return ExportResult(
        contents=result[0],
        download_filename=result[1],
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
        file_manager=file_manager,
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
    from marimo._server.sessions import Session

    instantiated_event = asyncio.Event()

    class DefaultSessionConsumer(SessionConsumer):
        def __init__(self) -> None:
            self.did_error = False
            super().__init__(consumer_id=ConsumerId("default"))

        def on_start(
            self,
        ) -> Callable[[KernelMessage], None]:
            def listener(message: KernelMessage) -> None:
                # Print errors to stderr
                if message[0] == "cell-op":
                    op_data = message[1]
                    output = op_data.get("output")
                    console_output = op_data.get("console")
                    if (
                        output
                        and output["channel"] == CellChannel.MARIMO_ERROR
                    ):
                        errors = cast(list[Any], output["data"])

                        @dataclass
                        class Container:
                            error: Error

                        for err in errors:
                            parsed = parse_raw({"error": err}, Container)
                            # Not all errors are fatal
                            if is_unexpected_error(parsed.error):
                                echo(
                                    f"{parsed.error.__class__.__name__}: {parsed.error.describe()}",
                                    file=sys.stderr,
                                )
                                self.did_error = True

                    if console_output:
                        console_as_list: list[dict[str, Any]] = (
                            console_output
                            if isinstance(console_output, list)
                            else [console_output]
                        )
                        try:
                            for line in console_as_list:
                                # We print to stderr to not interfere with the
                                # piped output
                                mimetype = line.get("mimetype")
                                if mimetype == "text/plain":
                                    echo(
                                        line["data"], file=sys.stderr, nl=False
                                    )
                        except Exception:
                            LOGGER.warning("Error printing console output")
                            pass

                if message[0] == "completed-run":
                    instantiated_event.set()

            return listener

        def on_stop(self) -> None:
            pass

        def write_operation(self, op: MessageOperation) -> None:
            pass

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
    session_consumer = DefaultSessionConsumer()
    session = Session.create(
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
    )

    # Run the notebook to completion once
    session.instantiate(
        InstantiateRequest(object_ids=[], values=[]),
        http_request=None,
    )
    await instantiated_event.wait()
    # Process console messages
    #
    # TODO(akshayka): A timing issue with the console output worker
    # might still exist; the better thing to do would be to flush
    # the worker, then ask it to quit and join on it. If we have an
    # issue with some outputs being missed, that's what we should do.
    session.message_distributor.flush()
    # Hack: yield to give the session view a chance to process the incoming
    # console operations.
    await asyncio.sleep(0.1)
    # Stop distributor, terminate kernel process, etc -- all information is
    # captured by the session view.
    session.close()
    return session.session_view, session_consumer.did_error
