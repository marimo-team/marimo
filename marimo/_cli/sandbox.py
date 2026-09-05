# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import atexit
import os
import platform
import signal
import subprocess
import sys
import tempfile
from enum import Enum
from pathlib import Path

import click

from marimo import _loggers
from marimo._cli.errors import MarimoCLIMissingDependencyError
from marimo._cli.print import bold, echo, green, muted
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._environments import environment, script_metadata
from marimo._environments.overlay import DepExtras, runtime_overlay
from marimo._environments.sandbox import Backend as SandboxBackend
from marimo._environments.uv import (
    UvCommandError,
    UvMissingScriptMetadataError,
    UvNotFoundError,
    find_uv_bin,
    is_uv_available,
    uv,
)
from marimo._utils.inline_script_metadata import (
    PyProjectReader,
    is_marimo_dependency,
)
from marimo._utils.versions import is_editable
from marimo._version import __version__


class SandboxMode(Enum):
    """Sandbox mode for marimo notebooks.

    - SINGLE: Single-file sandbox (the server runs from the notebook's
      script environment)
    - MULTI: Multi-file sandbox (IPC kernels with per-notebook venvs)
    """

    SINGLE = "single"
    MULTI = "multi"


LOGGER = _loggers.marimo_logger()


def maybe_prompt_run_in_sandbox(name: str | None) -> bool:
    if GLOBAL_SETTINGS.MANAGE_SCRIPT_METADATA:
        return False

    # This process was already launched inside a sandbox; re-wrapping
    # it would nest a second environment inside the first.
    if (
        GLOBAL_SETTINGS.SANDBOX_MODE is not None
        or GLOBAL_SETTINGS.SANDBOX_BACKEND is not None
    ):
        return False

    if name is None:
        return False

    if Path(name).is_dir():
        return False

    pyproject = PyProjectReader.from_filename(name)
    if not pyproject.dependencies:
        return False

    # Notebook has inlined dependencies.
    if is_uv_available():
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


def resolve_sandbox_mode(
    sandbox: bool | None, name: str | None
) -> SandboxMode | None:
    """Determine sandbox mode for the given target.

    Returns:
        - None: No sandboxing
        - SandboxMode.SINGLE: Single-file sandbox (server in the script
          environment)
        - SandboxMode.MULTI: Multi-file sandbox (IPC kernels with per-notebook venvs)

    When sandbox is None, prompts the user if the notebook has sandbox metadata
    (only for single notebooks, not directories).
    """
    # Determine if target is a directory (or None = current directory)
    is_directory = name is None or os.path.isdir(name)

    # When the sandbox flag is omitted we infer whether to
    # start in sandbox mode by examining the notebook file and
    # prompting the user. Only prompt for single notebooks, not directories.
    if sandbox is None:
        # Don't prompt for directories - user must explicitly pass --sandbox
        if not is_directory:
            sandbox = maybe_prompt_run_in_sandbox(name)
        else:
            sandbox = False

    if not sandbox:
        return None

    # Sandbox enabled - determine mode based on target type
    # Directory or home page -> multi-file sandbox (IPC kernels)
    # Single file -> single-file sandbox (server in the script environment)
    return SandboxMode.MULTI if is_directory else SandboxMode.SINGLE


def _is_versioned(dependency: str) -> bool:
    return any(c in dependency for c in ("==", ">=", "<=", ">", "<", "~"))


def _normalize_sandbox_dependencies(
    dependencies: list[str],
    marimo_version: str,
    additional_features: list[DepExtras],
) -> list[str]:
    """Normalize marimo dependencies to have only one version.

    If multiple marimo dependencies exist, prefer the one with brackets.
    Add version to the remaining one if not already versioned.
    """

    def include_features(dep: str, features: list[DepExtras]) -> str:
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


def _resolve_local_path_line(line: str, script_dir: Path) -> str:
    r"""Resolve a relative local-path requirement to an absolute path.

    >>> _resolve_local_path_line(
    ...     "-e ../pkg ; py<'3.12' # via foo", Path("/a/b")
    ... )
    '-e /a/pkg ; py<\'3.12\' # via foo'
    """
    rest = line.removeprefix("-e ")
    path_and_comment, _, _ = rest.partition(";")
    path_token, _, _ = path_and_comment.partition(" #")
    path_token = path_token.rstrip()
    if not path_token.startswith("."):
        return line
    resolved = str((script_dir / path_token).resolve())
    return line.replace(path_token, resolved, 1)


def _uv_export_script_requirements_txt(
    name: str | None,
) -> list[str]:
    if not name:
        return []

    result = uv(
        [
            "export",
            "--no-hashes",
            "--no-annotate",
            "--no-header",
            "--script",
            name,
        ]
    )
    script_dir = Path(name).resolve().parent
    return [
        _resolve_local_path_line(line, script_dir)
        for line in result.stdout.split("\n")
    ]


def _resolve_requirements_txt_lines(pyproject: PyProjectReader) -> list[str]:
    if pyproject.name and pyproject.name.endswith(".py"):
        try:
            return _uv_export_script_requirements_txt(pyproject.name)
        except UvMissingScriptMetadataError:
            # No PEP 723 block yet; marimo's own reader handles that fine.
            pass
        except UvCommandError as e:
            LOGGER.warning(
                "`uv export` failed for %s; falling back to marimo's own "
                "dependency resolution: %s",
                pyproject.name,
                e.stderr.strip(),
            )
    return pyproject.requirements_txt_lines


def get_marimo_dir() -> Path:
    from marimo._environments.overlay import marimo_dir

    return marimo_dir()


def construct_uv_flags(
    pyproject: PyProjectReader,
    temp_file: "tempfile._TemporaryFileWrapper[str]",  # noqa: UP037
    additional_features: list[DepExtras],
    additional_deps: list[str],
    python_version_override: str | None = None,
) -> list[str]:
    # Deprecated: retained for the quarto plugin. marimo launches
    # sandboxes from the script environment instead; the flags built here
    # flatten `[[tool.uv.index]]` semantics (#10547).

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

    # Python version: explicit override > script metadata > current interpreter.
    # The override deliberately wins over the script's `requires-python` —
    # `html-wasm --execute` needs the sandbox interpreter to match Pyodide
    # (3.12), even if the script declares something else. Any resulting
    # desync from the script's stated requirement is by design.
    if python_version_override:
        uv_flags.extend(["--python", python_version_override])
    elif pyproject.python_version:
        uv_flags.extend(["--python", pyproject.python_version])
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
    additional_features: list[DepExtras],
    additional_deps: list[str],
    python_version_override: str | None = None,
) -> list[str]:
    """Deprecated: retained for the quarto plugin."""
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
                pyproject,
                temp_file,
                additional_features,
                additional_deps,
                python_version_override=python_version_override,
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
    name: str | None = None,
    extras: list[DepExtras] | None = None,
    command_deps: list[str] | None = None,
    extra_env: dict[str, str] | None = None,
    python_version_override: str | None = None,
    pyodide_constraints: bool = False,
    backend: SandboxBackend = "uv",
) -> int:
    """Runs marimo inside the notebook's script environment.

    Synchronizes the environment from the notebook's metadata, then
    launches `python -m marimo <args...>` from it with marimo layered on
    top. uv resolves the metadata with its full semantics, so indexes,
    sources, and credentials behave as they do for `uv run notebook.py`,
    and the environment is shared with it. A target without a metadata
    block runs in an ephemeral environment instead.

    Used for "single" sandbox mode (marimo edit --sandbox notebook.py).
    For "multi" sandbox mode (directory), see IPCKernelManagerImpl.
    """
    from marimo._environments import backends
    from marimo._environments.errors import EnvironmentManagerError
    from marimo._environments.sandbox import NotebookSandbox

    try:
        backends.ensure_available(backend)
    except UvNotFoundError as e:
        raise MarimoCLIMissingDependencyError(
            "uv must be installed to use --sandbox.",
            "uv",
            additional_tip="Install uv from https://github.com/astral-sh/uv",
        ) from e
    except EnvironmentManagerError as e:
        # e.g. an environment manager too old for script environments.
        echo(str(e), err=True)
        return 1

    # NotebookSandbox prepares the runtime dependency through its backend
    # Adapter. The Python requirement remains a structural Manifest concern.
    if name is not None and name.endswith(".py") and backend == "uv":
        script_metadata.ensure_requires_python(name)

    cmd = _strip_sandbox_args(["-m", "marimo", *args])

    env = os.environ.copy()
    env["MARIMO_MANAGE_SCRIPT_METADATA"] = "true"
    # Let the inner marimo server poll for our PID so it can shut down if we
    # get SIGKILLed (signal handlers below can't catch uncatchable signals).
    env["MARIMO_ANCESTOR_PID"] = str(os.getpid())
    if extra_env:
        env.update(extra_env)

    if pyodide_constraints:
        from marimo._pyodide.pyodide_constraints import (
            write_constraint_file,
        )

        constraint_tmp = tempfile.NamedTemporaryFile(
            mode="w",
            delete=False,
            suffix="-pyodide-constraints.txt",
            encoding="utf-8",
        )
        constraint_tmp.close()
        constraint_path = constraint_tmp.name
        if write_constraint_file(constraint_path):
            # Resolution happens in the child uv process; see below.
            env["UV_CONSTRAINT"] = constraint_path

        def cleanup_constraint_file() -> None:
            try:
                os.unlink(constraint_path)
            except FileNotFoundError:
                pass

        atexit.register(cleanup_constraint_file)

    overlay = runtime_overlay(extras or [], command_deps or [])

    # Explicit override > metadata requires-python (uv reads it) > host.
    pyproject = (
        PyProjectReader.from_filename(name)
        if name is not None
        else PyProjectReader({}, config_path=None)
    )
    python_request = python_version_override or (
        None if pyproject.python_version else platform.python_version()
    )

    # An interpreter override (html-wasm pins the Pyodide version) must
    # not replace the notebook's shared script environment; it resolves
    # ephemerally with the notebook's dependencies layered instead.
    overridden = python_version_override is not None or pyodide_constraints

    plan: environment.ProcessPlan | None = None
    notebook_sandbox: NotebookSandbox | None = None
    if not overridden and (name is None or os.path.isfile(name)):
        notebook_sandbox = NotebookSandbox(name, backend)
        try:
            plan = notebook_sandbox.launch(
                cmd,
                overlay=overlay,
                base_env=env,
                python_override=python_request if backend == "uv" else None,
                on_output=lambda _line: None,
            )
            handle = notebook_sandbox.environment
            assert handle is not None
            echo(
                f"Using script environment: {muted(handle.root)}",
                err=True,
            )
            # Only a server whose kernel runs in the script environment
            # may route package changes through it.
            plan.env["MARIMO_SANDBOX_MODE"] = "single"
            plan.env["MARIMO_SANDBOX_BACKEND"] = backend
        except EnvironmentManagerError as e:
            notebook_sandbox.close()
            echo(str(e), err=True)
            return getattr(e, "returncode", None) or 1

    if plan is None:
        requirements = list(overlay.requirements)
        if overridden and name is not None and os.path.isfile(name):
            requirements = [
                line
                for line in _resolve_requirements_txt_lines(pyproject)
                if line.strip() and not is_marimo_dependency(line)
            ] + requirements
        from marimo._environments.environment import launch_isolated

        # The one resolve the parent environment cannot serve: an
        # overridden interpreter under external constraints.
        plan = launch_isolated(
            cmd,
            requirements=requirements,
            python=python_request or platform.python_version(),
            base_env=env,
        )

    try:
        return _wait_on_plan(plan)
    finally:
        if notebook_sandbox is not None:
            notebook_sandbox.close()


def _strip_sandbox_args(cmd: list[str]) -> list[str]:
    """Drop `--sandbox` and `--sandbox=<backend>` from a command line."""
    return [
        token
        for token in cmd
        if token != "--sandbox" and not token.startswith("--sandbox=")
    ]


def _wait_on_plan(plan: environment.ProcessPlan) -> int:
    """Runs the plan, forwarding signals, and returns its exit code."""
    echo(f"Running in a sandbox: {muted(' '.join(plan.argv))}", err=True)

    if sys.platform == "win32":
        # The console already delivers Ctrl-C to uv and the inner server;
        # forwarding CTRL_C_EVENT would rebroadcast to the whole console,
        # including ourselves (#4842). Let the inner server drive shutdown.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        process = subprocess.Popen(plan.argv, env=plan.env)
    else:
        # On Unix, run the child in its own session so that (a) the tty no
        # longer delivers SIGINT/SIGTERM to it directly and (b) we can
        # signal the whole subtree with a single killpg. The signal
        # handlers below are then the sole path for forwarding signals
        # from the CLI down to the inner marimo server and the kernel.
        process = subprocess.Popen(
            plan.argv, env=plan.env, start_new_session=True
        )

        def handler(sig: int, frame: object) -> None:
            del frame
            try:
                os.killpg(process.pid, sig)
            except ProcessLookupError:
                # Process may have already been terminated.
                pass

        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)
        signal.signal(signal.SIGHUP, handler)

    return process.wait()
