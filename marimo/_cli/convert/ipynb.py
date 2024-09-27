# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._cli.convert.utils import (
    load_external_file,
)
from marimo._convert.ipynb import convert_from_ipynb


def convert_from_ipynb_file(file_path: str) -> str:
    raw_notebook = load_external_file(file_path, "ipynb")
    return convert_from_ipynb(raw_notebook)
