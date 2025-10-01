# Copyright 2025 Marimo. All rights reserved.
from marimo._lint.rules.base import LintRule
from marimo._lint.rules.breaking.graph import (
    CycleDependenciesRule,
    MultipleDefinitionsRule,
    SetupCellDependenciesRule,
)
from marimo._lint.rules.breaking.self_import import SelfImportRule
from marimo._lint.rules.breaking.syntax_error import SyntaxErrorRule
from marimo._lint.rules.breaking.unparsable import UnparsableRule

BREAKING_RULE_CODES: dict[str, type[LintRule]] = {
    "MB001": UnparsableRule,
    "MB002": MultipleDefinitionsRule,
    "MB003": CycleDependenciesRule,
    "MB004": SetupCellDependenciesRule,
    "MB005": SyntaxErrorRule,
    "MB006": SelfImportRule,
}

__all__ = [
    "MultipleDefinitionsRule",
    "CycleDependenciesRule",
    "SetupCellDependenciesRule",
    "UnparsableRule",
    "SyntaxErrorRule",
    "SelfImportRule",
    "BREAKING_RULE_CODES",
]
