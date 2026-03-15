# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Optional, Union

from marimo._ast import codegen
from marimo._ast.compiler import extract_markdown

if TYPE_CHECKING:
    from marimo._ast.cell import Cell, CellImpl

DEFAULT_MARKDOWN_PREFIX = "r"
_PARAGRAPH_BLOCK_RE = re.compile(r"^\s*(?:<p>.*?</p>\s*)+$", re.DOTALL)
_PARAGRAPH_RE = re.compile(r"<p>(.*?)</p>", re.DOTALL)


def _normalize_paragraph_html(source: str) -> str:
    """Normalize notebooks that store markdown as top-level <p> blocks."""
    stripped = source.strip()
    if not stripped or _PARAGRAPH_BLOCK_RE.fullmatch(stripped) is None:
        return source

    paragraphs = [paragraph.strip() for paragraph in _PARAGRAPH_RE.findall(stripped)]
    if not paragraphs:
        return source
    return "\n\n".join(paragraphs)


def markdown_to_marimo(
    source: str, prefix: str = DEFAULT_MARKDOWN_PREFIX
) -> str:
    # NB. This should be kept in sync with the logic in
    # frontend/src/core/codemirror/language/languages/markdown.ts
    # ::transformOut
    source = _normalize_paragraph_html(source)
    source = source.replace('"""', '\\"\\"\\"')

    # 6 quotes in a row breaks
    if not source:
        source = " "
    return codegen.construct_markdown_call(source, '"""', prefix)


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
