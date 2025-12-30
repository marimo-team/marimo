# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import atexit
import os
import platform
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Literal, Optional

import click

from marimo import _loggers
from marimo._cli.print import bold, echo, green, muted
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._dependencies.dependencies import DependencyManager
from marimo._utils.inline_script_metadata import (
    PyProjectReader,
    is_marimo_dependency,
)
from marimo._utils.uv import find_uv_bin
from marimo._utils.versions import is_editable
from marimo._version import __version__

LOGGER = _loggers.marimo_logger()


def should_use_external_env(name: str | None) -> str | None:
    """Check if external environment is configured, return Python path.

    Checks both per-notebook [tool.marimo.env] and project-level config.

    Args:
        name: Path to the notebook file, or None.

    Returns:
        Absolute path to Python interpreter, or None if no external env configured.
    """
    from marimo._cli.external_env import is_same_python, resolve_python_path
    from marimo._config.manager import get_default_config_manager

    # Check per-notebook config first
    if name is not None and not Path(name).is_dir():
        try:
            pyproject = PyProjectReader.from_filename(name)
            env_config = pyproject.env_config
            if env_config:
                # Pass notebook path to resolve relative Python paths
                python_path = resolve_python_path(env_config, base_path=name)
                if python_path and not is_same_python(python_path):
                    return python_path
        except Exception as e:
            LOGGER.debug(f"Failed to read env config from notebook: {e}")

    # Check project-level config ([tool.marimo.env] in pyproject.toml)
    try:
        config = get_default_config_manager(current_path=name).get_config()
        env_config = config.get("env", {})
        if env_config:
            # Pass name to resolve relative Python paths
            python_path = resolve_python_path(env_config, base_path=name)
            if python_path and not is_same_python(python_path):
                return python_path
    except Exception as e:
        LOGGER.debug(f"Failed to read env config from project: {e}")

    return None


def _sync_deps_to_external_env(name: str | None, external_python: str) -> None:
    """Sync notebook dependencies to external environment using uv."""
    if name is None:
        return

    pyproject = PyProjectReader.from_filename(name)
    dependencies = pyproject.dependencies
    if not dependencies:
        echo("No dependencies to sync.", err=True)
        return

    uv_bin = find_uv_bin()

    # Normalize dependencies (adds marimo if needed)
    from marimo._version import __version__

    requirements = _normalize_sandbox_dependencies(
        dependencies, __version__, additional_features=[]
    )

    # Write to temp file
    import tempfile

    with tempfile.NamedTemporaryFile(
        mode="w", delete=False, suffix=".txt", encoding="utf-8"
    ) as f:
        f.write("\n".join(requirements))
        req_file = f.name

    try:
        echo(f"Syncing dependencies to: {muted(external_python)}", err=True)

        # Separate editable installs from regular requirements
        editable_reqs = [r for r in requirements if r.startswith("-e ")]
        regular_reqs = [r for r in requirements if not r.startswith("-e ")]

        # Install editable packages directly
        for editable in editable_reqs:
            editable_path = editable[3:].strip()
            result = subprocess.run(
                [
                    uv_bin,
                    "pip",
                    "install",
                    "--python",
                    external_python,
                    "-e",
                    editable_path,
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                echo(
                    f"Warning: Editable install failed: {result.stderr}",
                    err=True,
                )

        # Install regular packages
        if regular_reqs:
            with tempfile.NamedTemporaryFile(
                mode="w", delete=False, suffix=".txt", encoding="utf-8"
            ) as f:
                f.write("\n".join(regular_reqs))
                regular_req_file = f.name

            result = subprocess.run(
                [
                    uv_bin,
                    "pip",
                    "install",
                    "--python",
                    external_python,
                    "-r",
                    regular_req_file,
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                echo(
                    f"Warning: Package sync failed: {result.stderr}", err=True
                )
            else:
                echo(green("Dependencies synced successfully."), err=True)

            os.unlink(regular_req_file)
    finally:
        os.unlink(req_file)


def resolve_sandbox_mode(
    sandbox: bool | None, name: str | None
) -> tuple[bool, str | None]:
    """Resolve sandbox mode and external python, handling conflicts.

    Priority/Fallback Chain:
    1. --sandbox + external env → prompt to sync deps, use external env
    2. --sandbox + uv available → sandbox mode
    3. --sandbox + no uv + external env → external env (warn)
    4. --sandbox + no uv + no external env → error
    5. [tool.marimo.env] only → external env
    6. sandbox=None auto-detect → may prompt, prefer external env if configured

    Returns:
        (sandbox_mode: bool, external_python: str | None)
    """
    external_python = should_use_external_env(name)
    has_uv = DependencyManager.which("uv") is not None

    # Case 1: sandbox=True explicit + external env configured → offer sync
    if sandbox is True and external_python:
        if has_uv and sys.stdin.isatty() and not GLOBAL_SETTINGS.YES:
            sync_deps = click.confirm(
                "Both --sandbox and [tool.marimo.env] specified.\n"
                + green(
                    "Sync notebook dependencies to external environment?",
                    bold=True,
                ),
                default=True,
                err=True,
            )
            if sync_deps:
                _sync_deps_to_external_env(name, external_python)
        else:
            echo(
                "Warning: --sandbox and [tool.marimo.env] both specified. "
                "Using external environment.",
                err=True,
            )
        return False, external_python

    # Case 2: sandbox=True explicit + no uv
    if sandbox is True and not has_uv:
        if external_python:
            echo(
                "Warning: --sandbox requested but uv not installed. "
                "Falling back to external environment.",
                err=True,
            )
            return False, external_python
        else:
            raise click.UsageError(
                "uv must be installed to use --sandbox.\n"
                "Install it from: https://github.com/astral-sh/uv\n"
                "Or configure [tool.marimo.env] for external Python."
            )

    # Case 3: sandbox=None (auto-detect)
    if sandbox is None:
        sandbox_enabled = should_run_in_sandbox(sandbox=None, name=name)
        # If auto-detected sandbox but external env configured, prefer external
        if sandbox_enabled and external_python:
            return False, external_python
        return (
            sandbox_enabled,
            external_python if not sandbox_enabled else None,
        )

    # Case 4: sandbox=True with uv available, or sandbox=False
    return sandbox, external_python if not sandbox else None


DepFeatures = Literal["lsp", "recommended"]


def maybe_prompt_run_in_sandbox(name: str | None) -> bool:
    if GLOBAL_SETTINGS.MANAGE_SCRIPT_METADATA:
        return False

    if name is None:
        return False

    if Path(name).is_dir():
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


def should_run_in_sandbox(sandbox: bool | None, name: str | None) -> bool:
    """Return whether the named notebook should be run in a sandbox.

    Prompts the user if sandbox is None and the notebook has sandbox metadata
    (only for single notebook, not directories).

    With IPC-based kernel architecture, each notebook gets its own sandboxed
    kernel, so multi-notebook servers are now supported with --sandbox.
    """
    # When the sandbox flag is omitted we infer whether to
    # start in sandbox mode by examining the notebook file and
    # prompting the user. Only prompt for single notebooks, not directories.
    if sandbox is None:
        # Don't prompt for directories - user must explicitly pass --sandbox
        if name is not None and not os.path.isdir(name):
            sandbox = maybe_prompt_run_in_sandbox(name)
        else:
            sandbox = False

    return sandbox


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
            find_uv_bin(),
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

    if uv_needs_refresh:
        uv_flags.append("--refresh")

    # We use the specified Python version (if any), otherwise
    # the current Python version
    python_version = pyproject.python_version
    if python_version:
        uv_flags.extend(["--python", python_version])
    else:
        uv_flags.extend(["--python", platform.python_version()])

    index_url = pyproject.index_url
    if index_url:
        uv_flags.extend(["--index-url", index_url])

    extra_index_urls = pyproject.extra_index_urls
    if extra_index_urls:
        for url in extra_index_urls:
            uv_flags.extend(["--extra-index-url", url])

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
    if "--dangerous-sandbox" in cmd:
        cmd.remove("--dangerous-sandbox")

    pyproject = (
        PyProjectReader.from_filename(name)
        if name is not None
        else PyProjectReader({}, config_path=None)
    )

    uv_cmd = [find_uv_bin(), "run"]
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
    # If we fall back to the plain "uv" path, ensure it's actually on the system
    if find_uv_bin() == "uv" and not DependencyManager.which("uv"):
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
