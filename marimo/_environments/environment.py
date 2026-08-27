# Copyright 2026 Marimo. All rights reserved.
"""Provision script environments with uv.

`sync()` makes a script's environment match its PEP 723 metadata and
returns a frozen `Environment`. Synchronizing is idempotent and cheap
when nothing changed; callers synchronize before every launch. uv owns
resolution, so the metadata's indexes, sources, and credentials apply
exactly as they do for `uv run script.py`, and the environment is the
same one `uv run` uses.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import msgspec

from marimo import _loggers
from marimo._environments.uv import UvError, require_uv_bin, uv

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

LOGGER = _loggers.marimo_logger()

Action = Literal["created", "updated", "replaced", "unchanged"]

# `uv sync --script --output-format json` reports the environment path and
# interpreter on stdout. The flag landed in uv 0.7.21.
MINIMUM_UV_VERSION = (0, 7, 21)


class UvUnsupportedVersionError(UvError):
    """The installed uv predates the script-environment interface."""

    def __init__(self, found: str) -> None:
        minimum = ".".join(str(part) for part in MINIMUM_UV_VERSION)
        super().__init__(
            f"uv {minimum} or newer is required to manage sandbox "
            f"environments; found uv {found}. "
            "Upgrade with `uv self update`."
        )


class UvSyncReportError(UvError):
    """uv synchronized the script but its report was unreadable."""


@dataclass(frozen=True)
class Environment:
    """A synchronized script environment.

    An `updated` environment keeps its interpreter; newly installed
    packages are importable without a relaunch.
    """

    python: str
    root: str
    action: Action

    def requires_restart(self, previous: Environment | None) -> bool:
        """Whether a process launched from `previous` must be relaunched."""
        if previous is None:
            return False
        return self.action == "replaced" or self.python != previous.python

    def process_env(
        self, base: Mapping[str, str] | None = None
    ) -> dict[str, str]:
        """Environment variables for a process in this environment.

        Sets `VIRTUAL_ENV`, drops `UV_PROJECT_ENVIRONMENT`, and puts the
        environment's bin directory first on `PATH`, as `uv run` would.
        """
        env = dict(os.environ if base is None else base)
        env["VIRTUAL_ENV"] = self.root
        env.pop("UV_PROJECT_ENVIRONMENT", None)
        bin_dir = _venv_bin_dir(self.root)
        path = env.get("PATH")
        env["PATH"] = bin_dir if not path else bin_dir + os.pathsep + path
        return env


@dataclass(frozen=True)
class ProcessPlan:
    """A command ready to run inside a script environment."""

    argv: tuple[str, ...]
    env: dict[str, str]


def launch(
    environment: Environment,
    args: Sequence[str],
    *,
    overlay: Sequence[str] = (),
    base_env: Mapping[str, str] | None = None,
) -> ProcessPlan:
    """Plans running `python <args...>` inside the environment.

    With no overlay, the plan invokes the environment's interpreter
    directly. Overlay requirements (PEP 508, or `-e <path>` for an
    editable install) are layered via `uv run --with` into a cached side
    environment for this process only; the script environment and the
    manifest are never modified.
    """
    env = environment.process_env(base_env)
    if not overlay:
        return ProcessPlan(argv=(environment.python, *args), env=env)

    with_args: list[str] = []
    for requirement in overlay:
        if requirement.startswith("-e "):
            with_args.extend(["--with-editable", requirement[3:].strip()])
        else:
            with_args.extend(["--with", requirement])
    return ProcessPlan(
        argv=(
            require_uv_bin(),
            "run",
            # The script environment is VIRTUAL_ENV in `env`; --active
            # makes uv layer on top of it instead of ignoring it.
            "--active",
            "--no-project",
            "--python",
            environment.python,
            *with_args,
            "--",
            "python",
            *args,
        ),
        env=env,
    )


def sync(
    script: str,
    *,
    cwd: str | None = None,
    python_override: str | None = None,
) -> Environment:
    """Makes the script's environment match its metadata.

    Runs uv from `cwd`, normally the notebook's directory, so
    directory-scoped uv configuration applies. `python_override` wins
    over the script's `requires-python` (html-wasm export pins the
    Pyodide interpreter). Raises `UvCommandError` on failure and never
    mutates `script`.
    """
    ensure_supported_uv()
    args = [
        "sync",
        "--script",
        script,
        "--compile-bytecode",
        "--output-format",
        "json",
    ]
    if python_override is not None:
        args.extend(["--python", python_override])
    completed = uv(args, env=_sync_env(), cwd=cwd)
    return _parse_report(completed.stdout)


def ensure_supported_uv() -> None:
    """Raise `UvUnsupportedVersionError` for a uv below the minimum."""
    version = _uv_version()
    parsed = _parse_version(version)
    if parsed is None:
        # An unparsable version is likely newer than anything we know;
        # let the actual command fail if the interface is missing.
        LOGGER.debug("Could not parse uv version: %s", version)
        return
    if parsed < MINIMUM_UV_VERSION:
        raise UvUnsupportedVersionError(version)


def _uv_version() -> str:
    """The invoked uv's version string.

    Probed per call; caching would pin a stale answer across
    `uv self update` or a changed `UV` environment variable.
    """
    # "uv 0.7.21 (a1b2c3d4 2025-01-01)"
    stdout = uv(["--version"]).stdout.strip()
    return stdout.removeprefix("uv ").split(" ")[0]


def _parse_version(version: str) -> tuple[int, ...] | None:
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", version)
    if match is None:
        return None
    return tuple(int(part) for part in match.groups())


# The report schema is labeled preview upstream; only the fields consumed
# here are declared, and drift raises `UvSyncReportError` rather than
# guessing.
_ACTIONS: dict[str, Action] = {
    "create": "created",
    "update": "updated",
    "replace": "replaced",
    "check": "unchanged",
}


class _ReportPython(msgspec.Struct):
    path: str


class _ReportEnvironment(msgspec.Struct):
    path: str
    python: _ReportPython


class _ReportSync(msgspec.Struct):
    environment: _ReportEnvironment
    action: str


class _Report(msgspec.Struct):
    sync: _ReportSync


def _parse_report(stdout: str) -> Environment:
    try:
        report = msgspec.json.decode(stdout, type=_Report)
    except msgspec.DecodeError as error:
        raise UvSyncReportError(
            "uv synchronized the script but did not report its environment"
        ) from error
    reported_python = report.sync.environment.python.path
    root = report.sync.environment.path
    raw_action = report.sync.action
    action = _ACTIONS.get(raw_action)
    if action is None:
        # An unknown action still names a usable environment; interpreter
        # identity drives restarts, so treat it as an in-place update.
        LOGGER.debug("Unknown uv sync action: %s", raw_action)
        action = "updated"
    # The report spells the interpreter differently across actions (e.g.
    # bin/python on create, bin/python3 on check). Pick a stable name from
    # the root so interpreter identity is comparable across syncs.
    python = _venv_python(root) or reported_python
    return Environment(python=python, root=root, action=action)


def _venv_python(root: str) -> str | None:
    """The environment's interpreter, preferring the unversioned name.

    Symlinks are not resolved: bin/python commonly links to the base
    interpreter, and resolving it would launch outside the environment.
    """
    bin_dir = _venv_bin_dir(root)
    candidates: tuple[str, ...]
    if os.name == "nt":
        candidates = (os.path.join(bin_dir, "python.exe"),)
    else:
        candidates = (
            os.path.join(bin_dir, "python"),
            os.path.join(bin_dir, "python3"),
        )
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return None


def _venv_bin_dir(root: str) -> str:
    return os.path.join(root, "Scripts" if os.name == "nt" else "bin")


def _sync_env() -> dict[str, str]:
    """Environment for `uv sync --script` invocations.

    Script environments are selected by the script and its metadata; an
    enclosing project or virtualenv must not redirect synchronization.
    """
    env = dict(os.environ)
    env.pop("VIRTUAL_ENV", None)
    env.pop("UV_PROJECT_ENVIRONMENT", None)
    return env
