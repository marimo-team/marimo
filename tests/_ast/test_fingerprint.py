# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import ast

import pytest

from marimo._ast.fingerprint import ast_fingerprint, code_fingerprint
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


def test_fingerprint_is_stable_across_python_versions() -> None:
    # No version gate: every supported Python must produce this digest.
    assert code_fingerprint("import os\nx = {1: 'a'}\nx[1]") == (
        "ad8658a8c42531146be6bce07d450918d1d3f733d05c8d7cd1cdb5a861683da6"
    )


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("match x:\n case None: pass", "match x:\n case False: pass"),
        ("x = 0", "x = False"),
        ("f(**d)", "f(x=d)"),
        ("from . import x", "from .. import x"),
        ("def f(x: u'hey'): pass", "def f(x: 'hey'): pass"),
    ],
)
def test_falsy_literals_are_not_dropped(before: str, after: str) -> None:
    assert code_fingerprint(before) != code_fingerprint(after)


def test_formatting_changes_etags_without_changing_fingerprints() -> None:
    before = DocumentCell(CellId("a"), "x=1")
    after = DocumentCell(CellId("a"), "x = 1 # formatted")
    assert before.code_fingerprint == after.code_fingerprint
    assert before.etag != after.etag


@pytest.mark.parametrize("stage", ["ast.parse", "_feed"])
def test_ast_limits_preserve_document_source(
    monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    def exhausted(*_args: object, **_kwargs: object) -> None:
        raise RecursionError

    monkeypatch.setattr(f"marimo._ast.fingerprint.{stage}", exhausted)
    source = "x = 1"
    cell = DocumentCell(CellId("a"), source)
    edited = DocumentCell(CellId("a"), source + " # edited")
    assert cell.code == source
    assert cell.code_fingerprint == code_fingerprint(source)
    assert cell.code_fingerprint != edited.code_fingerprint


def test_deep_expression_can_be_stored() -> None:
    source = "x = " + "+".join(["1"] * 10000)
    assert DocumentCell(CellId("a"), source).code == source


def test_ast_fingerprint_matches_source_fingerprint() -> None:
    source = "x = 1\nx"
    assert ast_fingerprint(ast.parse(source)) == code_fingerprint(source)
    assert ast_fingerprint(ast.parse(source), suppress_output=True) == (
        code_fingerprint(source + ";")
    )
