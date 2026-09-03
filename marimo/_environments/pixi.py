# Copyright 2026 Marimo. All rights reserved.
"""Provision script environments with pixi.

The pixi backend mirrors the uv backend's contract through pixi's
script commands: `pixi install --script` synchronizes and reports the
environment, `pixi add --script --pypi` edits the manifest. Launch
overlays ride uv, invoked through `pixi exec` so pixi remains the only
required tool: uv's ephemeral `--with` environment chains the conda
prefix's site-packages, with overlay-first precedence.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from typing import TYPE_CHECKING, Any

from marimo import _loggers
from marimo._environments.errors import EnvironmentManagerError

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from marimo._environments.environment import Environment, ProcessPlan
    from marimo._environments.overlay import RuntimeOverlay

LOGGER = _loggers.marimo_logger()


class PixiError(EnvironmentManagerError):
    """Base class for pixi invocation errors."""


class PixiNotFoundError(PixiError):
    """No pixi executable was found."""

    def __init__(self) -> None:
        super().__init__(
            "pixi must be installed to use --sandbox=pixi. "
            "Install pixi from https://pixi.sh"
        )


class PixiUnsupportedVersionError(PixiError):
    """The installed pixi predates script environments."""

    def __init__(self) -> None:
        super().__init__(
            "--sandbox=pixi requires a pixi with `pixi install --script` "
            "support. Upgrade with `pixi self-update`."
        )


class PixiCommandError(PixiError):
    """A pixi command exited with a failure."""

    def __init__(
        self, command: Sequence[str], returncode: int, stderr: str
    ) -> None:
        self.command = tuple(command)
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(
            f"`{' '.join(self.command)}` failed with exit code "
            f"{returncode}.\n{stderr.strip()}"
        )


class PixiMissingScriptMetadataError(PixiCommandError):
    """The target script has no PEP 723 inline metadata block."""


def _command_error(
    completed: subprocess.CompletedProcess[str],
) -> PixiCommandError:
    output = completed.stderr or completed.stdout
    normalized = " ".join(output.lower().split())
    error_type: type[PixiCommandError] = PixiCommandError
    if "does not contain a pep 723 metadata block" in normalized:
        error_type = PixiMissingScriptMetadataError
    return error_type(completed.args, completed.returncode, output)


def find_pixi_bin() -> str | None:
    """Path to the pixi executable, or None if not found."""
    return shutil.which("pixi")


def is_pixi_available() -> bool:
    return find_pixi_bin() is not None


def require_pixi_bin() -> str:
    """Path to the pixi executable; raises `PixiNotFoundError`."""
    pixi_bin = find_pixi_bin()
    if pixi_bin is None:
        raise PixiNotFoundError()
    return pixi_bin


def ensure_supported_pixi() -> None:
    """Raise unless the invoked pixi understands `install --script`.

    Probe the capability rather than coupling marimo to a Pixi version.
    """
    completed = subprocess.run(
        [require_pixi_bin(), "install", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if completed.returncode != 0 or "--script" not in completed.stdout:
        raise PixiUnsupportedVersionError()


# `pixi install --script` reports the environment on stderr:
#   ✔ The script environment has been installed at '<prefix>'.
# A `--json` report is the upstream ask that retires this parse.
_INSTALLED_AT = re.compile(r"installed at '([^']+)'")
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def sync(
    script: str,
    *,
    cwd: str | None = None,
    on_output: Callable[[str], None] | None = None,
    on_command: Callable[[Sequence[str]], None] | None = None,
) -> Environment:
    """Makes the script's environment match its metadata.

    Runs `pixi install --script` from `cwd`, normally the notebook's
    directory. Returns the installed environment; pixi does not report
    what changed, so the action is always `updated` and restarts hinge
    on interpreter identity. Raises `PixiCommandError` on failure and
    never mutates `script`.
    """
    from marimo._environments.environment import Environment

    args = [
        require_pixi_bin(),
        "install",
        "--script",
        os.path.abspath(script),
    ]
    if on_command is not None:
        on_command(args)
    completed = subprocess.run(
        args,
        capture_output=True,
        text=True,
        # pixi must never hang waiting for input.
        stdin=subprocess.DEVNULL,
        env=command_env(),
        cwd=cwd,
        start_new_session=os.name != "nt",
    )
    if on_output is not None:
        for line in (completed.stdout + completed.stderr).splitlines(True):
            on_output(line)
    if completed.returncode != 0:
        raise _command_error(completed)
    report = _ANSI.sub("", completed.stderr)
    match = _INSTALLED_AT.search(report)
    if match is None:
        raise PixiError(
            "pixi installed the script environment but did not report "
            f"its location.\n{report.strip()}"
        )
    root = match.group(1)
    python = _env_python(root)
    if python is None:
        raise PixiError(f"No interpreter found in the environment at {root}")
    return Environment(python=python, root=root, action="updated")


def add(
    script: str,
    package: str,
    *,
    cwd: str,
    upgrade: bool = False,
    on_output: Callable[[str], None] | None = None,
    on_command: Callable[[Sequence[str]], None] | None = None,
) -> None:
    """Add a PyPI dependency to a script, or refresh it when upgrading.

    `pixi update` takes package names, not requirements; a constrained
    upgrade rewrites the manifest entry through `pixi add` instead, and
    the next solve advances within the new constraint.
    """
    if upgrade and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", package):
        args = [
            require_pixi_bin(),
            "update",
            "--script",
            os.path.abspath(script),
            package,
        ]
    else:
        args = [
            require_pixi_bin(),
            "add",
            "--script",
            os.path.abspath(script),
            "--pypi",
            package,
        ]
    _run(
        args,
        cwd=cwd,
        on_output=on_output,
        on_command=on_command,
    )


def remove(
    script: str,
    package: str,
    *,
    cwd: str,
    on_output: Callable[[str], None] | None = None,
    on_command: Callable[[Sequence[str]], None] | None = None,
) -> None:
    """Remove a direct PyPI dependency from a script."""
    args = [
        require_pixi_bin(),
        "remove",
        "--script",
        os.path.abspath(script),
        "--pypi",
        package,
    ]
    _run(
        args,
        cwd=cwd,
        on_output=on_output,
        on_command=on_command,
    )


def list_script_packages(script: str, *, cwd: str) -> list[dict[str, Any]]:
    """Return pixi's structured resolved package records for a script."""
    args = [
        require_pixi_bin(),
        "list",
        "--script",
        os.path.abspath(script),
        "--json",
    ]
    completed = _run(args, cwd=cwd)
    import json

    try:
        records = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise PixiError("pixi returned an unreadable package list") from error
    if not isinstance(records, list):
        raise PixiError("pixi returned an invalid package list")
    return [record for record in records if isinstance(record, dict)]


def _run(
    args: Sequence[str],
    *,
    cwd: str,
    on_output: Callable[[str], None] | None = None,
    on_command: Callable[[Sequence[str]], None] | None = None,
) -> subprocess.CompletedProcess[str]:
    if on_command is not None:
        on_command(args)
    completed = subprocess.run(
        args,
        capture_output=True,
        text=True,
        # pixi must never hang waiting for input.
        stdin=subprocess.DEVNULL,
        env=command_env(),
        cwd=cwd,
        start_new_session=os.name != "nt",
    )
    if on_output is not None:
        for line in (completed.stdout + completed.stderr).splitlines(True):
            on_output(line)
    if completed.returncode != 0:
        raise _command_error(completed)
    return completed


def ensure_marimo(
    path: str,
    *,
    on_command: Callable[[Sequence[str]], None] | None = None,
) -> None:
    """Add marimo to the script metadata if not already a dependency.

    The manifest carries a loose requirement so
    `pixi run --script notebook.py` works standalone; the launch overlay
    supplies the running version (or the development checkout), never the
    manifest. Creates the metadata block if the file has none. No-op for
    non-`.py` targets and for missing or empty files, whose block is the
    notebook serializer's to create.
    """
    from marimo._environments.script_metadata import (
        ensure_metadata_block,
        should_add_marimo,
    )

    if not should_add_marimo(path):
        return

    ensure_metadata_block(path)

    args = [
        require_pixi_bin(),
        "add",
        "--script",
        os.path.abspath(path),
        "--pypi",
        "marimo",
    ]
    if on_command is not None:
        on_command(args)
    completed = subprocess.run(
        args,
        capture_output=True,
        text=True,
        # pixi must never hang waiting for input.
        stdin=subprocess.DEVNULL,
        env=command_env(),
        cwd=os.path.dirname(os.path.abspath(path)),
        timeout=60,
        start_new_session=os.name != "nt",
    )
    if completed.returncode != 0:
        raise _command_error(completed)


# The uv that applies launch overlays, fetched through `pixi exec` so
# pixi stays the only required tool. The floor is where the behavior
# this relies on -- `uv run --python <conda-python> --with ...` chaining
# the conda prefix's site-packages -- was verified.
UV_OVERLAY_SPEC = "uv>=0.12"


def launch(
    environment: Environment,
    args: Sequence[str],
    *,
    overlay: RuntimeOverlay,
    base_env: Mapping[str, str] | None = None,
) -> ProcessPlan:
    """Plans running `python <args...>` inside the environment.

    A pixi script environment is a conda environment, so the plan supplies
    its conventional prefix variables and executable paths. `VIRTUAL_ENV`
    is dropped; a conda prefix is not a virtualenv. Pixi activation scripts
    are not evaluated by this launch path.

    The overlay is layered by uv, which pixi supplies through
    `pixi exec` so that pixi stays the only tool a pixi sandbox needs:

        pixi exec --spec "uv>=0.12" uv run --no-project \
            --python <prefix>/bin/python \
            --with marimo==<version> -- python <args...>

    uv resolves the overlay into an ephemeral environment created from
    the conda interpreter, which chains the prefix's site-packages
    behind it. Neither the environment nor the manifest is modified.
    See `RuntimeOverlay`, whose warning about conda and PyPI packaging
    applies here.
    """
    from marimo._environments.environment import ProcessPlan, _with_args

    env = dict(os.environ if base_env is None else base_env)
    env.pop("VIRTUAL_ENV", None)
    env.pop("UV_PROJECT_ENVIRONMENT", None)
    env["CONDA_PREFIX"] = environment.root
    env["CONDA_DEFAULT_ENV"] = os.path.basename(environment.root)
    path_entries = _activation_path_entries(environment.root)
    path = env.get("PATH")
    if path:
        path_entries = (*path_entries, path)
    env["PATH"] = os.pathsep.join(path_entries)
    return ProcessPlan(
        argv=(
            require_pixi_bin(),
            "exec",
            "--spec",
            UV_OVERLAY_SPEC,
            "uv",
            "run",
            "--no-project",
            "--python",
            environment.python,
            *_with_args(overlay.requirements),
            "--",
            "python",
            *args,
        ),
        env=env,
        start_new_session=True,
    )


def _activation_path_entries(
    root: str, *, platform: str | None = None
) -> tuple[str, ...]:
    """Executable paths exposed by a conventional conda prefix."""
    platform = os.name if platform is None else platform
    if platform == "nt":
        import ntpath

        return (
            root,
            ntpath.join(root, "Library", "mingw-w64", "bin"),
            ntpath.join(root, "Library", "usr", "bin"),
            ntpath.join(root, "Library", "bin"),
            ntpath.join(root, "Scripts"),
            ntpath.join(root, "bin"),
        )
    return (os.path.join(root, "bin"),)


def command_env() -> dict[str, str]:
    """Environment for pixi script commands.

    Drops activation state from any enclosing pixi, conda, or uv
    environment so the script's own manifest decides everything.
    """
    env = os.environ.copy()
    for variable in (
        "VIRTUAL_ENV",
        "UV_PROJECT_ENVIRONMENT",
        "CONDA_PREFIX",
        "CONDA_DEFAULT_ENV",
        "PIXI_PROJECT_MANIFEST",
        "PIXI_PROJECT_ROOT",
        "PIXI_ENVIRONMENT_NAME",
        "PIXI_IN_SHELL",
    ):
        env.pop(variable, None)
    return env


def _env_python(root: str) -> str | None:
    """The environment's interpreter within a conda prefix layout."""
    if os.name == "nt":
        candidates = (
            os.path.join(root, "python.exe"),
            os.path.join(root, "Scripts", "python.exe"),
        )
    else:
        candidates = (
            os.path.join(root, "bin", "python"),
            os.path.join(root, "bin", "python3"),
        )
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return None
