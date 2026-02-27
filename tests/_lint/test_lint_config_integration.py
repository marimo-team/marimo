# Copyright 2026 Marimo. All rights reserved.
"""Integration tests for lint config flowing through the pipeline."""

from __future__ import annotations

from marimo._lint.linter import Linter
from marimo._lint.rule_engine import RuleEngine


class TestRuleEngineConfig:
    def test_create_default_no_config(self):
        engine = RuleEngine.create_default()
        from marimo._lint.rules import RULE_CODES

        assert len(engine.rules) == len(RULE_CODES)

    def test_create_default_with_select(self):
        engine = RuleEngine.create_default(lint_config={"select": ["MB"]})
        assert all(r.code.startswith("MB") for r in engine.rules)
        assert len(engine.rules) == 5

    def test_create_default_with_ignore(self):
        engine = RuleEngine.create_default(lint_config={"ignore": ["MF001"]})
        codes = {r.code for r in engine.rules}
        assert "MF001" not in codes

    def test_create_default_empty_config(self):
        engine = RuleEngine.create_default(lint_config={})
        from marimo._lint.rules import RULE_CODES

        assert len(engine.rules) == len(RULE_CODES)


class TestLinterConfig:
    def test_linter_with_lint_config(self):
        linter = Linter(lint_config={"select": ["MB"]})
        assert all(r.code.startswith("MB") for r in linter.rule_engine.rules)

    def test_linter_with_ignore(self):
        linter = Linter(lint_config={"ignore": ["MF"]})
        assert not any(
            r.code.startswith("MF") for r in linter.rule_engine.rules
        )

    def test_linter_explicit_rules_ignores_config(self):
        """When explicit rules are passed, lint_config is not used."""
        from marimo._lint.rules.breaking import UnparsableRule

        explicit = [UnparsableRule()]
        linter = Linter(
            rules=explicit, lint_config={"select": ["MF"]}
        )
        assert len(linter.rule_engine.rules) == 1
        assert linter.rule_engine.rules[0].code == "MB001"

    def test_linter_no_config(self):
        linter = Linter()
        from marimo._lint.rules import RULE_CODES

        assert len(linter.rule_engine.rules) == len(RULE_CODES)
