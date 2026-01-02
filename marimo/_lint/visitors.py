# Copyright 2026 Marimo. All rights reserved.
"""AST visitors for linting purposes."""

from __future__ import annotations

import ast
from typing import Optional


class VariableLineVisitor(ast.NodeVisitor):
    """AST visitor to find the line number of a variable definition."""

    def __init__(self, target_variable: str):
        self.target_variable = target_variable
        self.line_number: Optional[int] = None
        self.column_number: int = 1

    def visit_Name(self, node: ast.Name) -> None:
        """Visit Name nodes to find variable definitions."""
        if node.id == self.target_variable:
            # Check if this is a definition (not just a reference)
            if isinstance(node.ctx, (ast.Store, ast.Del)):
                self.line_number = node.lineno
                self.column_number = node.col_offset + 1
                return
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit function definition nodes."""
        if node.name == self.target_variable:
            self.line_number = node.lineno
            self.column_number = node.col_offset + 1
            return
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit class definition nodes."""
        if node.name == self.target_variable:
            self.line_number = node.lineno
            self.column_number = node.col_offset + 1
            return
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Visit ImportFrom nodes to find imported variable definitions."""
        for alias in node.names:
            if (
                alias.asname == self.target_variable
                or alias.name == self.target_variable
            ):
                self.line_number = node.lineno
                self.column_number = node.col_offset + 1
                return
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        """Visit Import nodes to find imported variable definitions."""
        for alias in node.names:
            if (
                alias.asname == self.target_variable
                or alias.name == self.target_variable
            ):
                self.line_number = node.lineno
                self.column_number = node.col_offset + 1
                return
        self.generic_visit(node)
