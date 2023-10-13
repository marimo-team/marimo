# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import importlib.util


class DependencyManager:
    """Utilities for checking the status of dependencies."""

    @staticmethod
    def require_pandas(why: str) -> None:
        """
        Raise an ModuleNotFoundError if pandas is not installed.

        Args:
            why: A string of the form "for <reason>" that will be appended

        """
        if not DependencyManager.has_pandas():
            raise ModuleNotFoundError(
                f"pandas is required {why}. "
                + "You can install it with 'pip install pandas'"
            ) from None

    @staticmethod
    def require_numpy(why: str) -> None:
        """
        Raise an ModuleNotFoundError if numpy is not installed.

        Args:
            why: A string of the form "for <reason>" that will be appended

        """
        if not DependencyManager.has_numpy():
            raise ModuleNotFoundError(
                f"numpy is required {why}. "
                + "You can install it with 'pip install numpy'"
            ) from None

    @staticmethod
    def require_altair(why: str) -> None:
        """
        Raise an ModuleNotFoundError if altair is not installed.

        Args:
            why: A string of the form "for <reason>" that will be appended

        """
        if not DependencyManager.has_altair():
            raise ModuleNotFoundError(
                f"altair is required {why}. "
                + "You can install it with 'pip install altair'"
            ) from None

    @staticmethod
    def has_pandas() -> bool:
        """Return True if pandas is installed."""
        return importlib.util.find_spec("pandas") is not None

    @staticmethod
    def has_numpy() -> bool:
        """Return True if numpy is installed."""
        return importlib.util.find_spec("numpy") is not None

    @staticmethod
    def has_altair() -> bool:
        """Return True if altair is installed."""
        return importlib.util.find_spec("altair") is not None
