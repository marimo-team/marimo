# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import importlib.metadata
import importlib.util
import shutil
import sys
from dataclasses import dataclass

from marimo._dependencies.errors import ManyModulesNotFoundError


@dataclass
class Dependency:
    pkg: str
    min_version: str | None = None
    max_version: str | None = None

    def has(self, quiet: bool = False) -> bool:
        """Return True if the dependency is installed."""
        try:
            has_dep = importlib.util.find_spec(self.pkg) is not None
            if not has_dep:
                return False
        except (ModuleNotFoundError, importlib.metadata.PackageNotFoundError):
            # Could happen for nested imports (e.g. foo.bar)
            return False

        if not quiet and (self.min_version or self.max_version):
            self.warn_if_mismatch_version(self.min_version, self.max_version)
        return True

    def has_at_version(
        self,
        *,
        min_version: str | None,
        max_version: str | None = None,
        quiet: bool = False,
    ) -> bool:
        if not self.has(quiet=quiet):
            return False
        return _version_check(
            pkg=self.pkg,
            v=self.get_version(),
            min_v=min_version,
            max_v=max_version,
            quiet=quiet,
        )

    def has_required_version(self, quiet: bool = False) -> bool:
        return self.has_at_version(
            min_version=self.min_version,
            max_version=self.max_version,
            quiet=quiet,
        )

    def imported(self) -> bool:
        return self.pkg in sys.modules

    def require(self, why: str) -> None:
        """
        Raise an ModuleNotFoundError if the package is not installed.

        Args:
            why: A string of the form "for <reason>" that will be appended

        """
        if not self.has():
            message = f"{self.pkg} is required {why}."
            sys.stderr.write(message + "\n\n")
            # Including the `name` helps with auto-installations
            raise ModuleNotFoundError(message, name=self.pkg) from None

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
        try:
            return importlib.metadata.version(self.pkg)
        except importlib.metadata.PackageNotFoundError:
            return f"{__import__(self.pkg).__version__}"

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
    quiet: bool = False,
) -> bool:
    if min_v is None and max_v is None:
        return True

    from packaging import version

    parsed_min_version = version.parse(min_v) if min_v else None
    parsed_max_version = version.parse(max_v) if max_v else None
    parsed_v = version.parse(v)

    if parsed_min_version is not None and parsed_v < parsed_min_version:
        msg = f"Mismatched version of {pkg}: expected >={min_v}, got {v}"
        if raise_error:
            raise RuntimeError(msg)
        if not quiet:
            sys.stderr.write(f"{msg}. Some features may not work correctly.")
        return False

    if parsed_max_version is not None and parsed_v >= parsed_max_version:
        msg = f"Mismatched version of {pkg}: expected <{max_v}, got {v}"
        if raise_error:
            raise RuntimeError(msg)
        if not quiet:
            sys.stderr.write(f"{msg}. Some features may not work correctly.")
        return False

    return True


class DependencyManager:
    """Utilities for checking the status of dependencies."""

    sympy = Dependency("sympy")
    pandas = Dependency("pandas")
    polars = Dependency("polars")
    ibis = Dependency("ibis")
    dotenv = Dependency("dotenv")
    numpy = Dependency("numpy")
    altair = Dependency("altair", min_version="5.3.0", max_version="6.0.0")
    duckdb = Dependency("duckdb")
    chdb = Dependency("chdb")
    clickhouse_connect = Dependency("clickhouse_connect")
    sqlglot = Dependency("sqlglot")
    pillow = Dependency("PIL")
    plotly = Dependency("plotly")
    bokeh = Dependency("bokeh")
    pyarrow = Dependency("pyarrow")
    pyiceberg = Dependency("pyiceberg")
    openai = Dependency("openai")
    matplotlib = Dependency("matplotlib")
    anywidget = Dependency("anywidget")
    traitlets = Dependency("traitlets")
    watchdog = Dependency("watchdog")
    ipython = Dependency("IPython")
    ipywidgets = Dependency("ipywidgets")
    nbformat = Dependency("nbformat")
    narwhals = Dependency("narwhals")
    ruff = Dependency("ruff")
    black = Dependency("black")
    geopandas = Dependency("geopandas")
    opentelemetry = Dependency("opentelemetry")
    anthropic = Dependency("anthropic")
    google_ai = Dependency("google.generativeai")
    groq = Dependency("groq")
    panel = Dependency("panel")
    sqlalchemy = Dependency("sqlalchemy")
    pylsp = Dependency("pylsp")
    pytest = Dependency("pytest")
    vegafusion = Dependency("vegafusion")
    vl_convert_python = Dependency("vl_convert")
    dotenv = Dependency("dotenv")
    docstring_to_markdown = Dependency(
        "docstring_to_markdown", min_version="0.17.0"
    )
    tomlkit = Dependency("tomlkit")
    loro = Dependency("loro")
    boto3 = Dependency("boto3")
    litellm = Dependency("litellm")

    # Version requirements to properly support the new superfences introduced in
    # pymdown#2470
    new_superfences = Dependency("pymdownx", min_version="10.11.0")

    @staticmethod
    def has(pkg: str) -> bool:
        """Return True if any lib is installed."""
        return Dependency(pkg).has()

    @staticmethod
    def imported(pkg: str) -> bool:
        """Return True if the lib has been imported.

        Can be much faster than 'has'.
        """
        return Dependency(pkg).imported()

    @staticmethod
    def which(pkg: str) -> bool:
        """
        Checks if a CLI command is installed.
        """
        return shutil.which(pkg) is not None

    @staticmethod
    def require_many(why: str, *dependencies: Dependency) -> None:
        missing = [dep.pkg for dep in dependencies if not dep.has()]
        if missing:
            raise ManyModulesNotFoundError(
                missing,
                f"The following packages are required {why}: {', '.join(missing)}",
            )
