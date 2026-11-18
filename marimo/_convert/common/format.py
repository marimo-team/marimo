# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from marimo._ast import codegen
from marimo._ast.compiler import extract_markdown

if TYPE_CHECKING:
    from marimo._ast.cell import Cell, CellImpl

DEFAULT_MARKDOWN_PREFIX = "r"


def _escape_triple_quotes(source: str, quote: str) -> str | None:
    # Mirrors escapeTripleQuotes in markdown-parser.ts
    runs = f"(?:{quote}{{3}})+(?!{quote})"
    if re.search(rf"(?<!\\)(?:\\\\)*\\{runs}", source):
        return None
    triple = quote * 3
    return re.sub(
        runs, lambda run: run.group().replace(triple, "\\" + triple), source
    )


def markdown_to_marimo(
    source: str, prefix: str = DEFAULT_MARKDOWN_PREFIX
) -> str:
    # NB. This should be kept in sync with the logic in
    # packages/smart-cells/src/parsers/markdown-parser.ts::transformOut

    # 6 quotes in a row breaks
    if not source:
        source = " "

    # Prefer a delimiter the body does not contain: escapes survive in raw
    # strings and render as backslashes in code blocks.
    quotes = "'" if '"""' in source and "'''" not in source else "\"'"
    for quote in quotes:
        escaped = _escape_triple_quotes(source, quote)
        if escaped is not None:
            return codegen.construct_markdown_call(escaped, quote * 3, prefix)

    # Neither delimiter can hold this body losslessly.
    return codegen.construct_markdown_call(
        source.replace('""', '"\\"'), '"""', prefix
    )


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


def get_markdown_from_cell(cell: CellImpl | Cell, code: str) -> str | None:
    """Attempt to extract markdown from a cell, or return None"""

    if not (cell.refs == {"mo"} and not cell.defs):
        return None
    return extract_markdown(code)
