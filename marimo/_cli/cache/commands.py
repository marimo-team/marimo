# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from pathlib import Path

import click

from marimo import _loggers
from marimo._cli.errors import MarimoCLIError
from marimo._cli.help_formatter import ColoredGroup

LOGGER = _loggers.marimo_logger()

path_argument = click.argument(
    "path",
    required=False,
    default=".",
    type=click.Path(exists=True, path_type=Path),
)

recursive_option = click.option(
    "-r",
    "--recursive",
    is_flag=True,
    default=False,
    help=(
        "Search a directory PATH recursively for cache directories, "
        "skipping dot-folders."
    ),
)


def format_dir(cache_dir: Path) -> str:
    """Name a cache directory, and say so when it is not one yet."""
    if cache_dir.is_dir():
        return str(cache_dir)
    if cache_dir.exists():
        return f"{cache_dir} (not a directory)"
    return f"{cache_dir} (does not exist)"


def resolve_cache_dirs_or_error(path: Path, recursive: bool) -> list[Path]:
    """Resolve PATH, reporting a resolution failure as a CLI error.

    A `cache.store` entry in the configuration replaces the resolution: the
    kernel writes to the configured store, so the commands act there rather
    than on the directory PATH names. PATH is still validated, and still
    names the notebook whose manifest is read.
    """
    from marimo._save.cache_dirs import CacheDirError, resolve_cache_dirs

    try:
        cache_dirs = resolve_cache_dirs(path, recursive=recursive)
    except CacheDirError as e:
        raise MarimoCLIError(str(e)) from e
    configured = _configured_store_dirs(path, cache_dirs)
    if configured is None:
        return cache_dirs
    return configured


def _configured_store_dirs(
    path: Path, cache_dirs: list[Path]
) -> list[Path] | None:
    """Directories of the store the configuration picks, or `None`.

    A configuration that cannot be read does not pick a store, so the
    resolution falls back to PATH. A file store given no `save_path` writes
    beside the notebook, which is where PATH resolved to, so `cache_dirs`
    stand in for it. Outside a kernel the store itself cannot say where the
    notebook is.

    A store set by a layer that travels with the code, a pyproject or the
    notebook's own header, is not trusted by the default cache method,
    which keeps writing beside the notebook. Both places can then hold the
    notebook's entries, so both are acted on.
    """
    from marimo._save.stores import (
        cache_store_is_untrusted,
        configured_cache_store,
    )
    from marimo._save.stores.file import FileStore
    from marimo._save.stores.tiered import TieredStore

    try:
        store = configured_cache_store(current_path=str(path))
        if store is None:
            return None
        untrusted = cache_store_is_untrusted(current_path=str(path))
    except Exception:
        LOGGER.warning("Could not read the cache store from the config")
        return None

    tiers = store.stores if isinstance(store, TieredStore) else [store]
    directories: list[Path] = list(cache_dirs) if untrusted else []
    for tier in tiers:
        if isinstance(tier, FileStore) and tier.uses_default_path:
            directories.extend(cache_dirs)
        else:
            directories.extend(tier.local_dirs())
    return list(dict.fromkeys(directories))


@click.group(
    cls=ColoredGroup,
    help="""Inspect and clean up the on-disk cache.

These commands work on the `__marimo__/cache/` directories that
`mo.persistent_cache` writes. Each `mo.persistent_cache` name gets its
own block, the subdirectory that holds its entries, for example `train`
in `__marimo__/cache/train/`. A notebook PATH resolves to the cache
directory beside that notebook. A directory PATH resolves its own
`__marimo__/cache`, as if a notebook ran in that directory. Add `-r`
to search the directory recursively instead.
""",
)
def cache() -> None:
    pass


@cache.command(
    name="dir",
    help="""Print the cache directories that PATH resolves to.

PATH is a notebook file or a directory. It defaults to the current
directory. A notebook path resolves to the cache directory beside that
notebook. A directory resolves `__marimo__/cache` in that directory, as
if a notebook ran there. With `-r`/`--recursive`, the directory is
instead searched recursively for `__marimo__/cache` directories,
skipping dot-folders.

Example usage:

    marimo cache dir

    marimo cache dir notebook.py

    marimo cache dir -r notebooks/
""",
)
@path_argument
@recursive_option
def cache_dir(path: Path, recursive: bool) -> None:
    cache_dirs = resolve_cache_dirs_or_error(path, recursive)
    if not cache_dirs:
        click.echo("No cache directories found.")
        return

    for cache_directory in cache_dirs:
        click.echo(format_dir(cache_directory))
