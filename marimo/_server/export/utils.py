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
    name, _ext = os.path.splitext(basename)
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
    if basename.endswith(f".{extension}"):
        return basename
    return f"{os.path.splitext(basename)[0]}.{extension}"


def _const_string(args: list[ast.stmt]) -> str:
    (inner,) = args
    if hasattr(inner, "values"):
        (inner,) = inner.values
    return f"{inner.value}"  # type: ignore[attr-defined]


def _const_or_id(args: ast.stmt) -> str:
    if hasattr(args, "value"):
        return f"{args.value}"  # type: ignore[attr-defined]
    return f"{args.id}"  # type: ignore[attr-defined]


def get_markdown_from_cell(cell: Cell, code: str) -> Optional[str]:
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
        if body.value.func.attr == "md":  # type: ignore[attr-defined]
            value = body.value  # type: ignore[attr-defined]
        else:
            return None
        assert value.func.value.id == "mo"
        md_lines = _const_string(value.args).split("\n")
    except (AssertionError, AttributeError, ValueError, SyntaxError):
        # No reason to explicitly catch exceptions if we can't parse out
        # markdown. Just handle it as a code block.
        return None

    # Dedent behavior is a little different that in marimo js, so handle
    # accordingly.
    md_lines = [line.rstrip() for line in md_lines]
    md = dedent(md_lines[0]) + "\n" + dedent("\n".join(md_lines[1:]))
    md = md.strip()
    return md


def get_sql_options_from_cell(code: str) -> Optional[dict[str, str]]:
    # Note frontend/src/core/codemirror/language/sql.ts
    # also extracts options via ast. Ideally, these should be synced.
    options = {}
    code = code.strip()
    try:
        (body,) = ast.parse(code).body
        (target,) = body.targets  # type: ignore[attr-defined]
        options["query"] = target.id
        if body.value.func.attr == "sql":  # type: ignore[attr-defined]
            value = body.value  # type: ignore[attr-defined]
        else:
            return None
        if value.keywords:
            for keyword in value.keywords:  # type: ignore[attr-defined]
                options[keyword.arg] = _const_or_id(keyword.value)  # type: ignore[attr-defined]
        output = options.pop("output", "True").lower()
        if output == "false":
            options["hide_output"] = "True"

        return options
    except (AssertionError, AttributeError, ValueError):
        return None
