# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import altair  # type:ignore[import]
    import pandas as pd  # type:ignore[import]


class DependencyManager:
    """Utilities for checking the status of dependencies."""

    @staticmethod
    def require_pandas(why: str) -> None:
        """
        Raise an ImportError if pandas is not installed.

        Args:
            why: A string of the form "for <reason>" that will be appended

        """
        if not DependencyManager.has_pandas:
            raise ImportError(
                f"pandas is required {why}. "
                + "You can install it with 'pip install pandas'"
            ) from None

    @staticmethod
    def require_altair(why: str) -> None:
        """
        Raise an ImportError if altair is not installed.

        Args:
            why: A string of the form "for <reason>" that will be appended

        """
        if not DependencyManager.has_altair:
            raise ImportError(
                f"altair is required {why}. "
                + "You can install it with 'pip install altair'"
            ) from None

    @property
    @staticmethod
    def has_pandas() -> bool:
        """Return True if pandas is installed."""
        try:
            import pandas  # type:ignore[import]
        except ImportError:
            return False
        return True

    @property
    @staticmethod
    def has_altair() -> bool:
        """Return True if altair is installed."""
        try:
            import altair  # type:ignore[import]
        except ImportError:
            return False
        return True
