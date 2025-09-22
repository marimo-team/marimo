# Copyright 2025 Marimo. All rights reserved.

from marimo._lint import run_check


def test_ignore_scripts_flag(tmp_path):
    """Test that --ignore-scripts suppresses errors for non-marimo files."""

    # Create a temporary non-marimo Python file
    temp_file = tmp_path / "test_script.py"
    temp_file.write_text("""#!/usr/bin/env python3

# This is a regular Python script, not a marimo notebook
import os
import sys

def main():
    print("Hello, world!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
""")

    # Test without ignore_scripts flag - should error
    linter_with_error = run_check((str(temp_file),), ignore_scripts=False)
    assert linter_with_error.errored is True
    assert len(linter_with_error.files) == 1
    assert linter_with_error.files[0].failed is True
    assert "not a valid notebook" in linter_with_error.files[0].message

    # Test with ignore_scripts flag - should not error
    linter_ignore = run_check((str(temp_file),), ignore_scripts=True)
    assert linter_ignore.errored is False
    assert len(linter_ignore.files) == 1
    assert linter_ignore.files[0].skipped is True
    assert "not a marimo notebook" in linter_ignore.files[0].message


def test_ignore_scripts_still_processes_marimo_files(tmp_path):
    """Test that --ignore-scripts still processes valid marimo files."""

    # Create a temporary marimo file
    temp_file = tmp_path / "test_notebook.py"
    temp_file.write_text("""import marimo

__generated_with = "0.15.5"
app = marimo.App()

@app.cell
def _():
    import marimo as mo
    return (mo,)

if __name__ == "__main__":
    app.run()
""")

    # Test with ignore_scripts flag - should still process marimo files
    linter = run_check((str(temp_file),), ignore_scripts=True)
    assert linter.errored is False
    assert len(linter.files) == 1
    assert linter.files[0].failed is False
    assert linter.files[0].skipped is False
