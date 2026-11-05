# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import functools
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click

from marimo._cli.errors import MarimoCLIError
from marimo._cli.help_formatter import ColoredGroup
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._save.cache_dirs import CacheDirStats

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from marimo._save.cache_dirs import CachePlan
    from marimo._save.prune import PrunePlan

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

yes_option = click.option(
    "-y",
    "--yes",
    is_flag=True,
    default=False,
    help="Delete without asking for confirmation.",
)

dry_run_option = click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Report what deletions would occur.",
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


def _exit_if_incomplete(stats: CacheDirStats) -> None:
    """Fail the command when some paths were not cleaned."""
    if not stats.failures:
        return
    paths = (
        "1 path was" if stats.failures == 1 else f"{stats.failures} paths were"
    )
    raise MarimoCLIError(f"{paths} not cleaned. See the warnings above.")


def report(
    measured: list[tuple[Path, CacheDirStats]],
    notes: Mapping[Path, Sequence[str]] | None = None,
) -> CacheDirStats:
    """Print cache directory listing and total."""
    total = CacheDirStats()
    for cache_directory, stats in measured:
        total += stats
        click.echo(
            f"{format_dir(cache_directory)}\t{format_bytes(stats.total_bytes)}"
            f"\t{format_entries(stats.entries)}"
        )
        for note in (notes or {}).get(cache_directory, ()):
            click.echo(f"  {note}")
    if len(measured) > 1:
        click.echo(
            f"Total\t{format_bytes(total.total_bytes)}"
            f"\t{format_entries(total.entries)}"
        )
    return total


def report_plans(
    plans: Sequence[CachePlan],
    notes: Mapping[Path, Sequence[str]] | None = None,
) -> CacheDirStats:
    """Print what each plan frees, and return the total."""
    return report([(plan.cache_dir, plan.freed) for plan in plans], notes)


def resolve_cache_dirs_or_error(
    path: Path, recursive: bool, *, deleting: bool = False
) -> list[Path]:
    from marimo._save.cache_dirs import (
        CacheDirError,
        configured_store_dirs,
        named_by_path,
        resolve_cache_dirs,
    )

    if recursive and not path.is_dir():
        raise click.UsageError(
            f"-r/--recursive searches a directory, and {path} is a file."
        )
    try:
        cache_dirs = resolve_cache_dirs(
            path, recursive=recursive, deleting=deleting
        )
    except CacheDirError as e:
        raise MarimoCLIError(str(e)) from e
    configured = configured_store_dirs(path, cache_dirs)
    if not deleting:
        return configured
    kept, unnamed = named_by_path(path, cache_dirs, configured)
    for directory in unnamed:
        click.echo(
            f"Configured cache.store at {directory}; pass it as PATH "
            "to act on it."
        )
    return kept


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
    help="""Delete all relevant cache entries for a notebook or directory.

When this command is given a notebook path, it deletes all corresponding cache
entries. When given a directory path, it deletes all cache entries that
correspond to notebooks in that directory and (optionally) its subdirectories.
Additionally accepts explicit cache keys, as provided to `mo.persistent_cache`.
Defaults to the current directory if no path is provided.

Pass one or more arguments. Accepts `-r`/`--recursive` to search `path`
recursively. A prompt is provided before deletion; use `-y`/`--yes` to
skip the prompt, or `--dry-run` to simulate the deletion.

Example usage:

    marimo cache clean my_notebook.py

    marimo cache clean my_notebook.py train

    marimo cache clean notebooks/
""",
)
@path_argument
@click.argument("names", nargs=-1, metavar="[NAME]...")
@recursive_option
@yes_option
@dry_run_option
def cache_clean(
    path: Path,
    names: tuple[str, ...],
    recursive: bool,
    yes: bool,
    dry_run: bool,
) -> None:
    cache_dirs = resolve_cache_dirs_or_error(path, recursive, deleting=True)
    if not cache_dirs:
        click.echo("No cache directories found.")
        return

    if path.is_dir():
        _clean_blocks(cache_dirs, names, yes=yes, dry_run=dry_run)
        return
    for cache_directory in cache_dirs:
        _clean_tracked_entries(
            path, cache_directory, names, yes=yes, dry_run=dry_run
        )


def _clean_blocks(
    cache_dirs: list[Path],
    names: tuple[str, ...],
    *,
    yes: bool,
    dry_run: bool,
) -> None:
    from marimo._save.clean import apply_block_clean, plan_block_clean

    plans = [plan_block_clean(directory, names) for directory in cache_dirs]
    planned = report_plans(plans)
    if not planned.entries and not planned.total_bytes:
        click.echo("Nothing to delete.")
        _exit_if_incomplete(planned)
        return
    if dry_run:
        _report_deleted(planned, dry_run=True)
        _exit_if_incomplete(planned)
        return
    if not _confirm(planned, yes=yes):
        return
    freed = sum((apply_block_clean(p) for p in plans), CacheDirStats())
    _report_deleted(freed)
    _exit_if_incomplete(freed)


def _clean_tracked_entries(
    notebook: Path,
    cache_dir: Path,
    names: tuple[str, ...],
    *,
    yes: bool,
    dry_run: bool,
) -> None:
    from marimo._save.cache_dirs import CacheDirError
    from marimo._save.clean import apply_clean, plan_clean
    from marimo._save.manifest import ManifestError

    try:
        plan = plan_clean(cache_dir, notebook, names)
    except (CacheDirError, ManifestError, OSError) as e:
        raise MarimoCLIError(str(e)) from e
    if not plan.tracked:
        click.echo(format_dir(cache_dir))
        click.echo(f"Nothing is tracked for {notebook}.")
        return

    report([(cache_dir, plan.freed)])
    if not plan.entries:
        click.echo("Nothing to delete.")
        return

    def apply() -> CacheDirStats:
        return _apply_or_error(lambda: apply_clean(plan))

    if plan.deletes_nothing():
        # Forgetting a record no file answers to removes no cached value,
        # so the command does not ask.
        freed = CacheDirStats() if dry_run else apply()
        click.echo("Nothing to delete.")
        _report_forgotten(len(plan.entries), dry_run=dry_run)
        _exit_if_incomplete(freed)
        return
    if dry_run:
        _report_deleted(plan.freed, dry_run=True)
        return
    if not _confirm(plan.freed, yes=yes):
        return
    freed = apply()
    _report_deleted(freed)
    _exit_if_incomplete(freed)


@cache.command(
    name="prune",
    help="""Delete unused cache entries.

Determines which cache entries are addressable in a given notebook or directory,
and deletes the rest.
Ambiguous orphans are cleaned when `--force` is applied.

Defaults to the current directory if no path is provided. Accepts
`-r`/`--recursive` to search `path` recursively. A prompt is provided
before deletion; use `-y`/`--yes` to skip the prompt, or `--dry-run` to
simulate the deletion.

Example usage:

    marimo cache prune my_notebook.py

    marimo cache prune --dry-run -r notebooks/

    marimo cache prune -y notebooks/
""",
)
@path_argument
@recursive_option
@yes_option
@dry_run_option
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help=("Also prune potentially orphaned cache entries."),
)
def cache_prune(
    path: Path, recursive: bool, yes: bool, dry_run: bool, force: bool
) -> None:
    cache_dirs = resolve_cache_dirs_or_error(path, recursive, deleting=True)
    if not cache_dirs:
        click.echo("No cache directories found.")
        return

    _prune_cache_dirs(cache_dirs, force=force, yes=yes, dry_run=dry_run)


def _prune_cache_dirs(
    cache_dirs: list[Path],
    *,
    force: bool,
    yes: bool,
    dry_run: bool,
) -> None:
    from marimo._save.cache_dirs import CacheDirError
    from marimo._save.prune import apply_prune, plan_prune

    try:
        plans = [
            plan_prune(directory, force=force) for directory in cache_dirs
        ]
    except (CacheDirError, OSError) as e:
        raise MarimoCLIError(str(e)) from e
    planned = report_plans(
        plans, notes={plan.cache_dir: _prune_notes(plan) for plan in plans}
    )

    def apply() -> CacheDirStats:
        return sum(
            (
                _apply_or_error(functools.partial(apply_prune, plan))
                for plan in plans
            ),
            CacheDirStats(),
        )

    if not planned.entries and not planned.total_bytes:
        # Forgetting a record no file answers to removes no cached value,
        # so the command does not ask.
        forgotten = sum(plan.forgets() for plan in plans)
        freed = planned if dry_run or not forgotten else apply()
        click.echo("Nothing to delete.")
        _report_forgotten(forgotten, dry_run=dry_run)
        _exit_if_incomplete(freed)
        return
    if dry_run:
        _report_deleted(planned, dry_run=True)
        _exit_if_incomplete(planned)
        return
    if not _confirm(planned, yes=yes):
        return
    freed = apply()
    _report_deleted(freed)
    _exit_if_incomplete(freed)


def _prune_notes(plan: PrunePlan) -> list[str]:
    notes = list(plan.notes)
    if plan.dead_nodes:
        hashes = "path hash" if plan.dead_nodes == 1 else "path hashes"
        notes.append(
            f"{plan.dead_nodes} {hashes} of code the notebook no longer has."
        )
    if plan.untracked:
        notes.append(
            f"Kept {format_entries(plan.untracked)} that no manifest tracks."
        )
    if plan.claimed:
        notes.append(
            f"({plan.claimed}) cache entries are locked. Either the entry is "
            "being written, or a notebook unexpectedly crashed while caching. "
            "Pass --force to remove them."
        )
    return notes


def _apply_or_error(apply: Callable[[], CacheDirStats]) -> CacheDirStats:
    from marimo._save.cache_dirs import CacheDirError
    from marimo._save.manifest import ManifestError

    try:
        return apply()
    except (CacheDirError, ManifestError, OSError) as e:
        raise MarimoCLIError(str(e)) from e


def _confirm(planned: CacheDirStats, *, yes: bool) -> bool:
    """Confirm deletion. Without a terminal, only `-y` consents."""
    if yes or GLOBAL_SETTINGS.YES:
        return True
    what = (
        f"{format_entries(planned.entries)} "
        f"({format_bytes(planned.total_bytes)})"
    )
    if not sys.stdin.isatty():
        click.echo(f"Skipping {what}: rerun with -y to delete.")
        return False
    return click.confirm(f"Delete {what}?")


def _report_deleted(freed: CacheDirStats, *, dry_run: bool = False) -> None:
    verb = "Would delete" if dry_run else "Deleted"
    click.echo(
        f"{verb} {format_entries(freed.entries)}, "
        f"freeing {format_bytes(freed.total_bytes)}."
    )


def _report_forgotten(records: int, *, dry_run: bool) -> None:
    if not records:
        return
    verb = "Would forget" if dry_run else "Forgot"
    click.echo(f"{verb} {format_entries(records)} the cache no longer holds.")
