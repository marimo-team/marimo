# Copyright 2025 Marimo. All rights reserved.
"""Unit tests for the JSON formatter."""

import json
from pathlib import Path

from marimo._lint import run_check
from marimo._lint.diagnostic import Diagnostic, Severity
from marimo._lint.formatters import JSONFormatter


class TestJSONFormatter:
    """Test the JSONFormatter class."""

    def test_json_formatter_basic(self):
        """Test basic JSON formatting of a diagnostic."""
        diagnostic = Diagnostic(
            message="Test error message",
            line=10,
            column=5,
            code="MB001",
            name="test-error",
            severity=Severity.BREAKING,
            fixable=False,
            fix="Test fix hint",
            cell_id=["test-cell-id"],
        )

        formatter = JSONFormatter()
        result = formatter.format(diagnostic, "test.py")

        # Parse JSON to verify it's valid
        data = json.loads(result)

        assert data["type"] == "diagnostic"
        assert data["message"] == "Test error message"
        assert data["filename"] == "test.py"
        assert data["line"] == 10
        assert data["column"] == 5
        assert data["severity"] == "breaking"
        assert data["name"] == "test-error"
        assert data["code"] == "MB001"
        assert data["fixable"] is False
        assert data["fix"] == "Test fix hint"
        assert data["cell_id"] == ["test-cell-id"]

    def test_json_formatter_multiple_lines_columns(self):
        """Test JSON formatting with multiple lines and columns."""
        diagnostic = Diagnostic(
            message="Multiple location error",
            line=[1, 5, 10],
            column=[1, 3, 7],
            code="MB002",
            name="multiple-definitions",
            severity=Severity.BREAKING,
            fixable=False,
            cell_id=["cell1", "cell2", "cell3"],
        )

        formatter = JSONFormatter()
        result = formatter.format(diagnostic, "multi.py")

        data = json.loads(result)

        assert data["type"] == "diagnostic"
        assert data["line"] == 1  # First line
        assert data["column"] == 1  # First column
        assert data["lines"] == [1, 5, 10]  # All lines
        assert data["columns"] == [1, 3, 7]  # All columns

    def test_json_formatter_minimal_diagnostic(self):
        """Test JSON formatting with minimal diagnostic information."""
        diagnostic = Diagnostic(
            message="Minimal error",
            line=1,
            column=1,
        )

        formatter = JSONFormatter()
        result = formatter.format(diagnostic, "minimal.py")

        data = json.loads(result)

        assert data["type"] == "diagnostic"
        assert data["message"] == "Minimal error"
        assert data["filename"] == "minimal.py"
        assert data["line"] == 1
        assert data["column"] == 1
        # Optional fields should not be present if None
        assert "code" not in data
        assert "name" not in data
        assert "severity" not in data
        assert "fixable" not in data
        assert "fix" not in data
        assert "cell_id" not in data

    def test_json_formatter_with_unsafe_fixable(self):
        """Test JSON formatting with unsafe fixable diagnostic."""
        diagnostic = Diagnostic(
            message="Unsafe fix available",
            line=5,
            column=2,
            code="MF001",
            name="empty-cell",
            severity=Severity.FORMATTING,
            fixable="unsafe",
            fix="Remove empty cell",
        )

        formatter = JSONFormatter()
        result = formatter.format(diagnostic, "unsafe.py")

        data = json.loads(result)

        assert data["type"] == "diagnostic"
        assert data["fixable"] == "unsafe"
        assert data["severity"] == "formatting"


class TestJSONFormatterIntegration:
    """Integration tests for JSON formatter with run_check."""

    def test_run_check_json_format_clean_file(self, tmp_path):
        """Test run_check with JSON format on a clean file."""
        tmpdir = tmp_path
        notebook_file = Path(tmpdir) / "clean.py"
        notebook_content = """import marimo

__generated_with = "0.15.0"
app = marimo.App()


@app.cell
def __():
    x = 1
    return (x,)


if __name__ == "__main__":
    app.run()
"""
        notebook_file.write_text(notebook_content)

        linter = run_check((str(notebook_file),), formatter="json")
        result = linter.get_json_result()

        assert "issues" in result
        assert "summary" in result
        # May have some diagnostics, but check structure is correct
        assert isinstance(result["issues"], list)
        assert result["summary"]["total_files"] == 1
        assert result["summary"]["fixed_issues"] == 0

    def test_run_check_json_format_with_issues(self, tmp_path):
        """Test run_check with JSON format on a file with issues."""
        tmpdir = tmp_path
        notebook_file = Path(tmpdir) / "issues.py"
        # Create notebook with duplicate variable definition
        notebook_content = """import marimo

__generated_with = "0.15.0"
app = marimo.App()

@app.cell
def __():
    import marimo as mo
    return

@app.cell
def __():
    import marimo as mo  # Duplicate definition
    return
"""
        notebook_file.write_text(notebook_content)

        linter = run_check((str(notebook_file),), formatter="json")
        result = linter.get_json_result()

        assert "issues" in result
        assert "summary" in result
        assert len(result["issues"]) > 0

        # Check first diagnostic structure
        diagnostic = result["issues"][0]
        assert diagnostic["type"] == "diagnostic"
        assert "message" in diagnostic
        assert "filename" in diagnostic
        assert "line" in diagnostic
        assert "column" in diagnostic
        assert "severity" in diagnostic
        assert "name" in diagnostic
        assert "code" in diagnostic

        assert diagnostic["filename"] == str(notebook_file)
        assert diagnostic["severity"] == "breaking"
        assert "multiple" in diagnostic["message"].lower()

        # Check summary
        summary = result["summary"]
        assert summary["total_files"] == 1
        assert summary["files_with_issues"] == 1
        assert summary["total_issues"] > 0
        assert summary["errored"] is True

    def test_run_check_json_format_multiple_files(self, tmp_path):
        """Test run_check with JSON format on multiple files."""
        tmpdir = tmp_path
        # Clean file
        clean_file = Path(tmpdir) / "clean.py"
        clean_file.write_text("""import marimo

__generated_with = "0.15.0"
app = marimo.App()

@app.cell
def __():
    x = 1
    return (x,)
""")

        # File with issues
        issues_file = Path(tmpdir) / "issues.py"
        issues_file.write_text("""import marimo

__generated_with = "0.15.0"
app = marimo.App()

@app.cell
def __():
    import marimo as mo
    return

@app.cell
def __():
    import marimo as mo  # Duplicate
    return
""")

        # Empty file (should be skipped)
        empty_file = Path(tmpdir) / "empty.py"
        empty_file.write_text("")

        pattern = str(Path(tmpdir) / "*.py")
        linter = run_check((pattern,), formatter="json")
        result = linter.get_json_result()

        summary = result["summary"]
        assert summary["total_files"] == 3  # All three files processed
        # At least the issues.py file has problems, possibly others
        assert summary["files_with_issues"] >= 1
        assert summary["total_issues"] > 0

        # Check that issues contain diagnostics
        issues = result["issues"]
        assert len(issues) > 0

        # Should have at least some diagnostics from the issues file
        issues_from_file = [
            d for d in issues if str(issues_file) in d["filename"]
        ]
        assert len(issues_from_file) > 0

    def test_json_result_is_valid_json(self, tmp_path):
        """Test that the complete JSON result is valid JSON."""
        tmpdir = tmp_path
        notebook_file = Path(tmpdir) / "test.py"
        notebook_content = """import marimo

__generated_with = "0.15.0"
app = marimo.App()

@app.cell
def __():
    x = 1
    y = 1  # Same variable name in different lines
    return

@app.cell
def __():
    x = 2  # Multiple definition
    return
"""
        notebook_file.write_text(notebook_content)

        linter = run_check((str(notebook_file),), formatter="json")
        result = linter.get_json_result()

        # Convert to JSON string and parse it back to verify validity
        json_string = json.dumps(result)
        parsed_back = json.loads(json_string)

        assert parsed_back == result
        assert "issues" in parsed_back
        assert "summary" in parsed_back
        assert isinstance(parsed_back["issues"], list)
        assert isinstance(parsed_back["summary"], dict)

    def test_json_formatter_handles_unicode(self):
        """Test that JSON formatter handles unicode characters properly."""
        diagnostic = Diagnostic(
            message="Error with unicode: 测试 émoji 🚀",
            line=1,
            column=1,
            code="MB001",
            name="unicode-test",
            severity=Severity.BREAKING,
        )

        formatter = JSONFormatter()
        result = formatter.format(diagnostic, "unicode_test.py")

        # Should not raise an exception
        data = json.loads(result)
        assert "测试 émoji 🚀" in data["message"]

    def test_diagnostic_format_method_json(self):
        """Test diagnostic.format() method with JSON formatter."""
        diagnostic = Diagnostic(
            message="Test diagnostic format method",
            line=5,
            column=10,
            code="MB001",
            name="test-format",
            severity=Severity.BREAKING,
            filename="test.py",
        )

        result = diagnostic.format(formatter="json")
        data = json.loads(result)

        assert data["type"] == "diagnostic"
        assert data["message"] == "Test diagnostic format method"
        assert data["filename"] == "test.py"
        assert data["line"] == 5
        assert data["column"] == 10
        assert data["code"] == "MB001"

    def test_diagnostic_format_method_full(self):
        """Test diagnostic.format() method with full formatter."""
        diagnostic = Diagnostic(
            message="Test diagnostic format method",
            line=5,
            column=10,
            code="MB001",
            name="test-format",
            severity=Severity.BREAKING,
            filename="test.py",
        )

        result = diagnostic.format(formatter="full")

        # Should be the full formatted string with colors and context
        assert "critical[test-format]" in result
        assert "Test diagnostic format method" in result
        assert "test.py:5:10" in result

    def test_json_formatter_empty_diagnostics_list(self, tmp_path):
        """Test JSON result structure when no diagnostics are found."""
        tmpdir = tmp_path
        # Create a file that doesn't exist to get empty results
        linter = run_check(("nonexistent/**/*.py",), formatter="json")
        result = linter.get_json_result()

        assert result["issues"] == []
        assert result["summary"]["total_files"] == 0
        assert result["summary"]["files_with_issues"] == 0
        assert result["summary"]["total_issues"] == 0
        assert result["summary"]["fixed_issues"] == 0
        assert result["summary"]["errored"] is False

    def test_json_format_file_not_found_error(self):
        """Test JSON format handling of missing files."""
        linter = run_check(("nonexistent_file.py",), formatter="json")
        result = linter.get_json_result()

        assert len(result["issues"]) == 1
        error = result["issues"][0]
        assert error["type"] == "error"
        assert error["filename"] == "nonexistent_file.py"
        assert "File not found" in error["error"]

        # Check summary includes the error
        assert result["summary"]["total_files"] == 1
        assert result["summary"]["files_with_issues"] == 1
        assert result["summary"]["errored"] is True

    def test_json_format_syntax_error(self, tmp_path):
        """Test JSON format handling of syntax errors."""
        tmpdir = tmp_path
        broken_file = Path(tmpdir) / "broken.py"
        broken_file.write_text("import marimo\ndef broken(\n    pass")

        linter = run_check((str(broken_file),), formatter="json")
        result = linter.get_json_result()

        assert len(result["issues"]) == 1
        error = result["issues"][0]
        assert error["type"] == "error"
        assert error["filename"] == str(broken_file)
        assert "Failed to parse" in error["error"]

        # Check summary includes the error
        assert result["summary"]["total_files"] == 1
        assert result["summary"]["files_with_issues"] == 1
        assert result["summary"]["errored"] is True

    def test_json_format_mixed_diagnostics_and_errors(self, tmp_path):
        """Test JSON format with both diagnostics and file errors."""
        tmpdir = tmp_path
        # Working file with linting issues
        working_file = Path(tmpdir) / "working.py"
        working_file.write_text("""import marimo

__generated_with = "0.16.1"
app = marimo.App()

@app.cell
def __():
    import marimo as mo
    return

@app.cell
def __():
    import marimo as mo  # Duplicate
    return

if __name__ == "__main__":
    app.run()
""")

        # Broken file
        broken_file = Path(tmpdir) / "broken.py"
        broken_file.write_text("import marimo\ndef broken(\n    pass")

        linter = run_check(
            (str(working_file), str(broken_file), "missing.py"),
            formatter="json",
        )
        result = linter.get_json_result()

        # Should have 3 issues: 1 diagnostic + 2 errors
        assert len(result["issues"]) == 3

        # Check diagnostic
        diagnostic_issues = [
            i for i in result["issues"] if i["type"] == "diagnostic"
        ]
        assert len(diagnostic_issues) == 1
        assert diagnostic_issues[0]["severity"] == "breaking"
        assert "multiple" in diagnostic_issues[0]["message"].lower()

        # Check errors
        error_issues = [i for i in result["issues"] if i["type"] == "error"]
        assert len(error_issues) == 2

        filenames = [e["filename"] for e in error_issues]
        assert str(broken_file) in filenames
        assert "missing.py" in filenames

        # Check summary
        assert result["summary"]["total_files"] == 3
        assert result["summary"]["files_with_issues"] == 3
        assert result["summary"]["errored"] is True
