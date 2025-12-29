# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from marimo import _loggers

LOGGER = _loggers.marimo_logger()


def resolve_python_path(
    env_config: dict[str, Any],
    base_path: str | None = None,
) -> str | None:
    """Resolve environment config to an absolute Python path.

    Args:
        env_config: Dict with optional keys: python, conda, use_active
        base_path: Base path for resolving relative Python paths (e.g., notebook directory)

    Returns:
        Absolute path to Python interpreter, or None if no config specified.
    """
    # Direct Python path takes priority
    if python_path := env_config.get("python"):
        return _validate_python_path(python_path, base_path)

    # Conda environment by name
    if conda_env := env_config.get("conda"):
        return find_conda_python(conda_env)

    # Use currently active environment
    if env_config.get("use_active"):
        return find_active_python()

    return None


def _validate_python_path(
    python_path: str,
    base_path: str | None = None,
) -> str | None:
    """Validate that a Python path exists and is executable.

    Args:
        python_path: Path to Python interpreter (absolute or relative)
        base_path: Base path for resolving relative paths (e.g., notebook directory)

    Returns:
        Absolute path to Python interpreter, or None if not found.
        Note: Does NOT resolve symlinks, so venv Pythons remain as venv paths.
    """
    path = Path(python_path)

    # If relative path and base_path provided, resolve relative to base
    if not path.is_absolute() and base_path:
        base_dir = Path(base_path)
        if base_dir.is_file():
            base_dir = base_dir.parent
        path = base_dir / python_path

    if path.exists() and path.is_file():
        # Use absolute() instead of resolve() to preserve symlinks
        # This is important for venvs where we want to use the venv's
        # Python path to get its site-packages, not the underlying binary
        return str(path.absolute())
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


def is_same_python(python_path: str) -> bool:
    """Check if the given Python is in the same virtual environment.

    We compare virtual environment prefixes rather than resolved binaries,
    because tools like uv use symlinks to a shared Python installation.
    Two different venvs may have the same underlying Python binary but
    different packages.
    """
    try:
        # Get the venv prefix for current Python
        current_prefix = Path(sys.prefix).resolve()

        # Get the venv prefix for target Python
        # The prefix is typically 2 levels up from bin/python
        target_path = Path(python_path).resolve()
        target_prefix = target_path.parent.parent.resolve()

        return current_prefix == target_prefix
    except (OSError, ValueError):
        return False


def get_conda_env_vars(python_path: str) -> dict[str, str]:
    """Get environment variables needed for conda environments.

    For conda, we need to set LD_LIBRARY_PATH to include the conda lib dir
    so that compiled extensions (numpy, etc.) find their dependencies.

    Args:
        python_path: Path to the Python interpreter.

    Returns:
        Dictionary of environment variables to set.
    """
    env: dict[str, str] = {}

    # Check if this looks like a conda environment
    path = Path(python_path)
    # /path/to/env/bin/python -> /path/to/env
    conda_prefix = path.parent.parent
    lib_path = conda_prefix / "lib"

    if lib_path.exists() and (conda_prefix / "conda-meta").exists():
        # This is a conda environment - set LD_LIBRARY_PATH
        existing = os.environ.get("LD_LIBRARY_PATH", "")
        if existing:
            env["LD_LIBRARY_PATH"] = f"{lib_path}{os.pathsep}{existing}"
        else:
            env["LD_LIBRARY_PATH"] = str(lib_path)

    return env


def get_marimo_path() -> str:
    """Get the path to the marimo package for PYTHONPATH injection."""
    # marimo/_cli/external_env.py -> marimo/
    return str(Path(__file__).parent.parent)


def get_required_dependency_paths() -> list[str]:
    """Get paths to critical dependencies needed for IPC kernel.

    When marimo is injected via PYTHONPATH, we also need to inject
    its IPC dependencies (msgspec, pyzmq) since the external env
    may not have them.
    """
    paths = []

    # Critical dependencies for IPC
    dependencies = ["msgspec", "zmq"]  # zmq is the package name for pyzmq

    for dep in dependencies:
        try:
            import importlib.util

            spec = importlib.util.find_spec(dep)
            if spec and spec.origin:
                # Get the parent directory (site-packages or similar)
                dep_path = Path(spec.origin).parent
                # For packages like zmq, we want the parent of zmq/
                if dep_path.name == dep:
                    dep_path = dep_path.parent
                paths.append(str(dep_path))
        except (ImportError, AttributeError):
            LOGGER.debug(f"Could not find path for dependency: {dep}")

    return list(set(paths))  # Remove duplicates
