# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

from marimo._lint.rules.base import LintRule
from marimo._lint.rules.runtime.self_import import SelfImportRule

RUNTIME_RULE_CODES: dict[str, type[LintRule]] = {
    "MR001": SelfImportRule,
}

__all__ = [
    "SelfImportRule",
    "RUNTIME_RULE_CODES",
]
