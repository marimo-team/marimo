# Copyright 2025 Marimo. All rights reserved.
"""Unit tests for the run_check CLI integration."""

from pathlib import Path

from marimo._lint import FileStatus, Linter, run_check
from marimo._lint.diagnostic import Diagnostic, Severity


class TestRunCheck:
    """Test the run_check function and CLI integration."""

    def test_run_check_with_empty_files(self):
        """Test run_check with file patterns that match no files."""
        result = run_check(("nonexistent/**/*.py",))

        assert isinstance(result, Linter)
        assert len(result.files) == 0
        assert result.errored is False

    def test_run_check_with_unsupported_files(self, tmpdir):
        """Test run_check skips unsupported file types."""
        # Create a non-notebook file
        txt_file = Path(tmpdir) / "test.txt"
        txt_file.write_text("This is not a notebook")

        result = run_check((str(txt_file),))

        assert len(result.files) == 1
        assert result.files[0].skipped is True
        assert "not a notebook file" in result.files[0].message

    def test_run_check_with_empty_py_file(self, tmpdir):
        """Test run_check with an empty Python file."""
        py_file = Path(tmpdir) / "empty.py"
        py_file.write_text("")

        result = run_check((str(py_file),))

        assert len(result.files) == 1
        assert result.files[0].skipped is True
        assert "empty file" in result.files[0].message

    def test_run_check_with_valid_notebook(self, tmpdir):
        """Test run_check with a valid marimo notebook."""
        notebook_file = Path(tmpdir) / "notebook.py"
        notebook_content = """import marimo

__generated_with = "0.15.0"
app = marimo.App()

@app.cell
def __():
    x = 1
    return (x,)
"""
        notebook_file.write_text(notebook_content)

        result = run_check((str(notebook_file),))

        assert len(result.files) == 1
        assert result.files[0].skipped is False
        assert result.files[0].failed is False
        assert isinstance(result.files[0].diagnostics, list)

    def test_run_check_with_syntax_error(self, tmpdir):
        """Test run_check with a file containing syntax errors."""
        bad_file = Path(tmpdir) / "bad.py"
        bad_file.write_text(
            "import marimo\napp = marimo.App(\ndef broken(:\n    pass"
        )

        result = run_check((str(bad_file),))

        assert len(result.files) == 1
        assert result.files[0].failed is True
        assert "Failed to parse" in result.files[0].message
        assert len(result.files[0].details) > 0

    def test_run_check_with_glob_patterns(self, tmpdir):
        """Test run_check with glob patterns."""
        # Create multiple files
        py_file = Path(tmpdir) / "test.py"
        py_file.write_text("# empty notebook")

        md_file = Path(tmpdir) / "test.md"
        md_file.write_text("# Empty markdown")

        txt_file = Path(tmpdir) / "test.txt"
        txt_file.write_text("ignored")

        # Use glob pattern
        pattern = str(Path(tmpdir) / "*")
        result = run_check((pattern,))

        # Should find py and md files, skip txt
        assert len(result.files) == 3
        py_result = next(f for f in result.files if f.file.endswith(".py"))
        md_result = next(f for f in result.files if f.file.endswith(".md"))
        txt_result = next(f for f in result.files if f.file.endswith(".txt"))

        # py files with simple comments are not valid notebooks, so they fail parsing
        assert py_result.failed is True  # Not a valid notebook
        # md files with simple content might be processed differently
        assert (
            md_result.failed is False or md_result.skipped is True
        )  # Markdown files may be handled differently
        assert txt_result.skipped is True  # Not a notebook


class TestFileStatus:
    """Test the FileStatus class."""

    def test_file_status_initialization(self):
        """Test FileStatus initialization with defaults."""
        status = FileStatus(file="test.py")

        assert status.file == "test.py"
        assert status.diagnostics == []
        assert status.skipped is False
        assert status.failed is False
        assert status.message == ""
        assert status.details == []

    def test_file_status_with_diagnostics(self):
        """Test FileStatus with diagnostics."""
        diagnostic = Diagnostic(
            code="MB001",
            name="test-error",
            message="Test error",
            severity=Severity.BREAKING,
            cell_id=None,
            line=1,
            column=1,
            fixable=False,
        )

        status = FileStatus(file="test.py", diagnostics=[diagnostic])

        assert len(status.diagnostics) == 1
        assert status.diagnostics[0].code == "MB001"

    async def test_file_status_fix_no_fixable_diagnostics(self, tmpdir):
        """Test Linter.fix() with no fixable diagnostics."""
        test_file = Path(tmpdir) / "test.py"
        original_content = "# Original content"
        test_file.write_text(original_content)

        diagnostic = Diagnostic(
            message="Test error",
            cell_id=None,
            line=1,
            column=1,
            code="MB001",
            name="test-error",
            severity=Severity.BREAKING,
            fixable=False,  # Not fixable
        )

        # FileStatus needs notebook and contents for fix to work
        status = FileStatus(
            file=str(test_file),
            diagnostics=[diagnostic],
            notebook=None,  # No notebook means fix returns False
            contents=original_content,
        )

        # Since no notebook, fix should return False (no changes)
        linter = Linter()
        result = await linter.fix(status)
        assert result is False

        # File should remain unchanged
        assert test_file.read_text() == original_content

    async def test_file_status_fix_with_fixable_diagnostics(self, tmpdir):
        """Test Linter.fix() with fixable diagnostics (but no notebook)."""
        test_file = Path(tmpdir) / "test.py"
        original_content = "# Original content"
        test_file.write_text(original_content)

        diagnostic = Diagnostic(
            message="Formatting error",
            cell_id=None,
            line=1,
            column=1,
            code="MF001",
            name="formatting-error",
            severity=Severity.FORMATTING,
            fixable=True,  # Fixable
        )

        # FileStatus needs notebook and contents for fix to work
        status = FileStatus(
            file=str(test_file),
            diagnostics=[diagnostic],
            notebook=None,  # No notebook means fix returns False
            contents=original_content,
        )

        # Since no notebook, fix should return False (no changes)
        linter = Linter()
        result = await linter.fix(status)
        assert result is False

        # File should remain unchanged
        assert test_file.read_text() == original_content

    async def test_file_status_fix_with_multiple_diagnostics(self, tmpdir):
        """Test Linter.fix() with multiple diagnostics (but no notebook)."""
        test_file = Path(tmpdir) / "test.py"
        original_content = "# Original content"
        test_file.write_text(original_content)

        diagnostics = [
            Diagnostic(
                message="Formatting",
                cell_id=None,
                line=1,
                column=1,
                code="MF001",
                name="formatting-error",
                severity=Severity.FORMATTING,
                fixable=True,
            ),
            Diagnostic(
                message="Breaking",
                cell_id=None,
                line=2,
                column=1,
                code="MB001",
                name="breaking-error",
                severity=Severity.BREAKING,
                fixable=True,
            ),
            Diagnostic(
                message="Runtime",
                cell_id=None,
                line=3,
                column=1,
                code="MR001",
                name="runtime-error",
                severity=Severity.RUNTIME,
                fixable=True,
            ),
        ]

        # FileStatus needs notebook and contents for fix to work
        status = FileStatus(
            file=str(test_file),
            diagnostics=diagnostics,
            notebook=None,  # No notebook means fix returns False
            contents=original_content,
        )

        # Since no notebook, fix should return False (no changes)
        linter = Linter()
        result = await linter.fix(status)
        assert result is False

        # File should remain unchanged
        assert test_file.read_text() == original_content


class TestLinter:
    """Test the Linter class."""

    def test_check_result_initialization(self):
        """Test Linter initialization."""
        result = Linter()

        assert result.files == []
        assert result.errored is False

    def test_check_result_with_files(self):
        """Test Linter with file status objects added to files list."""
        file_status = FileStatus(file="test.py")
        result = Linter()

        # Manually add files and set errored (simulating after run)
        result.files.append(file_status)
        result.errored = True

        assert len(result.files) == 1
        assert result.files[0].file == "test.py"
        assert result.errored is True


class TestIntegration:
    """Integration tests combining multiple components."""

    def test_full_workflow_with_notebook_violations(self, tmpdir):
        """Test the full workflow with a notebook that has violations."""
        notebook_file = Path(tmpdir) / "bad_notebook.py"

        # Create a notebook with violations (missing __generated_with)
        notebook_content = """import marimo

app = marimo.App()

# This violates marimo structure - code outside cell
x = 1

@app.cell
def __():
    y = 2
    return (y,)
"""
        notebook_file.write_text(notebook_content)

        result = run_check((str(notebook_file),))

        assert len(result.files) == 1
        file_status = result.files[0]

        assert not file_status.skipped
        assert not file_status.failed
        assert len(file_status.diagnostics) > 0

        # Should have formatting violations
        assert any(
            d.severity == Severity.FORMATTING for d in file_status.diagnostics
        )

        # Test fixing (if notebook is available)
        if file_status.notebook is not None:
            # Use Linter.fix() method
            import asyncio

            linter = Linter()
            result = asyncio.run(linter.fix(file_status))
            assert isinstance(result, bool)

    def test_error_handling_in_run_check(self, tmpdir):
        """Test error handling in run_check."""
        # Test by providing invalid content that will cause parsing to fail
        test_file = Path(tmpdir) / "test.py"
        # Write invalid Python content that will cause an exception
        test_file.write_text(
            "import marimo\napp = marimo.App()\ndef broken(:\n    pass"
        )

        result = run_check((str(test_file),))

        assert len(result.files) == 1
        assert result.files[0].failed is True
        # Note: errored might not be True as we changed error handling
        assert "Failed to parse" in result.files[0].message

    def test_run_check_with_nonexistent_file_pattern(self):
        """Test run_check with a specific nonexistent file."""
        result = run_check(("nonexistent_file.py",))

        assert isinstance(result, Linter)
        assert len(result.files) == 1  # Should create a failed file status
        assert result.files[0].failed is True
        assert "File not found" in result.files[0].message

    def test_run_check_with_nonexistent_directory_pattern(self):
        """Test run_check with nonexistent directory patterns."""
        result = run_check(("nonexistent_dir/**/*.py",))

        assert isinstance(result, Linter)
        assert len(result.files) == 0
        assert result.errored is False
