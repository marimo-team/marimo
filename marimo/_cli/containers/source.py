# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import shutil
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

import click

from marimo._cli.containers.engine import BindMount
from marimo._cli.errors import MarimoCLIRuntimeError
from marimo._cli.files.cloudflare import is_r2_path
from marimo._cli.files.file_path import StaticNotebookReader
from marimo._utils.marimo_path import MarimoPath
from marimo._utils.url import is_url

if TYPE_CHECKING:
    from collections.abc import Iterator

_WORKSPACE = PurePosixPath("/marimo-notebook")


@dataclass(frozen=True)
class NotebookSource:
    path: str | None
    working_directory: str = "/home"
    mounts: tuple[BindMount, ...] = ()


@contextmanager
def prepare_notebook(path: str | None) -> Iterator[NotebookSource]:
    if path is None or is_url(path) or is_r2_path(path):
        yield NotebookSource(path)
        return

    try:
        selected = Path(path).expanduser()
        source = selected.resolve(strict=True)
        if not source.is_file() or (
            not MarimoPath.is_valid_path(selected)
            and not (
                selected.suffix == ".html"
                and StaticNotebookReader().can_read(str(selected.absolute()))
            )
        ):
            raise ValueError
    except (OSError, RuntimeError, ValueError) as error:
        raise click.UsageError(
            f"Select one existing local notebook file for container execution: {path}"
        ) from error

    try:
        # Finch shares the home directory with its VM by default.
        with TemporaryDirectory(
            prefix=".marimo-container-", dir=Path.home()
        ) as directory:
            staged = Path(directory) / selected.name
            shutil.copyfile(source, staged)
            staged.chmod(0o600)
            yield NotebookSource(
                path=str(_WORKSPACE / selected.name),
                working_directory=str(_WORKSPACE),
                mounts=(BindMount(source=directory, target=str(_WORKSPACE)),),
            )
    except OSError as error:
        message = (
            f"Could not prepare or remove the isolated notebook copy: {error}"
        )
        if isinstance(error.__context__, MarimoCLIRuntimeError):
            message = f"{error.__context__.format_message()}\n{message}"
        raise MarimoCLIRuntimeError(message) from error
