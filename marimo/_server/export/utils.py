# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
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
        initialization_id="_any_",
        session_consumer=NoopSessionConsumer(),
        mode=SessionMode.RUN,
        app_metadata=AppMetadata(
            query_params={},
            filename=file_manager.path,
            cli_args=cli_args,
        ),
        app_file_manager=file_manager,
        user_config_manager=config,
        virtual_files_supported=False,
    )

    # Run the app to completion once
    session.instantiate(InstantiateRequest(object_ids=[], values=[]))
    await instantiated_event.wait()

    return session
