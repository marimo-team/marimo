# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import dataclasses
import os
import re
import sys
from typing import TYPE_CHECKING

from marimo._utils.platform import is_pyodide

if TYPE_CHECKING:
    from collections.abc import Mapping


def in_virtual_environment() -> bool:
    """Returns True if a venv/virtualenv is activated"""
    # https://stackoverflow.com/questions/1871549/how-to-determine-if-python-is-running-inside-a-virtualenv/40099080#40099080
    base_prefix = (
        getattr(sys, "base_prefix", None)
        or getattr(sys, "real_prefix", None)
        or sys.prefix
    )
    return sys.prefix != base_prefix


def in_conda_env() -> bool:
    return "CONDA_DEFAULT_ENV" in os.environ


def is_dockerized() -> bool:
    return os.path.exists("/.dockerenv")


def is_modal_image() -> bool:
    return os.environ.get("MODAL_TASK_ID") is not None


def is_python_isolated() -> bool:
    """Returns True if not using system Python"""
    return (
        in_virtual_environment()
        or in_conda_env()
        or is_pyodide()
        or is_dockerized()
        or is_modal_image()
    )


def marker_environment_for_platform(
    sys_platform: str | None = None,
) -> dict[str, str]:
    """Build a PEP 508 marker evaluation environment.

    When `sys_platform` is provided, overrides the current platform (e.g.
    `"emscripten"` for Pyodide / WASM).
    """
    from packaging.markers import default_environment

    env = {k: str(v) for k, v in default_environment().items()}
    if sys_platform is not None:
        env["sys_platform"] = sys_platform
    return env


def requirement_applies(
    requirement: str,
    *,
    marker_environment: Mapping[str, str] | None = None,
) -> bool:
    """Return whether a PEP 508 requirement applies in the given environment."""
    if ";" not in requirement:
        return True
    _, marker_str = requirement.split(";", 1)
    marker_str = marker_str.strip()
    if not marker_str:
        return True
    from packaging.markers import Marker, default_environment

    env = (
        dict(marker_environment)
        if marker_environment is not None
        else {k: str(v) for k, v in default_environment().items()}
    )
    return Marker(marker_str).evaluate(env)


def strip_requirement_name(requirement: str) -> str:
    """Strip version specifiers and environment markers from a PEP 508 requirement."""
    if not requirement or not isinstance(requirement, str):
        return requirement if isinstance(requirement, str) else ""

    requirement = requirement.strip()
    if not requirement:
        return requirement

    # URL dependencies (package @ <url>) — leave as-is.
    if "@" in requirement:
        name, rhs = requirement.split("@", 1)
        rhs = rhs.strip()
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://", rhs):
            return requirement

    if ";" in requirement:
        requirement = requirement.split(";", 1)[0].strip()

    parts = re.split(
        r"\s*(?:===|==|!=|<=|>=|~=|<|>)\s*",
        requirement,
        maxsplit=1,
    )
    return parts[0].strip() if parts else requirement


def filter_requirements_for_emscripten(requirements: list[str]) -> list[str]:
    """Filter PEP 508 requirements to those applicable on Emscripten (Pyodide)."""
    env = marker_environment_for_platform("emscripten")
    return [
        req
        for req in requirements
        if requirement_applies(req, marker_environment=env)
    ]


def append_version(pkg_name: str, version: str | None) -> str:
    """Qualify a version string with a leading '==' if it doesn't have one"""
    if version is None:
        return pkg_name
    if version == "":
        return pkg_name
    if version == "latest":
        return pkg_name
    return f"{pkg_name}=={version}"


def split_packages(package: str) -> list[str]:
    """
    Splits a package string into a list of packages.

    This can handle editable packages (i.e. local directories)

    e.g.
    "package1[extra1,extra2]==1.0.0" -> ["package1[extra1,extra2]==1.0.0"]
    "package1 package2" -> ["package1", "package2"]
    "package1==1.0.0 package2==2.0.0" -> ["package1==1.0.0", "package2==2.0.0"]
    "package1 -e /path/to/package1" -> ["package1 -e /path/to/package1"]
    "package1 --editable /path/to/package1" -> ["package1 --editable /path/to/package1"]
    "package1 -e /path/to/package1 package2" -> ["package1 -e /path/to/package1", "package2"]
    "package1 @ /path/to/package1" -> ["package1 @ /path/to/package1"]
    "foo==1.0; python_version>'3.6' bar==2.0; sys_platform=='win32'" -> ["foo==1.0; python_version>'3.6'", "bar==2.0; sys_platform=='win32'"]
    """
    packages: list[str] = []
    current_package: list[str] = []
    in_environment_marker = False

    for part in package.split():
        if (
            part in ["-e", "--editable", "@"]
            or current_package
            and current_package[-1]
            in [
                "-e",
                "--editable",
                "@",
            ]
        ):
            current_package.append(part)
        elif part.endswith(";"):
            if current_package:
                packages.append(" ".join(current_package))
                current_package = []
            in_environment_marker = True
            current_package.append(part)
        elif in_environment_marker:
            current_package.append(part)
            if part.endswith(("'", '"')):
                in_environment_marker = False
                packages.append(" ".join(current_package))
                current_package = []
        else:
            if current_package:
                packages.append(" ".join(current_package))
            current_package = [part]

    if current_package:
        packages.append(" ".join(current_package))

    return [pkg.strip() for pkg in packages]


@dataclasses.dataclass
class PackageRequirement:
    """A package requirement with name and optional extras."""

    name: str
    extras: set[str] = dataclasses.field(default_factory=set)

    @classmethod
    def parse(cls, requirement: str) -> PackageRequirement:
        """Parse a package requirement string into name and extras."""
        match = re.match(r"^([^\[\]]+)(?:\[([^\[\]]+)\])?$", requirement)
        if not match:
            return cls(name=requirement)
        name = match.group(1)
        extras = set(match.group(2).split(",")) if match.group(2) else set()
        return cls(name=name, extras=extras)

    def __str__(self) -> str:
        """Convert back to a package requirement string."""
        if not self.extras:
            return self.name
        return f"{self.name}[{','.join(sorted(self.extras))}]"
