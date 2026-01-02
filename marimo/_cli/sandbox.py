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
    has_marimo_in_script_metadata,
    is_marimo_dependency,
)
from marimo._utils.uv import find_uv_bin
from marimo._utils.versions import is_editable
from marimo._version import __version__

LOGGER = _loggers.marimo_logger()

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


def should_run_in_sandbox(
    sandbox: bool | None, dangerous_sandbox: bool | None, name: str | None
) -> bool:
    """Return whether the named notebook should be run in a sandbox.

    Prompts the user if sandbox is None and the notebook has sandbox metadata.

    The `sandbox` arg is whether the user requested sandbox. Even
    if running in sandbox was requested, it may not be allowed
    if the target is a directory (unless overridden by `dangerous_sandbox`).
    """

    # Dangerous sandbox can be forced on by setting an environment variable;
    # this allows our VS Code extension to force sandbox regardless of the
    # marimo version.
    if sandbox and os.getenv("MARIMO_DANGEROUS_SANDBOX"):
        dangerous_sandbox = True

    if dangerous_sandbox and (name is None or os.path.isdir(name)):
        sandbox = True
        click.echo(
            click.style(
                "Warning: Using sandbox with multi-notebook edit servers is dangerous.\n",
                fg="yellow",
            )
            + "Notebook dependencies may not be respected, may not be written, and may be overwritten.\n"
            + "Learn more: https://github.com/marimo-team/marimo/issues/5219l.\n",
            err=True,
        )

    # When the sandbox flag is omitted we infer whether to
    # to start in sandbox mode by examining the notebook file and
    # prompting the user.
    if sandbox is None:
        sandbox = maybe_prompt_run_in_sandbox(name)

    # Validation: we don't yet support multi-notebook sandboxed servers.
    if (
        sandbox
        and not dangerous_sandbox
        and (name is None or os.path.isdir(name))
    ):
        raise click.UsageError(
            """marimo's package sandbox requires a notebook name:

    * marimo edit --sandbox my_notebook.py

  Multi-notebook sandboxed servers (marimo edit --sandbox) are not supported.
  Follow this issue at: https://github.com/marimo-team/marimo/issues/2598."""
        )

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


def _ensure_marimo_in_script_metadata(name: str | None) -> None:
    """Ensure marimo is in the script metadata if metadata exists.

    If the file has PEP 723 script metadata but marimo is not listed
    as a dependency, add it using uv.
    """

    # Only applicable to `.py` files.
    if name is None or not name.endswith(".py"):
        return

    # Check if script metadata exists and whether marimo is present
    # Returns: True (has marimo), False (no marimo), None (no metadata)
    has_marimo = has_marimo_in_script_metadata(name)
    if has_marimo is not False:
        # Either marimo is present (True) or no metadata exists (None)
        return

    # Add marimo to script metadata using uv
    try:
        result = subprocess.run(
            [find_uv_bin(), "add", "--script", name, "marimo"],
            check=True,
            capture_output=True,
            text=True,
        )
        LOGGER.info(f"Added marimo to script metadata: {result.stdout}")
    except subprocess.CalledProcessError as e:
        LOGGER.warning(f"Failed to add marimo to script metadata: {e.stderr}")
    except Exception as e:
        LOGGER.warning(f"Failed to add marimo to script metadata: {e}")


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

    # Ensure marimo is in the script metadata before running
    _ensure_marimo_in_script_metadata(name)

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
