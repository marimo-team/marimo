# Copyright 2026 Marimo. All rights reserved.
"""Typed wrappers for ``loro`` APIs with incomplete stubs.

The ``loro`` stubs omit return types on ``__new__`` and the
``ValueOrContainer`` union lacks a typed ``.container`` accessor.
These helpers isolate the ``type: ignore`` comments so the rest of
the codebase stays clean.
"""

from __future__ import annotations

from loro import LoroDoc, LoroText, ValueOrContainer


def create_doc() -> LoroDoc:
    return LoroDoc()  # type: ignore[no-untyped-call]


def create_text() -> LoroText:
    return LoroText()  # type: ignore[no-untyped-call]


def unwrap_text(val: ValueOrContainer) -> LoroText:
    """Extract a ``LoroText`` from a ``ValueOrContainer``."""
    container = val.container  # type: ignore[union-attr,attr-defined]
    assert isinstance(container, LoroText)
    return container
