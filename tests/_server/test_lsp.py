from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Literal, Union, cast
from unittest import mock

import pytest

from marimo._config.config import (
    CompletionConfig,
    LanguageServersConfig,
    MarimoConfig,
    merge_default_config,
)
from marimo._config.manager import (
    MarimoConfigReader,
    MarimoConfigReaderWithOverrides,
)
from marimo._loggers import get_log_directory
from marimo._messaging.ops import Alert
from marimo._server.lsp import (
    BaseLspServer,
    CompositeLspServer,
    CopilotLspServer,
    PyLspServer,
    any_lsp_server_running,
)

if TYPE_CHECKING:
    from collections.abc import Iterator


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

    def validate_requirements(self) -> Union[str, Literal[True]]:
        return True

    def get_command(self) -> list[str]:
        return ["mock_binary", "--port", str(self.port)]

    def missing_binary_alert(self) -> Alert:
        return Alert(title="Mock Alert", description="Mock missing binary")


def test_base_lsp_server_start_stop(
    mock_popen: mock.MagicMock,
    mock_process: mock.MagicMock,
):
    server = MockLspServer(port=8000)
    server.validate_requirements = mock.MagicMock(return_value=False)

    # Without binary install
    alert = server.start()
    assert alert is not None
    assert alert.title == "Mock Alert"
    assert alert.description == "Mock missing binary"

    server.validate_requirements = mock.MagicMock(return_value=True)

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
    server.validate_requirements = mock.MagicMock(return_value=False)
    alert = server.start()
    assert alert is not None
    assert alert.title == "Mock Alert"


def test_pylsp_server():
    import sys

    server = PyLspServer(port=8000)

    assert isinstance(server.validate_requirements(), (str, bool))
    assert server.get_command() == [
        sys.executable,
        "-m",
        "pylsp",
        "--ws",
        "-v",
        "--port",
        "8000",
        "--check-parent-process",
        "--log-file",
        str(get_log_directory() / "pylsp.log"),
    ]
    alert = server.missing_binary_alert()
    assert "Python LSP" in alert.title


def test_copilot_server():
    server = CopilotLspServer(port=8000)
    assert isinstance(server.validate_requirements(), (str, bool))
    if Path(server._lsp_bin()).exists():
        assert "node" in server.get_command()
        assert str(8000) in server.get_command()
    else:
        assert server.get_command() == []
    alert = server.missing_binary_alert()
    assert "GitHub Copilot" in alert.title


def test_composite_server():
    def as_reader(
        completion_config: CompletionConfig, config: LanguageServersConfig
    ) -> MarimoConfigReader:
        return cast(
            MarimoConfigReader,
            MarimoConfigReaderWithOverrides(
                {
                    "completion": completion_config,
                    "language_servers": config,
                    "experimental": {"lsp": True},
                },
            ),
        )

    with mock.patch("marimo._server.lsp.DependencyManager") as mock_dm:
        mock_dm.pylsp = mock.MagicMock()
        mock_dm.pylsp.has.return_value = True
        config = LanguageServersConfig({"pylsp": {"enabled": True}})
        completion_config = CompletionConfig(
            {"copilot": True, "activate_on_typing": True}
        )
        config_reader = as_reader(completion_config, config)
        server = CompositeLspServer(config_reader, min_port=8000)
        assert len(server.servers) == 2  # Both pylsp and copilot enabled
        assert server._is_enabled("pylsp") is True
        assert server._is_enabled("copilot") is True

        # Test with only pylsp
        config = LanguageServersConfig({"pylsp": {"enabled": True}})
        completion_config = CompletionConfig(
            {"copilot": False, "activate_on_typing": True}
        )
        config_reader = as_reader(completion_config, config)
        server = CompositeLspServer(config_reader, min_port=8000)
        assert len(server.servers) == 2
        assert server._is_enabled("pylsp") is True
        assert server._is_enabled("copilot") is False

        # Test with nothing enabled
        config = LanguageServersConfig({"pylsp": {"enabled": False}})
        completion_config = CompletionConfig(
            {"copilot": False, "activate_on_typing": True}
        )
        config_reader = as_reader(completion_config, config)
        server = CompositeLspServer(config_reader, min_port=8000)
        assert len(server.servers) == 2
        assert server._is_enabled("pylsp") is False
        assert server._is_enabled("copilot") is False


def test_any_lsp_server_running():
    # Test any_lsp_server_running function
    config: MarimoConfig = merge_default_config(
        {
            "completion": {"copilot": True, "activate_on_typing": True},
            "language_servers": {"pylsp": {"enabled": False}},
        }
    )
    assert any_lsp_server_running(config) is True

    config: MarimoConfig = merge_default_config(
        {
            "completion": {"copilot": False, "activate_on_typing": True},
            "language_servers": {"pylsp": {"enabled": True}},
        }
    )
    assert any_lsp_server_running(config) is True

    config: MarimoConfig = merge_default_config(
        {
            "completion": {"copilot": False, "activate_on_typing": True},
            "language_servers": {"pylsp": {"enabled": False}},
        }
    )
    assert any_lsp_server_running(config) is False

    config: MarimoConfig = merge_default_config(
        {
            "completion": {"copilot": False, "activate_on_typing": True},
            "language_servers": {},  # default is true
        }
    )
    assert any_lsp_server_running(config) is True
