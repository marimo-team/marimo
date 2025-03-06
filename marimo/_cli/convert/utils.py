# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import urllib.request
from pathlib import Path

from marimo._cli.file_path import get_github_src_url, is_github_src


def load_external_file(file_path: str, ext: str) -> str:
    notebook: str = ""
    if is_github_src(file_path, ext=ext):
        notebook = (
            urllib.request.urlopen(get_github_src_url(file_path))
            .read()
            .decode("utf-8")
        )
    else:
        notebook = Path(file_path).read_text(encoding="utf-8")

    return notebook
