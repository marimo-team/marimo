from __future__ import annotations

from collections.abc import Iterator
from unittest import mock

import pytest

from marimo._config.config import CompletionConfig, LanguageServersConfig
from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.ops import Alert
from marimo._server.lsp import (
    BaseLspServer,
    CompositeLspServer,
    CopilotLspServer,
    PyLspServer,
)


@pytest.fixture
def mock_process():
    process = mock.MagicMock()
    process.returncode = None
    return process


@pytest.fixture
def mock_popen(mock_process: mock.MagicMock) -> Iterator[mock.MagicMock]:
    with mock.patch("subprocess.Popen", return_value=mock_process) as popen:
        yield popen


@pytest.fixture
def mock_which():
    with mock.patch("shutil.which", return_value="/mock/path") as which:
        yield which


class MockLspServer(BaseLspServer):
    id = "mock"

    def binary_name(self) -> str:
        return "mock_binary"

    def get_command(self) -> str:
        return f"mock_binary --port {self.port}"

    def missing_binary_alert(self) -> Alert:
        return Alert(title="Mock Alert", description="Mock missing binary")


def test_base_lsp_server_start_stop(
    mock_which: mock.MagicMock,
    mock_popen: mock.MagicMock,
    mock_process: mock.MagicMock,
):
    server = MockLspServer(port=8000)

    mock_which.return_value = None

    # Without binary install
    alert = server.start()
    assert alert is not None
    assert alert.title == "Mock Alert"
    assert alert.description == "Mock missing binary"

    # Add binary
    mock_which.return_value = "/mock/path"

    # Test start
    alert = server.start()
    assert alert is None
    mock_popen.assert_called_once()
    assert server.is_running() is False  # Process exists but not running

    # Test stop
    server.stop()
    mock_process.terminate.assert_called_once()
    assert server.process is None


def test_base_lsp_server_missing_binary(mock_which: mock.MagicMock):
    server = MockLspServer(port=8000)
    mock_which.return_value = None
    alert = server.start()
    assert alert is not None
    assert alert.title == "Mock Alert"


def test_pylsp_server():
    server = PyLspServer(port=8000)
    assert server.binary_name() == "pylsp"
    assert server.get_command() == "pylsp --ws -v --port 8000"
    alert = server.missing_binary_alert()
    assert "Python LSP" in alert.title


def test_copilot_server():
    server = CopilotLspServer(port=8000)
    assert server.binary_name() == "node"
    assert "node" in server.get_command()
    assert str(8000) in server.get_command()
    alert = server.missing_binary_alert()
    assert "GitHub Copilot" in alert.title


def test_composite_server():
    config = LanguageServersConfig({"pylsp": {"enabled": True}})
    completion_config = CompletionConfig(
        {"copilot": True, "activate_on_typing": True}
    )

    with mock.patch("marimo._server.lsp.DependencyManager") as mock_dm:
        mock_dm.pylsp = mock.MagicMock()
        mock_dm.pylsp.has.return_value = True
        server = CompositeLspServer(config, completion_config, min_port=8000)
        assert len(server.servers) == 2  # Both pylsp and copilot enabled

        # Test with only pylsp
        config = LanguageServersConfig({"pylsp": {"enabled": True}})
        completion_config = CompletionConfig(
            {"copilot": False, "activate_on_typing": True}
        )
        server = CompositeLspServer(config, completion_config, min_port=8000)
        assert len(server.servers) == 1

        # Test with nothing enabled
        config = LanguageServersConfig({"pylsp": {"enabled": False}})
        completion_config = CompletionConfig(
            {"copilot": False, "activate_on_typing": True}
        )
        server = CompositeLspServer(config, completion_config, min_port=8000)
        assert len(server.servers) == 0


@pytest.mark.skipif(
    not DependencyManager.pylsp.has(),
    reason="pylsp is not installed",
)
def test_pylsp_hooks():
    from marimo._server.lsp import pylsp_completions, pylsp_hover

    # Mock document and position
    mock_doc = mock.MagicMock()
    mock_doc.source = "def test(): pass"
    mock_doc.path = "test.py"
    position = {"line": 0, "character": 4}

    # Test hover
    hover_result = pylsp_hover({}, mock_doc, position)
    assert hover_result is None or isinstance(hover_result, dict)

    # Test completions
    completion_result = pylsp_completions(mock_doc, position)
    assert completion_result is None
