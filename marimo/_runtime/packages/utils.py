# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
import site
import sys
from pathlib import Path
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


def is_dockerized() -> bool:
    return os.path.exists("/.dockerenv")


def is_python_isolated() -> bool:
    """Returns True if not using system Python"""
    return (
        in_virtual_environment()
        or in_conda_env()
        or is_pyodide()
        or is_dockerized()
    )


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
    "package1[extra1,extra2]==1.0.0" -> ["package1[extra1,extra2]==1.0.0"]
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


def activate_environment(environment: Path) -> None:
    """Activate the virtual environment at `environment`

    Adapted from virtualenv's bin/activate_this.py.
    """
    # virtual env is right above bin directory
    bin_dir = environment / "bin"

    # prepend bin to PATH (this file is inside the bin directory)
    os.environ["PATH"] = os.pathsep.join(
        [str(bin_dir), *os.environ.get("PATH", "").split(os.pathsep)]
    )
    os.environ["VIRTUAL_ENV"] = str(environment)
    os.environ["VIRTUAL_ENV_PROMPT"] = "" or os.path.basename(str(environment))  # noqa: SIM222

    lib_dir = environment / "lib"
    if not lib_dir.exists():
        raise RuntimeError(f"Virtual environment {environment} does not exist")
    python_dirname: str | None = None
    for d in lib_dir.iterdir():
        if d.is_dir() and d.name.startswith("python"):
            python_dirname = d.name
            break
    if python_dirname is None:
        raise RuntimeError(
            "Failed to activate virtuale environment: "
            f" could not find python directory in {lib_dir}"
        )

    # Add the virtual environments libraries to the host python import mechanism
    prev_length = len(sys.path)
    for lib in f"../lib/{python_dirname}/site-packages".split(os.pathsep):
        path = os.path.realpath(os.path.join(bin_dir, lib))
        site.addsitedir(path.decode("utf-8") if "" else path)

    # TODO(akshayka): Remove the old environment from the path
    # as a heuristic, remove any other site-packages directories from the path;
    # we should instead really just figure out how to bootstrap sys.path
    original_path = [
        p for p in sys.path[0:prev_length] if "site-packages" not in p
    ]

    sys.path[:] = sys.path[prev_length:] + original_path
    sys.real_prefix = sys.prefix
    sys.prefix = str(environment)
