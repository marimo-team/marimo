# Copyright 2026 Marimo. All rights reserved.
"""Unit tests for lint rule selection."""

from __future__ import annotations

from marimo._lint.rule_selector import resolve_rules
from marimo._lint.rules import RULE_CODES


class TestResolveRules:
    def test_empty_config_returns_all_rules(self):
        rules = resolve_rules({})
        assert len(rules) == len(RULE_CODES)

    def test_select_by_category_prefix(self):
        rules = resolve_rules({"select": ["MB"]})
        assert all(r.code.startswith("MB") for r in rules)
        assert len(rules) == 5

    def test_select_exact_code(self):
        rules = resolve_rules({"select": ["MB001"]})
        assert len(rules) == 1
        assert rules[0].code == "MB001"

    def test_select_multiple_prefixes(self):
        rules = resolve_rules({"select": ["MB", "MR"]})
        codes = {r.code for r in rules}
        assert all(c.startswith(("MB", "MR")) for c in codes)
        assert len(rules) == 8  # 5 MB + 3 MR

    def test_select_all(self):
        rules = resolve_rules({"select": ["ALL"]})
        assert len(rules) == len(RULE_CODES)

    def test_ignore_single_rule(self):
        rules = resolve_rules({"ignore": ["MF004"]})
        codes = {r.code for r in rules}
        assert "MF004" not in codes
        assert len(rules) == len(RULE_CODES) - 1

    def test_ignore_category(self):
        rules = resolve_rules({"ignore": ["MF"]})
        assert not any(r.code.startswith("MF") for r in rules)

    def test_select_and_ignore(self):
        rules = resolve_rules({"select": ["MB"], "ignore": ["MB001"]})
        codes = {r.code for r in rules}
        assert "MB001" not in codes
        assert all(c.startswith("MB") for c in codes)
        assert len(rules) == 4

    def test_partial_prefix(self):
        rules = resolve_rules({"select": ["MB00"]})
        assert all(r.code.startswith("MB00") for r in rules)
        assert len(rules) > 0

    def test_unknown_prefix_returns_empty(self):
        rules = resolve_rules({"select": ["XX"]})
        assert len(rules) == 0

    def test_sorted_order(self):
        rules = resolve_rules({})
        codes = [r.code for r in rules]
        assert codes == sorted(codes)

    def test_custom_all_rules(self):
        from marimo._lint.rules.breaking import UnparsableRule
        from marimo._lint.rules.runtime import SelfImportRule

        custom = {"MB001": UnparsableRule, "MR001": SelfImportRule}
        rules = resolve_rules({"select": ["MB"]}, all_rules=custom)
        assert len(rules) == 1
        assert rules[0].code == "MB001"

    def test_ignore_all_returns_empty(self):
        rules = resolve_rules({"ignore": ["ALL"]})
        assert len(rules) == 0

    def test_select_all_ignore_some(self):
        rules = resolve_rules({"select": ["ALL"], "ignore": ["MF"]})
        assert not any(r.code.startswith("MF") for r in rules)
        assert any(r.code.startswith("MB") for r in rules)
