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


async def test_base_lsp_server_start_stop(
    mock_popen: mock.MagicMock,
    mock_process: mock.MagicMock,
):
    server = MockLspServer(port=8000)
    server.validate_requirements = mock.MagicMock(return_value=False)

    # Without binary install
    alert = await server.start()
    assert alert is not None
    assert alert.title == "Mock Alert"
    assert alert.description == "Mock missing binary"

    server.validate_requirements = mock.MagicMock(return_value=True)

    # Test start
    alert = await server.start()
    assert alert is None
    mock_popen.assert_called_once()
    assert server.is_running() is False  # Process exists but not running

    # Test stop
    server.stop()
    mock_process.terminate.assert_called_once()
    assert server.process is None


async def test_base_lsp_server_missing_binary(mock_which: mock.MagicMock):
    server = MockLspServer(port=8000)
    mock_which.return_value = None
    server.validate_requirements = mock.MagicMock(return_value=False)
    alert = await server.start()
    assert alert is not None
    assert alert.title == "Mock Alert"


async def test_pylsp_server():
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
    if server._lsp_bin().exists():
        assert "node" in server.get_command()
        assert str(8000) in server.get_command()
    else:
        assert server.get_command() == []
    alert = server.missing_binary_alert()
    assert "GitHub Copilot" in alert.title


def test_copilot_server_command_quotes_path(tmp_path: Path) -> None:
    """Test that paths with spaces are properly quoted in the copilot command."""
    from unittest import mock

    server = CopilotLspServer(port=8000)

    # Create LSP directory with spaces
    lsp_dir_with_spaces = tmp_path / "my folder with spaces"
    lsp_dir_with_spaces.mkdir(parents=True)

    # Create the required files
    lsp_bin = lsp_dir_with_spaces / "index.cjs"
    lsp_bin.touch()

    copilot_dir = lsp_dir_with_spaces / "copilot"
    copilot_dir.mkdir()
    copilot_bin = copilot_dir / "language-server.js"
    copilot_bin.touch()

    # Mock the _lsp_dir method to return our test directory
    with mock.patch.object(
        server, "_lsp_dir", return_value=lsp_dir_with_spaces
    ):
        command = server.get_command()

        # Find the --lsp argument
        lsp_arg_index = command.index("--lsp")
        lsp_command = command[lsp_arg_index + 1]

        # The command should contain the quoted path
        assert "node" in lsp_command
        assert (
            str(copilot_bin) in lsp_command
            or f"'{copilot_bin}'" in lsp_command
            or f'"{copilot_bin}"' in lsp_command
        )
        assert "--stdio" in lsp_command


def test_copilot_server_node_version_validation():
    server = CopilotLspServer(port=8000)

    # Test missing node
    with mock.patch(
        "marimo._dependencies.dependencies.DependencyManager.which",
        return_value=None,
    ):
        result = server.validate_requirements()
        assert isinstance(result, str)
        assert "node.js binary is missing" in result

    # Test node version < 20
    with (
        mock.patch(
            "marimo._dependencies.dependencies.DependencyManager.which",
            return_value="/usr/bin/node",
        ),
        mock.patch("subprocess.run") as mock_run,
    ):
        mock_run.return_value = mock.MagicMock(
            returncode=0, stdout="v18.17.0\n"
        )
        result = server.validate_requirements()
        assert isinstance(result, str)
        assert "Node.js version 18.17.0 is too old" in result
        assert "requires Node.js version 20 or higher" in result

    # Test node version >= 20
    with (
        mock.patch(
            "marimo._dependencies.dependencies.DependencyManager.which",
            return_value="/usr/bin/node",
        ),
        mock.patch("subprocess.run") as mock_run,
    ):
        mock_run.return_value = mock.MagicMock(
            returncode=0, stdout="v20.10.0\n"
        )
        result = server.validate_requirements()
        assert result is True

    # Test subprocess failure (fail open)
    with (
        mock.patch(
            "marimo._dependencies.dependencies.DependencyManager.which",
            return_value="/usr/bin/node",
        ),
        mock.patch("subprocess.run") as mock_run,
    ):
        mock_run.return_value = mock.MagicMock(
            returncode=1, stderr="Command failed"
        )
        result = server.validate_requirements()
        assert result is True  # Should fail open

    # Test exception during version check (fail open)
    with (
        mock.patch(
            "marimo._dependencies.dependencies.DependencyManager.which",
            return_value="/usr/bin/node",
        ),
        mock.patch("subprocess.run", side_effect=Exception("Network error")),
    ):
        result = server.validate_requirements()
        assert result is True  # Should fail open


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
        total_lsp_servers = 4
        config = LanguageServersConfig(
            {
                "pylsp": {"enabled": True},
                "ty": {"enabled": True},
                "basedpyright": {"enabled": True},
            }
        )
        completion_config = CompletionConfig(
            {"copilot": True, "activate_on_typing": True}
        )
        config_reader = as_reader(completion_config, config)
        config = config_reader.get_config()
        server = CompositeLspServer(config_reader, min_port=8000)
        assert (
            len(server.servers) == total_lsp_servers
        )  # Both pylsp and copilot enabled
        assert server._is_enabled(config, "pylsp") is True
        assert server._is_enabled(config, "copilot") is True
        assert server._is_enabled(config, "ty") is True
        assert server._is_enabled(config, "basedpyright") is True

        # Test with only pylsp
        config = LanguageServersConfig({"pylsp": {"enabled": True}})
        completion_config = CompletionConfig(
            {"copilot": False, "activate_on_typing": True}
        )
        config_reader = as_reader(completion_config, config)
        config = config_reader.get_config()
        server = CompositeLspServer(config_reader, min_port=8000)
        assert len(server.servers) == total_lsp_servers
        assert server._is_enabled(config, "pylsp") is True
        assert server._is_enabled(config, "copilot") is False
        assert server._is_enabled(config, "ty") is False

        # Test with only ty enabled
        config = LanguageServersConfig(
            {
                "ty": {"enabled": True},
                "pylsp": {"enabled": False},
                "basedpyright": {"enabled": False},
            }
        )
        completion_config = CompletionConfig(
            {"copilot": False, "activate_on_typing": True}
        )
        config_reader = as_reader(completion_config, config)
        config = config_reader.get_config()
        server = CompositeLspServer(config_reader, min_port=8000)
        assert len(server.servers) == total_lsp_servers
        assert server._is_enabled(config, "pylsp") is False
        assert server._is_enabled(config, "basedpyright") is False
        assert server._is_enabled(config, "copilot") is False
        assert server._is_enabled(config, "ty") is True

        # Test with only basedpyright enabled
        config = LanguageServersConfig(
            {
                "basedpyright": {"enabled": True},
                "pylsp": {"enabled": False},
                "ty": {"enabled": False},
            }
        )
        completion_config = CompletionConfig(
            {"copilot": False, "activate_on_typing": True}
        )
        config_reader = as_reader(completion_config, config)
        config = config_reader.get_config()
        server = CompositeLspServer(config_reader, min_port=8000)
        assert len(server.servers) == total_lsp_servers
        assert server._is_enabled(config, "pylsp") is False
        assert server._is_enabled(config, "basedpyright") is True
        assert server._is_enabled(config, "copilot") is False
        assert server._is_enabled(config, "ty") is False

        # Test with nothing enabled
        config = LanguageServersConfig({"pylsp": {"enabled": False}})
        completion_config = CompletionConfig(
            {"copilot": False, "activate_on_typing": True}
        )
        config_reader = as_reader(completion_config, config)
        config = config_reader.get_config()
        server = CompositeLspServer(config_reader, min_port=8000)
        assert len(server.servers) == total_lsp_servers
        assert server._is_enabled(config, "pylsp") is False
        assert server._is_enabled(config, "copilot") is False
        assert server._is_enabled(config, "ty") is False


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
