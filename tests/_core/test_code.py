# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import sys

import pytest

from marimo._core.code import code_fingerprint
from marimo._core.document import DocumentCell
from marimo._core.protocol import CellId


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("x=1", "# comment\nx = 1\n"),
        ("", "# just a comment\n"),
        ("x + 1", "(x + 1)"),
        ("x = 1", "x = 1;"),
        ("x;", "x; # suppress output\n"),
        ("x = 'hello'", 'x = "hello"'),
        ("x = 1", "x\u00a0= 1"),
        ("async def f():\n    await g()", "async def f():\n  await g()"),
    ],
)
def test_formatting_preserves_fingerprints(before: str, after: str) -> None:
    assert code_fingerprint(before) == code_fingerprint(after)


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("x = 1\nx + 1", 'x = "1"\nx + 1'),
        ("x = 1; y = 23", "x = 12; y = 3"),
        ("x = 1", "x = True"),
        ("x = 1", "x = 1.0"),
        ("def f(x): return x", "def f(y): return y"),
        ("x", "x;"),
        ("x", "x; # hidden"),
        ("x = 'a b'", "x = 'ab'"),
        ("await f()", "await g()"),
        ("if !!!", "if !!! # comment"),
        ("x =", "x = "),
    ],
)
def test_meaningful_changes_change_fingerprints(
    before: str, after: str
) -> None:
    assert code_fingerprint(before) != code_fingerprint(after)


def test_fingerprint_scheme_includes_python_version() -> None:
    fingerprint = code_fingerprint("x = 1")
    prefix = f"py-ast-v1:{sys.version_info.major}.{sys.version_info.minor}:"
    assert fingerprint.startswith(prefix)
    digest = fingerprint.removeprefix(prefix)
    assert len(digest) == 64
    assert int(digest, 16) >= 0


def test_formatting_changes_etags_without_changing_fingerprints() -> None:
    before = DocumentCell(CellId("a"), "x=1")
    after = DocumentCell(CellId("a"), "x = 1 # formatted")
    assert before.code_fingerprint == after.code_fingerprint
    assert before.etag != after.etag
