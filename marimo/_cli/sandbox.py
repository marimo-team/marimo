# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import atexit
import os
import re
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

import click

from marimo import __version__, _loggers
from marimo._cli.file_path import FileContentReader
from marimo._cli.print import bold, echo, green, muted
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._dependencies.dependencies import DependencyManager
from marimo._utils.versions import is_editable

LOGGER = _loggers.marimo_logger()

REGEX = (
    r"(?m)^# /// (?P<type>[a-zA-Z0-9-]+)$\s(?P<content>(^#(| .*)$\s)+)^# ///$"
)


def _get_dependencies(script: str) -> List[str] | None:
    """Get dependencies from string representation of script."""
    try:
        pyproject = _read_pyproject(script) or {}
        return _pyproject_toml_to_requirements_txt(pyproject)
    except Exception as e:
        LOGGER.warning(f"Failed to parse dependencies: {e}")
        return None


def _pyproject_toml_to_requirements_txt(
    pyproject: Dict[str, Any],
) -> List[str]:
    """
    Convert a pyproject.toml file to a requirements.txt file.

    If there is a `[tool.uv.sources]` section, we resolve the dependencies
    to their corresponding source.

    # dependencies = [
    #     "python-gcode",
    # ]
    #
    # [tool.uv.sources]
    # python-gcode = { git = "https://github.com/fetlab/python_gcode", rev = "new" }
    """  # noqa: E501
    dependencies = cast(List[str], pyproject.get("dependencies", []))
    if not dependencies:
        return []

    uv_sources = pyproject.get("tool", {}).get("uv", {}).get("sources", {})

    for dependency, source in uv_sources.items():
        # Find the index of the dependency. This may have a version
        # attached, so we cannot do .index()
        dep_index: int | None = None
        for i, dep in enumerate(dependencies):
            if (
                dep == dependency
                or dep.startswith(f"{dependency}==")
                or dep.startswith(f"{dependency}<")
                or dep.startswith(f"{dependency}>")
                or dep.startswith(f"{dependency}~")
            ):
                dep_index = i
                break

        if dep_index is None:
            continue

        new_dependency = None

        # Handle git dependencies
        if "git" in source:
            git_url = f"git+{source['git']}"
            ref = (
                source.get("rev") or source.get("branch") or source.get("tag")
            )
            new_dependency = (
                f"{dependency} @ {git_url}@{ref}"
                if ref
                else f"{dependency} @ {git_url}"
            )
        # Handle local paths
        elif "path" in source:
            new_dependency = f"{dependency} @ {source['path']}"

        # Handle URLs
        elif "url" in source:
            new_dependency = f"{dependency} @ {source['url']}"

        if new_dependency:
            if source.get("marker"):
                new_dependency += f"; {source['marker']}"

            dependencies[dep_index] = new_dependency

    return dependencies


def get_dependencies_from_filename(name: str) -> List[str]:
    if not name:
        return []

    try:
        contents, _ = FileContentReader().read_file(name)
        return _get_dependencies(contents) or []
    except FileNotFoundError:
        return []
    except Exception:
        LOGGER.warning(f"Failed to read dependencies from {name}")
        return []


def _read_pyproject(script: str) -> Dict[str, Any] | None:
    """
    Read the pyproject.toml file from the script.

    Adapted from https://peps.python.org/pep-0723/#reference-implementation
    """
    name = "script"
    matches = list(
        filter(lambda m: m.group("type") == name, re.finditer(REGEX, script))
    )
    if len(matches) > 1:
        raise ValueError(f"Multiple {name} blocks found")
    elif len(matches) == 1:
        content = "".join(
            line[2:] if line.startswith("# ") else line[1:]
            for line in matches[0].group("content").splitlines(keepends=True)
        )
        import tomlkit

        pyproject = tomlkit.parse(content)

        return pyproject
    else:
        return None


def _get_python_version_requirement(
    pyproject: Dict[str, Any] | None,
) -> str | None:
    """Extract Python version requirement from pyproject metadata."""
    if pyproject is None:
        return None

    try:
        version = pyproject.get("requires-python")
        # Only return string version requirements
        if not isinstance(version, str):
            return None
        return version
    except Exception as e:
        LOGGER.warning(f"Failed to parse Python version requirement: {e}")
        return None


def prompt_run_in_sandbox(name: str | None) -> bool:
    if GLOBAL_SETTINGS.MANAGE_SCRIPT_METADATA:
        return False

    if name is None:
        return False

    dependencies = get_dependencies_from_filename(name)
    if not dependencies:
        return False

    # Notebook has inlined dependencies.
    if DependencyManager.which("uv"):
        if GLOBAL_SETTINGS.YES:
            return True

        # Check if not in an interactive terminal (i.e. Docker)
        # default to False
        if not sys.stdin.isatty():
            return False

        return click.confirm(
            "This notebook has inlined package dependencies.\n"
            + green(
                "Run in a sandboxed venv containing this notebook's "
                "dependencies?",
                bold=True,
            ),
            default=True,
        )
    else:
        echo(
            bold(
                "This notebook has inlined package dependencies. \n"
                + "Consider installing uv so that marimo can create a "
                "temporary venv with the notebook's packages: "
                "https://github.com/astral-sh/uv"
            )
        )
    return False


def _is_marimo_dependency(dependency: str) -> bool:
    # Split on any version specifier
    without_version = re.split(r"[=<>~]+", dependency)[0]
    # Match marimo and marimo[extras], but not marimo-<something-else>
    return without_version == "marimo" or without_version.startswith("marimo[")


def _is_versioned(dependency: str) -> bool:
    return any(c in dependency for c in ("==", ">=", "<=", ">", "<", "~"))


def _normalize_sandbox_dependencies(
    dependencies: List[str], marimo_version: str
) -> List[str]:
    """Normalize marimo dependencies to have only one version.

    If multiple marimo dependencies exist, prefer the one with brackets.
    Add version to the remaining one if not already versioned.
    """
    # Find all marimo dependencies
    marimo_deps = [d for d in dependencies if _is_marimo_dependency(d)]
    if not marimo_deps:
        if is_editable("marimo"):
            LOGGER.info("Using editable of marimo for sandbox")
            return dependencies + [f"-e {get_marimo_dir()}"]

        return dependencies + [f"marimo=={marimo_version}"]

    # Prefer the one with brackets if it exists
    bracketed = next((d for d in marimo_deps if "[" in d), None)
    chosen = bracketed if bracketed else marimo_deps[0]

    # Remove all marimo deps
    filtered = [d for d in dependencies if not _is_marimo_dependency(d)]

    if is_editable("marimo"):
        LOGGER.info("Using editable of marimo for sandbox")
        return filtered + [f"-e {get_marimo_dir()}"]

    # Add version if not already versioned
    if not _is_versioned(chosen):
        chosen = f"{chosen}=={marimo_version}"

    return filtered + [chosen]


def get_marimo_dir() -> Path:
    return Path(__file__).parent.parent.parent


def construct_uv_command(args: list[str], name: str | None) -> list[str]:
    cmd = ["marimo"] + args
    if "--sandbox" in cmd:
        cmd.remove("--sandbox")

    # If name if a filepath, parse the dependencies from the file
    dependencies = (
        get_dependencies_from_filename(name) if name is not None else []
    )

    # If there are no dependencies, which can happen for marimo new or
    # on marimo edit a_new_file.py, uv may use a cached venv, even though
    # we are passing --isolated; `--refresh` ensures that the venv is
    # actually ephemeral.
    uv_needs_refresh = not dependencies

    # Normalize marimo dependencies
    dependencies = _normalize_sandbox_dependencies(dependencies, __version__)

    with tempfile.NamedTemporaryFile(
        mode="w", delete=False, suffix=".txt"
    ) as temp_file:
        temp_file.write("\n".join(dependencies))
        temp_file_path = temp_file.name
    # Clean up the temporary file after the subprocess has run
    atexit.register(lambda: os.unlink(temp_file_path))

    # Get Python version requirement if available
    if name is not None and os.path.exists(name):
        contents, _ = FileContentReader().read_file(name)
        pyproject = _read_pyproject(contents)
        python_version = (
            _get_python_version_requirement(pyproject)
            if pyproject is not None
            else None
        )
    else:
        python_version = None

    # Construct base UV command
    uv_cmd = [
        "uv",
        "run",
        "--isolated",
        # sandboxed notebook shouldn't pick up existing pyproject.toml,
        # which may conflict with the sandbox requirements
        "--no-project",
        "--with-requirements",
        temp_file_path,
    ] + (["--refresh"] if uv_needs_refresh else [])

    # Add Python version if specified
    if python_version:
        uv_cmd.extend(["--python", python_version])

    # Final command assembly: combine the uv prefix with the original marimo
    # command.
    return uv_cmd + cmd


def run_in_sandbox(
    args: list[str],
    name: Optional[str] = None,
) -> int:
    if not DependencyManager.which("uv"):
        raise click.UsageError("uv must be installed to use --sandbox")
    uv_cmd = construct_uv_command(args, name)

    echo(f"Running in a sandbox: {muted(' '.join(uv_cmd))}")

    env = os.environ.copy()
    env["MARIMO_MANAGE_SCRIPT_METADATA"] = "true"

    process = subprocess.Popen(uv_cmd, env=env)

    def handler(sig: int, frame: Any) -> None:
        del sig
        del frame
        if sys.platform == "win32":
            os.kill(process.pid, signal.CTRL_C_EVENT)
        else:
            os.kill(process.pid, signal.SIGINT)

    signal.signal(signal.SIGINT, handler)

    return process.wait()
