# Copyright 2025 Marimo. All rights reserved.
from marimo._lint.rules.base import LintRule
from marimo._lint.rules.breaking.graph import (
    CycleDependenciesRule,
    MultipleDefinitionsRule,
    SetupCellDependenciesRule,
)
from marimo._lint.rules.breaking.unparsable import UnparsableRule

BREAKING_RULE_CODES: dict[str, type[LintRule]] = {
    "MB001": UnparsableRule,
    "MR002": MultipleDefinitionsRule,
    "MR003": CycleDependenciesRule,
    "MR004": SetupCellDependenciesRule,
}

__all__ = [
    "MultipleDefinitionsRule",
    "CycleDependenciesRule",
    "SetupCellDependenciesRule",
    "UnparsableRule",
    "BREAKING_RULE_CODES",
]
