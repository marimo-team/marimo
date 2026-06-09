# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import sys
from types import ModuleType
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from collections.abc import Callable

    import pytest


def install_run_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    pyodide_module = ModuleType("pyodide")
    ffi_module = ModuleType("pyodide.ffi")

    def run_sync(awaitable: object) -> object:
        return asyncio.run(cast(Any, awaitable))

    cast(Any, ffi_module).run_sync = run_sync
    cast(Any, pyodide_module).ffi = ffi_module
    monkeypatch.setitem(sys.modules, "pyodide", pyodide_module)
    monkeypatch.setitem(sys.modules, "pyodide.ffi", ffi_module)


async def wait_until(
    predicate: Callable[[], bool],
    *,
    timeout: float = 1,
) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not bool(predicate()):
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError(
                "condition did not become true before timeout"
            )
        await asyncio.sleep(0)
