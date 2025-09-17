# Copyright 2025 Marimo. All rights reserved.
from marimo._lint.rules.base import LintRule, UnsafeFixRule
from marimo._lint.rules.formatting.empty_cells import EmptyCellRule
from marimo._lint.rules.formatting.general import GeneralFormattingRule
from marimo._lint.rules.formatting.parsing import StderrRule, StdoutRule

FORMATTING_RULE_CODES: dict[str, type[LintRule]] = {
    "MF001": GeneralFormattingRule,
    "MF002": StdoutRule,
    "MF003": StderrRule,
    "MF004": EmptyCellRule,
}

__all__ = [
    "GeneralFormattingRule",
    "FORMATTING_RULE_CODES",
    "StdoutRule",
    "StderrRule",
    "EmptyCellRule",
    "UnsafeFixRule",
]
