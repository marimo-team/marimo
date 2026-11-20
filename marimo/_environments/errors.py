# Copyright 2026 Marimo. All rights reserved.
"""The base error for environment-manager failures.

Every failure invoking an environment manager -- or the manifest edits
delegated to one -- derives from this type, so callers of
backend-agnostic seams catch one error instead of enumerating backends.
"""

from __future__ import annotations


class EnvironmentManagerError(Exception):
    """Base for failures invoking an environment manager."""


class EnvironmentManagerNotFoundError(EnvironmentManagerError):
    """The selected environment manager is not installed or on PATH."""


class MissingScriptMetadataError(EnvironmentManagerError):
    """The target script has no PEP 723 inline metadata block."""


class SandboxRestartRequired(EnvironmentManagerError):
    """Applying the manifest requires relaunching the kernel.

    The active interpreter is incompatible, or synchronization selected a
    different prefix. Callers must not report the requested
    packages as importable until the kernel launches the new environment.
    """
