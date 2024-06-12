# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import ast


class NameTransformer(ast.NodeTransformer):
    def __init__(self, name_substitutions: dict[str, str]) -> None:
        self._name_substitutions = name_substitutions
        super().__init__()

    def visit_Name(self, node: ast.Name) -> ast.Name:
        if node.id in self._name_substitutions:
            return ast.Name(
                **{**node.__dict__, "id": self._name_substitutions[node.id]}
            )
        else:
            return node
