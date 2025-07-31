# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._ast import codegen


def markdown_to_marimo(source: str) -> str:
    source = source.replace('"""', '\\"\\"\\"')
    return "\n".join(
        [
            "mo.md(",
            # r-string: a backslash is just a backslash!
            codegen.indent_text('r"""'),
            codegen.indent_text(source),
            codegen.indent_text('"""'),
            ")",
        ]
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
