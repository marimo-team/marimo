# Copyright 2026 Marimo. All rights reserved.
"""The base error for environment-manager failures.

Every failure invoking an environment manager -- or the manifest edits
delegated to one -- derives from this type, so callers of
backend-agnostic callers catch one error instead of enumerating backends.
"""

from __future__ import annotations


class EnvironmentManagerError(Exception):
    """Base for failures invoking an environment manager."""
