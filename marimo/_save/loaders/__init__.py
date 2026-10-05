# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, cast

from marimo import _loggers
from marimo._entrypoints.registry import EntryPointRegistry
from marimo._save.loaders.json import JsonLoader
from marimo._save.loaders.lazy import (
    LazyLoader,
    WasmLazyLoader,
    dump_cache_manifests,
    flush_active_caches,
)
from marimo._save.loaders.loader import (
    BasePersistenceLoader,
    Loader,
    LoaderPartial,
    LoaderType,
)
from marimo._save.loaders.memory import MemoryLoader
from marimo._save.loaders.pickle import PickleLoader
from marimo._utils.platform import is_pyodide

if TYPE_CHECKING:
    from marimo._config.config import CacheLoader, MarimoConfig

LOGGER = _loggers.marimo_logger()

LoaderKey = Literal["memory", "pickle", "json", "lazy"]

# What `mo.persistent_cache` uses when neither `method` nor `cache.loader`
# is set.
DEFAULT_LOADER: CacheLoader = "lazy"

# Third-party persistent loaders. A package registers a `Loader` subclass
# under `[project.entry-points."marimo.cache.loader"]`, and `cache.loader`
# or `method=` selects it by name. `MARIMO_CACHE_LOADER_ALLOWLIST` and
# `_DENYLIST` gate it like the other registries. Built-in names win.
_LOADER_REGISTRY = EntryPointRegistry[LoaderType]("marimo.cache.loader")


@dataclass(frozen=True)
class DualLoader:
    """A loader registered as a native/WASM pair under one name.

    `resolve()` performs the *single* environment check and returns the
    concrete loader class, so nothing downstream re-checks the platform.
    Any loader can opt into dual behavior by registering one of these.
    """

    native: LoaderType
    wasm: LoaderType

    def resolve(self) -> LoaderType:
        return self.wasm if is_pyodide() else self.native


def resolve_loader(entry: LoaderType | DualLoader) -> LoaderType:
    """Resolve a registry entry to a concrete loader class."""
    return entry.resolve() if isinstance(entry, DualLoader) else entry


PERSISTENT_LOADERS: dict[LoaderKey, LoaderType | DualLoader] = {
    "pickle": PickleLoader,
    "json": JsonLoader,
    "lazy": DualLoader(native=LazyLoader, wasm=WasmLazyLoader),
}


def persistent_loader_names(
    registry: EntryPointRegistry[LoaderType] | None = None,
) -> list[str]:
    """Built-in persistent loader names plus allowed entry points."""
    registry = registry or _LOADER_REGISTRY
    return sorted(set(PERSISTENT_LOADERS) | set(registry.names()))


def get_persistent_loader(
    key: str,
    registry: EntryPointRegistry[LoaderType] | None = None,
) -> LoaderType:
    """Resolve a persistent loader by name.

    Built-in names win over entry points. Raises `ValueError` for an unknown
    or disallowed name, an entry point that fails to load, or one that is not
    a `Loader` subclass.
    """
    registry = registry or _LOADER_REGISTRY
    if key in PERSISTENT_LOADERS:
        return resolve_loader(PERSISTENT_LOADERS[cast("LoaderKey", key)])
    try:
        loader = registry.get(key)
    except (KeyError, ValueError) as e:
        raise ValueError(
            f"Invalid method {key!r}, expected one of "
            f"{persistent_loader_names(registry)}"
        ) from e
    except Exception as e:
        raise ValueError(f"Failed to load cache loader {key!r}: {e}") from e
    if not (isinstance(loader, type) and issubclass(loader, Loader)):
        raise ValueError(
            f"Cache loader {key!r} must be a Loader subclass, got {loader!r}."
        )
    return loader


def normalize_loader_key(
    raw: Any,
    registry: EntryPointRegistry[LoaderType] | None = None,
) -> CacheLoader:
    """Validate a `cache.loader` value, falling back to `DEFAULT_LOADER`.

    A built-in name or an allowed `marimo.cache.loader` entry point is valid.
    The entry point is not imported here; `get_persistent_loader` loads it
    when a cache first needs it.
    """
    registry = registry or _LOADER_REGISTRY
    if raw is None:
        return DEFAULT_LOADER
    if isinstance(raw, str) and (
        raw in PERSISTENT_LOADERS or raw in registry.names()
    ):
        return raw
    LOGGER.warning(
        "Invalid cache.loader %r; expected one of %s. Using %r.",
        raw,
        persistent_loader_names(registry),
        DEFAULT_LOADER,
    )
    return DEFAULT_LOADER


def get_loader_key(
    current_path: str | None = None,
    *,
    config: MarimoConfig | None = None,
) -> CacheLoader:
    """Resolve `cache.loader` for the session, else `DEFAULT_LOADER`.

    Pass `config`, the kernel's effective merged config, to honor a value the
    session or a WebAssembly export provides. Otherwise the on-disk user and
    project config is read.
    """
    if config is None:
        from marimo._config.manager import get_default_config_manager

        config = get_default_config_manager(
            current_path=current_path
        ).get_config()
    return normalize_loader_key((config.get("cache") or {}).get("loader"))


__all__ = [
    "DEFAULT_LOADER",
    "PERSISTENT_LOADERS",
    "BasePersistenceLoader",
    "DualLoader",
    "JsonLoader",
    "LazyLoader",
    "Loader",
    "LoaderKey",
    "LoaderPartial",
    "LoaderType",
    "MemoryLoader",
    "PickleLoader",
    "WasmLazyLoader",
    "dump_cache_manifests",
    "flush_active_caches",
    "get_loader_key",
    "get_persistent_loader",
    "normalize_loader_key",
    "persistent_loader_names",
    "resolve_loader",
]
