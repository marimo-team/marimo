from typing import Literal

# Internal entrypoints. Not user-facing as the API is not stable.
KnownEntryPoint = Literal[
    "marimo.cell.executor",
    "marimo.cache.store",
    "marimo.kernel.lifespan",
    "marimo.server.asgi.lifespan",
    "marimo.server.asgi.middleware",
]
