# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._lint.rules.base import LintRule
from marimo._lint.rules.runtime.branch_expression import BranchExpressionRule
from marimo._lint.rules.runtime.self_import import SelfImportRule

RUNTIME_RULE_CODES: dict[str, type[LintRule]] = {
    "MR001": SelfImportRule,
    "MR002": BranchExpressionRule,
}

__all__ = [
    "BranchExpressionRule",
    "SelfImportRule",
    "RUNTIME_RULE_CODES",
]
