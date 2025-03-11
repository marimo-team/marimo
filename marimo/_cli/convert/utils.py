# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import urllib.request
from pathlib import Path

import click

from marimo._cli.file_path import get_github_src_url, is_github_src
from marimo._utils.url import is_url


def load_external_file(file_path: str, ext: str) -> str:
    notebook: str = ""
    if is_github_src(file_path, ext=ext):
        notebook = (
            urllib.request.urlopen(get_github_src_url(file_path))
            .read()
            .decode("utf-8")
        )
    elif is_url(file_path):
        notebook = urllib.request.urlopen(file_path).read().decode("utf-8")
    else:
        if not Path(file_path).exists():
            raise click.FileError(file_path, "File does not exist")
        notebook = Path(file_path).read_text(encoding="utf-8")

    return notebook
