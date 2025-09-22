# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import ast
import os
import re
from typing import Optional, Union

from marimo._ast.cell import Cell, CellImpl
from marimo._ast.compiler import const_or_id, extract_markdown


def format_filename_title(filename: str) -> str:
    basename = os.path.basename(filename)
    name, _ext = os.path.splitext(basename)
    title = re.sub("[-_]", " ", name)
    return title.title()


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


def get_markdown_from_cell(
    cell: Union[CellImpl, Cell], code: str
) -> Optional[str]:
    """Attempt to extract markdown from a cell, or return None"""

    if not (cell.refs == {"mo"} and not cell.defs):
        return None
    return extract_markdown(code)


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
                options[keyword.arg] = const_or_id(keyword.value)  # type: ignore[attr-defined]
        output = options.pop("output", "True").lower()
        if output == "false":
            options["hide_output"] = "True"

        return options
    except (AssertionError, AttributeError, ValueError):
        return None
