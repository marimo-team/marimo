# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import re
import subprocess
from typing import TYPE_CHECKING

from tests.mocks import snapshotter

snapshot = snapshotter(__file__)

if TYPE_CHECKING:
    from pathlib import Path


class TestConvert:
    @staticmethod
    def test_convert_ipynb(tmp_path: Path) -> None:
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

        p = subprocess.run(
            ["marimo", "convert", str(notebook_path)],
            capture_output=True,
            text=True,
        )
        assert p.returncode == 0, p.stderr
        output = p.stdout
        output = re.sub(r"__generated_with = .*", "", output)
        snapshot("ipynb_to_marimo.txt", output)

    @staticmethod
    def test_convert_markdown(tmp_path: Path) -> None:
        md_path = tmp_path / "test_markdown.md"
        md_content = """
# Test Markdown

print('Hello from Markdown!')
"""
        md_path.write_text(md_content)

        p = subprocess.run(
            ["marimo", "convert", str(md_path)],
            capture_output=True,
            text=True,
        )
        assert p.returncode == 0, p.stderr
        output = p.stdout
        output = re.sub(r"__generated_with = .*", "", output)
        snapshot("markdown_to_marimo.txt", output)

    @staticmethod
    def test_convert_with_output(tmp_path: Path) -> None:
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
    "print('Hello, Output!')"
   ]
  }
 ],
 "metadata": {},
 "nbformat": 4,
 "nbformat_minor": 4
}
"""
        notebook_path.write_text(notebook_content)
        output_path = tmp_path / "output.py"

        p = subprocess.run(
            ["marimo", "convert", str(notebook_path), "-o", str(output_path)],
            capture_output=True,
            text=True,
        )
        assert p.returncode == 0, p.stderr
        assert output_path.exists()
        output_content = output_path.read_text()
        output_content = re.sub(r"__generated_with = .*", "", output_content)
        snapshot("ipynb_to_marimo_with_output.txt", output_content)

    @staticmethod
    def test_convert_invalid_file(tmp_path: Path) -> None:
        invalid_file = tmp_path / "invalid.txt"
        invalid_file.touch()

        p = subprocess.run(
            ["marimo", "convert", str(invalid_file)],
            capture_output=True,
            text=True,
        )
        assert p.returncode != 0
        assert "File must be an .ipynb or .md file" in p.stderr
