# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import tempfile
import unittest.mock as mock
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from marimo._server.lsp import CopilotLspServer
from marimo._utils.platform import is_windows


class TestCopilotLspServerPaths:
    """Test CopilotLspServer with paths containing spaces, specifically targeting Windows."""

    def test_copilot_command_with_spaces_in_path_windows(self):
        """Test that copilot commands handle paths with spaces correctly on Windows."""
        with tempfile.TemporaryDirectory(prefix="test space dir ") as temp_dir:
            temp_path = Path(temp_dir)

            # Create a mock copilot directory structure with spaces
            copilot_dir = temp_path / "copilot"
            copilot_dir.mkdir()
            copilot_bin = copilot_dir / "language-server.js"
            copilot_bin.write_text("// mock copilot binary")

            # Create a mock LSP binary with spaces in path
            lsp_bin = temp_path / "index.cjs"
            lsp_bin.write_text("// mock lsp binary")

            server = CopilotLspServer(port=8080)

            # Mock the _lsp_dir and _lsp_bin methods to return our test paths
            with (
                patch.object(server, "_lsp_dir", return_value=temp_path),
                patch.object(server, "_lsp_bin", return_value=lsp_bin),
                patch("marimo._loggers.get_log_directory", return_value=temp_path),
            ):
                command = server.get_command()

                # Verify the command was generated
                assert command is not None
                assert len(command) > 0

                # Verify that the command contains the expected structure
                assert command[0] == "node"
                assert str(lsp_bin) in command
                assert "--port" in command
                assert "8080" in command
                assert "--lsp" in command

                # Find the --lsp command argument
                lsp_arg_index = command.index("--lsp") + 1
                lsp_command = command[lsp_arg_index]

                # The lsp_command should contain the quoted copilot binary path
                assert "node" in lsp_command
                assert str(copilot_bin) in lsp_command or f'"{copilot_bin}"' in lsp_command
                assert "--stdio" in lsp_command

    @pytest.mark.skipif(not is_windows(), reason="Windows-specific path quoting test")
    def test_copilot_command_windows_path_quoting(self):
        """Test Windows-specific path quoting for copilot binary paths."""
        with tempfile.TemporaryDirectory(prefix="Program Files Space Test ") as temp_dir:
            temp_path = Path(temp_dir)

            # Create directory structure with spaces similar to "Program Files"
            copilot_dir = temp_path / "copilot with spaces"
            copilot_dir.mkdir()
            copilot_bin = copilot_dir / "language-server.js"
            copilot_bin.write_text("// mock copilot binary")

            lsp_bin = temp_path / "index.cjs"
            lsp_bin.write_text("// mock lsp binary")

            server = CopilotLspServer(port=8080)

            with (
                patch.object(server, "_lsp_dir", return_value=temp_path),
                patch.object(server, "_lsp_bin", return_value=lsp_bin),
                patch("marimo._loggers.get_log_directory", return_value=temp_path),
            ):
                command = server.get_command()

                # Get the LSP command string
                lsp_arg_index = command.index("--lsp") + 1
                lsp_command = command[lsp_arg_index]

                # On Windows, paths with spaces should be properly quoted
                # The cmd_quote function should handle this
                assert '"' in lsp_command or all(
                    " " not in part for part in lsp_command.split()
                )

                # Verify the copilot binary path is present (quoted or unquoted)
                copilot_bin_str = str(copilot_bin)
                assert (
                    copilot_bin_str in lsp_command
                    or f'"{copilot_bin_str}"' in lsp_command
                )

    def test_copilot_command_with_nonexistent_lsp_binary(self):
        """Test that copilot command returns empty list when LSP binary doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Don't create the LSP binary - it should not exist
            lsp_bin = temp_path / "nonexistent_index.cjs"

            server = CopilotLspServer(port=8080)

            with (
                patch.object(server, "_lsp_dir", return_value=temp_path),
                patch.object(server, "_lsp_bin", return_value=lsp_bin),
            ):
                command = server.get_command()

                # Should return empty command when binary doesn't exist
                assert command == []

    def test_copilot_validate_requirements_node_missing(self):
        """Test that copilot validation fails when node is missing."""
        server = CopilotLspServer(port=8080)

        with patch("marimo._dependencies.dependencies.DependencyManager.which", return_value=None):
            result = server.validate_requirements()
            assert result != True
            assert "node.js binary is missing" in result

    def test_copilot_validate_requirements_node_old_version(self):
        """Test that copilot validation fails when node version is too old."""
        server = CopilotLspServer(port=8080)

        with (
            patch("marimo._dependencies.dependencies.DependencyManager.which", return_value="/usr/bin/node"),
            patch("subprocess.run") as mock_run,
        ):
            # Mock node version check to return old version
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="v18.20.0\n"
            )

            result = server.validate_requirements()
            assert result != True
            assert "Node.js version 18.20.0 is too old" in result
            assert "requires Node.js version 20 or higher" in result

    def test_copilot_validate_requirements_node_good_version(self):
        """Test that copilot validation succeeds with good node version."""
        server = CopilotLspServer(port=8080)

        with (
            patch("marimo._dependencies.dependencies.DependencyManager.which", return_value="/usr/bin/node"),
            patch("subprocess.run") as mock_run,
        ):
            # Mock node version check to return good version
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="v20.10.0\n"
            )

            result = server.validate_requirements()
            assert result is True

    def test_copilot_command_structure_consistency(self):
        """Test that the copilot command structure is consistent."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create complete directory structure
            copilot_dir = temp_path / "copilot"
            copilot_dir.mkdir()
            copilot_bin = copilot_dir / "language-server.js"
            copilot_bin.write_text("// mock copilot binary")

            lsp_bin = temp_path / "index.cjs"
            lsp_bin.write_text("// mock lsp binary")

            server = CopilotLspServer(port=9999)

            with (
                patch.object(server, "_lsp_dir", return_value=temp_path),
                patch.object(server, "_lsp_bin", return_value=lsp_bin),
                patch("marimo._loggers.get_log_directory", return_value=temp_path),
            ):
                command = server.get_command()

                # Verify the command structure matches expected format:
                # ["node", "lsp_bin", "--port", "port", "--lsp", "copilot_command", "--log-file", "log_file"]
                expected_structure = [
                    "node",
                    str(lsp_bin),
                    "--port",
                    "9999",
                    "--lsp",
                    mock.ANY,  # This is the copilot command string
                    "--log-file",
                    mock.ANY,  # This is the log file path
                ]

                assert len(command) == len(expected_structure)
                for i, (actual, expected) in enumerate(zip(command, expected_structure)):
                    if expected != mock.ANY:
                        assert actual == expected, f"Mismatch at index {i}: {actual} != {expected}"

    def test_copilot_command_windows_quoting_simulation(self):
        """Test Windows path quoting behavior by mocking is_windows()."""
        with tempfile.TemporaryDirectory(prefix="Program Files Test ") as temp_dir:
            temp_path = Path(temp_dir)

            # Create directory structure with spaces
            copilot_dir = temp_path / "GitHub Copilot"
            copilot_dir.mkdir()
            copilot_bin = copilot_dir / "language-server.js"
            copilot_bin.write_text("// mock copilot binary")

            lsp_bin = temp_path / "index.cjs"
            lsp_bin.write_text("// mock lsp binary")

            server = CopilotLspServer(port=8080)

            with (
                patch.object(server, "_lsp_dir", return_value=temp_path),
                patch.object(server, "_lsp_bin", return_value=lsp_bin),
                patch("marimo._loggers.get_log_directory", return_value=temp_path),
                # Mock is_windows to return True to test Windows quoting behavior
                patch("marimo._utils.strings.is_windows", return_value=True),
            ):
                command = server.get_command()

                # Get the LSP command string
                lsp_arg_index = command.index("--lsp") + 1
                lsp_command = command[lsp_arg_index]

                # With spaces in the path and Windows quoting, we should see proper quoting
                # The cmd_quote function should quote paths with spaces
                copilot_bin_str = str(copilot_bin)
                if " " in copilot_bin_str:
                    # Path has spaces, so it should be quoted in the command
                    assert '"' in lsp_command, f"Expected quotes in command: {lsp_command}"

                # Verify the basic structure is still correct
                assert "node" in lsp_command
                assert "--stdio" in lsp_command

    def test_copilot_command_move_lsp_bin_to_space_path(self):
        """Test moving the lsp_bin to a path with spaces, specifically targeting Windows scenarios."""
        with tempfile.TemporaryDirectory(prefix="Space Path Test ") as temp_dir:
            temp_path = Path(temp_dir)

            # Create a nested directory structure with multiple spaces
            space_dir = temp_path / "Program Files" / "Marimo LSP Server"
            space_dir.mkdir(parents=True)

            # Move the LSP binary to the space path
            lsp_bin = space_dir / "index.cjs"
            lsp_bin.write_text("// mock lsp binary in space path")

            # Create copilot structure
            copilot_dir = space_dir / "copilot"
            copilot_dir.mkdir()
            copilot_bin = copilot_dir / "language-server.js"
            copilot_bin.write_text("// mock copilot binary in space path")

            server = CopilotLspServer(port=8080)

            with (
                patch.object(server, "_lsp_dir", return_value=space_dir),
                patch.object(server, "_lsp_bin", return_value=lsp_bin),
                patch("marimo._loggers.get_log_directory", return_value=space_dir),
            ):
                command = server.get_command()

                # Verify command is generated successfully even with spaces in paths
                assert command is not None
                assert len(command) > 0

                # The lsp_bin path with spaces should be handled correctly
                assert str(lsp_bin) in command

                # Get the LSP command part
                lsp_arg_index = command.index("--lsp") + 1
                lsp_command = command[lsp_arg_index]

                # Verify copilot binary path is in the command (quoted or not)
                copilot_bin_str = str(copilot_bin)
                assert (
                    copilot_bin_str in lsp_command
                    or f'"{copilot_bin_str}"' in lsp_command
                ), f"Copilot binary path not found in: {lsp_command}"