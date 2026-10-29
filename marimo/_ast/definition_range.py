# Copyright 2026 Marimo. All rights reserved.
"""Locate a module-level binding's identifier in its original source."""

from __future__ import annotations

import ast
import io
import tokenize
from dataclasses import dataclass


@dataclass(frozen=True)
class DefinitionRange:
    """Zero-based identifier range with Unicode code-point columns."""

    line: int
    column: int
    end_column: int


def find_definition_range(
    module: ast.Module, name: str, source: str
) -> DefinitionRange | None:
    """Return the first module-level binding's range, when present in source."""
    visitor = _DefinitionVisitor(name, source)
    visitor.visit(module)
    return visitor.range


_SCOPES = (
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ClassDef,
    ast.Lambda,
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
)


class _DefinitionVisitor(ast.NodeVisitor):
    def __init__(self, name: str, source: str) -> None:
        self._name = name
        self._lines = source.splitlines()
        self._tokens = tuple(
            tokenize.generate_tokens(io.StringIO(source).readline)
        )
        self.range: DefinitionRange | None = None

    def visit(self, node: ast.AST) -> None:
        if self.range is not None:
            return
        if isinstance(node, _SCOPES):
            if (
                isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                )
                and node.name == self._name
            ):
                self._record(node)
            return
        super().visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id == self._name and isinstance(node.ctx, ast.Store):
            self._record(node)

    def visit_alias(self, node: ast.alias) -> None:
        if (node.asname or node.name.split(".")[0]) == self._name:
            self._record(node, last=node.asname is not None)

    def _record(
        self,
        node: ast.Name
        | ast.alias
        | ast.FunctionDef
        | ast.AsyncFunctionDef
        | ast.ClassDef,
        *,
        last: bool = False,
    ) -> None:
        # AST columns are UTF-8 byte offsets; tokenize columns count characters.
        line = node.lineno
        column = len(
            self._lines[line - 1]
            .encode("utf-8")[: node.col_offset]
            .decode("utf-8")
        )
        end_line = node.end_lineno
        if end_line is None:
            raise RuntimeError("AST node has no end line")
        if node.end_col_offset is None:
            raise RuntimeError("AST node has no end column")
        end_column = len(
            self._lines[end_line - 1]
            .encode("utf-8")[: node.end_col_offset]
            .decode("utf-8")
        )
        tokens = [
            token
            for token in self._tokens
            if token.type == tokenize.NAME
            and token.string == self._name
            and (line, column) <= token.start < (end_line, end_column)
        ]
        if tokens:
            token = tokens[-1] if last else tokens[0]
            self.range = DefinitionRange(
                line=token.start[0] - 1,
                column=token.start[1],
                end_column=token.end[1],
            )
