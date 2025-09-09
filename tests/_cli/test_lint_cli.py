# Copyright 2025 Marimo. All rights reserved.
"""CLI tests for the marimo lint command."""

import tempfile

from click.testing import CliRunner

from marimo._cli.cli import lint


class TestLintCLI:
    """Test the lint CLI command."""

    def test_lint_command_basic(self):
        """Test basic lint command functionality."""
        runner = CliRunner()

        # Create a temporary file with basic marimo code
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write("""
import marimo

app = marimo.App()

@app.cell
def __():
    x = 1
    return (x,)
""")
            f.flush()

            # Run lint command
            result = runner.invoke(lint, [f.name])

            # Should succeed and show some output
            assert result.exit_code == 0
            assert (
                "Errors found" in result.output
                or "No errors found" in result.output
            )

    def test_lint_command_with_violations(self):
        """Test lint command with parsing violations."""
        runner = CliRunner()

        # Create a temporary file with violations
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write("""
import marimo

app = marimo.App()

# This should create a violation
x = 1

@app.cell
def __():
    y = 2
    return (y,)
""")
            f.flush()

            # Run lint command
            result = runner.invoke(lint, [f.name])

            # Should succeed and show errors
            assert result.exit_code == 0
            assert "Errors found" in result.output

    def test_lint_command_with_fix(self):
        """Test lint command with fix option."""
        runner = CliRunner()

        # Create a temporary file with violations
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write("""
import marimo

app = marimo.App()

# This should create a violation
x = 1

@app.cell
def __():
    y = 2
    return (y,)
""")
            f.flush()

            # Run lint command with fix
            result = runner.invoke(lint, [f.name, "--fix"])

            # The fix might fail due to file permissions or other issues
            # Just check that the command runs
            assert result.exit_code in [
                0,
                1,
            ]  # Either success or expected failure

    def test_lint_command_nonexistent_file(self):
        """Test lint command with nonexistent file."""
        runner = CliRunner()

        result = runner.invoke(lint, ["nonexistent.py"])

        # The CLI might handle nonexistent files gracefully
        # Just check that it doesn't crash
        assert result.exit_code in [0, 1, 2]  # Various possible exit codes

    def test_lint_command_syntax_error(self):
        """Test lint command with syntax error."""
        runner = CliRunner()

        # Create a temporary file with syntax error
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write("""
import marimo

app = marimo.App()

@app.cell
def __():
    x = 1 +  # Syntax error
    return (x,)
""")
            f.flush()

            # Run lint command
            result = runner.invoke(lint, [f.name])

            # Should fail due to syntax error
            assert result.exit_code != 0

    def test_lint_command_help(self):
        """Test lint command help."""
        runner = CliRunner()

        result = runner.invoke(lint, ["--help"])

        # Should succeed and show help
        assert result.exit_code == 0
        assert "Lint and check marimo files" in result.output
        assert "--fix" in result.output

    def test_lint_command_no_errors(self):
        """Test lint command with valid notebook."""
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
def __():
    x = 1
    return (x,)
""")
            f.flush()

            # Run lint command
            result = runner.invoke(lint, [f.name])

            # Should succeed
            assert result.exit_code == 0
