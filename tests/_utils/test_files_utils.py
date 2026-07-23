# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import tempfile
from pathlib import Path

from marimo._utils import files as files_mod
from marimo._utils.files import expand_file_patterns, natural_sort


def test_natural_sort_orders_numeric_runs() -> None:
    names = ["file10.txt", "file2.txt", "file1.txt"]
    assert sorted(names, key=natural_sort) == [
        "file1.txt",
        "file2.txt",
        "file10.txt",
    ]


def test_natural_sort_case_insensitive_alpha() -> None:
    # Non-numeric segments are lowercased in the key
    assert natural_sort("Apple") == natural_sort("apple")


def test_natural_sort_empty() -> None:
    assert natural_sort("") == [""]


def test_natural_sort_mixed_segments() -> None:
    assert natural_sort("a10b2") == ["a", 10, "b", 2, ""]


def test_get_root_before_glob() -> None:
    assert files_mod._get_root("src/*.py") == "src"
    assert files_mod._get_root("*.py") == "."
    root = files_mod._get_root("nosuchdir/nope.py")
    assert isinstance(root, str)


def test_expand_file_patterns_single_file() -> None:
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "nb.py"
        f.write_text("# x\n", encoding="utf-8")
        assert expand_file_patterns((str(f),)) == [f]


def test_expand_file_patterns_directory_skips_dotdirs() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "a.py").write_text("a\n", encoding="utf-8")
        nested = root / "sub"
        nested.mkdir()
        (nested / "b.py").write_text("b\n", encoding="utf-8")
        hidden = root / ".git"
        hidden.mkdir()
        (hidden / "secret.py").write_text("s\n", encoding="utf-8")

        found = expand_file_patterns((str(root),))
        names = {p.name for p in found}
        assert names == {"a.py", "b.py"}
