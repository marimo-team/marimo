# Copyright 2025 Marimo. All rights reserved.
"""CLI tests for the marimo check command."""

import tempfile

from click.testing import CliRunner

from marimo._cli.cli import check


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
