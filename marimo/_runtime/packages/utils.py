# Copyright 2024 Marimo. All rights reserved.
import os
import sys

from marimo._utils.platform import is_pyodide


def in_virtual_environment() -> bool:
    """Returns True if a venv/virtualenv is activated"""
    # https://stackoverflow.com/questions/1871549/how-to-determine-if-python-is-running-inside-a-virtualenv/40099080#40099080  # noqa: E501
    base_prefix = (
        getattr(sys, "base_prefix", None)
        or getattr(sys, "real_prefix", None)
        or sys.prefix
    )
    return sys.prefix != base_prefix


def in_conda_env() -> bool:
    return "CONDA_DEFAULT_ENV" in os.environ


def is_python_isolated() -> bool:
    """Returns True if not using system Python"""
    return in_virtual_environment() or in_conda_env() or is_pyodide()
