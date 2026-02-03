from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from marimo._ai._tools.base import ToolContext
from marimo._ai._tools.tools.create_notebook import (
    CreateNotebook,
    CreateNotebookArgs,
)
from marimo._ai._tools.types import MarimoNotebookInfo
from marimo._ai._tools.utils.exceptions import ToolExecutionError
from marimo._server.file_router import LazyListOfFilesAppFileRouter
from marimo._session.model import ConnectionState


@dataclass
class MockAppFileManager:
    filename: str | None
    path: str | None


@dataclass
class MockSession:
    _connection_state: ConnectionState
    app_file_manager: MockAppFileManager

    def connection_state(self) -> ConnectionState:
        return self._connection_state


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
    sessions: dict[str, MockSession]
    file_router: MockLazyFileRouter | MockFileRouter | None = None

    def get_active_connection_count(self) -> int:
        return len(
            [
                s
                for s in self.sessions.values()
                if s.connection_state()
                in (ConnectionState.OPEN, ConnectionState.ORPHANED)
            ]
        )


@dataclass
class MockAppState:
    host: str = "localhost"
    port: int = 2718
    base_url: str = "/"


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

    # Mock get_app to return app state
    mock_app = Mock()
    mock_app.state = MockAppState()
    context.get_app = Mock(return_value=mock_app)

    return context


@pytest.fixture
def tool(mock_context: Mock) -> CreateNotebook:
    """Create a CreateNotebook tool instance with mocked context."""
    tool = CreateNotebook(ToolContext())
    tool.context = mock_context
    return tool


class TestCreateNotebookBasic:
    """Test basic notebook creation functionality."""

    def test_create_notebook_simple(self, tool: CreateNotebook, temp_dir: str):
        """Test creating a simple notebook without prompt."""
        with patch(
            "marimo._ai._tools.tools.create_notebook.AppStateBase"
        ) as mock_app_state:
            mock_app_state.from_app.return_value = MockAppState()

            result = tool.handle(CreateNotebookArgs(filename="test.py"))

        assert result.status == "success"
        assert result.file_path.endswith("test.py")
        assert temp_dir in result.file_path
        assert "localhost:2718" in result.url
        assert "file=test.py" in result.url

        # Verify file was created
        assert Path(result.file_path).exists()

        # Verify content is valid marimo notebook
        content = Path(result.file_path).read_text()
        assert "import marimo" in content
        assert "marimo.App" in content
        assert "@app.cell" in content

    def test_create_notebook_adds_py_extension(
        self,
        tool: CreateNotebook,
        temp_dir: str,  # noqa: ARG002
    ):
        """Test that .py extension is added if missing."""
        with patch(
            "marimo._ai._tools.tools.create_notebook.AppStateBase"
        ) as mock_app_state:
            mock_app_state.from_app.return_value = MockAppState()

            result = tool.handle(CreateNotebookArgs(filename="mynotebook"))

        assert result.file_path.endswith("mynotebook.py")
        assert Path(result.file_path).exists()

    def test_create_notebook_with_prompt_fallback(
        self,
        tool: CreateNotebook,
        temp_dir: str,  # noqa: ARG002
    ):
        """Test creating notebook with prompt falls back to minimal when AI unavailable."""
        with patch(
            "marimo._ai._tools.tools.create_notebook.AppStateBase"
        ) as mock_app_state:
            mock_app_state.from_app.return_value = MockAppState()

            # Patch AI generation to return None (AI unavailable)
            with patch.object(tool, "_try_ai_generation", return_value=None):
                result = tool.handle(
                    CreateNotebookArgs(
                        filename="analysis.py",
                        prompt="Analyze some data",
                    )
                )

        assert result.status == "success"
        content = Path(result.file_path).read_text()
        # Prompt should be included as a comment in fallback
        assert "Analyze some data" in content
        assert "import marimo" in content

    def test_create_notebook_marks_router_stale(
        self,
        tool: CreateNotebook,
        temp_dir: str,  # noqa: ARG002
    ):
        """Test that directory file router is marked stale after creation."""
        with patch(
            "marimo._ai._tools.tools.create_notebook.AppStateBase"
        ) as mock_app_state:
            mock_app_state.from_app.return_value = MockAppState()

            tool.handle(CreateNotebookArgs(filename="test.py"))

        file_router = tool.context.session_manager.file_router
        assert file_router._stale_marked is True


class TestFilenameHandling:
    """Test filename validation and collision handling."""

    def test_auto_suffix_on_collision(
        self, tool: CreateNotebook, temp_dir: str
    ):
        """Test that numeric suffix is added when file exists."""
        # Create existing file
        existing_path = Path(temp_dir) / "existing.py"
        existing_path.write_text("# existing file")

        with patch(
            "marimo._ai._tools.tools.create_notebook.AppStateBase"
        ) as mock_app_state:
            mock_app_state.from_app.return_value = MockAppState()

            result = tool.handle(CreateNotebookArgs(filename="existing.py"))

        assert result.file_path.endswith("existing_1.py")
        assert Path(result.file_path).exists()
        # Original file should be unchanged
        assert existing_path.read_text() == "# existing file"

    def test_auto_suffix_multiple_collisions(
        self, tool: CreateNotebook, temp_dir: str
    ):
        """Test suffix increments correctly with multiple collisions."""
        # Create existing files
        (Path(temp_dir) / "test.py").write_text("# 0")
        (Path(temp_dir) / "test_1.py").write_text("# 1")
        (Path(temp_dir) / "test_2.py").write_text("# 2")

        with patch(
            "marimo._ai._tools.tools.create_notebook.AppStateBase"
        ) as mock_app_state:
            mock_app_state.from_app.return_value = MockAppState()

            result = tool.handle(CreateNotebookArgs(filename="test.py"))

        assert result.file_path.endswith("test_3.py")

    def test_invalid_filename_dot_prefix(self, tool: CreateNotebook):
        """Test that filenames starting with dot are rejected."""
        with pytest.raises(ToolExecutionError) as exc_info:
            tool.handle(CreateNotebookArgs(filename=".hidden.py"))

        assert exc_info.value.code == "INVALID_FILENAME"

    def test_filename_sanitization(
        self,
        tool: CreateNotebook,
        temp_dir: str,  # noqa: ARG002
    ):
        """Test that path separators are removed from filename."""
        with patch(
            "marimo._ai._tools.tools.create_notebook.AppStateBase"
        ) as mock_app_state:
            mock_app_state.from_app.return_value = MockAppState()

            result = tool.handle(
                CreateNotebookArgs(filename="path/to/notebook.py")
            )

        # Should only use the basename
        assert result.file_path.endswith("notebook.py")
        assert "path/to" not in result.file_path


class TestDirectoryResolution:
    """Test target directory resolution for different router types."""

    def test_directory_mode(self, tool: CreateNotebook, temp_dir: str):
        """Test notebook creation in directory mode."""
        with patch(
            "marimo._ai._tools.tools.create_notebook.AppStateBase"
        ) as mock_app_state:
            mock_app_state.from_app.return_value = MockAppState()

            result = tool.handle(CreateNotebookArgs(filename="test.py"))

        assert temp_dir in result.file_path

    def test_single_file_mode(self, temp_dir: str):
        """Test notebook creation in single-file mode (no directory)."""
        context = Mock(spec=ToolContext)

        # Single-file mode: router has no directory
        file_router = MockFileRouter(_directory=None)
        session_path = os.path.join(temp_dir, "existing_notebook.py")

        session = MockSession(
            _connection_state=ConnectionState.OPEN,
            app_file_manager=MockAppFileManager(
                filename=session_path, path=session_path
            ),
        )
        session_manager = MockSessionManager(
            sessions={"s1": session}, file_router=file_router
        )
        context.session_manager = session_manager
        context.get_active_sessions_internal = Mock(
            return_value=[
                MarimoNotebookInfo(
                    name="existing_notebook.py",
                    path=session_path,
                    session_id="s1",
                )
            ]
        )

        mock_app = Mock()
        mock_app.state = MockAppState()
        context.get_app = Mock(return_value=mock_app)

        tool = CreateNotebook(ToolContext())
        tool.context = context

        with patch(
            "marimo._ai._tools.tools.create_notebook.AppStateBase"
        ) as mock_app_state:
            mock_app_state.from_app.return_value = MockAppState()

            result = tool.handle(CreateNotebookArgs(filename="sibling.py"))

        # Should be created in same directory as existing notebook
        assert temp_dir in result.file_path
        assert result.file_path.endswith("sibling.py")

    def test_no_directory_error(self):
        """Test error when no directory can be determined."""
        context = Mock(spec=ToolContext)

        file_router = MockFileRouter(_directory=None)
        session_manager = MockSessionManager(
            sessions={}, file_router=file_router
        )
        context.session_manager = session_manager
        context.get_active_sessions_internal = Mock(return_value=[])

        tool = CreateNotebook(ToolContext())
        tool.context = context

        with pytest.raises(ToolExecutionError) as exc_info:
            tool.handle(CreateNotebookArgs(filename="test.py"))

        assert exc_info.value.code == "NO_DIRECTORY"


class TestValidation:
    """Test notebook content validation."""

    def test_valid_notebook_content(
        self,
        tool: CreateNotebook,
        temp_dir: str,  # noqa: ARG002
    ):
        """Test that generated minimal notebook passes validation."""
        with patch(
            "marimo._ai._tools.tools.create_notebook.AppStateBase"
        ) as mock_app_state:
            mock_app_state.from_app.return_value = MockAppState()

            result = tool.handle(CreateNotebookArgs(filename="valid.py"))

        assert result.status == "success"

        # Run marimo check on the created file
        from marimo._lint import Severity, collect_messages

        linter, _ = collect_messages(
            result.file_path, min_severity=Severity.BREAKING
        )
        assert linter.issues_count == 0

    def test_ai_content_validation_fallback(
        self,
        tool: CreateNotebook,
        temp_dir: str,  # noqa: ARG002
    ):
        """Test that invalid AI content falls back to minimal notebook."""
        invalid_ai_content = "this is not a valid marimo notebook"

        with patch(
            "marimo._ai._tools.tools.create_notebook.AppStateBase"
        ) as mock_app_state:
            mock_app_state.from_app.return_value = MockAppState()

            # Patch _generate_notebook_content to simulate the full flow:
            # AI returns invalid content -> validation fails -> fallback
            original_generate = tool._generate_notebook_content

            def patched_generate(prompt):
                # First call _try_ai_generation would return invalid content
                # but validation would fail, so we simulate the fallback
                return tool._create_minimal_notebook(prompt)

            with patch.object(
                tool, "_try_ai_generation", return_value=invalid_ai_content
            ):
                result = tool.handle(
                    CreateNotebookArgs(
                        filename="test.py", prompt="Generate something"
                    )
                )

        # Should still succeed with fallback content
        assert result.status == "success"
        content = Path(result.file_path).read_text()
        assert "import marimo" in content
        assert "marimo.App" in content

    def test_validation_rejects_invalid_content(self, tool: CreateNotebook):
        """Test that _validate_notebook_content rejects invalid content."""
        invalid_content = "print('hello world')"
        error = tool._validate_notebook_content(invalid_content)
        assert error is not None
        assert "not a valid" in error.lower()

    def test_validation_accepts_valid_content(self, tool: CreateNotebook):
        """Test that _validate_notebook_content accepts valid content."""
        valid_content = tool._create_minimal_notebook(None)
        error = tool._validate_notebook_content(valid_content)
        assert error is None


class TestURLGeneration:
    """Test URL generation for different configurations."""

    def test_url_with_default_host(
        self,
        tool: CreateNotebook,
        temp_dir: str,  # noqa: ARG002
    ):
        """Test URL generation with localhost."""
        with patch(
            "marimo._ai._tools.tools.create_notebook.AppStateBase"
        ) as mock_app_state:
            mock_app_state.from_app.return_value = MockAppState(
                host="localhost", port=2718, base_url="/"
            )

            result = tool.handle(CreateNotebookArgs(filename="test.py"))

        assert "http://localhost:2718" in result.url
        assert "file=test.py" in result.url

    def test_url_with_bind_all_host(
        self,
        tool: CreateNotebook,
        temp_dir: str,  # noqa: ARG002
    ):
        """Test URL generation when host is 0.0.0.0."""
        with patch(
            "marimo._ai._tools.tools.create_notebook.AppStateBase"
        ) as mock_app_state:
            mock_app_state.from_app.return_value = MockAppState(
                host="0.0.0.0", port=8080, base_url="/"
            )

            result = tool.handle(CreateNotebookArgs(filename="test.py"))

        # Should use localhost instead of 0.0.0.0
        assert "http://localhost:8080" in result.url

    def test_url_with_base_url(
        self,
        tool: CreateNotebook,
        temp_dir: str,  # noqa: ARG002
    ):
        """Test URL generation with custom base URL."""
        with patch(
            "marimo._ai._tools.tools.create_notebook.AppStateBase"
        ) as mock_app_state:
            mock_app_state.from_app.return_value = MockAppState(
                host="localhost", port=2718, base_url="/marimo/"
            )

            result = tool.handle(CreateNotebookArgs(filename="test.py"))

        assert "/marimo" in result.url
        assert "file=" in result.url


class TestMinimalNotebookGeneration:
    """Test the minimal notebook generation."""

    def test_minimal_notebook_without_prompt(self, tool: CreateNotebook):
        """Test minimal notebook generation without prompt."""
        content = tool._create_minimal_notebook(None)

        assert "import marimo" in content
        assert "marimo.App()" in content
        assert "@app.cell" in content
        assert "import marimo as mo" in content
        assert 'if __name__ == "__main__":' in content

    def test_minimal_notebook_with_prompt(self, tool: CreateNotebook):
        """Test minimal notebook generation with prompt."""
        content = tool._create_minimal_notebook("Build a dashboard")

        assert "import marimo" in content
        assert "Build a dashboard" in content
        assert "# Task:" in content
