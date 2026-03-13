# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from marimo._config.config import LintConfig
    from marimo._lint.rules.base import LintRule


def _matches_any_prefix(code: str, prefixes: list[str]) -> bool:
    """Check if a rule code matches any of the given prefixes.

    "ALL" matches everything. Otherwise, prefix matching:
    "MB" matches "MB001", "MF0" matches "MF001", "MF001" is exact.
    """
    for prefix in prefixes:
        if prefix == "ALL" or code.startswith(prefix):
            return True
    return False


def resolve_rules(
    config: LintConfig,
    all_rules: dict[str, type[LintRule]] | None = None,
) -> list[LintRule]:
    """Resolve a LintConfig into a concrete list of enabled LintRule instances.

    Algorithm:
        1. If config.select is non-empty, start with matching rules.
           Otherwise, start with ALL available rules.
        2. Remove rules matching config.ignore prefixes.
        3. Return instantiated rules in sorted code order.

    Args:
        config: LintConfig with optional ``select`` and ``ignore`` keys.
        all_rules: Available rule classes keyed by code.
            Defaults to ``RULE_CODES`` when None.

    Returns:
        Instantiated LintRule list, sorted by code.
    """
    if all_rules is None:
        from marimo._lint.rules import RULE_CODES

        all_rules = RULE_CODES

    codes = set(all_rules.keys())
    select = config.get("select")
    ignore = config.get("ignore")

    # Step 1: base set
    if select:
        codes = {c for c in codes if _matches_any_prefix(c, select)}

    # Step 2: remove ignored
    if ignore:
        codes = {c for c in codes if not _matches_any_prefix(c, ignore)}

    # Step 3: instantiate in deterministic order
    return [all_rules[c]() for c in sorted(codes)]
