# Copyright 2026 Marimo. All rights reserved.
"""Resolve Pyodide-compatible package constraints from pyodide-lock.json."""

from __future__ import annotations

import json
import urllib.request
from typing import Any

from marimo import _loggers

LOGGER = _loggers.marimo_logger()

# Pyodide version matching frontend/package.json — update together.
PYODIDE_VERSION = "0.27.7"

# Derived from the lockfile's info.python field (Pyodide 0.27.7 → 3.12.7).
PYODIDE_PYTHON_VERSION = "3.12"

_LOCKFILE_URL = (
    "https://cdn.jsdelivr.net/pyodide/v{version}/full/pyodide-lock.json"
)


def fetch_pyodide_package_versions(
    pyodide_version: str = PYODIDE_VERSION,
) -> dict[str, str]:
    """Fetch pyodide-lock.json and return {package_name: version} dict.

    Only includes entries with package_type == "package" and excludes
    test packages (names ending in "-tests").
    """
    url = _LOCKFILE_URL.format(version=pyodide_version)
    with urllib.request.urlopen(url, timeout=30) as resp:
        data: dict[str, Any] = json.loads(resp.read())
    packages = data.get("packages", {})
    return {
        spec["name"]: spec["version"]
        for spec in packages.values()
        if spec.get("package_type") == "package"
        and not spec["name"].endswith("-tests")
    }


def write_constraint_file(
    path: str,
    pyodide_version: str = PYODIDE_VERSION,
) -> bool:
    """Fetch Pyodide lockfile and write a pip constraints file.

    Returns True on success, False if the lockfile couldn't be fetched.
    """
    try:
        versions = fetch_pyodide_package_versions(pyodide_version)
    except Exception:
        LOGGER.warning(
            "Could not fetch Pyodide lockfile — "
            "running without package version constraints."
        )
        return False
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(
            f"{pkg}=={version}\n" for pkg, version in sorted(versions.items())
        )
    return True


def check_wasm_compatibility(
    notebook_path: str,
    pyodide_version: str = PYODIDE_VERSION,
) -> list[str]:
    """Check resolved notebook deps for packages incompatible with WASM.

    A package is incompatible if uv resolves it to a platform-specific
    wheel (has native extensions) and it's not pre-built in Pyodide.

    Returns a list of incompatible package names (empty = all OK).
    """
    import subprocess

    from marimo._cli.sandbox import find_uv_bin

    try:
        pyodide_packages = fetch_pyodide_package_versions(pyodide_version)
    except Exception:
        return []

    pyodide_names = {_normalize_name(name) for name in pyodide_packages}

    try:
        result = subprocess.run(
            [
                find_uv_bin(),
                "pip",
                "compile",
                "--python-version",
                PYODIDE_PYTHON_VERSION,
                "--no-header",
                "--no-annotate",
                notebook_path,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            return []
    except Exception:
        return []

    incompatible: list[str] = []
    for line in result.stdout.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Extract package name (before ==, >=, etc.)
        name = line.split("==")[0].split(">=")[0].split("<=")[0].strip()
        normalized = _normalize_name(name)
        # Pure-python packages are fine — they'll be micropip-installed.
        # Platform-specific packages not in Pyodide are the problem.
        # We check PyPI for wheel availability in a simpler way:
        # if the package is in Pyodide, it's fine. Otherwise, we check
        # if it has a pure-python wheel via the JSON API.
        if normalized not in pyodide_names and _has_native_extension(
            normalized
        ):
            incompatible.append(name)

    return incompatible


def _normalize_name(name: str) -> str:
    """Normalize package name per PEP 503."""
    import re

    return re.sub(r"[-_.]+", "-", name).lower()


def _has_native_extension(package_name: str) -> bool:
    """Check if a package only ships platform-specific wheels on PyPI.

    Returns True if the package has no pure-python wheel (py3-none-any).
    """
    url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
    except Exception:
        return False

    urls = data.get("urls", [])
    if not urls:
        return False

    for file_info in urls:
        filename = file_info.get("filename", "")
        if filename.endswith(".whl") and "py3-none-any" in filename:
            return False
        if filename.endswith((".tar.gz", ".zip")):
            # Source distributions can be pure-python
            return False

    return True
