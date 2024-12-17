"""MkDocs macros for marimo documentation."""

import re
from pathlib import Path
from typing import Any


def define_env(env: Any):
    """Hook function for MkDocs macros plugin."""

    @env.macro
    def create_marimo_embed(code: str, size: str = "medium"):
        """Convert a marimo code snippet into a markdown code block.

        Args:
            code: The marimo code to embed
            size: The size of the embed ("small", "medium", or "large")
        """
        # Remove raw tags if present
        code = code.strip()
        code = re.sub(r"{%\s*raw\s*%}|{%\s*endraw\s*%}", "", code)

        # Remove ```python if present
        code = code.strip()
        if code.startswith("```python"):
            code = code[9:]  # first 9 characters are ```python
            code = code[:-3]  # last 3 characters are ```

        # Normalize size
        size = size.lower()
        if size not in ["small", "medium", "large"]:
            size = "medium"

        # Create markdown code block
        return create_marimo_iframe(code, size)

    @env.filter
    def convert_raw_block(text: str) -> str:
        """Convert Jinja2 raw blocks to plain text."""
        return re.sub(r"{%\s*raw\s*%}|{%\s*endraw\s*%}", "", text)

    @env.macro
    def include_file(filename: str) -> str:
        """Include a file's contents."""
        file_path = Path(env.conf["docs_dir"]) / filename
        if not file_path.exists():
            return f"Error: File {filename} not found"
        with open(file_path, "r") as f:
            return f.read()


import urllib.parse


def uri_encode_component(code: str) -> str:
    return urllib.parse.quote(code, safe="~()*!.'")


def create_marimo_iframe(
    code: str,
    size: str = "default",
    mode: str = "read",
    app_width: str = "normal",
) -> str:
    header = "\n".join(
        [
            "import marimo",
            f'app = marimo.App(width="{app_width}")',
            "",
        ]
    )
    footer = "\n".join(
        [
            "",
            "@app.cell",
            "def __():",
            "    import marimo as mo",
            "    return",
        ]
    )
    body = header + code + footer
    encoded_code = uri_encode_component(body)

    return f"""<iframe
    class="demo {size}"
    src="https://marimo.app/?code={encoded_code}&embed=true&mode={mode}"
    allow="camera; geolocation; microphone; fullscreen; autoplay; encrypted-media; picture-in-picture; clipboard-read; clipboard-write"
    width="100%"
    frameBorder="0"
></iframe>"""
