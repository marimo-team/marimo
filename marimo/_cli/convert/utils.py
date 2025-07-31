# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from pathlib import Path

import click

import marimo._utils.requests as requests
from marimo._cli.file_path import get_github_src_url, is_github_src
from marimo._utils.url import is_url


def load_external_file(file_path: str, ext: str) -> str:
    notebook: str = ""
    if is_github_src(file_path, ext=ext):
        notebook = (
            requests.get(get_github_src_url(file_path))
            .raise_for_status()
            .text()
        )
    elif is_url(file_path):
        notebook = requests.get(file_path).raise_for_status().text()
    else:
        if not Path(file_path).exists():
            raise click.FileError(file_path, "File does not exist")
        notebook = Path(file_path).read_text(encoding="utf-8")

    return notebook
