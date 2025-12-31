# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import ast
import os
import re
import textwrap
from typing import TYPE_CHECKING

from marimo import _loggers
from marimo._ast import codegen
from marimo._ast.compiler import const_or_id
from marimo._ast.names import is_internal_cell_name
from marimo._convert.utils import get_markdown_from_cell
from marimo._schemas.serialization import NotebookSerializationV1
from marimo._types.ids import CellId_t
from marimo._version import __version__

if TYPE_CHECKING:
    from marimo._ast.cell import CellImpl
    from marimo._ast.visitor import Language

LOGGER = _loggers.marimo_logger()


def convert_from_ir_to_markdown(
    notebook: NotebookSerializationV1,
    filename: str | None = None,
) -> str:
    from marimo._ast.app_config import _AppConfig
    from marimo._ast.compiler import compile_cell
    from marimo._convert.markdown.markdown import (
        formatted_code_block,
        is_sanitized_markdown,
    )
    from marimo._utils import yaml

    filename = filename or notebook.filename or "notebook.md"
    app_title = notebook.app.options.get("app_title", None)
    if not app_title:
        app_title = _format_filename_title(filename)

    metadata: dict[str, str | list[str]] = {}
    metadata.update(
        {
            "title": app_title,
            "marimo-version": __version__,
        }
    )

    # Put data from AppFileManager into the yaml header.
    ignored_keys = {"app_title"}
    default_config = _AppConfig().asdict()

    # Get values defined in _AppConfig without explicitly extracting keys,
    # as long as it isn't the default.
    metadata.update(
        {
            k: v
            for k, v in notebook.app.options.items()
            if k not in ignored_keys and v != default_config.get(k)
        }
    )

    # Add header from notebook if present
    if notebook.header and notebook.header.value:
        metadata["header"] = notebook.header.value.strip()

    # Add the expected qmd filter to the metadata.
    is_qmd = filename.endswith(".qmd")
    if is_qmd:
        if "filters" not in metadata:
            metadata["filters"] = []
        if "marimo" not in str(metadata["filters"]):
            if isinstance(metadata["filters"], str):
                metadata["filters"] = metadata["filters"].split(",")
            if isinstance(metadata["filters"], list):
                metadata["filters"].append("marimo-team/marimo")
            else:
                LOGGER.warning(
                    "Unexpected type for filters: %s",
                    type(metadata["filters"]),
                )

    header = yaml.marimo_compat_dump(
        {
            k: v
            for k, v in metadata.items()
            if v is not None and v != "" and v != []
        },
        sort_keys=False,
    )
    document = ["---", header.strip(), "---", ""]
    previous_was_markdown = False

    for cell in notebook.cells:
        code = cell.code
        # Config values are opt in, so only include if they are set.
        attributes = cell.options.copy()

        # Extract name from options if present (for unparsable cells)
        # and use it instead of cell.name
        cell_name = attributes.pop("name", None) or cell.name

        # Allow for attributes like column index.
        attributes = {k: repr(v).lower() for k, v in attributes.items() if v}
        if not is_internal_cell_name(cell_name):
            attributes["name"] = cell_name

        # No "cell" typically means not parseable. However newly added
        # cells require compilation before cell is set.
        # TODO: Refactor so it doesn't occur in export (codegen
        # does this too)
        # NB. Also need to recompile in the sql case since sql parsing is
        # cached.
        language: Language = "python"
        cell_impl: CellImpl | None = None
        try:
            cell_impl = compile_cell(code, cell_id=CellId_t("dummy"))
            language = cell_impl.language
        except SyntaxError:
            pass

        if cell_impl:
            # Markdown that starts a column is forced to code.
            column = attributes.get("column", None)
            if not column or column == "0":
                markdown = get_markdown_from_cell(cell_impl, code)
                # Unsanitized markdown is forced to code.
                if markdown and is_sanitized_markdown(markdown):
                    # Use blank HTML comment to separate markdown codeblocks
                    if previous_was_markdown:
                        document.append("<!---->")
                    previous_was_markdown = True
                    document.append(markdown)
                    continue
                # In which case we need to format it like our python blocks.
                elif cell_impl.markdown:
                    code = codegen.format_markdown(cell_impl)

            attributes["language"] = language
            # Definitely a code cell, but need to determine if it can be
            # formatted as non-python.
            if attributes["language"] == "sql":
                sql_options: dict[str, str] | None = (
                    _get_sql_options_from_cell(code)
                )
                if not sql_options:
                    # means not sql.
                    attributes.pop("language")
                else:
                    # Ignore default query value.
                    if sql_options.get("query") == "_df":
                        sql_options.pop("query")
                    attributes.update(sql_options)
                    code = "\n".join(cell_impl.raw_sqls).strip()

        # Definitely no "cell"; as such, treat as code, as everything in
        # marimo is code.
        else:
            attributes["unparsable"] = "true"

        # Dedent and strip code to prevent whitespace accumulation on roundtrips
        code = textwrap.dedent(code).strip()

        # Add a blank line between markdown and code
        if previous_was_markdown:
            document.append("")
        previous_was_markdown = False
        document.append(formatted_code_block(code, attributes, is_qmd=is_qmd))

    return "\n".join(document).strip()


def _format_filename_title(filename: str) -> str:
    basename = os.path.basename(filename)
    name, _ext = os.path.splitext(basename)
    title = re.sub("[-_]", " ", name)
    return title.title()


def _get_sql_options_from_cell(code: str) -> dict[str, str] | None:
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
