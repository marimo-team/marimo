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
    if cache_dir.is_dir():
        return str(cache_dir)
    if cache_dir.exists():
        return f"{cache_dir} (not a directory)"
    return f"{cache_dir} (does not exist)"


_BYTE_UNITS = ("B", "KB", "MB", "GB", "TB", "PB")


def format_bytes(size: int) -> str:
    """Render a byte count in binary units, where 1 KB is 1024 B."""
    value = float(size)
    unit = 0
    # Round before comparing, so a value that renders as a full 1024 of its
    # unit moves up instead of printing as "1024.0".
    while round(value, 1) >= 1024 and unit < len(_BYTE_UNITS) - 1:
        value /= 1024
        unit += 1
    if unit == 0:
        return f"{size} B"
    return f"{value:.1f} {_BYTE_UNITS[unit]}"


def format_entries(entries: int) -> str:
    return f"{entries} entry" if entries == 1 else f"{entries} entries"


def resolve_cache_dirs_or_error(path: Path, recursive: bool) -> list[Path]:
    """Resolve PATH, reporting a resolution failure as a CLI error."""
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
    """Directories of the store configuration, or `None`."""
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

These commands work on the `__marimo__/cache/` directories written by marimo's
caching (`mo.persistent_cache`).
""",
)
def cache() -> None:
    pass


@cache.command(
    name="dir",
    help="""Print the cache directories for the directory of the argument.

A blank argument defaults to the current directory, otherwise the provided
argument should be a notebook file or directory. A notebook path resolves to the
cache directory used by a given notebook. A directory resolves within that
directory, as if a notebook ran there. With `-r`/`--recursive`, the directory is
instead searched recursively for `cache` directories, skipping dot-folders.

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


@cache.command(
    name="size",
    help="""Print disk usage and entry counts for the cache.

Prints the disk usage and entry count for each cache directory that
PATH resolves to, and a total when there is more than one. Accepts
`-r`/`--recursive` to search PATH recursively.

Example usage:

    marimo cache size

    marimo cache size -r notebooks/
""",
)
@path_argument
@recursive_option
def cache_size(path: Path, recursive: bool) -> None:
    from marimo._save.cache_dirs import CacheDirStats, cache_dir_stats

    cache_dirs = resolve_cache_dirs_or_error(path, recursive)
    if not cache_dirs:
        click.echo("No cache directories found.")
        return

    total = CacheDirStats()
    for cache_directory in cache_dirs:
        stats = cache_dir_stats(cache_directory)
        total += stats
        label = format_dir(cache_directory)
        click.echo(
            f"{label}\t{format_bytes(stats.total_bytes)}"
            f"\t{format_entries(stats.entries)}"
        )

    if len(cache_dirs) > 1:
        click.echo(
            f"Total\t{format_bytes(total.total_bytes)}"
            f"\t{format_entries(total.entries)}"
        )
