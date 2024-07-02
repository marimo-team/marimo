# Copyright 2024 Marimo. All rights reserved.
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
    def require_polars(why: str) -> None:
        """
        Raise an ModuleNotFoundError if polars is not installed.

        Args:
            why: A string of the form "for <reason>" that will be appended

        """
        if not DependencyManager.has_polars():
            raise ModuleNotFoundError(
                f"polars is required {why}. "
                + "You can install it with 'pip install polars'"
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
    def require_duckdb(why: str) -> None:
        """
        Raise an ModuleNotFoundError if duckdb is not installed.

        Args:
            why: A string of the form "for <reason>" that will be appended

        """
        if not DependencyManager.has_duckdb():
            raise ModuleNotFoundError(
                f"duckdb is required {why}. "
                + "You can install it with 'pip install duckdb'"
            ) from None

    @staticmethod
    def require_pillow(why: str) -> None:
        """
        Raise an ModuleNotFoundError if pillow is not installed.

        Args:
            why: A string of the form "for <reason>" that will be appended

        """
        if not DependencyManager.has_pillow():
            raise ModuleNotFoundError(
                f"pillow is required {why}. "
                + "You can install it with 'pip install pillow'"
            ) from None

    @staticmethod
    def require_plotly(why: str) -> None:
        """
        Raise an ModuleNotFoundError if plotly is not installed.

        Args:
            why: A string of the form "for <reason>" that will be appended

        """
        if not DependencyManager.has_plotly():
            raise ModuleNotFoundError(
                f"plotly is required {why}. "
                + "You can install it with 'pip install plotly'"
            ) from None

    @staticmethod
    def require_pyarrow(why: str) -> None:
        """
        Raise an ModuleNotFoundError if pyarrow is not installed.

        Args:
            why: A string of the form "for <reason>" that will be appended

        """
        if not DependencyManager.has_pyarrow():
            raise ModuleNotFoundError(
                f"pyarrow is required {why}. "
                + "You can install it with 'pip install pyarrow'"
            ) from None

    @staticmethod
    def has(pkg: str) -> bool:
        """Return True if any lib is installed."""
        return importlib.util.find_spec(pkg) is not None

    @staticmethod
    def has_openai() -> bool:
        """Return True if openai is installed."""
        return importlib.util.find_spec("openai") is not None

    @staticmethod
    def has_pandas() -> bool:
        """Return True if pandas is installed."""
        return importlib.util.find_spec("pandas") is not None

    @staticmethod
    def has_pyarrow() -> bool:
        """Return True if pyarrow is installed."""
        return importlib.util.find_spec("pyarrow") is not None

    @staticmethod
    def has_polars() -> bool:
        """Return True if polars is installed."""
        return importlib.util.find_spec("polars") is not None

    @staticmethod
    def has_numpy() -> bool:
        """Return True if numpy is installed."""
        return importlib.util.find_spec("numpy") is not None

    @staticmethod
    def has_altair() -> bool:
        """Return True if altair is installed."""
        return importlib.util.find_spec("altair") is not None

    @staticmethod
    def has_duckdb() -> bool:
        """Return True if duckdb is installed."""
        return importlib.util.find_spec("duckdb") is not None

    @staticmethod
    def has_pillow() -> bool:
        """Return True if pillow is installed."""
        return importlib.util.find_spec("PIL") is not None

    @staticmethod
    def has_plotly() -> bool:
        """Return True if plotly is installed."""
        return importlib.util.find_spec("plotly") is not None

    @staticmethod
    def has_matplotlib() -> bool:
        """Return True if matplotlib is installed."""
        return importlib.util.find_spec("matplotlib") is not None

    @staticmethod
    def has_anywidget() -> bool:
        """Return True if anywidget is installed."""
        return importlib.util.find_spec("anywidget") is not None

    @staticmethod
    def has_watchdog() -> bool:
        """Return True if watchdog is installed."""
        return importlib.util.find_spec("watchdog") is not None

    @staticmethod
    def has_ipython() -> bool:
        """Return True if IPython is installed."""
        return importlib.util.find_spec("IPython") is not None

    @staticmethod
    def has_nbformat() -> bool:
        """Return True if nbformat is installed."""
        return importlib.util.find_spec("nbformat") is not None
