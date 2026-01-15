# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Optional, Union
from urllib.parse import quote

from marimo._ast import codegen
from marimo._ast.compiler import extract_markdown

if TYPE_CHECKING:
    from marimo._ast.cell import Cell, CellImpl


# --- Format conversion utilities ---


def markdown_to_marimo(source: str) -> str:
    # NB. This should be kept in sync with the logic in
    # frontend/src/core/codemirror/language/languages/markdown.ts
    # ::transformOut
    source = source.replace('"""', '\\"\\"\\"')

    # 6 quotes in a row breaks
    if not source:
        source = " "
    return codegen.construct_markdown_call(source, '"""', "r")


def sql_to_marimo(
    source: str,
    table: str,
    hide_output: bool = False,
    engine: str | None = None,
) -> str:
    terminal_options = [codegen.indent_text('"""')]
    if hide_output:
        terminal_options.append(codegen.indent_text("output=False"))
    if engine:
        terminal_options.append(codegen.indent_text(f"engine={engine}"))

    return "\n".join(
        [
            f"{table} = mo.sql(",
            # f-string: expected for sql
            codegen.indent_text('f"""'),
            codegen.indent_text(source),
            ",\n".join(terminal_options),
            ")",
        ]
    )


def get_markdown_from_cell(
    cell: Union[CellImpl, Cell], code: str
) -> Optional[str]:
    """Attempt to extract markdown from a cell, or return None"""

    if not (cell.refs == {"mo"} and not cell.defs):
        return None
    return extract_markdown(code)


# --- Filename utilities ---


def get_filename(filename: Optional[str], default: str = "notebook.py") -> str:
    if not filename:
        filename = default
    return filename


def get_download_filename(filename: Optional[str], extension: str) -> str:
    filename = filename or f"notebook.{extension}"
    basename = os.path.basename(filename)
    if basename.endswith(f".{extension}"):
        return basename
    return f"{os.path.splitext(basename)[0]}.{extension}"


def make_download_headers(filename: str) -> dict[str, str]:
    """Create headers for file download with proper Content-Disposition encoding.

    This function handles non-ASCII filenames using RFC 5987 encoding
    (filename*=UTF-8''...) to avoid UnicodeEncodeError when the filename
    contains characters outside the Latin-1 range.

    Args:
        filename: The filename for the download (may contain non-ASCII chars)

    Returns:
        A dict with the Content-Disposition header properly encoded
    """
    # URL-encode the filename for RFC 5987 (preserves safe chars like .)
    encoded_filename = quote(filename, safe="")

    # Use RFC 5987 encoding: filename*=UTF-8''<url-encoded-filename>
    # Also provide a fallback ASCII filename for older clients
    return {
        "Content-Disposition": (
            f"attachment; filename*=UTF-8''{encoded_filename}"
        )
    }
