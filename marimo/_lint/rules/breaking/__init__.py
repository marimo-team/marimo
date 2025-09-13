# Copyright 2025 Marimo. All rights reserved.
from marimo._lint.rules.base import LintRule
from marimo._lint.rules.breaking.unparsable import UnparsableRule

BREAKING_RULE_CODES: dict[str, type[LintRule]] = {
    "MB001": UnparsableRule,
}

__all__ = ["UnparsableRule", "BREAKING_RULE_CODES"]
