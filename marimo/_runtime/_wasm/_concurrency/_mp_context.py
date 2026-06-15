# Copyright 2026 Marimo. All rights reserved.
"""Process start-method helpers for the Pyodide process adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, NoReturn

from marimo._runtime._wasm._concurrency._wait import (
    UnsupportedWasmConcurrencyError,
)

if TYPE_CHECKING:
    from collections.abc import Callable


def cpu_count() -> int:
    return 1


def get_all_start_methods() -> list[str]:
    return ["spawn"]


def validate_start_method(method: str | None) -> None:
    if method not in (None, "spawn"):
        raise ValueError("WASM multiprocessing shim only supports 'spawn'")


def get_start_method(allow_none: bool = False) -> str:
    del allow_none
    return "spawn"


def set_start_method(method: str | None, force: bool = False) -> None:
    del force
    validate_start_method(method)


def get_context_factory(original: Callable[..., Any]) -> Callable[..., Any]:
    def _get_context(method: str | None = None) -> Any:
        validate_start_method(method)
        return original("spawn")

    return _get_context


def freeze_support() -> None:
    return None


def unsupported_factory(api: str) -> Callable[..., NoReturn]:
    def _unsupported(*args: Any, **kwargs: Any) -> NoReturn:
        del args, kwargs
        raise UnsupportedWasmConcurrencyError(
            f"{api} is not supported by the Pyodide WASM process adapter"
        )

    return _unsupported
