from marimo._lint.rules.base import LintRule
from marimo._lint.rules.runtime.graph import (
    CycleDependenciesRule,
    MultipleDefinitionsRule,
    SetupCellDependenciesRule,
)

RUNTIME_RULE_CODES: dict[str, type[LintRule]] = {
    "MR001": MultipleDefinitionsRule,
    "MR002": CycleDependenciesRule,
    "MR003": SetupCellDependenciesRule,
}

__all__ = [
    "MultipleDefinitionsRule",
    "CycleDependenciesRule",
    "SetupCellDependenciesRule",
    "RUNTIME_RULE_CODES",
]
