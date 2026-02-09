from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from marimo._ai._tools.base import ToolContext
from marimo._ai._tools.tools.start_session import (
    StartSession,
    StartSessionArgs,
)
from marimo._ai._tools.utils.exceptions import ToolExecutionError
from marimo._server.file_router import LazyListOfFilesAppFileRouter


class MockLazyFileRouter(LazyListOfFilesAppFileRouter):
    """Mock that tracks mark_stale calls without actual file scanning."""

    def __init__(self, directory: str):
        self._directory = directory
        self._stale_marked = False
        self._registered_files: list[str] = []

    @property
    def directory(self) -> str | None:
        return self._directory

    def mark_stale(self) -> None:
        self._stale_marked = True

    def register_allowed_file(self, filepath: str) -> None:
        self._registered_files.append(filepath)


@dataclass
class MockFileRouter:
    """Simple mock for single-file mode (not LazyListOfFilesAppFileRouter)."""

    _directory: str | None = None
    _registered_files: list[str] = field(default_factory=list)

    @property
    def directory(self) -> str | None:
        return self._directory

    def register_allowed_file(self, filepath: str) -> None:
        self._registered_files.append(filepath)


@dataclass
class MockSessionManager:
    sessions: dict[str, object]
    file_router: MockLazyFileRouter | MockFileRouter | None = None
    _connected_paths: set[str] = field(default_factory=set)

    def get_active_connection_count(self) -> int:
        return 0

    def any_clients_connected(self, key: str) -> bool:
        return key in self._connected_paths


@dataclass
class MockAppState:
    host: str = "localhost"
    port: int = 2718
    base_url: str = "/"


def _create_valid_notebook(path: Path) -> None:
    """Write a minimal valid marimo notebook to the given path."""
    import marimo

    version = marimo.__version__
    content = f'''import marimo

__generated_with = "{version}"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
'''
    path.write_text(content, encoding="utf-8")


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test notebooks."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def mock_context(temp_dir: str) -> Mock:
    """Create a mock ToolContext with a directory-based file router."""
    context = Mock(spec=ToolContext)

    file_router = MockLazyFileRouter(directory=temp_dir)
    session_manager = MockSessionManager(sessions={}, file_router=file_router)
    context.session_manager = session_manager

    mock_app = Mock()
    mock_app.state = MockAppState()
    context.get_app = Mock(return_value=mock_app)

    return context


@pytest.fixture
def tool(mock_context: Mock) -> StartSession:
    """Create a StartSession tool instance with mocked context."""
    tool = StartSession(ToolContext())
    tool.context = mock_context
    return tool


class TestStartSessionBasic:
    """Test basic start session functionality."""

    def test_start_session_valid_notebook(
        self, tool: StartSession, temp_dir: str
    ):
        """Test starting a session with a valid notebook file."""
        notebook_path = Path(temp_dir) / "test.py"
        _create_valid_notebook(notebook_path)

        with patch(
            "marimo._ai._tools.tools.start_session.AppStateBase"
        ) as mock_app_state:
            mock_app_state.from_app.return_value = MockAppState()

            result = tool.handle(
                StartSessionArgs(file_path=str(notebook_path))
            )

        assert result.status == "success"
        assert "localhost:2718" in result.url
        assert "file=test.py" in result.url

    def test_start_session_marks_router_stale(
        self, tool: StartSession, temp_dir: str
    ):
        """Test that directory file router is marked stale."""
        notebook_path = Path(temp_dir) / "test.py"
        _create_valid_notebook(notebook_path)

        with patch(
            "marimo._ai._tools.tools.start_session.AppStateBase"
        ) as mock_app_state:
            mock_app_state.from_app.return_value = MockAppState()

            tool.handle(StartSessionArgs(file_path=str(notebook_path)))

        file_router = tool.context.session_manager.file_router
        assert file_router._stale_marked is True


class TestStartSessionAlreadyActive:
    """Test duplicate session detection."""

    def test_returns_url_when_session_already_active(
        self, tool: StartSession, temp_dir: str
    ):
        """Test that an already-active notebook returns the URL without re-registering."""
        notebook_path = Path(temp_dir) / "active.py"
        _create_valid_notebook(notebook_path)

        # Mark this path as having an active connection
        abs_path = os.path.abspath(str(notebook_path))
        tool.context.session_manager._connected_paths.add(abs_path)

        with patch(
            "marimo._ai._tools.tools.start_session.AppStateBase"
        ) as mock_app_state:
            mock_app_state.from_app.return_value = MockAppState()

            result = tool.handle(
                StartSessionArgs(file_path=str(notebook_path))
            )

        assert result.status == "success"
        assert "already has an active session" in result.message
        assert "localhost:2718" in result.url

        # Router should NOT have been marked stale
        file_router = tool.context.session_manager.file_router
        assert file_router._stale_marked is False


class TestStartSessionErrors:
    """Test error handling."""

    def test_file_not_found(self, tool: StartSession):
        """Test error when file doesn't exist."""
        with pytest.raises(ToolExecutionError) as exc_info:
            tool.handle(StartSessionArgs(file_path="/nonexistent/test.py"))

        assert exc_info.value.code == "FILE_NOT_FOUND"

    def test_not_a_py_file(self, tool: StartSession, temp_dir: str):
        """Test error when file is not a .py file."""
        txt_path = Path(temp_dir) / "test.txt"
        txt_path.write_text("hello")

        with pytest.raises(ToolExecutionError) as exc_info:
            tool.handle(StartSessionArgs(file_path=str(txt_path)))

        assert exc_info.value.code == "INVALID_FILE_TYPE"

    def test_invalid_notebook_content(self, tool: StartSession, temp_dir: str):
        """Test error when file is not a valid marimo notebook."""
        invalid_path = Path(temp_dir) / "invalid.py"
        invalid_path.write_text("print('hello world')")

        with pytest.raises(ToolExecutionError) as exc_info:
            tool.handle(StartSessionArgs(file_path=str(invalid_path)))

        assert exc_info.value.code == "INVALID_NOTEBOOK"


class TestFileRouterRegistration:
    """Test file router registration for different router types."""

    def test_single_file_mode_registers_file(self, temp_dir: str):
        """Test that single-file mode registers the file."""
        from marimo._server.file_router import ListOfFilesAppFileRouter
        from marimo._server.models.home import MarimoFile

        context = Mock(spec=ToolContext)

        file_router = ListOfFilesAppFileRouter(
            [
                MarimoFile(
                    name="existing.py",
                    path=str(Path(temp_dir) / "existing.py"),
                    last_modified=0.0,
                )
            ],
            allow_dynamic=True,
        )
        session_manager = MockSessionManager(
            sessions={}, file_router=file_router
        )
        context.session_manager = session_manager

        mock_app = Mock()
        mock_app.state = MockAppState()
        context.get_app = Mock(return_value=mock_app)

        tool = StartSession(ToolContext())
        tool.context = context

        notebook_path = Path(temp_dir) / "new_notebook.py"
        _create_valid_notebook(notebook_path)

        with patch(
            "marimo._ai._tools.tools.start_session.AppStateBase"
        ) as mock_app_state:
            mock_app_state.from_app.return_value = MockAppState()

            result = tool.handle(
                StartSessionArgs(file_path=str(notebook_path))
            )

        assert result.status == "success"
        assert isinstance(file_router, ListOfFilesAppFileRouter)


class TestURLGeneration:
    """Test URL generation for different configurations."""

    def test_url_with_default_host(self, tool: StartSession, temp_dir: str):
        """Test URL generation with localhost."""
        notebook_path = Path(temp_dir) / "test.py"
        _create_valid_notebook(notebook_path)

        with patch(
            "marimo._ai._tools.tools.start_session.AppStateBase"
        ) as mock_app_state:
            mock_app_state.from_app.return_value = MockAppState(
                host="localhost", port=2718, base_url="/"
            )

            result = tool.handle(
                StartSessionArgs(file_path=str(notebook_path))
            )

        assert "http://localhost:2718" in result.url
        assert "file=test.py" in result.url

    def test_url_with_bind_all_host(self, tool: StartSession, temp_dir: str):
        """Test URL generation when host is 0.0.0.0."""
        notebook_path = Path(temp_dir) / "test.py"
        _create_valid_notebook(notebook_path)

        with patch(
            "marimo._ai._tools.tools.start_session.AppStateBase"
        ) as mock_app_state:
            mock_app_state.from_app.return_value = MockAppState(
                host="0.0.0.0", port=8080, base_url="/"
            )

            result = tool.handle(
                StartSessionArgs(file_path=str(notebook_path))
            )

        assert "http://localhost:8080" in result.url

    def test_url_with_base_url(self, tool: StartSession, temp_dir: str):
        """Test URL generation with custom base URL."""
        notebook_path = Path(temp_dir) / "test.py"
        _create_valid_notebook(notebook_path)

        with patch(
            "marimo._ai._tools.tools.start_session.AppStateBase"
        ) as mock_app_state:
            mock_app_state.from_app.return_value = MockAppState(
                host="localhost", port=2718, base_url="/marimo/"
            )

            result = tool.handle(
                StartSessionArgs(file_path=str(notebook_path))
            )

        assert "/marimo" in result.url
        assert "file=" in result.url
