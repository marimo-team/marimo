# Copyright 2026 Marimo. All rights reserved.
"""The base error for environment-manager failures.

Every failure invoking an environment manager -- or the manifest edits
delegated to one -- derives from this type, so callers of
backend-agnostic seams catch one error instead of enumerating backends.
"""

from __future__ import annotations


class EnvironmentManagerError(Exception):
    """Base for failures invoking an environment manager."""


class SandboxRestartRequired(EnvironmentManagerError):
    """The manifest synchronized, but not into the live kernel's prefix.

    This is not a solver failure. Callers must not report the requested
    packages as importable until the kernel launches the new environment.
    """
