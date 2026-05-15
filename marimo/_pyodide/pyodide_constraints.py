# Copyright 2026 Marimo. All rights reserved.
"""Resolve Pyodide-compatible package constraints from pyodide-lock.json.

The lockfile is fetched from `wasm.marimo.app` (which serves a marimo-patched
fork of upstream `pyodide-lock.json`). Set `MARIMO_PYODIDE_LOCK_FILE` to read
a local copy instead — useful for offline / air-gapped environments and for
testing.
"""

from __future__ import annotations

import os
import re

import msgspec

from marimo import _loggers
from marimo._utils import requests
from marimo._version import __version__

LOGGER = _loggers.marimo_logger()

# Pyodide version matching frontend/package.json — update together.
PYODIDE_VERSION = "0.27.7"

# Derived from the lockfile's info.python field (Pyodide 0.27.7 → 3.12.7).
PYODIDE_PYTHON_VERSION = "3.12"

# Env var pointing at a local pyodide-lock.json. Lets offline / air-gapped
# users supply the lockfile out-of-band instead of fetching from the host.
PYODIDE_LOCK_FILE_ENV = "MARIMO_PYODIDE_LOCK_FILE"

# We host our own version of
# "https://cdn.jsdelivr.net/pyodide/v{version}/full/pyodide-lock.json"
# as marimo contains patches to support more packages. The `v` query is
# the marimo version (cache-buster); the server selects the lockfile for
# whichever pyodide release that marimo build was pinned to.
_LOCKFILE_URL = f"https://wasm.marimo.app/pyodide-lock.json?v={__version__}"


class PyodidePackage(msgspec.Struct, kw_only=True):
    """A single package entry inside pyodide-lock.json."""

    name: str
    version: str
    package_type: str = ""


class PyodideLockfile(msgspec.Struct, kw_only=True):
    """Top-level shape of pyodide-lock.json.

    Other fields (`info`, `package` indices, etc.) are ignored.
    """

    packages: dict[str, PyodidePackage] = msgspec.field(default_factory=dict)


def _read_lockfile() -> PyodideLockfile:
    override = os.environ.get(PYODIDE_LOCK_FILE_ENV)
    if override:
        with open(override, "rb") as f:
            payload = f.read()
    else:
        # `marimo._utils.requests` ships its own `marimo/<version>` UA.
        payload = (
            requests.get(_LOCKFILE_URL, timeout=30).raise_for_status().content
        )
    return msgspec.json.decode(payload, type=PyodideLockfile)


def fetch_pyodide_package_versions() -> dict[str, str]:
    """Fetch pyodide-lock.json and return {package_name: version}.

    Reads from the path in `$MARIMO_PYODIDE_LOCK_FILE` if set, otherwise
    fetches from `wasm.marimo.app`. Only entries with
    `package_type == "package"` are included; test packages
    (names ending in `-tests`) are excluded.
    """
    lockfile = _read_lockfile()
    return {
        spec.name: spec.version
        for spec in lockfile.packages.values()
        if spec.package_type == "package" and not spec.name.endswith("-tests")
    }


def write_constraint_file(
    path: str,
) -> bool:
    """Fetch Pyodide lockfile and write a pip constraints file.

    Returns True on success, False if the lockfile couldn't be fetched.
    """
    try:
        versions = fetch_pyodide_package_versions()
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
