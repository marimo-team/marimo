# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
import urllib.parse
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from marimo._ai._tools.base import ToolBase
from marimo._ai._tools.types import SuccessResult, ToolGuidelines
from marimo._ai._tools.utils.exceptions import ToolExecutionError
from marimo._server.api.deps import AppStateBase
from marimo._server.file_router import (
    LazyListOfFilesAppFileRouter,
    ListOfFilesAppFileRouter,
)
from marimo._session.consumer import SessionConsumer
from marimo._session.model import ConnectionState
from marimo._types.ids import ConsumerId, SessionId

if TYPE_CHECKING:
    from marimo._messaging.types import KernelMessage
    from marimo._session import Session
    from marimo._session.events import SessionEventBus


class HeadlessSessionConsumer(SessionConsumer):
    """A session consumer for MCP-driven headless sessions.

    This consumer doesn't send messages to any frontend — it just
    keeps the session alive so MCP tools can inspect it.
    """

    def __init__(self) -> None:
        self._consumer_id = ConsumerId(f"mcp-{uuid.uuid4().hex[:8]}")

    @property
    def consumer_id(self) -> ConsumerId:
        return self._consumer_id

    def notify(self, notification: KernelMessage) -> None:
        del notification

    def on_attach(self, session: Session, event_bus: SessionEventBus) -> None:
        del session, event_bus

    def on_detach(self) -> None:
        pass

    def connection_state(self) -> ConnectionState:
        return ConnectionState.OPEN


@dataclass
class StartSessionArgs:
    file_path: str
    """Absolute path to an existing marimo notebook .py file."""


@dataclass
class StartSessionOutput(SuccessResult):
    session_id: str = ""
    """The session ID for the started notebook."""

    url: str = ""
    """The URL to open the notebook in the browser."""


class StartSession(ToolBase[StartSessionArgs, StartSessionOutput]):
    """Start a session for an existing marimo notebook file.

    Registers the notebook file with the running marimo server and creates
    a headless kernel session so that MCP tools like get_cell_outputs and
    get_lightweight_cell_map can interact with the notebook without opening
    a browser.

    Returns:
        A success result containing the session ID and URL.
    """

    guidelines = ToolGuidelines(
        when_to_use=[
            "When the user wants to open a notebook in the browser",
            "After creating or editing a notebook .py file on disk",
        ],
        avoid_if=[
            "When the notebook is already open in the browser",
        ],
        side_effects=[
            "Registers the file with the marimo server's file router",
            "Creates a kernel session and instantiates the notebook",
        ],
        additional_info="The file must be a valid marimo notebook (.py). "
        "Use get_active_notebooks to check if a notebook is already running.",
    )

    def handle(self, args: StartSessionArgs) -> StartSessionOutput:
        file_path = args.file_path

        # Validate file exists
        if not os.path.isfile(file_path):
            raise ToolExecutionError(
                f"File not found: {file_path}",
                code="FILE_NOT_FOUND",
                is_retryable=False,
                suggested_fix="Provide an absolute path to an existing .py file.",
            )

        # Validate it's a .py file
        if not file_path.endswith(".py"):
            raise ToolExecutionError(
                "File must be a .py file",
                code="INVALID_FILE_TYPE",
                is_retryable=False,
                suggested_fix="Provide a path to a .py marimo notebook file.",
            )

        # Check if a session is already active for this file
        abs_path = os.path.abspath(file_path)
        if self.context.session_manager.any_clients_connected(abs_path):
            # Find the existing session ID
            existing_session_id = self._find_session_id_for_path(abs_path)
            directory = str(Path(file_path).parent)
            url = self._build_notebook_url(file_path, directory)
            return StartSessionOutput(
                session_id=existing_session_id or "",
                url=url,
                message=f"Notebook already has an active session: {file_path}",
                next_steps=[
                    f"Open the notebook at: {url}",
                ],
            )

        # Validate it's a valid marimo notebook
        validation_error = self._validate_notebook_content(file_path)
        if validation_error is not None:
            raise ToolExecutionError(
                f"Invalid marimo notebook: {validation_error}",
                code="INVALID_NOTEBOOK",
                is_retryable=False,
                suggested_fix="Ensure the file is a valid marimo notebook.",
            )

        # Register the file with the router
        self._register_file_with_router(file_path)

        # Create a headless session
        session_id = self._create_headless_session(abs_path)

        # Build the URL
        directory = str(Path(file_path).parent)
        url = self._build_notebook_url(file_path, directory)

        return StartSessionOutput(
            session_id=session_id,
            url=url,
            message=f"Session started for notebook: {file_path}",
            next_steps=[
                f"Use session_id '{session_id}' with get_lightweight_cell_map, get_cell_outputs, etc.",
                f"Open the notebook at: {url}",
            ],
        )

    def _find_session_id_for_path(self, abs_path: str) -> Optional[str]:
        """Find the session ID for a notebook at the given path."""
        for (
            session_id,
            session,
        ) in self.context.session_manager.sessions.items():
            if session.app_file_manager.path == abs_path:
                return session_id
        return None

    def _validate_notebook_content(self, file_path: str) -> Optional[str]:
        """Validate that the file is a valid marimo notebook.

        Returns None if valid, or an error message if invalid.
        Uses the same lightweight check as the directory scanner:
        the file must contain 'import marimo' and 'marimo.App'.
        """
        from marimo._server.files.directory_scanner import is_marimo_app

        if not is_marimo_app(file_path):
            return "File does not appear to be a marimo notebook (missing 'import marimo' and/or 'marimo.App')"

        return None

    def _register_file_with_router(self, file_path: str) -> None:
        """Register the file with the file router."""
        file_router = self.context.session_manager.file_router

        if isinstance(file_router, LazyListOfFilesAppFileRouter):
            file_router.mark_stale()
        elif isinstance(file_router, ListOfFilesAppFileRouter):
            file_router.register_allowed_file(file_path)

    def _create_headless_session(self, file_key: str) -> str:
        """Create a headless session for the notebook via the session manager."""
        from marimo._server.models.models import InstantiateNotebookRequest

        session_id = SessionId(f"s_{uuid.uuid4().hex[:12]}")
        consumer = HeadlessSessionConsumer()

        session = self.context.session_manager.create_session(
            session_id=session_id,
            session_consumer=consumer,
            query_params={},
            file_key=file_key,
            auto_instantiate=True,
        )

        # Instantiate the notebook (run all cells)
        session.instantiate(
            InstantiateNotebookRequest(
                object_ids=[],
                values=[],
                auto_run=True,
            ),
            http_request=None,
        )

        return session_id

    def _build_notebook_url(self, file_path: str, directory: str) -> str:
        """Build the URL to open the notebook."""
        app = self.context.get_app()
        state = AppStateBase.from_app(app)

        host = state.host
        port = state.port
        base_url = state.base_url.rstrip("/")

        try:
            relative_path = os.path.relpath(file_path, directory)
        except ValueError:
            # On Windows, relpath can fail across drives
            relative_path = file_path

        # Normalize to forward slashes for URL compatibility (Windows uses backslashes)
        relative_path = relative_path.replace(os.sep, "/")

        file_param = urllib.parse.quote(relative_path, safe="")

        display_host = host
        if host in ("0.0.0.0", "::"):
            display_host = "localhost"

        return f"http://{display_host}:{port}{base_url}?file={file_param}"
