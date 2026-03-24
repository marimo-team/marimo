# Copyright 2026 Marimo. All rights reserved.
"""Typed wrappers for ``loro`` constructors.

The ``loro`` stubs omit return types on ``__new__``, which triggers
mypy ``no-untyped-call``.  These helpers provide correctly-typed
construction so the rest of the codebase stays clean.
"""

from __future__ import annotations

from loro import LoroDoc, LoroText


def create_doc() -> LoroDoc:
    return LoroDoc()  # type: ignore[no-untyped-call]


def create_text() -> LoroText:
    return LoroText()  # type: ignore[no-untyped-call]
