# Copyright 2025 Marimo. All rights reserved.
from marimo._lint.rules.base import LintRule
from marimo._lint.rules.breaking import BREAKING_RULE_CODES
from marimo._lint.rules.formatting import FORMATTING_RULE_CODES

RULE_CODES: dict[str, type[LintRule]] = (
    BREAKING_RULE_CODES | FORMATTING_RULE_CODES
)

__all__ = [
    "RULE_CODES",
    "BREAKING_RULE_CODES",
    "FORMATTING_RULE_CODES",
]
