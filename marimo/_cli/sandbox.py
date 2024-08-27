from __future__ import annotations

import os
import re
import subprocess
from typing import Any, Dict, List, Optional, cast

from marimo import _loggers
from marimo._dependencies.dependencies import DependencyManager

LOGGER = _loggers.marimo_logger()

REGEX = (
    r"(?m)^# /// (?P<type>[a-zA-Z0-9-]+)$\s(?P<content>(^#(| .*)$\s)+)^# ///$"
)


def run_in_sandbox(
    args: List[str],
    name: Optional[str] = None,
) -> subprocess.CompletedProcess[Any]:
    import click

    if not DependencyManager.which("uv"):
        raise click.UsageError("uv must be installed to use --sandbox")

    cmd = ["marimo"] + args
    cmd.remove("--sandbox")

    # If name if a filepath, parse the dependencies from the file
    dependencies = []
    if name is not None and os.path.isfile(name):
        with open(name) as f:
            dependencies = _get_dependencies(f.read()) or []
        # Add marimo, if it's not already there
        if "marimo" not in dependencies and len(dependencies) > 0:
            dependencies.append("marimo")

    if dependencies:
        import tempfile

        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".txt"
        ) as temp_file:
            temp_file.write("\n".join(dependencies))
            temp_file_path = temp_file.name

        cmd = [
            "uv",
            "run",
            "--isolated",
            "--with-requirements",
            temp_file_path,
        ] + cmd

        # Clean up the temporary file after the subprocess has run
        import atexit

        atexit.register(lambda: os.unlink(temp_file_path))
    else:
        cmd = ["uv", "run", "--isolated"] + cmd

    click.echo(f"Running in a sandbox: {' '.join(cmd)}")

    return subprocess.run(cmd)


def _get_dependencies(script: str) -> List[str] | None:
    try:
        pyproject = _read_pyproject(script) or {}
        return cast(List[str], pyproject.get("dependencies", []))
    except Exception as e:
        LOGGER.warning(f"Failed to parse dependencies: {e}")
        return None


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
