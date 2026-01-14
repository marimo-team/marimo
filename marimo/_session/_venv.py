# Copyright 2026 Marimo. All rights reserved.
"""Virtual environment configuration utilities.

This module provides utilities for working with configured virtual environments
in marimo's sandbox mode. It handles:
- Finding Python interpreters in virtual environments
- Checking marimo installation status in venvs
- PYTHONPATH injection for kernel subprocesses
- Installing marimo into configured venvs
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from marimo import _loggers
from marimo._cli.print import echo
from marimo._utils.uv import find_uv_bin
from marimo._version import __version__

if TYPE_CHECKING:
    from marimo._config.config import VenvConfig

LOGGER = _loggers.marimo_logger()

# Dependencies required for IPC kernel communication (ZeroMQ-based)
IPC_KERNEL_DEPS: list[str] = ["pyzmq"]


def _find_python_in_venv(venv_path: str) -> str | None:
    """Find Python interpreter in a venv directory.

    Args:
        venv_path: Path to the virtualenv directory.

    Returns:
        Path to Python binary, or None if not found.
    """
    venv = Path(venv_path)
    if not venv.exists() or not venv.is_dir():
        return None

    if sys.platform == "win32":
        python_path = venv / "Scripts" / "python.exe"
    else:
        python_path = venv / "bin" / "python"

    if not python_path.exists():
        return None

    return str(python_path.absolute())


def get_configured_venv_python(
    venv_config: VenvConfig,
    base_path: str | None = None,
) -> str | None:
    """Get Python path from venv config.

    Args:
        venv_config: The venv config dict (from config.get("venv")).
        base_path: Base path for resolving relative venv paths (e.g., script path).

    Returns:
        Path to Python interpreter in configured venv, or None if not configured.

    Raises:
        ValueError: If venv is configured but invalid.
    """
    venv_path = venv_config.get("path")

    if not venv_path:
        return None

    if base_path and not os.path.isabs(venv_path):
        base_dir = os.path.dirname(os.path.abspath(base_path))
        venv_path = os.path.join(base_dir, venv_path)

    if not os.path.isdir(venv_path):
        raise ValueError(f"Configured venv does not exist: {venv_path}")

    python_path = _find_python_in_venv(venv_path)
    if not python_path:
        raise ValueError(
            f"No Python interpreter found in configured venv: {venv_path}"
        )

    return python_path


def get_kernel_pythonpath() -> str:
    """Get PYTHONPATH for kernel subprocess.

    Returns paths needed to import marimo and its dependencies (pyzmq, msgspec)
    from the parent process's environment. Used when launching a kernel
    in a configured venv that has marimo available via path injection.

    Returns:
        Colon-separated (or semicolon on Windows) path string for PYTHONPATH.
    """
    paths: list[str] = []

    # Find actual paths where dependencies are installed by checking their __file__
    # This is more reliable than site.getsitepackages() which may return
    # ephemeral paths e.g. when running via `uv run --with=pyzmq`.
    # We also include msgspec as a reliable dependency that _should_ be in the
    # desired user system path.
    # Also add marimo's parent directory.
    # NB. If running in edit mode this may be local directory.
    for module_name in ["marimo", "zmq", "msgspec"]:
        try:
            module = __import__(module_name)
            if hasattr(module, "__file__") and module.__file__:
                # Get the site-packages directory containing this module
                module_path = Path(module.__file__).parent.parent
                module_path_str = str(module_path)
                if module_path_str not in paths:
                    paths.append(module_path_str)
        except ImportError:
            pass

    return os.pathsep.join(paths)


def has_marimo_installed(venv_python: str) -> bool:
    """Check if marimo and its IPC deps are installed in the venv.

    Args:
        venv_python: Path to the venv's Python interpreter.

    Returns:
        True if marimo, msgspec, and zmq can all be imported.
    """
    result = subprocess.run(
        [
            venv_python,
            "-c",
            "import marimo, msgspec, zmq; print(marimo.__version__)",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False

    venv_version = result.stdout.strip()
    if venv_version != __version__:
        LOGGER.warning(
            f"marimo version mismatch: venv has {venv_version}, "
            f"current is {__version__}. "
            f"This may cause unexpected behavior. "
            f"Consider upgrading both environments to the same version: "
            f"uv pip install --upgrade marimo"
        )

    return True


def check_python_version_compatibility(venv_python: str) -> bool:
    """Check if venv Python version matches current Python.

    Binary dependencies (pyzmq, msgspec) aren't cross-version compatible,
    so the venv must use the same Python major.minor version.

    Args:
        venv_python: Path to the venv's Python interpreter.

    Returns:
        True if versions match, False otherwise.
    """
    result = subprocess.run(
        [
            venv_python,
            "-c",
            "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')",
        ],
        capture_output=True,
        text=True,
    )
    venv_version = result.stdout.strip()
    current_version = f"{sys.version_info.major}.{sys.version_info.minor}"

    return venv_version == current_version


def install_marimo_into_venv(venv_python: str) -> None:
    """Install marimo and IPC dependencies into a venv.

    Installs marimo and IPC dependencies (pyzmq) into the specified venv.

    Args:
        venv_python: Path to the venv's Python interpreter.
    """
    uv_bin = find_uv_bin()

    packages = [f"marimo=={__version__}"] + IPC_KERNEL_DEPS

    echo("Installing marimo into configured venv...", err=True)

    result = subprocess.run(
        [uv_bin, "pip", "install", "--python", venv_python] + packages,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        LOGGER.warning(
            f"Failed to install marimo into configured venv: {result.stderr}"
        )
