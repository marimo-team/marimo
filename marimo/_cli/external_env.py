# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

from marimo import _loggers

LOGGER = _loggers.marimo_logger()


def resolve_python_path(env_config: dict[str, Any]) -> str | None:
    """Resolve environment config to an absolute Python path.

    Args:
        env_config: Dict with optional keys: python, conda, use_active

    Returns:
        Absolute path to Python interpreter, or None if no config specified.
    """
    # Direct Python path takes priority
    if python_path := env_config.get("python"):
        return _validate_python_path(python_path)

    # Conda environment by name
    if conda_env := env_config.get("conda"):
        return find_conda_python(conda_env)

    # Use currently active environment
    if env_config.get("use_active"):
        return find_active_python()

    return None


def _validate_python_path(python_path: str) -> str | None:
    """Validate that a Python path exists and is executable."""
    path = Path(python_path)
    if path.exists() and path.is_file():
        return str(path.resolve())
    LOGGER.warning(f"Python path does not exist: {python_path}")
    return None


def find_python_in_venv(venv_path: str) -> str | None:
    """Find Python interpreter in a virtual environment directory.

    Args:
        venv_path: Path to the virtual environment directory.

    Returns:
        Absolute path to Python interpreter, or None if not found.
    """
    venv = Path(venv_path)
    if not venv.exists() or not venv.is_dir():
        LOGGER.warning(f"Virtual environment path does not exist: {venv_path}")
        return None

    # Platform-specific Python location
    if sys.platform == "win32":
        python_path = venv / "Scripts" / "python.exe"
    else:
        python_path = venv / "bin" / "python"

    if not python_path.exists():
        LOGGER.warning(f"Python not found in venv: {venv_path}")
        return None

    return str(python_path.resolve())


def find_conda_python(env_name: str) -> str | None:
    """Find Python in a conda environment by name.

    Args:
        env_name: Name of the conda environment.

    Returns:
        Absolute path to Python interpreter, or None if not found.
    """
    # Check if conda is available
    conda_bin = shutil.which("conda")
    if not conda_bin:
        LOGGER.debug("Conda CLI not found, cannot resolve conda environment")
        return None

    # Try to get environment info from conda
    try:
        result = subprocess.run(
            [conda_bin, "info", "--envs", "--json"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        envs_info = json.loads(result.stdout)
        envs = envs_info.get("envs", [])

        # Look for matching environment
        for env_path in envs:
            env_path = Path(env_path)
            if env_path.name == env_name:
                return find_python_in_venv(str(env_path))

        # Also check if it's in the envs directory
        conda_prefix = os.environ.get("CONDA_PREFIX")
        if conda_prefix:
            # Try parent envs directory
            envs_dir = Path(conda_prefix).parent
            if envs_dir.name == "envs":
                env_path = envs_dir / env_name
                if env_path.exists():
                    return find_python_in_venv(str(env_path))
            # Try base conda envs directory
            base_envs = Path(conda_prefix) / "envs" / env_name
            if base_envs.exists():
                return find_python_in_venv(str(base_envs))

        LOGGER.debug(f"Conda environment not found: {env_name}")
        return None

    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        json.JSONDecodeError,
    ) as e:
        LOGGER.debug(f"Failed to query conda environments: {e}")
        return None


def find_active_python() -> str | None:
    """Find Python from currently active virtual environment.

    Checks VIRTUAL_ENV first (standard venv/virtualenv), then CONDA_PREFIX.

    Returns:
        Absolute path to Python interpreter, or None if no active env.
    """
    # Check for standard venv/virtualenv
    if venv := os.environ.get("VIRTUAL_ENV"):
        python_path = find_python_in_venv(venv)
        if python_path:
            return python_path

    # Check for conda environment
    if conda_prefix := os.environ.get("CONDA_PREFIX"):
        python_path = find_python_in_venv(conda_prefix)
        if python_path:
            return python_path

    return None


def _check_marimo_installed(python_path: str) -> bool:
    """Check if marimo is installed in the given Python environment."""
    try:
        result = subprocess.run(
            [python_path, "-c", "import marimo"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


# Internal env var to prevent recursion when re-invoking with external Python
_EXTERNAL_ENV_ACTIVE = "_MARIMO_EXTERNAL_ENV_ACTIVE"


def is_external_env_active() -> bool:
    """Check if we're already running with an external environment."""
    return os.environ.get(_EXTERNAL_ENV_ACTIVE) == "1"


def run_with_external_python(
    python_path: str,
    args: list[str],
    env: Optional[dict[str, str]] = None,
) -> int:
    """Run marimo using the specified Python interpreter.

    If marimo is not installed in the external environment, it will be
    injected via PYTHONPATH so that the external env's packages
    still take precedence (PYTHONPATH is appended, not prepended).

    Args:
        python_path: Absolute path to Python interpreter.
        args: Command line arguments to pass to marimo.
        env: Optional environment variables to set.

    Returns:
        Exit code from the subprocess.
    """
    from marimo._cli.print import echo, muted

    # Set up environment
    proc_env = os.environ.copy()
    if env:
        proc_env.update(env)

    # Prevent recursion
    proc_env[_EXTERNAL_ENV_ACTIVE] = "1"

    # Check if marimo is installed in the external environment
    if _check_marimo_installed(python_path):
        # Marimo is installed - use standard invocation
        cmd = [python_path, "-m", "marimo"] + args
        echo(f"Using external Python: {muted(python_path)}", err=True)
    else:
        # Marimo not installed - inject via PYTHONPATH
        # PYTHONPATH entries are added after the external env's site-packages,
        # so external env's packages take precedence
        current_pythonpath = os.pathsep.join(sys.path)
        existing = proc_env.get("PYTHONPATH", "")
        if existing:
            proc_env["PYTHONPATH"] = f"{existing}{os.pathsep}{current_pythonpath}"
        else:
            proc_env["PYTHONPATH"] = current_pythonpath

        cmd = [python_path, "-m", "marimo"] + args
        echo(
            f"Using external Python: {muted(python_path)} "
            "(injecting marimo via PYTHONPATH)",
            err=True,
        )

    return subprocess.call(cmd, env=proc_env)
