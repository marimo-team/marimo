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

from marimo import _loggers
from marimo._dependencies.dependencies import DependencyManager

LOGGER = _loggers.marimo_logger()

REGEX = (
    r"(?m)^# /// (?P<type>[a-zA-Z0-9-]+)$\s(?P<content>(^#(| .*)$\s)+)^# ///$"
)


def run_in_sandbox(
    args: List[str],
    name: Optional[str] = None,
) -> int:
    if not DependencyManager.which("uv"):
        raise click.UsageError("uv must be installed to use --sandbox")

    cmd = ["marimo"] + args
    cmd.remove("--sandbox")

    # If name if a filepath, parse the dependencies from the file
    dependencies = []
    if name is not None and os.path.isfile(name):
        with open(name) as f:
            dependencies = _get_dependencies(f.read()) or []

    # The sandbox needs to manage marimo, too, to make sure
    # that the outer environment doesn't leak into the sandbox.
    if "marimo" not in dependencies:
        dependencies.append("marimo")

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

    click.echo(f"Running in a sandbox: {' '.join(cmd)}")

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
