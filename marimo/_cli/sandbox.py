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
from typing import Any, Literal, Optional, cast

import click

from marimo import __version__, _loggers
from marimo._cli.file_path import FileContentReader
from marimo._cli.print import bold, echo, green, muted
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._dependencies.dependencies import DependencyManager
from marimo._utils.scripts import read_pyproject_from_script
from marimo._utils.versions import is_editable

LOGGER = _loggers.marimo_logger()

DepFeatures = Literal["lsp", "recommended"]


class PyProjectReader:
    def __init__(self, project: dict[str, Any]):
        self.project = project

    @staticmethod
    def from_filename(name: str) -> PyProjectReader:
        return PyProjectReader(_get_pyproject_from_filename(name) or {})

    @staticmethod
    def from_script(script: str) -> PyProjectReader:
        return PyProjectReader(read_pyproject_from_script(script) or {})

    @property
    def extra_index_urls(self) -> list[str]:
        # See https://docs.astral.sh/uv/reference/settings/#pip_extra-index-url
        return (  # type: ignore[no-any-return]
            self.project.get("tool", {})
            .get("uv", {})
            .get("extra-index-url", [])
        )

    @property
    def index_configs(self) -> list[dict[str, str]]:
        # See https://docs.astral.sh/uv/reference/settings/#index
        return self.project.get("tool", {}).get("uv", {}).get("index", [])  # type: ignore[no-any-return]

    @property
    def index_url(self) -> str | None:
        # See https://docs.astral.sh/uv/reference/settings/#pip_index-url
        return (  # type: ignore[no-any-return]
            self.project.get("tool", {}).get("uv", {}).get("index-url", None)
        )

    @property
    def python_version(self) -> str | None:
        try:
            version = self.project.get("requires-python")
            # Only return string version requirements
            if not isinstance(version, str):
                return None
            return version
        except Exception as e:
            LOGGER.warning(f"Failed to parse Python version requirement: {e}")
            return None

    @property
    def dependencies(self) -> list[str]:
        return self.project.get("dependencies", [])  # type: ignore[no-any-return]

    @property
    def requirements_txt_lines(self) -> list[str]:
        """Get dependencies from string representation of script."""
        try:
            return _pyproject_toml_to_requirements_txt(self.project)
        except Exception as e:
            LOGGER.warning(f"Failed to parse dependencies: {e}")
            return []


def _pyproject_toml_to_requirements_txt(
    pyproject: dict[str, Any],
) -> list[str]:
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
    dependencies = cast(list[str], pyproject.get("dependencies", []))
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


def _get_pyproject_from_filename(name: str) -> dict[str, Any] | None:
    try:
        contents, _ = FileContentReader().read_file(name)
        return read_pyproject_from_script(contents)
    except FileNotFoundError:
        return None
    except Exception:
        LOGGER.warning(f"Failed to read pyproject.toml from {name}")
        return None


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


def _is_marimo_dependency(dependency: str) -> bool:
    # Split on any version specifier
    without_version = re.split(r"[=<>~]+", dependency)[0]
    # Match marimo and marimo[extras], but not marimo-<something-else>
    return without_version == "marimo" or without_version.startswith("marimo[")


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
    marimo_deps = [d for d in dependencies if _is_marimo_dependency(d)]
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
    filtered = [d for d in dependencies if not _is_marimo_dependency(d)]

    if is_editable("marimo"):
        LOGGER.info("Using editable of marimo for sandbox")
        return filtered + [f"-e {get_marimo_dir()}"]

    # Add version if not already versioned
    if not _is_versioned(chosen):
        chosen = f"{chosen}=={marimo_version}"

    return filtered + [include_features(chosen, additional_features)]


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
    dependencies = pyproject.requirements_txt_lines

    # If there are no dependencies, which can happen for marimo new or
    # on marimo edit a_new_file.py, uv may use a cached venv, even though
    # we are passing --isolated; `--refresh` ensures that the venv is
    # actually ephemeral.
    uv_needs_refresh = not dependencies

    # Normalize marimo dependencies
    dependencies = _normalize_sandbox_dependencies(
        dependencies, __version__, additional_features
    )

    # Add additional dependencies
    dependencies.extend(additional_deps)

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
        else PyProjectReader({})
    )

    uv_cmd = ["uv", "run"]
    with tempfile.NamedTemporaryFile(
        mode="w", delete=False, suffix=".txt"
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
