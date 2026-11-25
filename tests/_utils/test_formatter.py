# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import subprocess
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from inline_snapshot import snapshot

from marimo._dependencies.dependencies import DependencyManager
from marimo._utils.formatter import (
    BlackFormatter,
    CellCodes,
    DefaultFormatter,
    FormatError,
    Formatter,
    RuffFormatter,
    ruff,
)

HAS_RUFF = DependencyManager.ruff.has() or DependencyManager.which("ruff")


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
        mock_instance.format.assert_called_once_with(
            codes, stdin_filename=None
        )
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
        """Test RuffFormatter wraps cell code before formatting."""
        import textwrap

        mock_ruff.return_value = {"cell1": "def _():\n    x = 1"}
        formatter = RuffFormatter(line_length=100)
        codes: CellCodes = {"cell1": "x=1"}

        result = await formatter.format(codes)

        wrapped_codes: CellCodes = {
            "cell1": "def _():\n" + textwrap.indent("x=1", "    ")
        }
        mock_ruff.assert_called_once_with(
            wrapped_codes,
            "format",
            "--line-length",
            "100",
            stdin_filename=None,
        )
        assert result == {"cell1": "x = 1"}

    @patch("marimo._utils.formatter.ruff")
    async def test_ruff_formatter_passes_stdin_filename(
        self, mock_ruff: MagicMock
    ) -> None:
        """Test RuffFormatter forwards notebook filename for config discovery."""
        import textwrap

        mock_ruff.return_value = {"cell1": "def _():\n    x = 1"}
        formatter = RuffFormatter(line_length=100)
        codes: CellCodes = {"cell1": "x=1"}

        result = await formatter.format(
            codes, stdin_filename="/tmp/notebook.py"
        )

        wrapped_codes: CellCodes = {
            "cell1": "def _():\n" + textwrap.indent("x=1", "    ")
        }
        mock_ruff.assert_called_once_with(
            wrapped_codes,
            "format",
            "--line-length",
            "100",
            stdin_filename="/tmp/notebook.py",
        )
        assert result == {"cell1": "x = 1"}

    @patch("marimo._utils.formatter.ruff")
    async def test_ruff_formatter_nested_function_single_blank_line(
        self, mock_ruff: MagicMock
    ) -> None:
        """Regression test for #9848: nested functions get 1 blank line (function
        scope), not 2 (file scope). The wrap/unwrap logic ensures ruff sees cell
        code as a function body, not a module."""
        cell_code = "x = 3\ndef _foo():\n    return x + 1\nprint(_foo())"
        # Ruff formats the wrapped cell with 1 blank line around the nested def
        wrapped_formatted = "def _():\n    x = 3\n\n    def _foo():\n        return x + 1\n\n    print(_foo())"
        mock_ruff.return_value = {"cell1": wrapped_formatted}

        formatter = RuffFormatter(line_length=88)
        result = await formatter.format({"cell1": cell_code})

        # Unwrapped result must have exactly 1 blank line before and after _foo,
        # not 2 (which file-scope ruff would produce without the wrap).
        output = result["cell1"]
        assert (
            output == "x = 3\n\ndef _foo():\n    return x + 1\n\nprint(_foo())"
        )
        assert "\n\n\n" not in output

    @patch("marimo._utils.formatter.ruff")
    async def test_ruff_formatter_app_function_cell(
        self, mock_ruff: MagicMock
    ) -> None:
        """Regression test: @app.function cells (top-level function definitions)
        are wrapped before formatting so ruff applies E301 (nested defs get
        1 blank line), not E302 (top-level defs get 2 blank lines)."""
        cell_code = 'def foo():\n    """Something here"""'
        wrapped_formatted = (
            'def _():\n    def foo():\n        """Something here"""'
        )
        mock_ruff.return_value = {"cell1": wrapped_formatted}

        formatter = RuffFormatter(line_length=88)
        result = await formatter.format({"cell1": cell_code})

        assert result == {"cell1": 'def foo():\n    """Something here"""'}

    @patch("marimo._utils.formatter.ruff")
    async def test_ruff_formatter_preserves_class_decorator(
        self, mock_ruff: MagicMock
    ) -> None:
        cell_code = (
            "@dataclasses.dataclass\nclass Test:\n    name: str\n    age: int"
        )
        wrapped_formatted = (
            "def _():\n"
            "    @dataclasses.dataclass\n"
            "    class Test:\n"
            "        name: str\n"
            "        age: int"
        )
        mock_ruff.return_value = {"cell1": wrapped_formatted}

        formatter = RuffFormatter(line_length=88)
        result = await formatter.format({"cell1": cell_code})

        assert result == {"cell1": cell_code}

    @pytest.mark.skipif(not HAS_RUFF, reason="ruff not installed")
    async def test_ruff_formatter_preserves_comments(self) -> None:
        """Regression test for #10054/#10057: comments must survive the real
        wrap -> ruff -> unwrap round-trip. Comments are not AST nodes, so a
        leading comment sits before the first body statement's lineno and a
        trailing comment sits after the last statement's end_lineno; both were
        previously dropped."""
        cell_code = "# leading comment\nx=1\ny = 2  # inline comment\n# interior comment\nz = 3  # last-line comment\n# trailing comment"

        result = await RuffFormatter(line_length=88).format({"c": cell_code})

        assert result["c"] == snapshot(
            """\
# leading comment
x = 1
y = 2  # inline comment
# interior comment
z = 3  # last-line comment
# trailing comment"""
        )

    @patch("marimo._utils.formatter.ruff")
    async def test_ruff_formatter_comment_only_cell(
        self, mock_ruff: MagicMock
    ) -> None:
        """Comment-only cells are left unwrapped (def _(): # comment is a
        syntax error) and passed through ruff unchanged."""
        cell_code = "# just a comment"
        mock_ruff.return_value = {"cell1": cell_code}

        formatter = RuffFormatter(line_length=88)
        result = await formatter.format({"cell1": cell_code})

        # ruff receives the comment unwrapped, not inside def _():
        mock_ruff.assert_called_once_with(
            {"cell1": cell_code},
            "format",
            "--line-length",
            "88",
            stdin_filename=None,
        )
        assert result == {"cell1": cell_code}

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

    @patch("marimo._utils.formatter._ruff_binary", return_value="/bin/ruff")
    @patch("marimo._utils.formatter._run_subprocess_safe")
    async def test_command_preserves_filename(self, run, binary):
        del binary
        run.return_value = (b"x = 1\n", b"", 0)
        assert await ruff(
            {"a": "x=1"},
            "format",
            "--line-length",
            "88",
            stdin_filename="/project/notebook.py",
        ) == {"a": "x = 1"}
        run.assert_awaited_once_with(
            "/bin/ruff",
            "format",
            "--line-length",
            "88",
            "--stdin-filename",
            "/project/notebook.py",
            "-",
            input_data=b"x=1",
        )

    @patch("marimo._utils.formatter._ruff_binary", return_value="/bin/ruff")
    async def test_bounded_concurrency_and_failure_isolation(self, binary):
        del binary
        active = 0
        peak = 0

        async def run(*_args: str, input_data: bytes):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.001)
            active -= 1
            if input_data == b"invalid":
                return b"", b"syntax error", 1
            return input_data + b"\n", b"", 0

        codes = {str(i): str(i) for i in range(32)}
        codes["bad"] = "invalid"
        with patch(
            "marimo._utils.formatter._run_subprocess_safe", side_effect=run
        ):
            result = await ruff(codes, "format")
        assert result == {
            key: value for key, value in codes.items() if key != "bad"
        }
        assert 1 < peak <= 8

    @patch("marimo._utils.formatter._run_subprocess_safe")
    @patch("marimo._utils.formatter._ruff_binary", return_value="/bin/ruff")
    async def test_process_budget(self, binary, run):
        del binary
        run.return_value = (b"x = 1", b"", 0)
        assert await ruff({}, "format") == {}
        run.assert_not_called()
        codes = {str(i): "x=1" for i in range(100)}
        assert len(await ruff(codes, "format")) == 100
        assert run.await_count == 100
        assert all(
            call.args == ("/bin/ruff", "format", "-")
            for call in run.call_args_list
        )

    async def test_cancelled_subprocess_is_killed_and_drained(self):
        from marimo._utils.formatter import _run_subprocess_safe

        started = asyncio.Event()
        process = MagicMock(returncode=None)

        async def communicate(input_data=None):
            del input_data
            started.set()
            await asyncio.Event().wait()

        process.communicate = AsyncMock(side_effect=communicate)
        with patch("asyncio.create_subprocess_exec", return_value=process):
            task = asyncio.create_task(_run_subprocess_safe("ruff"))
            await started.wait()
            process.communicate.side_effect = None
            process.communicate.return_value = (b"", b"")
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        process.kill.assert_called_once_with()
        assert process.communicate.await_count == 2

    def test_binary_resolution_is_cached(self):
        from marimo._utils.formatter import _ruff_binary

        _ruff_binary.cache_clear()
        try:
            with patch(
                "marimo._utils.formatter.subprocess.check_output",
                return_value="/venv/ruff\n",
            ) as find:
                assert _ruff_binary() == "/venv/ruff"
                assert _ruff_binary() == "/venv/ruff"
                assert find.call_count == 1
                assert find.call_args.args[0][:3] == [
                    sys.executable,
                    "-I",
                    "-c",
                ]
        finally:
            _ruff_binary.cache_clear()

    @pytest.mark.parametrize("binary", ["/global/ruff", None])
    def test_binary_fallback(self, binary):
        from marimo._utils.formatter import _ruff_binary

        _ruff_binary.cache_clear()
        try:
            with (
                patch(
                    "marimo._utils.formatter.subprocess.check_output",
                    side_effect=subprocess.CalledProcessError(1, "python"),
                ),
                patch(
                    "marimo._utils.formatter.shutil.which", return_value=binary
                ),
            ):
                if binary:
                    assert _ruff_binary() == binary
                else:
                    with pytest.raises(ModuleNotFoundError):
                        _ruff_binary()
        finally:
            _ruff_binary.cache_clear()

    @pytest.mark.skipif(not HAS_RUFF, reason="ruff not installed")
    async def test_local_ruff_module_is_not_imported(
        self, tmp_path, monkeypatch
    ):
        from marimo._utils.formatter import _ruff_binary

        (tmp_path / "ruff.py").write_text(
            'raise RuntimeError("project module must not execute")\n'
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.syspath_prepend(str(tmp_path))
        monkeypatch.delitem(sys.modules, "ruff", raising=False)
        monkeypatch.delitem(sys.modules, "ruff.__main__", raising=False)
        _ruff_binary.cache_clear()
        try:
            assert await ruff({"a": "x=1"}, "format") == {"a": "x = 1"}
            assert "ruff" not in sys.modules
        finally:
            _ruff_binary.cache_clear()

    @pytest.mark.skipif(not HAS_RUFF, reason="ruff not installed")
    async def test_project_configuration_and_invalid_cell(self, tmp_path):
        (tmp_path / "ruff.toml").write_text(
            '[format]\nquote-style = "single"\n'
        )
        assert await RuffFormatter(88).format(
            {"valid": 'x="hello"', "invalid": "x = ("},
            stdin_filename=str(tmp_path / "notebook.py"),
        ) == {"valid": "x = 'hello'"}

    @patch("asyncio.to_thread")
    @patch("asyncio.create_subprocess_exec")
    async def test_run_subprocess_safe_falls_back_on_windows(
        self, mock_subprocess_exec: MagicMock, mock_to_thread: MagicMock
    ):
        """Test _run_subprocess_safe falls back to subprocess.run on Windows."""
        from marimo._utils.formatter import _run_subprocess_safe

        # Mock asyncio.create_subprocess_exec to raise NotImplementedError (Windows behavior)
        mock_subprocess_exec.side_effect = NotImplementedError()

        # Mock asyncio.to_thread to return subprocess result
        mock_to_thread.return_value = (b"output", b"error", 0)

        result = await _run_subprocess_safe("python", "--version")

        assert result == (b"output", b"error", 0)
        mock_to_thread.assert_called_once()


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
        assert all(isinstance(k, str) for k in codes)
        assert all(isinstance(v, str) for v in codes.values())
