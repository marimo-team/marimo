# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from marimo._ai._tools.base import ToolBase
from marimo._ai._tools.types import SuccessResult, ToolGuidelines
from marimo._ai._tools.utils.exceptions import ToolExecutionError
from marimo._server.api.deps import AppStateBase
from marimo._server.file_router import (
    LazyListOfFilesAppFileRouter,
    ListOfFilesAppFileRouter,
)


@dataclass
class StartSessionArgs:
    file_path: str
    """Absolute path to an existing marimo notebook .py file."""


@dataclass
class StartSessionOutput(SuccessResult):
    url: str = ""
    """The URL to open the notebook in the browser."""


class StartSession(ToolBase[StartSessionArgs, StartSessionOutput]):
    """Start a session for an existing marimo notebook file.

    Registers the notebook file with the running marimo server so it becomes
    accessible in the browser. The actual kernel session starts when a browser
    connects to the returned URL.

    Returns:
        A success result containing the URL to open the notebook.
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
            directory = str(Path(file_path).parent)
            url = self._build_notebook_url(file_path, directory)
            return StartSessionOutput(
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

        # Build the URL
        directory = str(Path(file_path).parent)
        url = self._build_notebook_url(file_path, directory)

        return StartSessionOutput(
            url=url,
            message=f"Notebook registered: {file_path}",
            next_steps=[
                f"Open the notebook at: {url}",
                "Use get_active_notebooks to see all running notebooks",
            ],
        )

    def _validate_notebook_content(self, file_path: str) -> Optional[str]:
        """Validate that the file is a valid marimo notebook.

        Returns None if valid, or an error message if invalid.
        """
        from marimo._lint import Severity, collect_messages

        try:
            linter, messages = collect_messages(
                file_path, min_severity=Severity.BREAKING
            )

            if linter.errored:
                return f"Not a valid marimo notebook:\n{messages}"

            if linter.issues_count > 0:
                return f"Notebook has breaking issues:\n{messages}"

            return None
        except Exception as e:
            return f"Validation error: {e}"

    def _register_file_with_router(self, file_path: str) -> None:
        """Register the file with the file router."""
        file_router = self.context.session_manager.file_router

        if isinstance(file_router, LazyListOfFilesAppFileRouter):
            file_router.mark_stale()
        elif isinstance(file_router, ListOfFilesAppFileRouter):
            file_router.register_allowed_file(file_path)

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
