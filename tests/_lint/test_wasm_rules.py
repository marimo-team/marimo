# Copyright 2026 Marimo. All rights reserved.
"""Tests for WASM compatibility lint rules (MW001, MW002, MW003)."""

from __future__ import annotations

import json
from typing import Self
from unittest.mock import patch

from marimo._ast.parse import parse_notebook
from marimo._lint.diagnostic import Severity
from marimo._utils.requests import Response
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


_PEP723_NOTEBOOK = """# /// script
# requires-python = ">=3.11"
# dependencies = [{deps}]
# ///

import marimo

__generated_with = "0.23.2"
app = marimo.App()


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
"""


def _fake_lockfile_response(packages: dict[str, str]) -> Response:
    """Build a fake pyodide-lock.json response for the given {name: version}."""
    payload = {
        "packages": {
            name: {
                "name": name,
                "version": version,
                "package_type": "package",
            }
            for name, version in packages.items()
        }
    }
    return Response(
        status_code=200,
        content=json.dumps(payload).encode("utf-8"),
        headers={},
    )


class _FakePypiResponse:
    """Stand-in for the urllib response used by ``_has_wasm_compatible_wheel``."""

    def __init__(self, payload: dict[str, object]):
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        return None


class TestMW003IncompatiblePackages:
    """MW003: PEP 723 deps incompatible with WASM/Pyodide."""

    def _write_and_parse(self, tmp_path, deps: list[str]):
        nb_file = tmp_path / "nb.py"
        deps_literal = ", ".join(f'"{d}"' for d in deps)
        nb_file.write_text(_PEP723_NOTEBOOK.format(deps=deps_literal))
        contents = nb_file.read_text()
        notebook = parse_notebook(contents, filepath=str(nb_file))
        return notebook, contents

    def test_pyodide_listed_dep_not_flagged(self, monkeypatch, tmp_path):
        """Lockfile lookup short-circuits before the PyPI fetch."""
        from marimo._lint.rules.wasm import incompatible_packages as mod

        # _resolve_dep_tree walks importlib.metadata locally — short-circuit
        # it so the test doesn't depend on the host env.
        monkeypatch.setattr(mod, "_resolve_dep_tree", lambda deps: deps)
        # Guard: PyPI must not be hit when the dep is already in the lockfile.
        mod._has_wasm_compatible_wheel.cache_clear()

        notebook, contents = self._write_and_parse(tmp_path, ["numpy"])
        with (
            patch(
                "marimo._pyodide.pyodide_constraints.requests.get",
                return_value=_fake_lockfile_response({"numpy": "2.0.2"}),
            ),
            patch(
                "marimo._lint.rules.wasm.incompatible_packages."
                "urllib.request.urlopen",
                side_effect=AssertionError(
                    "PyPI must not be queried for lockfile-listed packages"
                ),
            ),
        ):
            diagnostics = lint_notebook(
                notebook, contents, lint_config={"select": ["MW003"]}
            )
        assert not any(d.code == "MW003" for d in diagnostics)

    def test_dep_without_compatible_wheel_flagged(self, monkeypatch, tmp_path):
        """Non-lockfile dep whose PyPI release ships only native wheels fires MW003."""
        from marimo._lint.rules.wasm import incompatible_packages as mod

        monkeypatch.setattr(mod, "_resolve_dep_tree", lambda deps: deps)
        mod._has_wasm_compatible_wheel.cache_clear()

        notebook, contents = self._write_and_parse(tmp_path, ["jaxlib"])
        pypi_payload = {
            "urls": [
                {
                    "filename": "jaxlib-0.4.30-cp312-cp312-manylinux2014_x86_64.whl"
                }
            ]
        }
        with (
            patch(
                "marimo._pyodide.pyodide_constraints.requests.get",
                return_value=_fake_lockfile_response({}),
            ),
            patch(
                "marimo._lint.rules.wasm.incompatible_packages."
                "urllib.request.urlopen",
                return_value=_FakePypiResponse(pypi_payload),
            ),
        ):
            diagnostics = lint_notebook(
                notebook, contents, lint_config={"select": ["MW003"]}
            )
        mw003 = [d for d in diagnostics if d.code == "MW003"]
        assert len(mw003) == 1
        assert "jaxlib" in mw003[0].message
        assert mw003[0].severity == Severity.WASM
