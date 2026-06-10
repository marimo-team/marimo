# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._runtime._wasm._concurrency._install import (
    install_wasm_concurrency_shims,
    install_wasm_process_shims,
    unpatch_wasm_concurrency_shims,
    unpatch_wasm_process_shims,
)
from marimo._runtime._wasm._patches import Unpatch


def ensure_wasm_runtime_bootstrapped() -> Unpatch:
    """Install Pyodide runtime patches before notebook code imports runtime."""
    core_unpatch = install_wasm_concurrency_shims()
    try:
        process_unpatch = install_wasm_process_shims()
    except BaseException:
        core_unpatch()
        raise

    def unpatch() -> None:
        try:
            process_unpatch()
        finally:
            core_unpatch()

    return unpatch


def unpatch_wasm_runtime() -> None:
    """Remove active Pyodide runtime patches for tests."""
    unpatch_wasm_process_shims()
    unpatch_wasm_concurrency_shims()


__all__ = [
    "Unpatch",
    "ensure_wasm_runtime_bootstrapped",
    "install_wasm_concurrency_shims",
    "install_wasm_process_shims",
    "unpatch_wasm_runtime",
]
