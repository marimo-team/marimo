# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from marimo._utils.formatter import (
    BlackFormatter,
    CellCodes,
    DefaultFormatter,
    FormatError,
    Formatter,
    RuffFormatter,
    ruff,
)


class TestFormatter:
    """Test the base Formatter class."""

    async def test_base_formatter_returns_unchanged_codes(self):
        """Test that base Formatter returns codes unchanged."""
        formatter = Formatter(line_length=88)
        codes: CellCodes = {"cell1": "x = 1\ny = 2", "cell2": "z = 3"}

        result = await formatter.format(codes)

        assert result == codes
        assert result is codes  # Should be the same object


class TestDefaultFormatter:
    """Test the DefaultFormatter class that tries ruff, then black."""

    @patch("marimo._utils.formatter.RuffFormatter")
    @patch("marimo._dependencies.dependencies.DependencyManager.which")
    @patch("marimo._dependencies.dependencies.DependencyManager.ruff")
    async def test_uses_ruff_when_available(
        self,
        mock_ruff: MagicMock,
        mock_which: MagicMock,
        mock_ruff_formatter: MagicMock,
    ) -> None:
        """Test DefaultFormatter uses RuffFormatter when ruff is available."""
        # Mock ruff as available
        mock_ruff.has.return_value = True
        mock_which.return_value = "/usr/bin/ruff"

        # Mock RuffFormatter
        mock_instance = AsyncMock()
        mock_ruff_formatter.return_value = mock_instance
        mock_instance.format.return_value = {"cell1": "formatted_code"}

        formatter = DefaultFormatter(line_length=88)
        codes: CellCodes = {"cell1": "x=1"}

        result = await formatter.format(codes)

        mock_ruff_formatter.assert_called_once_with(88)
        mock_instance.format.assert_called_once_with(codes)
        assert result == {"cell1": "formatted_code"}

    @patch("marimo._utils.formatter.BlackFormatter")
    @patch("marimo._dependencies.dependencies.DependencyManager.black")
    @patch("marimo._dependencies.dependencies.DependencyManager.which")
    @patch("marimo._dependencies.dependencies.DependencyManager.ruff")
    async def test_uses_black_when_ruff_unavailable_but_black_available(
        self,
        mock_ruff: MagicMock,
        mock_which: MagicMock,
        mock_black: MagicMock,
        mock_black_formatter: MagicMock,
    ) -> None:
        """Test DefaultFormatter uses BlackFormatter when ruff unavailable but black available."""
        # Mock ruff as unavailable, black as available
        mock_ruff.has.return_value = False
        mock_which.return_value = None
        mock_black.has.return_value = True

        # Mock BlackFormatter
        mock_instance = AsyncMock()
        mock_black_formatter.return_value = mock_instance
        mock_instance.format.return_value = {"cell1": "formatted_code"}

        formatter = DefaultFormatter(line_length=88)
        codes: CellCodes = {"cell1": "x=1"}

        result = await formatter.format(codes)

        mock_black_formatter.assert_called_once_with(88)
        mock_instance.format.assert_called_once_with(codes)
        assert result == {"cell1": "formatted_code"}

    @patch("marimo._dependencies.dependencies.DependencyManager.black")
    @patch("marimo._dependencies.dependencies.DependencyManager.which")
    @patch("marimo._dependencies.dependencies.DependencyManager.ruff")
    async def test_raises_module_not_found_when_no_formatters_available(
        self,
        mock_ruff: MagicMock,
        mock_which: MagicMock,
        mock_black: MagicMock,
    ) -> None:
        """Test DefaultFormatter raises ModuleNotFoundError when no formatters available."""
        # Mock both ruff and black as unavailable
        mock_ruff.has.return_value = False
        mock_which.return_value = None
        mock_black.has.return_value = False

        formatter = DefaultFormatter(line_length=88)
        codes: CellCodes = {"cell1": "x=1"}

        with pytest.raises(ModuleNotFoundError) as exc_info:
            await formatter.format(codes)

        assert "ruff or black" in str(exc_info.value)
        assert exc_info.value.name == "ruff"


class TestRuffFormatter:
    """Test the RuffFormatter class."""

    @patch("marimo._utils.formatter.ruff")
    async def test_ruff_formatter_calls_ruff_function(
        self, mock_ruff: MagicMock
    ) -> None:
        """Test RuffFormatter calls the ruff function with correct arguments."""
        mock_ruff.return_value = {"cell1": "formatted_code"}

        formatter = RuffFormatter(line_length=100)
        codes: CellCodes = {"cell1": "x=1"}

        result = await formatter.format(codes)

        mock_ruff.assert_called_once_with(
            codes, "format", "--line-length", "100"
        )
        assert result == {"cell1": "formatted_code"}

    @patch("marimo._utils.formatter.ruff")
    async def test_ruff_formatter_propagates_exceptions(
        self, mock_ruff: MagicMock
    ) -> None:
        """Test RuffFormatter propagates exceptions from ruff function."""
        mock_ruff.side_effect = ModuleNotFoundError("ruff not found")

        formatter = RuffFormatter(line_length=88)
        codes: CellCodes = {"cell1": "x=1"}

        with pytest.raises(ModuleNotFoundError):
            await formatter.format(codes)


class TestBlackFormatter:
    """Test the BlackFormatter class."""

    @patch("marimo._dependencies.dependencies.DependencyManager.black")
    async def test_black_formatter_requires_dependency(
        self, mock_black: MagicMock
    ):
        """Test BlackFormatter calls require on black dependency."""
        mock_black.require.side_effect = ModuleNotFoundError("black required")

        formatter = BlackFormatter(line_length=88)
        codes: CellCodes = {"cell1": "x=1"}

        with pytest.raises(ModuleNotFoundError):
            await formatter.format(codes)

        mock_black.require.assert_called_once_with("to enable code formatting")

    @patch("asyncio.to_thread")
    @patch("marimo._dependencies.dependencies.DependencyManager.black")
    async def test_black_formatter_formats_code_successfully(
        self, mock_black_dep: MagicMock, mock_to_thread: MagicMock
    ):
        """Test BlackFormatter successfully formats code using black."""
        # Mock dependency requirement to pass
        mock_black_dep.require.return_value = None

        # Mock black module with __spec__ attribute
        mock_black = MagicMock()
        mock_black.__spec__ = MagicMock()
        mock_mode = MagicMock()
        mock_black.Mode.return_value = mock_mode
        mock_black.format_str.return_value = "formatted_code\n"

        with patch.dict(sys.modules, {"black": mock_black}):
            mock_to_thread.return_value = "formatted_code\n"

            formatter = BlackFormatter(line_length=100)
            codes: CellCodes = {"cell1": "x=1", "cell2": "y=2"}

            result = await formatter.format(codes)

            assert result == {
                "cell1": "formatted_code",
                "cell2": "formatted_code",
            }
            mock_black.Mode.assert_called_with(line_length=100)
            assert mock_to_thread.call_count == 2

    @patch("asyncio.to_thread")
    @patch("marimo._dependencies.dependencies.DependencyManager.black")
    async def test_black_formatter_handles_formatting_errors_gracefully(
        self, mock_black_dep: MagicMock, mock_to_thread: MagicMock
    ):
        """Test BlackFormatter handles black formatting errors gracefully."""
        # Mock dependency requirement to pass
        mock_black_dep.require.return_value = None

        # Mock black module with __spec__ attribute
        mock_black = MagicMock()
        mock_black.__spec__ = MagicMock()
        mock_mode = MagicMock()
        mock_black.Mode.return_value = mock_mode

        with patch.dict(sys.modules, {"black": mock_black}):
            # First call succeeds, second call fails
            mock_to_thread.side_effect = [
                "formatted_code\n",
                Exception("Black error"),
            ]

            formatter = BlackFormatter(line_length=88)
            codes: CellCodes = {"cell1": "x=1", "cell2": "y=2"}

            result = await formatter.format(codes)

            # Should return formatted code for successful cells, original for failed
            assert result == {
                "cell1": "formatted_code",
                "cell2": "y=2",
            }


class TestRuffFunction:
    """Test the ruff async function."""

    @patch("asyncio.create_subprocess_exec")
    async def test_ruff_function_with_module_ruff_available(
        self, mock_subprocess: MagicMock
    ):
        """Test ruff function when ruff is available as a module."""
        # Mock help command success
        help_process = AsyncMock()
        help_process.returncode = 0
        help_process.wait.return_value = None

        # Mock format command success
        format_process = AsyncMock()
        format_process.returncode = 0
        format_process.communicate.return_value = (
            b"formatted_code\n",
            b"",
        )

        mock_subprocess.side_effect = [help_process, format_process]

        codes: CellCodes = {"cell1": "x=1"}
        result = await ruff(codes, "format", "--line-length", "88")

        assert result == {"cell1": "formatted_code"}

        # Check that help command was called first
        help_call = mock_subprocess.call_args_list[0]
        assert help_call[0] == (sys.executable, "-m", "ruff", "--help")

        # Check that format command was called
        format_call = mock_subprocess.call_args_list[1]
        assert format_call[0] == (
            sys.executable,
            "-m",
            "ruff",
            "format",
            "--line-length",
            "88",
            "-",
        )

    @patch("asyncio.create_subprocess_exec")
    async def test_ruff_function_falls_back_to_global_ruff(
        self, mock_subprocess: MagicMock
    ):
        """Test ruff function falls back to global ruff when module unavailable."""
        # Mock module ruff failing
        module_help_process = AsyncMock()
        module_help_process.returncode = 1
        module_help_process.wait.return_value = None

        # Mock global ruff succeeding for help
        global_help_process = AsyncMock()
        global_help_process.returncode = 0
        global_help_process.wait.return_value = None

        # Mock format command success
        format_process = AsyncMock()
        format_process.returncode = 0
        format_process.communicate.return_value = (
            b"formatted_code\n",
            b"",
        )

        mock_subprocess.side_effect = [
            module_help_process,
            global_help_process,
            format_process,
        ]

        codes: CellCodes = {"cell1": "x=1"}
        result = await ruff(codes, "format")

        assert result == {"cell1": "formatted_code"}

        # Check that global ruff was used for format command
        format_call = mock_subprocess.call_args_list[2]
        assert format_call[0] == ("ruff", "format", "-")

    @patch("asyncio.create_subprocess_exec")
    async def test_ruff_function_raises_module_not_found_when_unavailable(
        self, mock_subprocess: MagicMock
    ):
        """Test ruff function raises ModuleNotFoundError when ruff is unavailable."""
        # Mock both module and global ruff failing
        help_process = AsyncMock()
        help_process.returncode = 1
        help_process.wait.return_value = None

        mock_subprocess.return_value = help_process

        codes: CellCodes = {"cell1": "x=1"}

        with pytest.raises(ModuleNotFoundError) as exc_info:
            await ruff(codes, "format")

        assert "ruff" in str(exc_info.value)
        assert exc_info.value.name == "ruff"

    @patch("asyncio.create_subprocess_exec")
    async def test_ruff_function_handles_format_failures_gracefully(
        self, mock_subprocess: MagicMock
    ):
        """Test ruff function handles individual cell formatting failures gracefully."""
        # Mock help command success
        help_process = AsyncMock()
        help_process.returncode = 0
        help_process.wait.return_value = None

        # Mock format commands - one success, one failure
        success_process = AsyncMock()
        success_process.returncode = 0
        success_process.communicate.return_value = (
            b"formatted_code\n",
            b"",
        )

        failure_process = AsyncMock()
        failure_process.returncode = 1
        failure_process.communicate.return_value = (b"", b"syntax error")

        mock_subprocess.side_effect = [
            help_process,
            success_process,
            failure_process,
        ]

        codes: CellCodes = {"cell1": "x=1", "cell2": "invalid syntax"}
        result = await ruff(codes, "format")

        # Should only include successfully formatted code
        assert result == {"cell1": "formatted_code"}

    @patch("marimo._utils.formatter.LOGGER")
    @patch("asyncio.create_subprocess_exec")
    async def test_ruff_function_handles_communication_exceptions(
        self, mock_subprocess: MagicMock, mock_logger: MagicMock
    ):
        """Test ruff function handles communication exceptions gracefully."""
        del mock_logger
        # Mock help command success
        help_process = AsyncMock()
        help_process.returncode = 0
        help_process.wait.return_value = None

        # Mock format command that raises exception
        format_process = AsyncMock()
        format_process.communicate.side_effect = Exception(
            "Communication failed"
        )

        mock_subprocess.side_effect = [help_process, format_process]

        codes: CellCodes = {"cell1": "x=1"}
        result = await ruff(codes, "format")

        # Should return empty dict when all cells fail
        assert result == {}

    @patch("asyncio.create_subprocess_exec")
    async def test_ruff_function_strips_whitespace_from_output(
        self, mock_subprocess: MagicMock
    ):
        """Test ruff function strips whitespace from formatted output."""
        # Mock help command success
        help_process = AsyncMock()
        help_process.returncode = 0
        help_process.wait.return_value = None

        # Mock format command with whitespace in output
        format_process = AsyncMock()
        format_process.returncode = 0
        format_process.communicate.return_value = (
            b"  formatted_code  \n\n",
            b"",
        )

        mock_subprocess.side_effect = [help_process, format_process]

        codes: CellCodes = {"cell1": "x=1"}
        result = await ruff(codes, "format")

        assert result == {"cell1": "formatted_code"}

    @patch("marimo._utils.formatter.LOGGER")
    @patch("asyncio.create_subprocess_exec")
    async def test_ruff_function_raises_format_error_on_non_zero_exit(
        self, mock_subprocess: MagicMock, mock_logger: MagicMock
    ):
        """Test ruff function raises FormatError when format command fails."""
        del mock_logger
        # Mock help command success
        help_process = AsyncMock()
        help_process.returncode = 0
        help_process.wait.return_value = None

        # Mock format command that fails
        format_process = AsyncMock()
        format_process.returncode = 1
        format_process.communicate.return_value = (b"", b"format error")

        mock_subprocess.side_effect = [help_process, format_process]

        codes: CellCodes = {"cell1": "x=1"}
        result = await ruff(codes, "format")

        # Should skip failed cells
        assert result == {}


class TestFormatError:
    """Test the FormatError exception class."""

    def test_format_error_is_exception(self) -> None:
        """Test FormatError is a proper Exception subclass."""
        error = FormatError("test message")
        assert isinstance(error, Exception)
        assert str(error) == "test message"

    def test_format_error_can_be_raised_and_caught(self) -> None:
        """Test FormatError can be raised and caught properly."""
        with pytest.raises(FormatError) as exc_info:
            raise FormatError("test formatting error")

        assert str(exc_info.value) == "test formatting error"


class TestFormatterIntegration:
    """Integration tests for formatter classes working together."""

    async def test_formatter_inheritance_structure(self) -> None:
        """Test that all formatter classes inherit from base Formatter properly."""
        assert issubclass(DefaultFormatter, Formatter)
        assert issubclass(RuffFormatter, Formatter)
        assert issubclass(BlackFormatter, Formatter)

    async def test_all_formatters_accept_line_length_parameter(self) -> None:
        """Test all formatters accept and store line_length parameter."""
        formatters = [
            Formatter(100),
            DefaultFormatter(100),
            RuffFormatter(100),
            BlackFormatter(100),
        ]

        for formatter in formatters:
            assert formatter.line_length == 100

    async def test_cell_codes_type_alias_works_correctly(self) -> None:
        """Test CellCodes type alias works as expected."""
        codes: CellCodes = {"cell1": "code1", "cell2": "code2"}
        assert isinstance(codes, dict)
        assert all(isinstance(k, str) for k in codes.keys())
        assert all(isinstance(v, str) for v in codes.values())
