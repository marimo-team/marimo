# Copyright 2026 Marimo. All rights reserved.
"""Tests for WASM compatibility lint rules (MW001, MW002, MW003)."""

from __future__ import annotations

from marimo._ast.parse import parse_notebook
from marimo._lint.diagnostic import Severity
from tests._lint.utils import lint_notebook

TEST_FILE = "tests/_lint/test_files/wasm_incompatible.py"


def _load_notebook():
    with open(TEST_FILE) as f:
        code = f.read()
    return parse_notebook(code, filepath=TEST_FILE), code


class TestWasmRulesOffByDefault:
    """MW rules should not fire without explicit --select MW."""

    def test_no_wasm_diagnostics_by_default(self):
        notebook, contents = _load_notebook()
        diagnostics = lint_notebook(notebook, contents)
        assert not any(d.code.startswith("MW") for d in diagnostics)


class TestMW001IncompatibleImports:
    """MW001: Importing modules unavailable in WASM/Pyodide."""

    def test_subprocess_flagged(self):
        notebook, contents = _load_notebook()
        diagnostics = lint_notebook(
            notebook, contents, lint_config={"select": ["MW001"]}
        )
        codes = [d.code for d in diagnostics]
        messages = [d.message for d in diagnostics]
        assert "MW001" in codes
        assert any("subprocess" in m for m in messages)

    def test_multiprocessing_flagged(self):
        notebook, contents = _load_notebook()
        diagnostics = lint_notebook(
            notebook, contents, lint_config={"select": ["MW001"]}
        )
        messages = [d.message for d in diagnostics]
        assert any("multiprocessing" in m for m in messages)

    def test_pdb_flagged(self):
        notebook, contents = _load_notebook()
        diagnostics = lint_notebook(
            notebook, contents, lint_config={"select": ["MW001"]}
        )
        messages = [d.message for d in diagnostics]
        assert any("pdb" in m for m in messages)

    def test_severity_is_wasm(self):
        notebook, contents = _load_notebook()
        diagnostics = lint_notebook(
            notebook, contents, lint_config={"select": ["MW001"]}
        )
        for d in diagnostics:
            assert d.severity == Severity.WASM

    def test_safe_imports_not_flagged(self):
        """Standard safe imports like os should not be flagged."""
        notebook, contents = _load_notebook()
        diagnostics = lint_notebook(
            notebook, contents, lint_config={"select": ["MW001"]}
        )
        messages = " ".join(d.message for d in diagnostics)
        # os is importable in Pyodide; only specific os.* calls are bad (MW002)
        assert "Module 'os'" not in messages


class TestMW002UnsafeSystemCalls:
    """MW002: System calls that fail in WASM/Pyodide."""

    def test_os_system_flagged(self):
        notebook, contents = _load_notebook()
        diagnostics = lint_notebook(
            notebook, contents, lint_config={"select": ["MW002"]}
        )
        messages = [d.message for d in diagnostics]
        assert any("os.system()" in m for m in messages)

    def test_breakpoint_flagged(self):
        notebook, contents = _load_notebook()
        diagnostics = lint_notebook(
            notebook, contents, lint_config={"select": ["MW002"]}
        )
        messages = [d.message for d in diagnostics]
        assert any("breakpoint()" in m for m in messages)

    def test_severity_is_wasm(self):
        notebook, contents = _load_notebook()
        diagnostics = lint_notebook(
            notebook, contents, lint_config={"select": ["MW002"]}
        )
        for d in diagnostics:
            assert d.severity == Severity.WASM

    def test_line_numbers_are_set(self):
        notebook, contents = _load_notebook()
        diagnostics = lint_notebook(
            notebook, contents, lint_config={"select": ["MW002"]}
        )
        for d in diagnostics:
            assert d.line > 0


class TestMW001AndMW002Together:
    """Both MW001 and MW002 should fire on the test file."""

    def test_combined_diagnostics(self):
        notebook, contents = _load_notebook()
        diagnostics = lint_notebook(
            notebook, contents, lint_config={"select": ["MW"]}
        )
        codes = {d.code for d in diagnostics}
        assert "MW001" in codes
        assert "MW002" in codes
