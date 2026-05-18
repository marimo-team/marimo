# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import ast
import os
import re
import textwrap
from typing import TYPE_CHECKING

from marimo._ast import codegen
from marimo._ast.compiler import const_or_id
from marimo._ast.names import is_internal_cell_name
from marimo._convert.common.format import get_markdown_from_cell
from marimo._convert.markdown.flavor import normalize_markdown_flavor
from marimo._convert.markdown.flavor.base import (
    CodeCellBlock,
    MarkdownCellBlock,
    MarkdownExportDocument,
    MarkdownFlavor,
    MarkdownFlavorName,
)
from marimo._schemas.serialization import NotebookSerializationV1
from marimo._types.ids import CellId_t
from marimo._version import __version__

if TYPE_CHECKING:
    from marimo._ast.cell import CellImpl
    from marimo._ast.visitor import Language


def convert_from_ir_to_markdown(
    notebook: NotebookSerializationV1,
    filename: str | None = None,
    flavor: MarkdownFlavor | MarkdownFlavorName | None = None,
) -> str:
    filename = filename or notebook.filename or "notebook.md"
    markdown_flavor = normalize_markdown_flavor(flavor, filename=filename)
    document = _notebook_to_markdown_export_document(notebook, filename)
    return markdown_flavor.render_document(document)


def _notebook_to_markdown_export_document(
    notebook: NotebookSerializationV1,
    filename: str,
) -> MarkdownExportDocument:
    from marimo._ast.app_config import _AppConfig
    from marimo._ast.compiler import compile_cell
    from marimo._convert.markdown.to_ir import (
        is_sanitized_markdown,
    )
    from marimo._utils import yaml

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

    header: str | None = None

    # Recover frontmatter metadata from header
    if notebook.header and notebook.header.value:
        try:
            frontmatter = yaml.load(notebook.header.value)
            if isinstance(frontmatter, dict):
                # Insert metadata before config so config takes precedence
                _recovered = dict(frontmatter)
                _recovered.update(metadata)
                metadata = _recovered
        except (yaml.YAMLError, AssertionError):
            # Not valid YAML dict — treat as script preamble
            header = notebook.header.value.strip()
            metadata["header"] = header

    document = MarkdownExportDocument(
        metadata=metadata,
        header=header,
        blocks=[],
    )

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
                    document.blocks.append(MarkdownCellBlock(markdown))
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

        language = attributes.pop("language", "python")
        document.blocks.append(
            CodeCellBlock(
                source=code,
                language=language,
                options=attributes,
            )
        )

    return document


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
