# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._lint.rules.base import LintRule, UnsafeFixRule
from marimo._lint.rules.formatting.empty_cells import EmptyCellRule
from marimo._lint.rules.formatting.general import GeneralFormattingRule
from marimo._lint.rules.formatting.markdown_dedent import MarkdownDedentRule
from marimo._lint.rules.formatting.parsing import (
    MiscLogRule,
    SqlParseRule,
    StderrRule,
    StdoutRule,
)

FORMATTING_RULE_CODES: dict[str, type[LintRule]] = {
    "MF001": GeneralFormattingRule,
    "MF002": StdoutRule,
    "MF003": StderrRule,
    "MF004": EmptyCellRule,
    "MF005": SqlParseRule,
    "MF006": MiscLogRule,
    "MF007": MarkdownDedentRule,
}

__all__ = [
    "GeneralFormattingRule",
    "FORMATTING_RULE_CODES",
    "StdoutRule",
    "StderrRule",
    "EmptyCellRule",
    "SqlParseRule",
    "MiscLogRule",
    "MarkdownDedentRule",
    "UnsafeFixRule",
]
