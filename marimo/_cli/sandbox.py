# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import atexit
import os
import platform
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Literal, Optional

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


def should_run_in_sandbox(sandbox: bool | None, name: str | None) -> bool:
    """Return whether the named notebook should be run in a sandbox.

    Prompts the user if sandbox is None and the notebook has sandbox metadata
    (only for single notebook, not directories).

    With IPC-based kernel architecture (home sandbox mode), each notebook gets
    its own sandboxed kernel, so multi-notebook servers are now supported with
    --sandbox.
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


def is_home_sandbox_mode(sandbox: bool, name: str | None) -> bool:
    """Check if we should use IPC kernel for home sandbox mode.

    Home sandbox mode activates when:
    - sandbox flag is True
    - AND name is a directory OR name is None (current directory)

    This mode uses IPC kernels with ZeroMQ for per-notebook sandboxed
    environments.
    """
    if not sandbox:
        return False
    # name is None means current directory (home page)
    # or name is explicitly a directory
    return name is None or os.path.isdir(name)


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
    """Run marimo in a sandboxed uv environment.

    This wraps the marimo command with `uv run` to create an isolated
    virtual environment with the notebook's dependencies.

    Used for single-notebook sandbox mode (marimo edit --sandbox notebook.py).
    For home sandbox mode (directory), see IPCKernelManagerImpl which
    creates per-notebook sandboxed kernels.
    """
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

    def handler(sig: int, frame: object) -> None:
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


# Dependencies required for IPC kernel communication (ZeroMQ-based)
IPC_KERNEL_DEPS: list[str] = ["pyzmq"]


def get_sandbox_requirements(
    filename: str | None,
    additional_deps: list[str] | None = None,
) -> list[str]:
    """Get normalized requirements for sandbox venv.

    Reads dependencies from the notebook's PEP 723 script metadata,
    normalizes marimo dependency, and adds any additional deps
    (e.g., IPC_KERNEL_DEPS for kernel communication).

    Args:
        filename: Path to notebook file, or None for empty deps.
        additional_deps: Extra dependencies to add if not already present.

    Returns:
        List of normalized requirement strings.
    """
    pyproject = (
        PyProjectReader.from_filename(filename)
        if filename is not None
        else PyProjectReader({}, config_path=None)
    )

    dependencies = _resolve_requirements_txt_lines(pyproject)
    normalized = _normalize_sandbox_dependencies(
        dependencies, __version__, additional_features=[]
    )

    # Add additional deps if not already present
    if additional_deps:
        existing_lower = {
            d.lower().split("[")[0].split(">=")[0].split("==")[0]
            for d in normalized
        }
        for dep in additional_deps:
            if dep.lower() not in existing_lower:
                normalized.append(dep)

    return normalized


def build_sandbox_venv(
    filename: str | None,
    additional_deps: list[str] | None = None,
) -> tuple[str, str]:
    """Build sandbox venv and install dependencies.

    Creates an ephemeral virtual environment using uv with the notebook's
    dependencies installed. Used for IPC kernel mode where each notebook
    gets its own sandboxed environment.

    Args:
        filename: Path to notebook file for reading dependencies.
        additional_deps: Extra dependencies to add (e.g., IPC_KERNEL_DEPS).

    Returns:
        Tuple of (sandbox_dir, venv_python_path).

    Raises:
        RuntimeError: If dependency installation fails.
    """
    uv_bin = find_uv_bin()

    # Create temp directory for sandbox venv
    sandbox_dir = tempfile.mkdtemp(prefix="marimo-sandbox-")
    venv_path = os.path.join(sandbox_dir, "venv")

    # Phase 1: Create venv
    echo(f"Creating sandbox environment: {muted(venv_path)}", err=True)
    subprocess.run(
        [uv_bin, "venv", "--seed", venv_path],
        check=True,
        capture_output=True,
    )

    # Get venv Python path
    if sys.platform == "win32":
        venv_python = os.path.join(venv_path, "Scripts", "python.exe")
    else:
        venv_python = os.path.join(venv_path, "bin", "python")

    # Phase 2: Install dependencies
    requirements = get_sandbox_requirements(filename, additional_deps)
    echo("Installing sandbox dependencies...", err=True)

    # Separate editable installs from regular requirements
    # Editable installs look like "-e /path/to/package"
    editable_reqs = [r for r in requirements if r.startswith("-e ")]
    regular_reqs = [r for r in requirements if not r.startswith("-e ")]

    # Install editable packages directly (not via requirements file)
    for editable in editable_reqs:
        # Extract path from "-e /path/to/package"
        editable_path = editable[3:].strip()
        result = subprocess.run(
            [
                uv_bin,
                "pip",
                "install",
                "--python",
                venv_python,
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

    # Install regular packages via requirements file
    if regular_reqs:
        req_file = os.path.join(sandbox_dir, "requirements.txt")
        with open(req_file, "w", encoding="utf-8") as f:
            f.write("\n".join(regular_reqs))

        result = subprocess.run(
            [
                uv_bin,
                "pip",
                "install",
                "--python",
                venv_python,
                "-r",
                req_file,
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            # Clean up on failure
            cleanup_sandbox_dir(sandbox_dir)
            raise RuntimeError(
                f"Failed to install sandbox dependencies: {result.stderr}"
            )

    return sandbox_dir, venv_python


def cleanup_sandbox_dir(sandbox_dir: str | None) -> None:
    """Clean up sandbox directory.

    Safely removes the sandbox directory and all its contents.
    Silently ignores errors (e.g., if directory doesn't exist).

    Args:
        sandbox_dir: Path to sandbox directory, or None (no-op).
    """
    if sandbox_dir:
        try:
            shutil.rmtree(sandbox_dir)
        except OSError:
            pass
