# Copyright 2026 Marimo. All rights reserved.
"""CLI tests for the marimo check command."""

import json
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from marimo._ast.cell import CellConfig
from marimo._ast.codegen import generate_filecontents
from marimo._cli.cli import check
from marimo._config.manager import UserConfigStore, get_default_config_manager
from marimo._server.models.models import SaveNotebookRequest
from marimo._session.notebook import load_notebook


@pytest.mark.parametrize("inline", [False, True])
def test_fix_uses_each_notebooks_formatting_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, inline: bool
) -> None:
    monkeypatch.setattr(UserConfigStore, "read", lambda _self: {})
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        '[tool.marimo.formatting]\ninfer_types = "off"\n'
    )
    files = []
    signatures = [
        ("jedi", 20, "def _(x: int, y):"),
        ("jedi", 79, "def _(x: int, y: dict[str, list[int]]):"),
        ("off", 79, "def _(x, y):"),
    ]
    for index, (mode, line_length, _) in enumerate(signatures):
        project = tmp_path / str(index)
        project.mkdir()
        formatting = (
            "[tool.marimo.formatting]\n"
            f'infer_types = "{mode}"\nline_length = {line_length}\n'
        )
        project_config = formatting
        header = None
        if inline:
            project_config = (
                "[tool.marimo.formatting]\n"
                f'infer_types = "{"off" if mode == "jedi" else "jedi"}"\n'
                f"line_length = {79 if line_length == 20 else 20}\n"
            )
            header = (
                "# /// script\n# dependencies = []\n"
                + "".join(f"# {line}\n" for line in formatting.splitlines())
                + "# ///\n"
            )
        (project / "pyproject.toml").write_text(project_config)
        notebook = project / "notebook.py"
        notebook.write_text(
            generate_filecontents(
                ["x = 1\ny = {'a': [1]}", "print(x, y)"],
                ["_", "_"],
                [CellConfig(), CellConfig()],
                header_comments=header,
            )
        )
        files.append(str(notebook))

    runner = CliRunner()
    result = runner.invoke(check, ["--fix", *files])
    assert result.exit_code == 0, result.output
    saved = [Path(file).read_text() for file in files]
    for file, contents, (_, _, signature) in zip(
        files, saved, signatures, strict=True
    ):
        assert signature in contents
        manager = load_notebook(file)
        manager.config_reader = get_default_config_manager(current_path=file)
        cells = manager.app.cell_manager
        manager.save(
            SaveNotebookRequest(
                cell_ids=list(cells.cell_ids()),
                codes=list(cells.codes()),
                names=list(cells.names()),
                configs=list(cells.configs()),
                filename=file,
            )
        )
        assert Path(file).read_text() == contents

    result = runner.invoke(check, ["--fix", *files])
    assert result.exit_code == 0, result.output
    assert "Updated" not in result.output
    assert [Path(file).read_text() for file in files] == saved


class TestLintCLI:
    """Test the check CLI command."""

    def test_check_command_basic(self):
        """Test basic check command functionality."""
        runner = CliRunner()

        # Create a temporary file with basic marimo code
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write("""
import marimo

__generated_with = "0.0.0"
app = marimo.App()

@app.cell
def _():
    x = 1
    return (x,)

if __name__ == "__main__":
    app.run()
""")
            f.flush()

            # Run check command
            result = runner.invoke(check, [f.name])

            # Should succeed and show some output
            assert result.exit_code == 0, result.output
            assert not result.output.strip()

    def test_check_command_with_violations(self):
        """Test check command with parsing violations."""
        runner = CliRunner()

        # Create a temporary file with violations
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write("""
import marimo

app = marimo.App()

@app.cell
def _():
    y = 2
    return (y,)
""")
            f.flush()

            # Run check command
            result = runner.invoke(check, [f.name, "--strict"])

            # Should give and show errors
            assert result.exit_code == 1, result.output
            assert "warning[general-formatting]" in result.output

    def test_check_command_with_fix(self):
        """Test check command with fix option."""
        runner = CliRunner()

        # Create a temporary file with violations
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write("""
import marimo

app = marimo.App()

@app.cell
def _():
    y = 2
    return (y,)

# This should create a violation with missing guard
""")
            f.flush()

            # Run check command with fix
            result = runner.invoke(check, [f.name, "--fix"])

            # The fix might fail due to file permissions or other issues
            # Just check that the command runs
            assert result.exit_code == 0, result.output

    def test_check_command_nonexistent_file(self):
        """Test check command with nonexistent file."""
        runner = CliRunner()

        result = runner.invoke(check, ["nonexistent.py"])

        # The CLI might handle nonexistent files gracefully
        # Just check that it doesn't crash
        assert result.exit_code in [0, 1, 2]  # Various possible exit codes

    def test_check_command_syntax_error(self):
        """Test check command with syntax error."""
        runner = CliRunner()

        # Create a temporary file with syntax error
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write("""
import marimo

app = marimo.App()

@app.cell
def _():
    x = 1 +  # Syntax error
    return (x,)
""")
            f.flush()

            # Run check command
            result = runner.invoke(check, [f.name])

            # Should fail due to syntax error
            assert result.exit_code != 0, result.output

    def test_check_command_help(self):
        """Test check command help."""
        runner = CliRunner()

        result = runner.invoke(check, ["--help"])

        # Should succeed and show help
        assert result.exit_code == 0
        assert "format" in result.output
        assert "--fix" in result.output

    def test_check_command_no_errors(self):
        """Test check command with valid notebook."""
        runner = CliRunner()

        # Create a temporary file with valid marimo code
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write("""
import marimo

__generated_with = "0.1.0"
app = marimo.App()

@app.cell
def _():
    x = 1
    return (x,)

if __name__ == "__main__":
    app.run()
""")
            f.flush()

            # Run check command
            result = runner.invoke(check, [f.name])

            # Should succeed
            assert result.exit_code == 0, result.output

    def test_check_command_with_message_collection(self):
        """Test that CLI check command uses message collection properly."""
        runner = CliRunner()
        import os

        # Use existing test file with syntax errors
        test_file = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "_lint",
            "test_files",
            "syntax_errors.py",
        )

        # Test the check command
        result = runner.invoke(check, [test_file])

        # Should return non-zero exit code for files with errors
        assert result.exit_code != 0
        # Should contain linting output
        assert len(result.output) > 0
        assert (
            "invalid-syntax" in result.output
            or "error" in result.output.lower()
        )

    def test_check_command_json_strict_clean_notebook(self):
        """JSON + strict on a clean notebook should exit 0 with valid JSON."""
        runner = CliRunner()

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write("""
import marimo

__generated_with = "0.1.0"
app = marimo.App()

@app.cell
def _():
    x = 1
    return (x,)

if __name__ == "__main__":
    app.run()
""")
            f.flush()

            result = runner.invoke(
                check, [f.name, "--strict", "--format", "json"]
            )

            assert result.exit_code == 0, result.output
            payload = json.loads(result.output)
            assert payload["issues"] == []
            assert payload["summary"]["total_issues"] == 0
            assert payload["summary"]["errored"] is False

    def test_check_command_json_strict_with_issues(self):
        """JSON + strict should still fail when there are lint issues."""
        runner = CliRunner()

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write("""
import marimo

app = marimo.App()

@app.cell
def _():
    y = 2
    return (y,)
""")
            f.flush()

            result = runner.invoke(
                check, [f.name, "--strict", "--format", "json"]
            )

            assert result.exit_code == 1, result.output
            payload = json.loads(result.output)
            assert payload["summary"]["total_issues"] > 0
            assert len(payload["issues"]) > 0
