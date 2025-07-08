# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import http.server
import re
import shutil
import socketserver
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Any

import pytest

from marimo._server.utils import find_free_port
from marimo._utils.platform import is_windows
from tests.mocks import snapshotter

snapshot = snapshotter(__file__)


# HTTP server for testing remote file conversion
class MockHTTPServer:
    def __init__(self, directory: Path, port: int):
        self.directory = directory
        self.port = port
        self.server = None
        self.thread = None

    def start(self):
        # Create a simple HTTP server that serves files from the directory
        directory = self.directory  # Create a local reference to directory

        class CustomHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                super().__init__(*args, directory=str(directory), **kwargs)

        self.server = socketserver.TCPServer(
            ("localhost", self.port), CustomHandler
        )

        # Run server in a separate thread
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        if self.thread:
            self.thread.join()

    def get_url(self, path: str) -> str:
        return f"http://localhost:{self.port}/{path}"


@pytest.fixture(scope="session")
def http_server():
    tmp_path = tempfile.mkdtemp()
    port = find_free_port(1234)
    server = MockHTTPServer(Path(tmp_path), port=port)
    server.start()
    yield server
    server.stop()
    shutil.rmtree(tmp_path)


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

    @staticmethod
    def test_convert_remote_ipynb(http_server: MockHTTPServer) -> None:
        # Create a notebook file
        notebook_path = http_server.directory / "remote_notebook.ipynb"
        notebook_content = """
{
 "cells": [
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "print('Hello from Remote Notebook!')"
   ]
  }
 ],
 "metadata": {},
 "nbformat": 4,
 "nbformat_minor": 4
}
"""
        notebook_path.write_text(notebook_content)

        # Convert remote file
        p = subprocess.run(
            [
                "marimo",
                "convert",
                http_server.get_url("remote_notebook.ipynb"),
            ],
            capture_output=True,
            text=True,
        )
        assert p.returncode == 0, p.stderr
        output = p.stdout
        output = re.sub(r"__generated_with = .*", "", output)
        snapshot("remote_ipynb_to_marimo.txt", output)

    @staticmethod
    @pytest.mark.skipif(
        is_windows(),
        reason="Markdown conversion adds extra new line on Windows",
    )
    def test_convert_remote_markdown(http_server: MockHTTPServer) -> None:
        # Create a markdown file
        md_path = http_server.directory / "remote_markdown.md"
        md_content = """
# Remote Markdown Test

```python
print('Hello from Remote Markdown!')
```
"""
        md_path.write_text(md_content)

        # Convert remote file
        p = subprocess.run(
            [
                "marimo",
                "convert",
                http_server.get_url("remote_markdown.md"),
            ],
            capture_output=True,
            text=True,
        )
        assert p.returncode == 0, p.stderr
        output = p.stdout
        output = re.sub(r"__generated_with = .*", "", output)
        snapshot("remote_markdown_to_marimo.txt", output)

    @staticmethod
    def test_convert_remote_invalid_file(http_server: MockHTTPServer) -> None:
        # Create an invalid file
        invalid_file = http_server.directory / "invalid.txt"
        invalid_file.write_text(
            "This is not a valid notebook or markdown file"
        )

        # Try to convert invalid remote file
        p = subprocess.run(
            ["marimo", "convert", http_server.get_url("invalid.txt")],
            capture_output=True,
            text=True,
        )
        assert p.returncode != 0
        assert "File must be an .ipynb or .md file" in p.stderr

    @staticmethod
    def test_convert_nonexistent_remote_file(
        http_server: MockHTTPServer,
    ) -> None:
        # Try to convert non-existent remote file
        p = subprocess.run(
            [
                "marimo",
                "convert",
                http_server.get_url("nonexistent.ipynb"),
            ],
            capture_output=True,
            text=True,
        )
        assert p.returncode != 0
        # The error message will be from urllib.error.HTTPError
        assert "HTTP Error 404" in p.stderr or "Not Found" in p.stderr
