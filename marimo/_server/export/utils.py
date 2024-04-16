from __future__ import annotations

from typing import Callable

from marimo._config.manager import UserConfigManager
from marimo._messaging.ops import MessageOperation
from marimo._messaging.types import KernelMessage
from marimo._runtime.requests import AppMetadata
from marimo._server.export.exporter import Exporter
from marimo._server.file_router import AppFileRouter
from marimo._server.model import ConnectionState, SessionConsumer, SessionMode
from marimo._server.models.export import ExportAsHTMLRequest
from marimo._server.sessions import Session


async def run_app_then_export_as_html(
    filename: str,
    include_code: bool,
) -> tuple[str, str]:
    # Create a file router and file manager
    file_router = AppFileRouter.from_filename(filename)
    file_key = file_router.get_unique_file_key()
    assert file_key is not None
    file_manager = file_router.get_file_manager(file_key)

    # Create a no-op session consumer
    class NoopSessionConsumer(SessionConsumer):
        def on_start(
            self,
            check_alive: Callable[[], None],
        ) -> Callable[[KernelMessage], None]:
            del check_alive
            return lambda _: None

        def on_stop(self) -> None:
            pass

        async def write_operation(self, op: MessageOperation) -> None:
            pass

        def connection_state(self) -> ConnectionState:
            return ConnectionState.OPEN

    config = UserConfigManager()

    # Create a session
    session = Session.create(
        initialization_id=file_key,
        session_consumer=NoopSessionConsumer(),
        mode=SessionMode.RUN,
        app_metadata=AppMetadata(query_params={}, filename=file_manager.path),
        app_file_manager=file_manager,
        user_config_manager=config,
    )

    # Run the app to completion once
    await session.app_file_manager.app.run_async()

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
