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
        linter = Linter(rules=explicit, lint_config={"select": ["MF"]})
        assert len(linter.rule_engine.rules) == 1
        assert linter.rule_engine.rules[0].code == "MB001"

    def test_linter_no_config(self):
        linter = Linter()
        from marimo._lint.rules import RULE_CODES

        assert len(linter.rule_engine.rules) == len(RULE_CODES)


class TestPep723LintConfig:
    """Test that PEP 723 inline script metadata can configure lint rules."""

    FILE = "tests/_lint/test_files/empty_cell_with_lint_config.py"

    def _read_and_parse(self):
        from marimo._ast.parse import parse_notebook

        with open(self.FILE) as f:
            code = f.read()
        return parse_notebook(code, filepath=self.FILE), code

    def test_empty_cell_ignored_via_pep723_lint_config(self):
        """MF004 is suppressed when the notebook's PEP 723 metadata ignores it."""
        from marimo._config.manager import ScriptConfigManager

        notebook, _ = self._read_and_parse()

        # Read lint config from the notebook's PEP 723 metadata
        script_mgr = ScriptConfigManager(self.FILE)
        config = script_mgr.get_config(hide_secrets=False)
        lint_config = config.get("lint")
        assert lint_config is not None, (
            "Expected [tool.marimo.lint] in metadata"
        )
        assert "MF004" in lint_config.get("ignore", [])

        from tests._lint.utils import lint_notebook

        diagnostics = lint_notebook(notebook, lint_config=lint_config)
        codes = [d.code for d in diagnostics]
        assert "MF004" not in codes

    def test_empty_cell_detected_without_config(self):
        """Without lint config, the empty cell IS detected as MF004."""
        notebook, _ = self._read_and_parse()

        from tests._lint.utils import lint_notebook

        diagnostics = lint_notebook(notebook)
        codes = [d.code for d in diagnostics]
        assert "MF004" in codes
