# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click

from marimo import _loggers
from marimo._cli.errors import MarimoCLIError
from marimo._cli.help_formatter import ColoredGroup
from marimo._config.settings import GLOBAL_SETTINGS

if TYPE_CHECKING:
    from marimo._save.cache_dirs import CacheDirStats
    from marimo._save.prune import DirectoryPrunePlan, PrunePlan

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


def stats_line(cache_dir: Path, stats: CacheDirStats) -> str:
    return (
        f"{format_dir(cache_dir)}\t{format_bytes(stats.total_bytes)}"
        f"\t{format_entries(stats.entries)}"
    )


def total_line(total: CacheDirStats) -> str:
    return (
        f"Total\t{format_bytes(total.total_bytes)}"
        f"\t{format_entries(total.entries)}"
    )


def report(measured: list[tuple[Path, CacheDirStats]]) -> CacheDirStats:
    """Print what each cache directory holds, and a total across several."""
    from marimo._save.cache_dirs import CacheDirStats

    total = CacheDirStats()
    for cache_directory, stats in measured:
        total += stats
        click.echo(stats_line(cache_directory, stats))
    if len(measured) > 1:
        click.echo(total_line(total))
    return total


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
    from marimo._save.cache_dirs import cache_dir_stats

    cache_dirs = resolve_cache_dirs_or_error(path, recursive)
    if not cache_dirs:
        click.echo("No cache directories found.")
        return

    report(
        [
            (cache_directory, cache_dir_stats(cache_directory))
            for cache_directory in cache_dirs
        ]
    )


@cache.command(
    name="clean",
    help="""Delete cache entries outright.

With a notebook PATH, deletes exactly the entries listed in that
notebook's manifest, then empties those records from the manifest.
Entries the manifest does not list are left in place. With a directory
PATH, deletes blocks directly, including their blob directories, the
folders that hold each entry's stored value, or every block if you
name none. Pass one or more NAME arguments to limit either mode to
those blocks. Each NAME must match a name given to
`mo.persistent_cache`. Accepts `-r`/`--recursive` to search PATH
recursively.

Example usage:

    marimo cache clean my_notebook.py

    marimo cache clean my_notebook.py train

    marimo cache clean notebooks/
""",
)
@path_argument
@click.argument("names", nargs=-1, metavar="[NAME]...")
@recursive_option
@click.option(
    "--yes",
    "--force",
    "-y",
    is_flag=True,
    default=False,
    help="Delete without asking for confirmation.",
)
def cache_clean(
    path: Path, names: tuple[str, ...], recursive: bool, yes: bool
) -> None:
    cache_dirs = resolve_cache_dirs_or_error(path, recursive)
    if not cache_dirs:
        click.echo("No cache directories found.")
        return

    if path.is_dir():
        _clean_blocks(cache_dirs, names, yes=yes)
        return
    # A configured store can keep a copy of the manifest in several
    # directories; each is cleaned on its own record.
    for cache_directory in cache_dirs:
        _clean_tracked_entries(path, cache_directory, names, yes=yes)


def _clean_blocks(
    cache_dirs: list[Path], names: tuple[str, ...], *, yes: bool
) -> None:
    """Delete whole blocks from every cache directory PATH resolved to."""
    from marimo._save.cache_dirs import CacheDirStats, clean_cache_dir

    planned = report(
        [
            (
                cache_directory,
                clean_cache_dir(cache_directory, names, dry_run=True),
            )
            for cache_directory in cache_dirs
        ]
    )
    if _deletes_nothing(planned):
        click.echo("Nothing to delete.")
        return
    if not _confirm(planned, yes=yes):
        return

    freed = CacheDirStats()
    for cache_directory in cache_dirs:
        freed += clean_cache_dir(cache_directory, names)
    _report_deleted(freed)


def _clean_tracked_entries(
    notebook: Path, cache_dir: Path, names: tuple[str, ...], *, yes: bool
) -> None:
    """Delete the entries `notebook`'s manifest lists, and forget them."""
    from marimo._save.cache_dirs import (
        CacheDirStats,
        block_dir_name,
        delete_cache_entries,
    )
    from marimo._save.manifest import (
        ManifestError,
        load_manifest,
        manifest_name,
    )
    from marimo._save.stores.file import FileStore

    key = manifest_name(notebook)
    store = FileStore(save_path=str(cache_dir))
    manifest = None
    if cache_dir.is_dir():
        try:
            manifest = load_manifest(store, key)
        except (ManifestError, OSError) as e:
            raise MarimoCLIError(str(e)) from e
    if manifest is None:
        click.echo(format_dir(cache_dir))
        click.echo(f"Nothing is tracked for {notebook}.")
        return

    entries = manifest.entries()
    if names:
        wanted = {block_dir_name(name) for name in names}
        entries = {entry for entry in entries if entry[0] in wanted}

    planned = delete_cache_entries(cache_dir, entries, dry_run=True)
    report([(cache_dir, planned)])
    if not entries:
        click.echo("Nothing to delete.")
        return

    # A record whose entry no file answers to is dropped without asking.
    # Forgetting it takes nothing away from the cache.
    deleting = not _deletes_nothing(planned)
    if deleting and not _confirm(planned, yes=yes):
        return

    freed = (
        delete_cache_entries(cache_dir, entries)
        if deleting
        else CacheDirStats()
    )
    # A record whose entry could not be removed is kept. The entry is still
    # there to be read, and to be deleted another time.
    manifest.discard(entries - _still_held(cache_dir, entries))
    try:
        store.put(key, manifest.to_bytes())
    except OSError as e:
        raise MarimoCLIError(f"Could not rewrite {key}: {e}") from e

    if deleting:
        _report_deleted(freed)
        return
    click.echo("Nothing to delete.")
    click.echo(
        f"Forgot {format_entries(len(entries))} the cache no longer holds."
    )


def _still_held(
    cache_dir: Path, entries: set[tuple[str, str]]
) -> set[tuple[str, str]]:
    """The entries a file on disk still answers to."""
    return {
        (block, key)
        for block, key in entries
        if (cache_dir / block / key).exists()
        or any((cache_dir / block).glob(f"{key}.*"))
    }


@cache.command(
    name="prune",
    help="""Delete cache entries that current code can no longer produce.

Uses each cache directory's manifest and the current source code to
find entries that current code can no longer produce, then deletes
them. Prune never deletes an entry recorded under code that still
exists. Deleting too much costs a recomputation. It never produces a
wrong result. Accepts `-r`/`--recursive` to search PATH recursively.

Example usage:

    marimo cache prune my_notebook.py

    marimo cache prune my_notebook.py --dry-run

    marimo cache prune my_notebook.py --force

Use `--dry-run` to report the planned deletions and delete nothing.
Use `--force` (or `-y`) to skip confirmation prompts, for
example in an automated script.
""",
)
@path_argument
@recursive_option
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Report the planned deletions and delete nothing.",
)
@click.option(
    "--force",
    "--yes",
    "-y",
    "force",
    is_flag=True,
    default=False,
    help="Prune without asking for confirmation.",
)
def cache_prune(
    path: Path, recursive: bool, dry_run: bool, force: bool
) -> None:
    from marimo._save.prune import PrunePlan, apply_prune, plan_prune

    cache_dirs = resolve_cache_dirs_or_error(path, recursive)
    if not cache_dirs:
        click.echo("No cache directories found.")
        return

    plan = plan_prune(cache_dirs)
    _report_plan(plan)
    if dry_run:
        click.echo("Deleted nothing (--dry-run).")
        return

    approved = PrunePlan(
        tuple(
            directory
            for directory in plan.directories
            if not directory.is_empty() and _approve(directory, force=force)
        )
    )
    freed = apply_prune(approved)
    if freed.entries:
        _report_deleted(freed)
        return
    click.echo("Nothing to delete.")


def _report_plan(plan: PrunePlan) -> None:
    """Print the planned deletions for each cache directory, and why."""
    for directory in plan.directories:
        click.echo(stats_line(directory.cache_dir, directory.freed))
        for note in _notes(directory):
            click.echo(f"  {note}")
    if len(plan.directories) > 1:
        click.echo(total_line(plan.freed))


def _notes(directory: DirectoryPrunePlan) -> list[str]:
    notes = [*directory.skips, *directory.confirmations]
    if directory.dead_nodes:
        records = "record" if directory.dead_nodes == 1 else "records"
        notes.append(
            f"{directory.dead_nodes} {records} of code the notebook no "
            "longer has."
        )
    if directory.untracked:
        notes.append(
            f"Kept {format_entries(directory.untracked)} that no readable "
            "manifest tracks."
        )
    return notes


def _approve(directory: DirectoryPrunePlan, *, force: bool) -> bool:
    """Ask before pruning a directory whose entries are not all accounted for.

    The reasons were printed with the plan. The prompt names the directory
    they belong to.
    """
    if not directory.needs_approval():
        return True
    if force or GLOBAL_SETTINGS.YES:
        return True
    if not _interactive():
        click.echo(
            f"Skipping {directory.cache_dir}: rerun with --force to prune it."
        )
        return False
    return click.confirm(
        f"Delete {format_entries(directory.freed.entries)} "
        f"({format_bytes(directory.freed.total_bytes)}) "
        f"from {directory.cache_dir}?"
    )


def _interactive() -> bool:
    """Whether anyone is there to answer a prompt."""
    return sys.stdin.isatty()


def _deletes_nothing(planned: CacheDirStats) -> bool:
    return not planned.entries and not planned.total_bytes


def _confirm(planned: CacheDirStats, *, yes: bool) -> bool:
    """Ask before deleting what `planned` measured.

    An answer already given, to this command or to `marimo` itself, stands in
    for the prompt.
    """
    if yes or GLOBAL_SETTINGS.YES:
        return True
    return click.confirm(
        f"Delete {format_entries(planned.entries)} "
        f"({format_bytes(planned.total_bytes)})?"
    )


def _report_deleted(freed: CacheDirStats) -> None:
    click.echo(
        f"Deleted {format_entries(freed.entries)}, "
        f"freeing {format_bytes(freed.total_bytes)}."
    )
