# Copyright 2026 Marimo. All rights reserved.
"""WASM-only monkey-patch framework.

`WasmPatchSet` wraps a target so that when the original raises a caught
exception, a fallback runs instead. Returns one unpatch handle for all
patches. No-op outside pyodide.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

from marimo import _loggers
from marimo._utils.platform import is_pyodide

LOGGER = _loggers.marimo_logger()

Unpatch = Callable[[], None]
Fallback = Callable[..., Any]
WrapperFactory = Callable[[Callable[..., Any]], Callable[..., Any]]


class WasmPatchSet:
    """Collects WASM-only monkey-patches with a single unpatch handle.

    `patch` replaces ``owner.attr`` with a wrapper: calls original; on
    ``catch`` exception, runs ``fallback(original, *args, **kwargs)``. If the
    fallback also raises, re-raises the original with the fallback chained so
    users see the real underlying error.
    """

    def __init__(self) -> None:
        self._unpatches: list[Unpatch] = []
        self._active = is_pyodide()

    def patch(
        self,
        owner: Any,
        attr: str,
        fallback: Fallback,
        *,
        catch: tuple[type[BaseException], ...] = (NameError, Exception),
    ) -> None:
        """Register a patch on ``owner.attr``.

        No-op outside pyodide or if ``attr`` is missing (e.g. renamed across
        polars versions).
        """

        def wrapper_factory(
            original: Callable[..., Any],
        ) -> Callable[..., Any]:
            @functools.wraps(original)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                try:
                    return original(*args, **kwargs)
                except catch as original_exc:
                    original_tb = original_exc.__traceback__
                    try:
                        return fallback(original, *args, **kwargs)
                    except ModuleNotFoundError:
                        # Let missing-dependency errors bubble up so marimo can
                        # prompt the user to install the package.
                        raise
                    except Exception as fallback_exc:
                        raise original_exc.with_traceback(
                            original_tb
                        ) from fallback_exc

            return wrapper

        self.replace(owner, attr, wrapper_factory)

    def replace(
        self,
        owner: Any,
        attr: str,
        wrapper_factory: WrapperFactory,
    ) -> None:
        """Replace ``owner.attr`` with a WASM-only wrapper.

        Unlike ``patch``, this does not call the original first. Use this for
        APIs where an original call can have side effects before failing.
        """
        if not self._active:
            return

        original = getattr(owner, attr, None)
        if original is None:
            return

        wrapper = wrapper_factory(original)
        setattr(owner, attr, wrapper)

        def _unpatch() -> None:
            # Only restore if we're still the active wrapper.
            if getattr(owner, attr, None) is wrapper:
                setattr(owner, attr, original)

        self._unpatches.append(_unpatch)

    def unpatch_all(self) -> Unpatch:
        """Return a callable that restores all originals (idempotent)."""
        unpatches = self._unpatches
        self._unpatches = []

        def _run() -> None:
            for u in reversed(unpatches):
                try:
                    u()
                except Exception as e:
                    LOGGER.warning("Failed to unpatch: %s", e)

        return _run
