# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from pathlib import Path

import click

from marimo._cli.errors import MarimoCLIError
from marimo._cli.help_formatter import ColoredGroup

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


def resolve_cache_dirs_or_error(path: Path, recursive: bool) -> list[Path]:
    """Resolve PATH, reporting a resolution failure as a CLI error."""
    from marimo._save.cache_dirs import CacheDirError, resolve_cache_dirs

    try:
        return resolve_cache_dirs(path, recursive=recursive)
    except CacheDirError as e:
        raise MarimoCLIError(str(e)) from e


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
        if cache_directory.is_dir():
            click.echo(str(cache_directory))
        else:
            click.echo(f"{cache_directory} (does not exist)")
