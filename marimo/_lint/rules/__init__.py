# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._lint.rules.base import LintRule
from marimo._lint.rules.breaking import BREAKING_RULE_CODES
from marimo._lint.rules.formatting import FORMATTING_RULE_CODES
from marimo._lint.rules.runtime import RUNTIME_RULE_CODES

RULE_CODES: dict[str, type[LintRule]] = (
    BREAKING_RULE_CODES | RUNTIME_RULE_CODES | FORMATTING_RULE_CODES
)

__all__ = [
    "RULE_CODES",
    "BREAKING_RULE_CODES",
    "RUNTIME_RULE_CODES",
    "FORMATTING_RULE_CODES",
]
