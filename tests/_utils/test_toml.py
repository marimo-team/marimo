# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import tempfile
from pathlib import Path

from marimo._utils.toml import toml_reader


def test_reads_simple_table() -> None:
    data = toml_reader.reads('title = "demo"\ncount = 3\n')
    assert data == {"title": "demo", "count": 3}


def test_reads_nested() -> None:
    src = """
[tool.marimo]
autosave = true

[tool.marimo.runtime]
on_cell_change = "autorun"
"""
    data = toml_reader.reads(src)
    assert data["tool"]["marimo"]["autosave"] is True
    assert data["tool"]["marimo"]["runtime"]["on_cell_change"] == "autorun"


def test_reads_invalid_raises_decode_error() -> None:
    raised = False
    try:
        toml_reader.reads("this is = = not toml")
    except toml_reader.decode_error:
        raised = True
    assert raised


def test_read_file_matches_reads() -> None:
    content = 'name = "x"\n'
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "cfg.toml"
        path.write_text(content, encoding="utf-8")
        assert toml_reader.read(path) == toml_reader.reads(content)
