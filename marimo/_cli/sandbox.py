# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import atexit
import os
import re
import signal
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional, cast

import click

from marimo import __version__, _loggers
from marimo._cli.file_path import FileContentReader
from marimo._cli.print import bold, echo, green
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._dependencies.dependencies import DependencyManager

LOGGER = _loggers.marimo_logger()

REGEX = (
    r"(?m)^# /// (?P<type>[a-zA-Z0-9-]+)$\s(?P<content>(^#(| .*)$\s)+)^# ///$"
)


def _get_dependencies(script: str) -> List[str] | None:
    """Get dependencies from string representation of script"""
    try:
        pyproject = _read_pyproject(script) or {}
        return cast(List[str], pyproject.get("dependencies", []))
    except Exception as e:
        LOGGER.warning(f"Failed to parse dependencies: {e}")
        return None


def get_dependencies_from_filename(name: str) -> List[str]:
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

        return tomlkit.parse(content)
    else:
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


def run_in_sandbox(
    args: List[str],
    name: Optional[str] = None,
) -> int:
    if not DependencyManager.which("uv"):
        raise click.UsageError("uv must be installed to use --sandbox")

    cmd = ["marimo"] + args
    if "--sandbox" in cmd:
        cmd.remove("--sandbox")

    # If name if a filepath, parse the dependencies from the file
    dependencies = (
        get_dependencies_from_filename(name) if name is not None else []
    )

    # The sandbox needs to manage marimo, too, to make sure
    # that the outer environment doesn't leak into the sandbox.
    if "marimo" not in dependencies:
        dependencies.append("marimo")

    # Rename marimo to marimo=={__version__}
    index_of_marimo = dependencies.index("marimo")
    if index_of_marimo != -1:
        dependencies[index_of_marimo] = f"marimo=={__version__}"

        # During development, you can comment this out to install an
        # editable version of marimo assuming you are in the marimo directory
        # DO NOT COMMIT THIS WHEN SUBMITTING PRs
        # dependencies[index_of_marimo] = "-e .[dev]"

    with tempfile.NamedTemporaryFile(
        mode="w", delete=False, suffix=".txt"
    ) as temp_file:
        temp_file.write("\n".join(dependencies))
        temp_file_path = temp_file.name
    # Clean up the temporary file after the subprocess has run
    atexit.register(lambda: os.unlink(temp_file_path))

    cmd = [
        "uv",
        "run",
        "--isolated",
        # sandboxed notebook shouldn't pick up existing pyproject.toml,
        # which may conflict with the sandbox requirements
        "--no-project",
        "--with-requirements",
        temp_file_path,
    ] + cmd

    echo(f"Running in a sandbox: {' '.join(cmd)}")

    env = os.environ.copy()
    env["MARIMO_MANAGE_SCRIPT_METADATA"] = "true"

    process = subprocess.Popen(cmd, env=env)

    def handler(sig: int, frame: Any) -> None:
        del sig
        del frame
        if sys.platform == "win32":
            os.kill(process.pid, signal.CTRL_C_EVENT)
        else:
            os.kill(process.pid, signal.SIGINT)

    signal.signal(signal.SIGINT, handler)

    return process.wait()
