# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Literal

# Internal entrypoints. Not user-facing as the API is not stable.
KnownEntryPoint = Literal[
    "marimo.cell.executor",
    "marimo.cache.store",
    "marimo.kernel.lifespan",
    "marimo.server.asgi.lifespan",
    "marimo.server.asgi.middleware",
]
