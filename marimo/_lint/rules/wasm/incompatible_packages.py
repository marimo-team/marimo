# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import functools
import importlib.metadata
import json
import re
import urllib.request
from typing import TYPE_CHECKING

from marimo._lint.diagnostic import Diagnostic, Severity
from marimo._lint.rules.base import LintRule

if TYPE_CHECKING:
    from marimo._lint.context import RuleContext


def _normalize_name(name: str) -> str:
    """Normalize package name per PEP 503."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _get_pyodide_packages() -> set[str] | None:
    """Fetch the set of normalized package names available in Pyodide."""
    try:
        from marimo._pyodide.pyodide_constraints import (
            fetch_pyodide_package_versions,
        )

        versions = fetch_pyodide_package_versions()
        return {_normalize_name(name) for name in versions}
    except Exception:
        return None


@functools.cache
def _has_wasm_compatible_wheel(package_name: str) -> bool:
    """Check PyPI for a pure-python or emscripten wheel.

    Returns True if micropip can install this package (has a
    py3-none-any wheel, a py2.py3-none-any wheel, or an
    emscripten/wasm32 wheel). Returns True on network failure
    (fail open). Cached so a single export with N transitive deps
    hits PyPI at most once per unique package name.
    """
    url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
    except Exception:
        return True  # Can't check — assume compatible.

    urls = data.get("urls", [])
    if not urls:
        return True  # No files — likely a namespace package.

    for file_info in urls:
        filename = file_info.get("filename", "")
        if filename.endswith(".whl"):
            if (
                "none-any" in filename
                or "emscripten" in filename
                or "wasm" in filename
            ):
                return True
        # Source distributions can be built as pure-python by micropip.
        if filename.endswith((".tar.gz", ".zip")):
            return True

    return False


def _get_notebook_deps(ctx: RuleContext) -> set[str] | None:
    """Extract PEP 723 dependencies from the notebook's script metadata."""
    if not ctx.notebook.filename:
        return None

    try:
        from marimo._runtime.packages.utils import (
            filter_requirements_for_emscripten,
        )
        from marimo._utils.inline_script_metadata import PyProjectReader

        reader = PyProjectReader.from_filename(ctx.notebook.filename)
        deps = filter_requirements_for_emscripten(reader.dependencies)
        if not deps:
            return None
        names: set[str] = set()
        for dep in deps:
            match = re.match(
                r"^([A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?)", dep
            )
            if match:
                names.add(_normalize_name(match.group(1)))
        return names
    except Exception:
        return None


def _resolve_dep_tree(root_deps: set[str]) -> set[str]:
    """Walk installed metadata to resolve the transitive dependency tree."""
    installed: dict[str, importlib.metadata.Distribution] = {}
    for dist in importlib.metadata.distributions():
        name = dist.metadata.get("Name")
        if name:
            installed[_normalize_name(name)] = dist

    resolved: set[str] = set()
    queue = list(root_deps)
    while queue:
        pkg = queue.pop()
        if pkg in resolved:
            continue
        resolved.add(pkg)

        entry: importlib.metadata.Distribution | None = installed.get(pkg)
        if entry is None:
            continue

        requires = entry.metadata.get_all("Requires-Dist") or []
        for req in requires:
            if "extra ==" in req:
                continue
            match = re.match(
                r"^([A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?)", req
            )
            if match:
                dep_name = _normalize_name(match.group(1))
                if dep_name not in resolved:
                    queue.append(dep_name)

    return resolved


class IncompatiblePackagesRule(LintRule):
    """MW003: Packages in the dependency tree incompatible with WASM.

    This rule resolves the notebook's PEP 723 dependency tree and checks
    each package against PyPI for WASM-compatible wheels. Catches
    transitive dependencies like `jaxlib` (pulled in by `jax`) that
    have no pure-python or emscripten wheel on PyPI.

    ## What it does

    Reads the notebook's PEP 723 `dependencies`, walks their transitive
    dependency tree via installed metadata, then queries PyPI's JSON API
    to check whether each package has a `py3-none-any` or emscripten
    wheel available. Packages only in pyodide-lock.json are also accepted.

    ## Why is this bad?

    Pyodide can only install pure-Python wheels via micropip, or packages
    that are pre-built in the Pyodide distribution. Packages with only
    platform-specific native wheels will fail to install in the browser.

    ## Examples

    **Problematic:**
    ```python
    import jax  # jaxlib (transitive dep) has only native wheels
    ```

    **Not flagged:**
    ```python
    import numpy  # Native, but pre-built in Pyodide
    ```

    **Not flagged:**
    ```python
    import requests  # Pure Python wheel on PyPI
    ```

    ## References

    - https://pyodide.org/en/stable/usage/packages-in-pyodide.html
    """

    code = "MW003"
    name = "incompatible-package"
    description = "Package with native extensions not available in Pyodide"
    severity = Severity.WASM
    fixable = False

    async def check(self, ctx: RuleContext) -> None:
        pyodide_packages = _get_pyodide_packages()
        if pyodide_packages is None:
            return

        notebook_deps = _get_notebook_deps(ctx)
        if notebook_deps is None:
            return

        notebook_deps.discard("marimo")
        if not notebook_deps:
            return

        dep_tree = _resolve_dep_tree(notebook_deps)

        incompatible: list[str] = []
        for pkg in sorted(dep_tree):
            # In Pyodide's lockfile — definitely available.
            if pkg in pyodide_packages:
                continue

            # Check PyPI for a WASM-compatible wheel.
            if not _has_wasm_compatible_wheel(pkg):
                incompatible.append(pkg)

        if not incompatible:
            return

        pkg_list = ", ".join(incompatible)
        await ctx.add_diagnostic(
            Diagnostic(
                message=(
                    f"Package(s) without WASM-compatible wheels on PyPI: "
                    f"{pkg_list}. "
                    f"These will fail to install in Pyodide."
                ),
                line=1,
                column=0,
                fix=(
                    "Remove these packages or replace with pure-Python "
                    "alternatives available in Pyodide."
                ),
            )
        )
