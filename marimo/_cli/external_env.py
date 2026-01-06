# Copyright 2026 Marimo. All rights reserved.
"""IPC helper functions for external Python environments.

These helpers are used when marimo needs to inject itself into an external
Python environment for IPC kernel communication.
"""

from __future__ import annotations

from pathlib import Path

from marimo import _loggers

LOGGER = _loggers.marimo_logger()


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
