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
class CreateNotebookArgs:
    filename: str
    """The filename for the new notebook (e.g., 'analysis.py'). Must end with .py"""

    prompt: Optional[str] = None
    """Optional prompt to generate initial notebook content using marimo's AI API.
    If not provided or if AI is unavailable, creates a notebook with an empty cell."""


@dataclass
class CreateNotebookOutput(SuccessResult):
    file_path: str = ""
    """The absolute path to the created notebook file."""

    url: str = ""
    """The URL to open the notebook in the browser."""


class CreateNotebook(ToolBase[CreateNotebookArgs, CreateNotebookOutput]):
    """Create a new marimo notebook file and return its URL.

    Creates a new notebook in the same directory as the currently running
    marimo server. If a prompt is provided and the marimo AI API is available,
    generates initial content from the prompt. Otherwise, creates a notebook
    with an empty cell.

    Returns:
        A success result containing the file path and URL to open the notebook.
    """

    guidelines = ToolGuidelines(
        when_to_use=[
            "When the user wants to create a new notebook",
            "When starting a new analysis or project",
        ],
        avoid_if=[
            "When the user wants to edit an existing notebook",
        ],
        side_effects=[
            "Creates a new .py file on disk",
        ],
        additional_info="The notebook will be created in the directory being served by marimo. "
        "If a file with the same name exists, a numeric suffix will be added.",
    )

    def handle(self, args: CreateNotebookArgs) -> CreateNotebookOutput:
        filename = args.filename
        prompt = args.prompt

        # Validate filename
        if not filename.endswith(".py"):
            filename = f"{filename}.py"

        # Sanitize filename - remove path separators and dangerous characters
        filename = os.path.basename(filename)
        if not filename or filename.startswith("."):
            raise ToolExecutionError(
                "Invalid filename",
                code="INVALID_FILENAME",
                is_retryable=False,
                suggested_fix="Provide a valid filename that doesn't start with a dot.",
            )

        # Get the directory to create the notebook in
        directory = self._get_target_directory()

        # Handle filename collision with auto-suffix
        file_path = self._get_unique_filepath(directory, filename)

        # Generate notebook content
        content = self._generate_notebook_content(prompt)

        # Write the file
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
        except OSError as e:
            raise ToolExecutionError(
                f"Failed to write notebook file: {e}",
                code="FILE_WRITE_ERROR",
                is_retryable=False,
                suggested_fix="Check file permissions and disk space.",
            ) from e

        # Register the file with the router so it can be accessed
        self._register_file_with_router(file_path)

        # Build the URL
        url = self._build_notebook_url(file_path, directory)

        return CreateNotebookOutput(
            file_path=file_path,
            url=url,
            message=f"Created notebook at {file_path}",
            next_steps=[
                f"Open the notebook at: {url}",
                "Use get_active_notebooks to see all running notebooks",
            ],
        )

    def _get_target_directory(self) -> str:
        """Get the directory where the notebook should be created."""
        file_router = self.context.session_manager.file_router

        # For directory mode, use the directory directly
        if file_router.directory:
            return file_router.directory

        # For single-file mode, derive directory from active sessions
        sessions = self.context.get_active_sessions_internal()
        if sessions:
            # Get directory from the first session's file path
            for session_info in sessions:
                if session_info.path and not session_info.path.startswith("("):
                    return str(Path(session_info.path).parent)

        raise ToolExecutionError(
            "Could not determine target directory",
            code="NO_DIRECTORY",
            is_retryable=False,
            suggested_fix="Ensure marimo is running with a file or directory.",
        )

    def _get_unique_filepath(self, directory: str, filename: str) -> str:
        """Get a unique filepath, adding numeric suffix if file exists."""
        base_path = Path(directory) / filename

        if not base_path.exists():
            return str(base_path)

        # Extract name and extension
        stem = base_path.stem
        suffix = base_path.suffix

        # Try adding numeric suffixes
        counter = 1
        while True:
            new_path = Path(directory) / f"{stem}_{counter}{suffix}"
            if not new_path.exists():
                return str(new_path)
            counter += 1
            if counter > 1000:
                raise ToolExecutionError(
                    "Could not find unique filename after 1000 attempts",
                    code="FILENAME_EXHAUSTED",
                    is_retryable=False,
                    suggested_fix="Try a different filename.",
                )

    def _generate_notebook_content(self, prompt: Optional[str]) -> str:
        """Generate notebook content, using AI if available."""
        if prompt:
            content = self._try_ai_generation(prompt)
            if content:
                # Validate AI-generated content
                validation_error = self._validate_notebook_content(content)
                if validation_error is None:
                    return content
                # AI content invalid, fall back to minimal notebook

        # Fallback: create minimal notebook with optional comment
        return self._create_minimal_notebook(prompt)

    def _validate_notebook_content(self, content: str) -> Optional[str]:
        """Validate that content is a valid marimo notebook using the linter.

        Returns None if valid, or an error message if invalid.
        Uses the same linting engine as `marimo check` to catch breaking issues.
        """
        import tempfile

        from marimo._lint import Severity, collect_messages

        # Write to a temporary file for validation
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            encoding="utf-8",
            delete=False,
        ) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            # Run linting with only BREAKING severity
            # This catches issues that would prevent the notebook from running
            linter, messages = collect_messages(
                tmp_path, min_severity=Severity.BREAKING
            )

            # Check if the file couldn't be parsed as a valid notebook
            if linter.errored:
                return f"Generated content is not a valid marimo notebook:\n{messages}"

            # Check if there are any breaking issues
            if linter.issues_count > 0:
                return f"Generated notebook has breaking issues:\n{messages}"

            return None
        except Exception as e:
            return f"Validation error: {e}"
        finally:
            # Clean up temp file
            try:
                Path(tmp_path).unlink()
            except OSError:
                pass

    def _try_ai_generation(self, prompt: str) -> Optional[str]:
        """Try to generate notebook content using the marimo AI API."""
        try:
            # Check if user has accepted terms (non-interactively)
            from marimo._config.cli_state import get_cli_state

            state = get_cli_state()
            if not state or not state.accepted_text_to_notebook_terms_at:
                # User hasn't accepted terms, can't use AI non-interactively
                return None

            # Check if terms are still valid
            from marimo._ai.text_to_notebook import _should_show_terms

            if _should_show_terms(state.accepted_text_to_notebook_terms_at):
                return None

            # Call the API
            import marimo._utils.requests as requests

            url = f"https://ai.marimo.app/api/notebook.py?prompt={urllib.parse.quote(prompt)}"
            headers = {"User-Agent": requests.MARIMO_USER_AGENT}
            result = (
                requests.get(url, headers=headers).raise_for_status().text()
            )

            if "marimo.App" in result:
                return result

            return None
        except Exception:
            # AI generation failed, will fall back to minimal notebook
            return None

    def _create_minimal_notebook(self, prompt: Optional[str]) -> str:
        """Create a minimal marimo notebook."""
        import marimo

        version = marimo.__version__

        if prompt:
            # Include the prompt as a comment for context
            # Escape any triple quotes in the prompt
            safe_prompt = prompt.replace('"""', '\\"\\"\\"')
            cell_code = f"""    # Task: {safe_prompt}
    import marimo as mo
    return (mo,)"""
        else:
            cell_code = """    import marimo as mo
    return (mo,)"""

        return f'''import marimo

__generated_with = "{version}"
app = marimo.App()


@app.cell
def _():
{cell_code}


if __name__ == "__main__":
    app.run()
'''

    def _register_file_with_router(self, file_path: str) -> None:
        """Register the new file with the file router."""
        file_router = self.context.session_manager.file_router

        if isinstance(file_router, LazyListOfFilesAppFileRouter):
            # For directory mode, mark stale so the new file is discovered
            file_router.mark_stale()
        elif isinstance(file_router, ListOfFilesAppFileRouter):
            # For single-file mode, explicitly register the file
            file_router.register_allowed_file(file_path)

    def _build_notebook_url(self, file_path: str, directory: str) -> str:
        """Build the URL to open the notebook."""
        app = self.context.get_app()
        state = AppStateBase.from_app(app)

        host = state.host
        port = state.port
        base_url = state.base_url.rstrip("/")

        # Use relative path from directory if possible
        try:
            relative_path = os.path.relpath(file_path, directory)
        except ValueError:
            # On Windows, relpath can fail across drives
            relative_path = file_path

        # URL encode the file parameter
        file_param = urllib.parse.quote(relative_path, safe="")

        # Build the URL
        # Handle host being 0.0.0.0 or :: (bind all interfaces)
        display_host = host
        if host in ("0.0.0.0", "::"):
            display_host = "localhost"

        return f"http://{display_host}:{port}{base_url}?file={file_param}"
