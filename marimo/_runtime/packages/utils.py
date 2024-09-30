# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
import sys
from typing import List, Optional

from marimo._utils.platform import is_pyodide


def in_virtual_environment() -> bool:
    """Returns True if a venv/virtualenv is activated"""
    # https://stackoverflow.com/questions/1871549/how-to-determine-if-python-is-running-inside-a-virtualenv/40099080#40099080  # noqa: E501
    base_prefix = (
        getattr(sys, "base_prefix", None)
        or getattr(sys, "real_prefix", None)
        or sys.prefix
    )
    return sys.prefix != base_prefix


def in_conda_env() -> bool:
    return "CONDA_DEFAULT_ENV" in os.environ


def is_python_isolated() -> bool:
    """Returns True if not using system Python"""
    return in_virtual_environment() or in_conda_env() or is_pyodide()


def append_version(pkg_name: str, version: Optional[str]) -> str:
    """Qualify a version string with a leading '==' if it doesn't have one"""
    if version is None:
        return pkg_name
    if version == "":
        return pkg_name
    if version == "latest":
        return pkg_name
    return f"{pkg_name}=={version}"


def split_packages(package: str) -> List[str]:
    """
    Splits a package string into a list of packages.

    This can handle editable packages (i.e. local directories)

    e.g.
    "package1 package2" -> ["package1", "package2"]
    "package1==1.0.0 package2==2.0.0" -> ["package1==1.0.0", "package2==2.0.0"]
    "package1 -e /path/to/package1" -> ["package1 -e /path/to/package1"]
    "package1 --editable /path/to/package1" -> ["package1 --editable /path/to/package1"]
    "package1 -e /path/to/package1 package2" -> ["package1 -e /path/to/package1", "package2"]
    "package1 @ /path/to/package1" -> ["package1 @ /path/to/package1"]
    "foo==1.0; python_version>'3.6' bar==2.0; sys_platform=='win32'" -> ["foo==1.0; python_version>'3.6'", "bar==2.0; sys_platform=='win32'"]
    """  # noqa: E501
    packages: List[str] = []
    current_package: List[str] = []
    in_environment_marker = False

    for part in package.split():
        if part in ["-e", "--editable", "@"]:
            current_package.append(part)
        elif current_package and current_package[-1] in [
            "-e",
            "--editable",
            "@",
        ]:
            current_package.append(part)
        elif part.endswith(";"):
            if current_package:
                packages.append(" ".join(current_package))
                current_package = []
            in_environment_marker = True
            current_package.append(part)
        elif in_environment_marker:
            current_package.append(part)
            if part.endswith("'") or part.endswith('"'):
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
