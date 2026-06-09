# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._runtime._wasm._concurrency._install import (
    install_wasm_threading_shims,
    unpatch_wasm_threading_shims,
)
from marimo._runtime._wasm._patches import Unpatch


def ensure_wasm_runtime_bootstrapped() -> Unpatch:
    """Install Pyodide runtime patches before notebook code imports runtime."""
    return install_wasm_threading_shims()


def unpatch_wasm_runtime() -> None:
    """Remove active Pyodide runtime patches for tests."""
    unpatch_wasm_threading_shims()


__all__ = [
    "Unpatch",
    "ensure_wasm_runtime_bootstrapped",
    "install_wasm_threading_shims",
    "unpatch_wasm_runtime",
]
