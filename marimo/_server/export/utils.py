# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from multiprocessing import Process
from typing import Callable

from marimo._config.manager import UserConfigManager
from marimo._messaging.ops import MessageOperation
from marimo._messaging.types import KernelMessage
from marimo._runtime.requests import AppMetadata, SerializedCLIArgs
from marimo._server.export.exporter import Exporter
from marimo._server.file_manager import AppFileManager
from marimo._server.file_router import AppFileRouter
from marimo._server.model import ConnectionState, SessionConsumer, SessionMode
from marimo._server.models.export import ExportAsHTMLRequest
from marimo._server.models.models import InstantiateRequest
from marimo._server.sessions import Session


def export_as_script(
    filename: str,
) -> tuple[str, str]:
    file_router = AppFileRouter.from_filename(filename)
    file_key = file_router.get_unique_file_key()
    assert file_key is not None
    file_manager = file_router.get_file_manager(file_key)

    return Exporter().export_as_script(file_manager)


async def run_app_then_export_as_html(
    filename: str,
    include_code: bool,
    cli_args: SerializedCLIArgs,
) -> tuple[str, str]:
    # Create a file router and file manager
    file_router = AppFileRouter.from_filename(filename)
    file_key = file_router.get_unique_file_key()
    assert file_key is not None
    file_manager = file_router.get_file_manager(file_key)

    config = UserConfigManager()
    session = await run_app_until_completion(file_manager, cli_args)
    # Export the session as HTML
    html, filename = Exporter().export_as_html(
        file_manager=session.app_file_manager,
        session_view=session.session_view,
        display_config=config.get_config()["display"],
        request=ExportAsHTMLRequest(
            include_code=include_code,
            download=False,
            files=[],
        ),
    )
    return html, filename


async def run_app_until_completion(
    file_manager: AppFileManager,
    cli_args: SerializedCLIArgs,
) -> Session:
    instantiated_event = asyncio.Event()

    # Create a no-op session consumer
    class NoopSessionConsumer(SessionConsumer):
        def on_start(
            self,
            check_alive: Callable[[], None],
        ) -> Callable[[KernelMessage], None]:
            del check_alive

            def listener(message: KernelMessage) -> None:
                if message[0] == "completed-run":
                    instantiated_event.set()

            return listener

        def on_stop(self) -> None:
            pass

        async def write_operation(self, op: MessageOperation) -> None:
            pass

        def connection_state(self) -> ConnectionState:
            return ConnectionState.OPEN

    config = UserConfigManager()

    # Create a session
    session = Session.create(
        # Any initialization ID will do
        initialization_id="_any_",
        session_consumer=NoopSessionConsumer(),
        # Run in EDIT mode so that console outputs are captured
        mode=SessionMode.EDIT,
        app_metadata=AppMetadata(
            query_params={},
            filename=file_manager.path,
            cli_args=cli_args,
        ),
        app_file_manager=file_manager,
        user_config_manager=config,
        virtual_files_supported=False,
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

    # Terminate the running kernel task -- all information is captured by
    # the session view.
    kernel_task = session.kernel_manager.kernel_task
    if kernel_task is not None and isinstance(kernel_task, Process):
        kernel_task.terminate()
    return session
