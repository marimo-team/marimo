# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import ast
import os
import re
from textwrap import dedent
from typing import Optional

from marimo._ast.cell import Cell
from marimo._server.file_manager import AppFileManager


def format_filename_title(filename: str) -> str:
    basename = os.path.basename(filename)
    name, ext = os.path.splitext(basename)
    title = re.sub("[-_]", " ", name)
    return title.title()


def get_filename(
    file_manager: AppFileManager, default: str = "notebook.py"
) -> str:
    filename = file_manager.filename
    if not filename:
        filename = default
    return filename


def get_app_title(file_manager: AppFileManager) -> str:
    if file_manager.app.config.app_title:
        return f"{file_manager.app.config.app_title}"
    filename = get_filename(file_manager)
    return format_filename_title(filename)


def get_download_filename(file_manager: AppFileManager, extension: str) -> str:
    filename = get_filename(file_manager, f"notebook.{extension}")
    basename = os.path.basename(filename)
    return f"{os.path.splitext(basename)[0]}.{extension}"


def _const_string(args: list[ast.stmt]) -> str:
    (inner,) = args
    if hasattr(inner, "values"):
        (inner,) = inner.values
    return f"{inner.value}"  # type: ignore[attr-defined]


def get_markdown_from_cell(
    cell: Cell, code: str, native_callout: bool = False
) -> Optional[str]:
    """Attempt to extract markdown from a cell, or return None"""

    if not (cell.refs == {"mo"} and not cell.defs):
        return None
    markdown_lines = [
        line for line in code.strip().split("\n") if line.startswith("mo.md(")
    ]
    if len(markdown_lines) > 1:
        return None

    code = code.strip()
    # Attribute Error handled by the outer try/except block.
    # Wish there was a more compact to ignore ignore[attr-defined] for all.
    try:
        (body,) = ast.parse(code).body
        callout = None
        if body.value.func.attr == "md":  # type: ignore[attr-defined]
            value = body.value  # type: ignore[attr-defined]
        elif body.value.func.attr == "callout":  # type: ignore[attr-defined]
            if not native_callout:
                return None
            if body.value.args:  # type: ignore[attr-defined]
                callout = _const_string(body.value.args)  # type: ignore[attr-defined]
            else:
                (keyword,) = body.value.keywords  # type: ignore[attr-defined]
                assert keyword.arg == "kind"
                callout = _const_string([keyword.value])  # type: ignore
            value = body.value.func.value  # type: ignore[attr-defined]
        else:
            return None
        assert value.func.value.id == "mo"
        md_lines = _const_string(value.args).split("\n")
    except (AssertionError, AttributeError, ValueError):
        # No reason to explicitly catch exceptions if we can't parse out
        # markdown. Just handle it as a code block.
        return None

    # Dedent behavior is a little different that in marimo js, so handle
    # accordingly.
    md_lines = [line.rstrip() for line in md_lines]
    md = dedent(md_lines[0]) + "\n" + dedent("\n".join(md_lines[1:]))
    md = md.strip()

    if callout:
        md = dedent(
            f"""
          ::: {{.callout-{callout}}}
          {md}
          :::"""
        )
    return md
