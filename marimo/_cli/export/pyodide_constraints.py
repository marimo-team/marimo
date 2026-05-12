# Copyright 2026 Marimo. All rights reserved.
"""Resolve Pyodide-compatible package constraints from pyodide-lock.json."""

from __future__ import annotations

import json
import os
import re
import urllib.request
from typing import Any

from marimo import _loggers
from marimo._version import __version__

LOGGER = _loggers.marimo_logger()

# Pyodide version matching frontend/package.json — update together.
PYODIDE_VERSION = "0.27.7"

# Derived from the lockfile's info.python field (Pyodide 0.27.7 → 3.12.7).
PYODIDE_PYTHON_VERSION = "3.12"

# Env var pointing at a local pyodide-lock.json. Lets offline / air-gapped
# users supply the lockfile out-of-band instead of fetching from the CDN.
PYODIDE_LOCK_FILE_ENV = "MARIMO_PYODIDE_LOCK_FILE"

# We host our own version of
# "https://cdn.jsdelivr.net/pyodide/v{version}/full/pyodide-lock.json"
# as marimo contains patches to support more packages. The `v` query is
# the marimo version (cache-buster); the server selects the lockfile for
# whichever pyodide release that marimo build was pinned to.
_LOCKFILE_URL = f"https://wasm.marimo.app/pyodide-lock.json?v={__version__}"


def _read_lockfile(pyodide_version: str) -> dict[str, Any]:
    del (
        pyodide_version
    )  # the marimo-hosted lockfile is version-pinned server-side
    override = os.environ.get(PYODIDE_LOCK_FILE_ENV)
    if override:
        with open(override, "rb") as f:
            return json.loads(f.read())  # type: ignore[no-any-return]
    # Cloudflare blocks the default `Python-urllib/...` User-Agent.
    req = urllib.request.Request(
        _LOCKFILE_URL, headers={"User-Agent": "marimo-cli"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())  # type: ignore[no-any-return]


def fetch_pyodide_package_versions(
    pyodide_version: str = PYODIDE_VERSION,
) -> dict[str, str]:
    """Fetch pyodide-lock.json and return {package_name: version} dict.

    Reads from the path in $MARIMO_PYODIDE_LOCK_FILE if set, otherwise
    fetches from the Pyodide CDN. Only includes entries with
    package_type == "package" and excludes test packages
    (names ending in "-tests").
    """
    data = _read_lockfile(pyodide_version)
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


def normalize_package_name(name: str) -> str:
    """Normalize package name per PEP 503."""
    return re.sub(r"[-_.]+", "-", name).lower()
