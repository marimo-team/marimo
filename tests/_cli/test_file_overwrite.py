# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
import subprocess
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from marimo._config.settings import GLOBAL_SETTINGS


@pytest.fixture
def existing_file() -> Generator[str, None, None]:
    """Create a temporary file that already exists."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
        f.write(b"existing content")
        path = f.name

    try:
        yield path
    finally:
        if os.path.exists(path):
            os.unlink(path)


def test_export_overwrite_confirm(
    temp_marimo_file: str, existing_file: str
) -> None:
    """Test export command with file overwrite confirmation (user confirms)."""
    p = subprocess.Popen(
        [
            "marimo",
            "export",
            "html",
            temp_marimo_file,
            "--output",
            existing_file,
        ],
        stdin=subprocess.PIPE,
    )

    assert p.poll() is None
    assert p.stdin is not None

    # Simulate user confirming overwrite
    p.stdin.write(b"y\n")
    p.stdin.flush()

    # Wait for process to complete
    p.wait(timeout=5)

    # Check that the file was overwritten
    assert os.path.exists(existing_file)
    assert p.returncode == 0


def test_export_overwrite_with_yes_flag() -> None:
    """Test export command with -y flag to automatically overwrite files."""
    # Create a temporary directory and file
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create a simple marimo file
        marimo_file = Path(tmp_dir) / "test.py"
        marimo_file.write_text("""
import marimo
app = marimo.App()

@app.cell
def __():
    print("Hello, World!")
    return

if __name__ == "__main__":
    app.run()
""")

        # Create an existing output file
        output_file = Path(tmp_dir) / "output.html"
        output_file.write_text("initial content")

        # Use the -y flag to verify that the file can be overwritten without prompting
        result = subprocess.run(
            [
                "marimo",
                "-y",
                "export",
                "html",
                str(marimo_file),
                "--output",
                str(output_file),
            ],
            capture_output=True,
            text=True,
        )

        # Check that the command completed successfully
        assert result.returncode == 0

        # Verify the file was overwritten with -y flag
        assert output_file.read_text() != "initial content"

        # Verify there was no prompt in the output
        assert "Warning: The file" not in result.stdout
        assert "Overwrite?" not in result.stdout


def test_export_overwrite_behavior_with_noninteractive_terminal(
    temp_marimo_file: str, existing_file: str
) -> None:
    """Test export command behavior with non-interactive terminal.

    This test verifies that when stdout is not a TTY, the prompt_to_overwrite function
    automatically returns True and overwrites the file without prompting.
    """
    # First, ensure the file exists with known content
    with open(existing_file, "w") as f:
        f.write("initial content")

    # Run the export command without -y flag
    # In a non-interactive terminal (which is the case in tests), it should overwrite without prompting
    p = subprocess.run(
        [
            "marimo",
            "export",
            "html",
            temp_marimo_file,
            "--output",
            existing_file,
        ],
        capture_output=True,
        text=True,
    )

    # Check that the command completed successfully
    assert p.returncode == 0

    # Verify the file was overwritten even without explicit confirmation
    # This is expected behavior in non-interactive terminals
    assert os.path.exists(existing_file)

    # The content should be different from the initial content
    with open(existing_file) as f:
        content = f.read()
    assert content != "initial content"
    assert "<!DOCTYPE html>" in content


def test_convert_overwrite_confirm(tmp_path: Path) -> None:
    """Test convert command with file overwrite confirmation (user confirms)."""
    # Create a notebook file
    notebook_path = tmp_path / "test_notebook.ipynb"
    notebook_content = """
    {
     "cells": [
      {
       "cell_type": "code",
       "execution_count": null,
       "metadata": {},
       "outputs": [],
       "source": [
        "print('Hello, World!')"
       ]
      }
     ],
     "metadata": {},
     "nbformat": 4,
     "nbformat_minor": 4
    }
    """
    notebook_path.write_text(notebook_content)

    # Create an existing output file
    output_path = tmp_path / "output.py"
    output_path.write_text("existing content")

    p = subprocess.Popen(
        [
            "marimo",
            "convert",
            str(notebook_path),
            "-o",
            str(output_path),
        ],
        stdin=subprocess.PIPE,
    )

    assert p.poll() is None
    assert p.stdin is not None

    # Simulate user confirming overwrite
    p.stdin.write(b"y\n")
    p.stdin.flush()

    # Wait for process to complete
    p.wait(timeout=5)

    # Check that the file was overwritten
    assert output_path.exists()
    assert p.returncode == 0
    assert output_path.read_text() != "existing content"


def test_convert_with_yes_flag(tmp_path: Path) -> None:
    """Test convert command with -y flag to automatically overwrite files."""
    # Create a notebook file
    notebook_path = tmp_path / "test_notebook.ipynb"
    notebook_content = """
    {
     "cells": [
      {
       "cell_type": "code",
       "execution_count": null,
       "metadata": {},
       "outputs": [],
       "source": [
        "print('Hello, World!')"
       ]
      }
     ],
     "metadata": {},
     "nbformat": 4,
     "nbformat_minor": 4
    }
    """
    notebook_path.write_text(notebook_content)

    # Create an existing output file
    output_path = tmp_path / "output.py"
    output_path.write_text("existing content")

    # Use the -y flag to verify that the file can be overwritten without prompting
    result = subprocess.run(
        [
            "marimo",
            "-y",
            "convert",
            str(notebook_path),
            "-o",
            str(output_path),
        ],
        capture_output=True,
        text=True,
    )

    # Check that the command completed successfully
    assert result.returncode == 0

    # Verify the file was overwritten with -y flag
    assert output_path.read_text() != "existing content"

    # Verify there was no prompt in the output
    assert "Warning: The file" not in result.stdout
    assert "Overwrite?" not in result.stdout
