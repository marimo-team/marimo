# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from typing import Any, Callable, Literal, cast

from marimo._cli.print import echo
from marimo._config.manager import (
    get_default_config_manager,
)
from marimo._messaging.cell_output import CellChannel
from marimo._messaging.errors import Error
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
from marimo._utils.marimo_path import MarimoPath
from marimo._utils.parse_dataclass import parse_raw


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
) -> ExportResult:
    file_router = AppFileRouter.from_filename(path)
    file_key = file_router.get_unique_file_key()
    assert file_key is not None
    file_manager = file_router.get_file_manager(file_key)

    result = Exporter().export_as_md(file_manager)
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


async def run_app_then_export_as_ipynb(
    path: MarimoPath,
    sort_mode: Literal["top-down", "topological"],
    cli_args: SerializedCLIArgs,
) -> ExportResult:
    file_router = AppFileRouter.from_filename(path)
    file_key = file_router.get_unique_file_key()
    assert file_key is not None
    file_manager = file_router.get_file_manager(file_key)

    with patch_html_for_non_interactive_output():
        (session_view, did_error) = await run_app_until_completion(
            file_manager, cli_args
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
) -> ExportResult:
    # Create a file router and file manager
    file_router = AppFileRouter.from_filename(path)
    file_key = file_router.get_unique_file_key()
    assert file_key is not None
    file_manager = file_router.get_file_manager(file_key)

    config = get_default_config_manager(current_path=file_manager.path)
    session_view, did_error = await run_app_until_completion(
        file_manager, cli_args
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
    import os

    from marimo._islands.island_generator import MarimoIslandGenerator

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
) -> tuple[SessionView, bool]:
    from marimo._server.sessions import Session

    instantiated_event = asyncio.Event()

    class DefaultSessionConsumer(SessionConsumer):
        def __init__(self) -> None:
            self.did_error = False
            super().__init__(consumer_id="default")

        def on_start(
            self,
        ) -> Callable[[KernelMessage], None]:
            def listener(message: KernelMessage) -> None:
                # Print errors to stderr
                if message[0] == "cell-op":
                    op_data = message[1]
                    if (
                        op_data.get("output")
                        and op_data["output"]["channel"]
                        == CellChannel.MARIMO_ERROR
                    ):
                        errors = cast(list[Any], op_data["output"]["data"])

                        @dataclass
                        class Container:
                            error: Error

                        for err in errors:
                            parsed = parse_raw({"error": err}, Container)
                            echo(
                                f"{parsed.error.__class__.__name__}: {parsed.error.describe()}",
                                file=sys.stderr,
                            )
                        self.did_error = True
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
            "runtime": {
                "on_cell_change": "autorun",
                "auto_instantiate": True,
                "auto_reload": "off",
            }
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
        ),
        app_file_manager=file_manager,
        user_config_manager=config_manager,
        virtual_files_supported=False,
        redirect_console_to_browser=False,
    )

    # Run the notebook to completion once
    session.instantiate(InstantiateRequest(object_ids=[], values=[]))
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
