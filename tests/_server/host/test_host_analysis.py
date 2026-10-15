# Copyright 2026 Marimo. All rights reserved.
"""The host's analyzer reports each cell's names, syntax errors, and conflicts."""

from __future__ import annotations

import asyncio
import threading
from unittest.mock import Mock

import pytest

from marimo._ast.cell import CellImpl
from marimo._ast.compiler import compile_cell
from marimo._core import protocol
from marimo._core.document import Document, DocumentCell
from marimo._server.host.analysis import CellAnalyzer, HostAnalyzer
from marimo._types.ids import CellId_t


def snapshot(codes: dict[str, str]) -> Document:
    return Document(
        [DocumentCell(cid, code) for cid, code in codes.items()],
        {},
    )


def analyze(
    codes: dict[str, str],
) -> dict[protocol.CellId, protocol.CellAnalysis]:
    return CellAnalyzer()(snapshot(codes))


def test_refs_are_names_other_cells_define() -> None:
    analyses = analyze(
        {
            "a": "import marimo as mo\nprint(len(x))",
            "b": "x = 21",
            "c": "y = x * 2",
        }
    )
    assert analyses["a"].defs == ("mo",)
    assert analyses["a"].refs == ("x",)
    assert analyses["b"] == protocol.CellAnalysis(
        defs=("x",), refs=(), errors=()
    )
    assert analyses["c"].refs == ("x",)


def test_a_name_defined_twice_is_an_error_on_each_definer() -> None:
    analyses = analyze({"a": "x = 1", "b": "y = 2\nx = y", "c": "z = x"})
    assert analyses["b"].refs == ()
    assert analyses["c"].refs == ("x",)
    assert analyses["c"].errors == ()

    (first,) = analyses["a"].errors
    (second,) = analyses["b"].errors
    assert first.kind == second.kind == "multiple-definitions"
    assert first.message == "Multiple cells define x"
    assert first.severity == "error"
    # Each copy is ranged at its own definition and lists every definer.
    assert first.range == span(0, 0, 1)
    assert second.range == span(1, 0, 1)
    assert first.related == second.related
    assert [(r.cell_id, r.range, r.message) for r in first.related] == [
        ("a", span(0, 0, 1), "Defines x"),
        ("b", span(1, 0, 1), "Defines x"),
    ]


def test_definition_ranges_cover_the_bound_name() -> None:
    analyses = analyze(
        {
            "a": "def x():\n    pass",
            "b": "import numpy as x",
            "c": "for x in range(3):\n    def y():\n        x = 1",
            "d": "mo.sql('CREATE TABLE x (id INT)')",
        }
    )
    ranges = {cell_id: analyses[cell_id].errors[0].range for cell_id in "abcd"}
    assert ranges["a"] == span(0, 4, 5)
    assert ranges["b"] == span(0, 16, 17)
    assert ranges["c"] == span(0, 4, 5)
    # A SQL definition has no name in the Python source.
    assert ranges["d"] is None


def span(line: int, start: int, end: int) -> protocol.Range:
    return protocol.Range(
        start=protocol.Position(line=line, character=start),
        end=protocol.Position(line=line, character=end),
    )


def test_qualified_sql_definitions_only_conflict_with_the_same_table() -> None:
    analyses = analyze(
        {
            "a": 'mo.sql("CREATE TABLE finance.datalake.xx (id INT)")',
            "b": 'mo.sql("CREATE TABLE finance.information_layer.xx (id INT)")',
            "c": 'mo.sql("CREATE TABLE finance.datalake.xx (id INT)")',
        }
    )
    assert analyses["b"].errors == ()
    for cid in ("a", "c"):
        (error,) = analyses[cid].errors
        assert error.kind == "multiple-definitions"
        assert tuple(item.cell_id for item in error.related) == ("a", "c")
        assert error.range is None


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("import xlib as x", span(0, 15, 16)),
        ("async def x():\n    pass", span(0, 10, 11)),
        ("s = '😀'; x = 1", span(0, 10, 11)),
        ("def f():\n    x = 1\nx = 2", span(2, 0, 1)),
        ("[x for x in ()]\nx = 2", span(1, 0, 1)),
    ],
)
def test_definition_ranges_use_shared_scope_and_token_handling(code, expected):
    analyses = analyze({"a": code, "b": "x = 0"})
    assert analyses["a"].errors[0].range == expected


def test_syntax_errors_leave_the_cell_without_names() -> None:
    analyses = analyze({"a": "def (:", "b": "x = 1"})

    (error,) = analyses["a"].errors
    assert error.kind == "invalid-syntax"
    assert error.source == "marimo"
    assert error.range is not None
    assert error.range.start.line == 0
    assert analyses["a"].defs == ()
    assert analyses["a"].refs == ()
    assert analyses["b"].errors == ()


def test_positions_count_utf16_code_units() -> None:
    analyses = analyze({"a": "s = '😀'; def (:"})

    (error,) = analyses["a"].errors
    assert error.range is not None
    # Python reports the error at `def`, code point 9. The emoji before it
    # is one code point but two UTF-16 units, so LSP sees it at 10.
    assert error.range.start.character == 10


def test_an_analyzer_kept_between_edits_matches_a_fresh_one() -> None:
    analyzer = CellAnalyzer()
    steps = [
        {"a": "x = 1", "b": "y = x"},
        {"a": "x = 1", "b": "y = x", "c": "x = 2"},
        {"a": "x = 1", "b": "y = x", "c": "z = y"},
        {"a": "x = 1", "b": "y = x\nw = z", "c": "z = y"},
        {"b": "y = x\nw = z", "c": "z = y"},
        {"b": "def (:", "c": "z = y"},
    ]
    for codes in steps:
        assert analyzer(snapshot(codes)) == analyze(codes), codes


def test_analyzer_retries_after_an_unexpected_compiler_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analyzer = CellAnalyzer()
    analyzer(snapshot({"a": "x = 1"}))
    codes = {"a": "y = 2", "b": "z = y"}

    def fail(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("compiler failed")

    with monkeypatch.context() as patch:
        patch.setattr("marimo._server.host.analysis.compile_cell", fail)
        with pytest.raises(RuntimeError, match="compiler failed"):
            analyzer(snapshot(codes))

    assert analyzer(snapshot(codes)) == analyze(codes)


async def test_host_analyzer_reports_each_revision_off_the_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loop = asyncio.get_running_loop()
    started = asyncio.Event()
    release = threading.Event()
    codes = {"a": "x = 1", "b": "y = x"}
    expected = analyze(codes)

    def blocked_compile(code: str, cell_id: CellId_t) -> CellImpl:
        loop.call_soon_threadsafe(started.set)
        if not release.wait(timeout=5):
            raise TimeoutError("the event loop did not release compilation")
        return compile_cell(code, cell_id)

    monkeypatch.setattr(
        "marimo._server.host.analysis.compile_cell", blocked_compile
    )
    analyzer = HostAnalyzer()
    reported = asyncio.create_task(analyzer.analyze(snapshot(codes)))
    try:
        await asyncio.wait_for(started.wait(), timeout=5)
        # The loop must resume while compilation is still blocked.
        assert not reported.done()
    finally:
        release.set()
        result = await asyncio.wait_for(reported, timeout=5)

    assert result == expected


async def test_host_analyzer_raises_unexpected_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analyzer = HostAnalyzer()

    def fail(*_: object, **__: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr("marimo._server.host.analysis.compile_cell", fail)
    with pytest.raises(RuntimeError, match="boom"):
        await analyzer.analyze(snapshot({"a": "x = 1"}))


def test_compilation_cache_uses_identity_and_code_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    compiler = Mock(wraps=compile_cell)
    monkeypatch.setattr("marimo._server.host.analysis.compile_cell", compiler)
    analyzer = CellAnalyzer()
    document = Document(
        [
            DocumentCell("a", "x = 1"),
            DocumentCell("b", "y = x"),
            DocumentCell("bad", "def (:"),
        ],
        {},
    )
    analyzer(document)
    assert compiler.call_count == 3

    # Names, configuration, and order are visible without recompiling code.
    document, _ = document.replace(
        [
            DocumentCell("b", "y = x", name="renamed"),
            DocumentCell("a", "x = 1"),
            DocumentCell("bad", "def (:"),
        ],
        {"width": "full"},
    )
    analyzer(document)
    assert compiler.call_count == 3

    # An unchanged cell loses its reference when its provider changes.
    document, _ = document.replace(
        [DocumentCell("a", "z = 1"), DocumentCell("b", "y = x")], {}
    )
    assert analyzer(document)[protocol.CellId("b")].refs == ()
    assert compiler.call_count == 4

    document, _ = document.replace([DocumentCell("b", "y = x")], {})
    analyzer(document)
    document, _ = document.replace(
        [DocumentCell("a", "z = 1"), DocumentCell("c", "y = x")], {}
    )
    analyzer(document)
    assert compiler.call_count == 6


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize(
    ("provider", "consumer", "refs"),
    [
        ('mo.sql("CREATE TABLE t (id INT)")', "print(t)", ()),
        (
            'mo.sql("CREATE TABLE s.t (id INT)")',
            'mo.sql("SELECT * FROM s.t")',
            ("s.t",),
        ),
        (
            'mo.sql("CREATE TABLE s.t (id INT)")',
            'mo.sql("SELECT * FROM other.t")',
            (),
        ),
        ("t = 1", 'mo.sql("SELECT * FROM t")', ("t",)),
    ],
)
def test_references_follow_runtime_language_semantics(
    provider, consumer, refs, reverse
):
    cells = [("provider", provider), ("consumer", consumer)]
    if reverse:
        cells.reverse()
    assert analyze(dict(cells))[protocol.CellId("consumer")].refs == refs
