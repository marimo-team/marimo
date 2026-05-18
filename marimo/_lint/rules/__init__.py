# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._lint.rules.base import LintRule
from marimo._lint.rules.breaking import BREAKING_RULE_CODES
from marimo._lint.rules.formatting import FORMATTING_RULE_CODES
from marimo._lint.rules.runtime import RUNTIME_RULE_CODES
from marimo._lint.rules.wasm import WASM_RULE_CODES

# Rules enabled by default (excludes opt-in categories like WASM).
DEFAULT_RULE_CODES: dict[str, type[LintRule]] = (
    BREAKING_RULE_CODES | RUNTIME_RULE_CODES | FORMATTING_RULE_CODES
)

# All known rules (including opt-in). Used when --select is provided.
RULE_CODES: dict[str, type[LintRule]] = DEFAULT_RULE_CODES | WASM_RULE_CODES

__all__ = [
    "BREAKING_RULE_CODES",
    "DEFAULT_RULE_CODES",
    "FORMATTING_RULE_CODES",
    "RULE_CODES",
    "RUNTIME_RULE_CODES",
    "WASM_RULE_CODES",
]
