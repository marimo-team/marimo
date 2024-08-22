# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import importlib.metadata
import importlib.util
import shutil
import sys
from dataclasses import dataclass

from packaging import version


@dataclass
class Dependency:
    pkg: str
    min_version: str | None = None
    max_version: str | None = None

    def has(self) -> bool:
        """Return True if the dependency is installed."""
        has_dep = importlib.util.find_spec(self.pkg) is not None
        if not has_dep:
            return False

        if self.min_version or self.max_version:
            self.warn_if_mismatch_version(self.min_version, self.max_version)
        return True

    def has_at_version(
        self, *, min_version: str | None, max_version: str | None = None
    ) -> bool:
        if not self.has():
            return False
        return _version_check(
            pkg=self.pkg,
            v=self.get_version(),
            min_v=min_version,
            max_v=max_version,
        )

    def require(self, why: str) -> None:
        """
        Raise an ModuleNotFoundError if the package is not installed.

        Args:
            why: A string of the form "for <reason>" that will be appended

        """
        if not self.has():
            raise ModuleNotFoundError(
                f"{self.pkg} is required {why}. "
                + f"You can install it with 'pip install {self.pkg}'."
            ) from None

    def require_at_version(
        self,
        why: str,
        *,
        min_version: str | None,
        max_version: str | None = None,
    ) -> None:
        self.require(why)

        _version_check(
            pkg=self.pkg,
            v=self.get_version(),
            min_v=min_version,
            max_v=max_version,
            raise_error=True,
        )

    def get_version(self) -> str:
        return importlib.metadata.version(self.pkg)

    def warn_if_mismatch_version(
        self,
        min_version: str | None = None,
        max_version: str | None = None,
    ) -> bool:
        return _version_check(
            pkg=self.pkg,
            v=self.get_version(),
            min_v=min_version,
            max_v=max_version,
            raise_error=False,
        )

    def require_version(
        self,
        min_version: str | None = None,
        max_version: str | None = None,
    ) -> None:
        _version_check(
            pkg=self.pkg,
            v=self.get_version(),
            min_v=min_version,
            max_v=max_version,
            raise_error=True,
        )


def _version_check(
    *,
    pkg: str,
    v: str,
    min_v: str | None = None,
    max_v: str | None = None,
    raise_error: bool = False,
) -> bool:
    if min_v is None and max_v is None:
        return True

    parsed_min_version = version.parse(min_v) if min_v else None
    parsed_max_version = version.parse(max_v) if max_v else None
    parsed_v = version.parse(v)

    if parsed_min_version is not None and parsed_v < parsed_min_version:
        msg = f"Mismatched version of {pkg}: expected >={min_v}, got {v}"
        if raise_error:
            raise RuntimeError(msg)
        sys.stderr.write(f"{msg}. Some features may not work correctly.")
        return False

    if parsed_max_version is not None and parsed_v >= parsed_max_version:
        msg = f"Mismatched version of {pkg}: expected <{max_v}, got {v}"
        if raise_error:
            raise RuntimeError(msg)
        sys.stderr.write(f"{msg}. Some features may not work correctly.")
        return False

    return True


class DependencyManager:
    """Utilities for checking the status of dependencies."""

    pandas = Dependency("pandas")
    polars = Dependency("polars")
    numpy = Dependency("numpy")
    altair = Dependency("altair", min_version="5.3.0", max_version="6.0.0")
    duckdb = Dependency("duckdb")
    pillow = Dependency("PIL")
    plotly = Dependency("plotly")
    pyarrow = Dependency("pyarrow")
    openai = Dependency("openai")
    matplotlib = Dependency("matplotlib")
    anywidget = Dependency("anywidget")
    watchdog = Dependency("watchdog")
    ipython = Dependency("IPython")
    ipywidgets = Dependency("ipywidgets")
    nbformat = Dependency("nbformat")
    narwhals = Dependency("narwhals")
    ruff = Dependency("ruff")
    black = Dependency("black")
    geopandas = Dependency("geopandas")
    opentelemetry = Dependency("opentelemetry")

    @staticmethod
    def has(pkg: str) -> bool:
        """Return True if any lib is installed."""
        return Dependency(pkg).has()

    @staticmethod
    def which(pkg: str) -> bool:
        """
        Checks if a CLI command is installed.
        """
        return shutil.which(pkg) is not None
