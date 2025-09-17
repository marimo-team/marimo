# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
import signal
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import pytest
from starlette.websockets import WebSocketDisconnect

from marimo._server.api.endpoints.terminal import (
    _create_process_cleanup_handler,
    _create_shell_environment,
    _decode_pty_data,
    _manage_command_buffer,
    _setup_child_process,
    _should_close_on_command,
)
from marimo._server.model import SessionMode
from marimo._server.sessions import SessionManager
from tests._server.conftest import get_session_manager

if TYPE_CHECKING:
    from starlette.testclient import TestClient

is_windows = sys.platform == "win32"
is_mac = sys.platform == "darwin"


@pytest.mark.skipif(is_windows, reason="Skip on Windows")
def test_terminal_ws(client: TestClient) -> None:
    with client.websocket_connect("/terminal/ws") as websocket:
        # Send echo message
        websocket.send_text("echo hello")
        data = websocket.receive_text()
        assert "echo hello" in data


def test_terminal_ws_not_allowed_in_run(client: TestClient) -> None:
    session_manager: SessionManager = get_session_manager(client)
    session_manager.mode = SessionMode.RUN
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/terminal/ws") as websocket:
            websocket.send_text("echo hello")
    session_manager.mode = SessionMode.EDIT


# Unit tests for terminal utility functions


class TestCreateShellEnvironment:
    def test_create_shell_environment_default_cwd(self) -> None:
        """Test shell environment creation with default working directory."""
        shell, env = _create_shell_environment()

        assert shell in ["/bin/bash", "/bin/zsh", "/bin/sh"]
        assert env["TERM"] == "xterm-256color"
        assert "LANG" in env
        assert "LC_ALL" in env

    def test_create_shell_environment_custom_cwd(self) -> None:
        """Test shell environment creation with custom working directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            shell, env = _create_shell_environment(cwd=temp_dir)

            assert shell in ["/bin/bash", "/bin/zsh", "/bin/sh"]
            assert env["TERM"] == "xterm-256color"

    @patch("os.getcwd")
    @patch("pathlib.Path.home")
    def test_create_shell_environment_fallback_cwd(
        self, mock_home: Mock, mock_getcwd: Mock
    ) -> None:
        """Test shell environment creation when getcwd fails."""
        mock_getcwd.side_effect = OSError("No such directory")
        mock_home.return_value = Path("/home/user")

        shell, env = _create_shell_environment()

        assert shell in ["/bin/bash", "/bin/zsh", "/bin/sh"]
        assert env["TERM"] == "xterm-256color"

    @patch("os.getcwd")
    @patch("pathlib.Path.home")
    def test_create_shell_environment_ultimate_fallback(
        self, mock_home: Mock, mock_getcwd: Mock
    ) -> None:
        """Test shell environment creation when both getcwd and home fail."""
        mock_getcwd.side_effect = OSError("No such directory")
        mock_home.side_effect = Exception("No home directory")

        shell, env = _create_shell_environment()

        assert shell in ["/bin/bash", "/bin/zsh", "/bin/sh"]
        assert env["TERM"] == "xterm-256color"

    @patch("os.path.exists")
    @patch.dict(os.environ, {"SHELL": "/nonexistent/shell"})
    def test_create_shell_environment_shell_fallback(
        self, mock_exists: Mock
    ) -> None:
        """Test shell selection fallback when default shell doesn't exist."""

        # Mock that the default shell doesn't exist, but /bin/bash does
        def exists_side_effect(path: str) -> bool:
            return path == "/bin/bash"

        mock_exists.side_effect = exists_side_effect

        shell, env = _create_shell_environment()

        assert shell == "/bin/bash"
        assert env["TERM"] == "xterm-256color"


class TestDecodeProxyData:
    def test_decode_pty_data_valid_utf8(self) -> None:
        """Test decoding valid UTF-8 data."""
        buffer = b"hello world"
        text, remaining = _decode_pty_data(buffer)

        assert text == "hello world"
        assert remaining == b""

    def test_decode_pty_data_with_unicode(self) -> None:
        """Test decoding UTF-8 data with unicode characters."""
        buffer = "hello 🌍".encode()
        text, remaining = _decode_pty_data(buffer)

        assert text == "hello 🌍"
        assert remaining == b""

    def test_decode_pty_data_invalid_utf8_ignored(self) -> None:
        """Test decoding invalid UTF-8 data with ignore errors."""
        buffer = b"hello\xff\xfeinvalid"
        text, remaining = _decode_pty_data(buffer)

        assert text == "helloinvalid"  # Invalid bytes are ignored
        assert remaining == b""

    def test_decode_pty_data_buffer_too_large(self) -> None:
        """Test decoding when buffer exceeds max size."""
        large_buffer = b"x" * 100000  # Larger than MAX_BUFFER_SIZE
        text, remaining = _decode_pty_data(large_buffer, max_buffer_size=1024)

        assert text == "x" * 100000  # Should decode with replacement
        assert remaining == b""

    def test_decode_pty_data_empty_buffer(self) -> None:
        """Test decoding empty buffer."""
        buffer = b""
        text, remaining = _decode_pty_data(buffer)

        assert text == ""
        assert remaining == b""


class TestShouldCloseOnCommand:
    def test_should_close_on_command_exit_with_return(self) -> None:
        """Test exit command detection with return key."""
        assert _should_close_on_command("exit", "\r") is True
        assert _should_close_on_command("EXIT", "\r") is True
        assert _should_close_on_command("  exit  ", "\r") is True

    def test_should_close_on_command_exit_with_newline(self) -> None:
        """Test exit command detection with newline."""
        assert _should_close_on_command("exit", "\n") is True
        assert _should_close_on_command("EXIT", "\n") is True
        assert _should_close_on_command("  exit  ", "\n") is True

    def test_should_close_on_command_not_exit(self) -> None:
        """Test non-exit commands don't trigger close."""
        assert _should_close_on_command("ls", "\r") is False
        assert _should_close_on_command("echo hello", "\n") is False
        assert _should_close_on_command("exit_status", "\r") is False

    def test_should_close_on_command_no_enter(self) -> None:
        """Test exit command without enter key doesn't trigger close."""
        assert _should_close_on_command("exit", "x") is False
        assert _should_close_on_command("exit", "") is False

    def test_should_close_on_command_empty_buffer(self) -> None:
        """Test empty command buffer."""
        assert _should_close_on_command("", "\r") is False
        assert _should_close_on_command("   ", "\n") is False


class TestManageCommandBuffer:
    def test_manage_command_buffer_normal_size(self) -> None:
        """Test command buffer management under normal size."""
        buffer = "ls -la"
        new_buffer = _manage_command_buffer(buffer, " /home")

        assert new_buffer == "ls -la /home"

    def test_manage_command_buffer_exceeds_max_size(self) -> None:
        """Test command buffer management when exceeding max size."""
        # Create a buffer that will exceed max size
        long_command = "x" * 1000
        buffer = long_command
        new_buffer = _manage_command_buffer(buffer, "y", max_size=500)

        # Should keep only the last 512 chars (KEEP_COMMAND_CHARS)
        assert len(new_buffer) == 512  # Exactly KEEP_COMMAND_CHARS
        assert new_buffer.endswith("y")
        assert new_buffer.startswith("x")

    def test_manage_command_buffer_empty_buffer(self) -> None:
        """Test command buffer management with empty buffer."""
        buffer = ""
        new_buffer = _manage_command_buffer(buffer, "hello")

        assert new_buffer == "hello"

    def test_manage_command_buffer_exactly_max_size(self) -> None:
        """Test command buffer management at exactly max size."""
        buffer = "x" * 100
        new_buffer = _manage_command_buffer(buffer, "y", max_size=100)

        assert len(new_buffer) == 101
        assert new_buffer == buffer + "y"


@pytest.mark.skipif(is_windows, reason="Skip on Windows")
class TestCreateProcessCleanupHandler:
    def test_create_process_cleanup_handler_normal_cleanup(self) -> None:
        """Test process cleanup handler creation and execution."""
        mock_child_pid = 12345
        mock_fd = 10

        cleanup = _create_process_cleanup_handler(mock_child_pid, mock_fd)

        with (
            patch("os.kill") as mock_kill,
            patch("os.waitpid") as mock_waitpid,
            patch("os.close") as mock_close,
        ):
            cleanup()

            # Should try graceful termination first
            mock_kill.assert_any_call(mock_child_pid, signal.SIGTERM)
            # Should try force kill
            mock_kill.assert_any_call(mock_child_pid, signal.SIGKILL)
            mock_waitpid.assert_called()
            mock_close.assert_called_with(mock_fd)

    def test_create_process_cleanup_handler_process_not_found(self) -> None:
        """Test cleanup handler when process doesn't exist."""
        mock_child_pid = 12345
        mock_fd = 10

        cleanup = _create_process_cleanup_handler(mock_child_pid, mock_fd)

        with (
            patch("os.kill") as mock_kill,
            patch("os.waitpid") as mock_waitpid,
            patch("os.close") as mock_close,
        ):
            mock_kill.side_effect = [
                None,
                ProcessLookupError("No such process"),
            ]

            cleanup()

            # Should still try to close the file descriptor
            mock_close.assert_called_with(mock_fd)

    def test_create_process_cleanup_handler_fd_error(self) -> None:
        """Test cleanup handler when file descriptor close fails."""
        mock_child_pid = 12345
        mock_fd = 10

        cleanup = _create_process_cleanup_handler(mock_child_pid, mock_fd)

        with (
            patch("os.kill") as mock_kill,
            patch("os.waitpid") as mock_waitpid,
            patch("os.close") as mock_close,
        ):
            mock_close.side_effect = OSError("Bad file descriptor")

            # Should not raise an exception
            cleanup()

            mock_close.assert_called_with(mock_fd)


class TestSetupChildProcess:
    @patch("os.chdir")
    @patch("os.execve")
    def test_setup_child_process_success(
        self, mock_execve: Mock, mock_chdir: Mock
    ) -> None:
        """Test successful child process setup."""
        shell = "/bin/bash"
        env = {"TERM": "xterm-256color", "PATH": "/usr/bin"}
        cwd = "/home/user"

        _setup_child_process(shell, env, cwd)

        mock_chdir.assert_called_once_with(cwd)
        mock_execve.assert_called_once_with(shell, [shell], env)

    @patch("os.chdir")
    @patch("os.execve")
    @patch("sys.exit")
    def test_setup_child_process_chdir_fails(
        self, mock_exit: Mock, mock_execve: Mock, mock_chdir: Mock
    ) -> None:
        """Test child process setup when chdir fails."""
        shell = "/bin/bash"
        env = {"TERM": "xterm-256color"}
        cwd = "/nonexistent"

        mock_chdir.side_effect = OSError("No such directory")

        _setup_child_process(shell, env, cwd)

        mock_chdir.assert_called_once_with(cwd)
        mock_execve.assert_not_called()
        mock_exit.assert_called_once_with(1)

    @patch("os.chdir")
    @patch("os.execve")
    @patch("sys.exit")
    def test_setup_child_process_execve_fails(
        self, mock_exit: Mock, mock_execve: Mock, mock_chdir: Mock
    ) -> None:
        """Test child process setup when execve fails."""
        shell = "/bin/bash"
        env = {"TERM": "xterm-256color"}
        cwd = "/home/user"

        mock_execve.side_effect = OSError("Exec format error")

        _setup_child_process(shell, env, cwd)

        mock_chdir.assert_called_once_with(cwd)
        mock_execve.assert_called_once_with(shell, [shell], env)
        mock_exit.assert_called_once_with(1)


# Additional edge case tests


class TestDecodeProxyDataEdgeCases:
    def test_decode_pty_data_partial_utf8_sequence(self) -> None:
        """Test handling of partial UTF-8 sequences."""
        # Create a partial UTF-8 sequence (emoji split across buffers)
        full_emoji = "🌍".encode()  # 4 bytes
        partial_buffer = full_emoji[:2]  # First 2 bytes only

        text, remaining = _decode_pty_data(partial_buffer)

        # Should handle gracefully with ignore errors
        assert isinstance(text, str)
        assert remaining == b""

    def test_decode_pty_data_mixed_valid_invalid(self) -> None:
        """Test decoding buffer with mix of valid and invalid UTF-8."""
        buffer = b"hello\xff\xfe world \xe2\x9c\x93"  # hello[invalid] world ✓
        text, remaining = _decode_pty_data(buffer)

        assert "hello" in text
        assert "world" in text
        assert remaining == b""


class TestCommandBufferEdgeCases:
    def test_manage_command_buffer_unicode_characters(self) -> None:
        """Test command buffer with unicode characters."""
        buffer = "echo 🌍"
        new_buffer = _manage_command_buffer(buffer, " 🚀")

        assert new_buffer == "echo 🌍 🚀"

    def test_manage_command_buffer_control_characters(self) -> None:
        """Test command buffer with control characters."""
        buffer = "ls\x1b[1m"  # ANSI escape sequence
        new_buffer = _manage_command_buffer(buffer, "\x1b[0m")

        assert new_buffer == "ls\x1b[1m\x1b[0m"

    def test_should_close_on_command_case_variations(self) -> None:
        """Test exit command detection with various case combinations."""
        test_cases = [
            ("exit", "\r", True),
            ("Exit", "\r", True),
            ("EXIT", "\r", True),
            ("eXiT", "\r", True),
            ("quit", "\r", False),  # Only 'exit' should work
            ("logout", "\r", False),
        ]

        for command, key, expected in test_cases:
            assert _should_close_on_command(command, key) == expected


@pytest.mark.skipif(is_windows, reason="Skip on Windows")
def test_terminal_ws_unicode_input(client: TestClient) -> None:
    """Test terminal websocket with unicode input."""
    with client.websocket_connect("/terminal/ws") as websocket:
        # Send unicode command
        websocket.send_text("echo 'Hello 🌍'")
        websocket.send_text("\r")
        data = websocket.receive_text()

        # Should handle unicode properly
        assert isinstance(data, str)


def test_terminal_ws_invalid_session_mode(client: TestClient) -> None:
    """Test terminal websocket rejects non-edit mode sessions."""
    session_manager: SessionManager = get_session_manager(client)
    original_mode = session_manager.mode

    try:
        # Test with RUN mode
        session_manager.mode = SessionMode.RUN
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/terminal/ws"):
                pass  # Should fail immediately

    finally:
        # Restore original mode
        session_manager.mode = original_mode
