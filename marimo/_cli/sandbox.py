# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import atexit
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Literal, Optional

import click

from marimo import __version__, _loggers
from marimo._cli.print import bold, echo, green, muted
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._dependencies.dependencies import DependencyManager
from marimo._utils.inline_script_metadata import (
    PyProjectReader,
    is_marimo_dependency,
)
from marimo._utils.versions import is_editable

LOGGER = _loggers.marimo_logger()

DepFeatures = Literal["lsp", "recommended"]


def maybe_prompt_run_in_sandbox(name: str | None) -> bool:
    if GLOBAL_SETTINGS.MANAGE_SCRIPT_METADATA:
        return False

    if name is None:
        return False

    pyproject = PyProjectReader.from_filename(name)
    if not pyproject.dependencies:
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
            err=True,
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


def _is_versioned(dependency: str) -> bool:
    return any(c in dependency for c in ("==", ">=", "<=", ">", "<", "~"))


def _normalize_sandbox_dependencies(
    dependencies: list[str],
    marimo_version: str,
    additional_features: list[DepFeatures],
) -> list[str]:
    """Normalize marimo dependencies to have only one version.

    If multiple marimo dependencies exist, prefer the one with brackets.
    Add version to the remaining one if not already versioned.
    """

    def include_features(dep: str, features: list[DepFeatures]) -> str:
        if not features:
            return dep

        # If already bracketed, add the features to the existing bracket
        if "[" in dep:
            return dep.replace("marimo[", f"marimo[{','.join(features)},")

        return dep.replace("marimo", f"marimo[{','.join(features)}]")

    # Find all marimo dependencies
    marimo_deps = [d for d in dependencies if is_marimo_dependency(d)]
    if not marimo_deps:
        if is_editable("marimo"):
            LOGGER.info("Using editable of marimo for sandbox")
            return dependencies + [f"-e {get_marimo_dir()}"]

        return dependencies + [
            include_features(f"marimo=={marimo_version}", additional_features)
        ]

    # Prefer the one with brackets if it exists
    bracketed = next((d for d in marimo_deps if "[" in d), None)
    chosen = bracketed if bracketed else marimo_deps[0]

    # Remove all marimo deps
    filtered = [d for d in dependencies if not is_marimo_dependency(d)]

    if is_editable("marimo"):
        LOGGER.info("Using editable of marimo for sandbox")
        return filtered + [f"-e {get_marimo_dir()}"]

    # Add version if not already versioned
    if not _is_versioned(chosen):
        chosen = f"{chosen}=={marimo_version}"

    return filtered + [include_features(chosen, additional_features)]


def _uv_export_script_requirements_txt(
    name: str | None,
) -> list[str]:
    if not name:
        return []

    result = subprocess.run(
        [
            "uv",
            "export",
            "--no-hashes",
            "--no-annotate",
            "--no-header",
            "--script",
            name,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.split("\n")


def _resolve_requirements_txt_lines(pyproject: PyProjectReader) -> list[str]:
    if pyproject.name and pyproject.name.endswith(".py"):
        try:
            return _uv_export_script_requirements_txt(pyproject.name)
        except subprocess.CalledProcessError:
            pass  # Fall back if uv fails
    return pyproject.requirements_txt_lines


def get_marimo_dir() -> Path:
    return Path(__file__).parent.parent.parent


def construct_uv_flags(
    pyproject: PyProjectReader,
    temp_file: "tempfile._TemporaryFileWrapper[str]",  # noqa: UP037
    additional_features: list[DepFeatures],
    additional_deps: list[str],
) -> list[str]:
    # NB. Used in quarto plugin

    # If name if a filepath, parse the dependencies from the file
    dependencies = _resolve_requirements_txt_lines(pyproject)

    # If there are no dependencies, which can happen for marimo new or
    # on marimo edit a_new_file.py, uv may use a cached venv, even though
    # we are passing --isolated; `--refresh` ensures that the venv is
    # actually ephemeral.
    uv_needs_refresh = not dependencies

    # Normalize marimo dependencies
    dependencies = _normalize_sandbox_dependencies(
        dependencies, __version__, additional_features
    )

    temp_file.write("\n".join(dependencies))

    # Construct base UV command
    uv_flags = [
        "--isolated",
        # sandboxed notebook shouldn't pick up existing pyproject.toml,
        # which may conflict with the sandbox requirements
        "--no-project",
        # trade installation time for faster start time
        "--compile-bytecode",
        "--with-requirements",
        temp_file.name,
    ]

    # Layer additional deps on top of the requirements
    if len(additional_deps) > 0:
        uv_flags.extend(["--with", ",".join(additional_deps)])

    # Add refresh
    if uv_needs_refresh:
        uv_flags.append("--refresh")

    # Add Python version if specified
    python_version = pyproject.python_version
    if python_version:
        uv_flags.extend(["--python", python_version])

    # Add index URL if specified
    index_url = pyproject.index_url
    if index_url:
        uv_flags.extend(["--index-url", index_url])

    # Add extra-index-urls if specified
    extra_index_urls = pyproject.extra_index_urls
    if extra_index_urls:
        for url in extra_index_urls:
            uv_flags.extend(["--extra-index-url", url])

    # Add index configs if specified
    index_configs = pyproject.index_configs
    if index_configs:
        for config in index_configs:
            if "url" in config:
                # Looks like: https://docs.astral.sh/uv/guides/scripts/#using-alternative-package-indexes
                uv_flags.extend(["--index", config["url"]])
    return uv_flags


def construct_uv_command(
    args: list[str],
    name: str | None,
    additional_features: list[DepFeatures],
    additional_deps: list[str],
) -> list[str]:
    cmd = ["marimo"] + args
    if "--sandbox" in cmd:
        cmd.remove("--sandbox")

    pyproject = (
        PyProjectReader.from_filename(name)
        if name is not None
        else PyProjectReader({}, config_path=None)
    )

    uv_cmd = ["uv", "run"]
    with tempfile.NamedTemporaryFile(
        mode="w", delete=False, suffix=".txt", encoding="utf-8"
    ) as temp_file:
        temp_file_path = temp_file.name
        uv_cmd.extend(
            construct_uv_flags(
                pyproject, temp_file, additional_features, additional_deps
            )
        )
    # Clean up the temporary file after the subprocess has run
    atexit.register(lambda: os.unlink(temp_file_path))

    # Final command assembly: combine the uv prefix with the original marimo
    # command.
    return uv_cmd + cmd


def run_in_sandbox(
    args: list[str],
    *,
    name: Optional[str] = None,
    additional_features: Optional[list[DepFeatures]] = None,
    additional_deps: Optional[list[str]] = None,
) -> int:
    if not DependencyManager.which("uv"):
        raise click.UsageError("uv must be installed to use --sandbox")
    uv_cmd = construct_uv_command(
        args, name, additional_features or [], additional_deps or []
    )

    echo(f"Running in a sandbox: {muted(' '.join(uv_cmd))}", err=True)

    env = os.environ.copy()
    env["MARIMO_MANAGE_SCRIPT_METADATA"] = "true"

    process = subprocess.Popen(uv_cmd, env=env)

    def handler(sig: int, frame: Any) -> None:
        del sig
        del frame
        try:
            if sys.platform == "win32":
                os.kill(process.pid, signal.CTRL_C_EVENT)
            else:
                os.kill(process.pid, signal.SIGINT)
        except ProcessLookupError:
            # Process may have already been terminated.
            pass

    signal.signal(signal.SIGINT, handler)

    return process.wait()
