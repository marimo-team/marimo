# Copyright 2026 Marimo. All rights reserved.
"""The host's analyzer reports names, syntax errors, conflicts, and cycles."""

from __future__ import annotations

import asyncio
import threading
from unittest.mock import Mock

import pytest
from inline_snapshot import snapshot

from marimo._ast.cell import CellImpl
from marimo._ast.compiler import compile_cell
from marimo._core import protocol
from marimo._core.document import CellSource, Document, DocumentSnapshot
from marimo._server.host.analysis import CellAnalyzer, HostAnalyzer
from marimo._types.ids import CellId_t


def document_snapshot(codes: dict[str, str]) -> DocumentSnapshot:
    return Document(
        protocol.NotebookId("n1"),
        [CellSource(cid, code) for cid, code in codes.items()],
        {},
    ).snapshot()


def analyze(
    codes: dict[str, str],
) -> dict[protocol.CellId, protocol.CellAnalysis]:
    return CellAnalyzer()(document_snapshot(codes))


def render_diagnostics(
    codes: dict[str, str],
    analyses: dict[protocol.CellId, protocol.CellAnalysis],
) -> str:
    """Show spans on source, with related spans labeled by their origin cell.

    Escape non-ASCII text and tabs so alignment does not depend on terminal
    character widths. Protocol columns count UTF-16 units, not characters.
    """

    def display(text: str) -> str:
        return text.encode("unicode_escape").decode("ascii")

    def column(text: str, offset: int) -> int:
        encoded = text.encode("utf-16-le")
        assert 0 <= offset * 2 <= len(encoded)
        return len(display(encoded[: offset * 2].decode("utf-16-le")))

    annotations: dict[str, list[tuple[protocol.Range | None, str]]] = {
        cid: [
            (error.range, f"{error.severity}[{error.kind}]: {error.message}")
            for error in analyses[cid].errors
        ]
        for cid in codes
    }
    for cid, analysis in analyses.items():
        for error in analysis.errors:
            for related in error.related:
                annotations[related.cell_id].append(
                    (related.range, f"related[{cid}]: {related.message}")
                )

    rendered: list[str] = []
    for cid, source in codes.items():
        rendered.append(f"-- {cid} --")
        lines = source.split("\n")
        width = len(str(len(lines)))
        for where, _ in annotations[cid]:
            if where is not None:
                assert 0 <= where.start.line <= where.end.line < len(lines)
        for index, text in enumerate(lines):
            rendered.append(f"{index + 1:>{width}} | {display(text)}")
            for where, label in annotations[cid]:
                if (
                    where is None
                    or not where.start.line <= index <= where.end.line
                ):
                    continue
                start = (
                    column(text, where.start.character)
                    if index == where.start.line
                    else 0
                )
                end = (
                    column(text, where.end.character)
                    if index == where.end.line
                    else len(display(text))
                )
                assert start <= end
                marker = " " * start + "^" * max(end - start, 1)
                rendered.append(f"{' ' * width} | {marker} {label}")
        for where, label in annotations[cid]:
            if where is None:
                rendered.append(f"{' ' * width} = {label} (no range)")
    return "\n".join(rendered)


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
    codes = {
        "a": "s = '😀'; value = 1",
        "b": "y = 2\nvalue = y",
        "c": "result = value",
    }
    analyses = analyze(codes)
    assert analyses["b"].refs == ()
    assert analyses["c"].refs == ("value",)
    assert render_diagnostics(codes, analyses) == snapshot("""\
-- a --
1 | s = '\\U0001f600'; value = 1
  |                   ^^^^^ error[multiple-definitions]: Multiple cells define value
  |                   ^^^^^ related[a]: Defines value
  |                   ^^^^^ related[b]: Defines value
-- b --
1 | y = 2
2 | value = y
  | ^^^^^ error[multiple-definitions]: Multiple cells define value
  | ^^^^^ related[a]: Defines value
  | ^^^^^ related[b]: Defines value
-- c --
1 | result = value\
""")


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize(
    ("codes", "dependencies"),
    [
        (
            {
                "a": "x = z",
                "b": "y = x",
                "c": "z = y",
                "downstream": "result = y",
            },
            [
                ("a", "Depends on c through z"),
                ("b", "Depends on a through x"),
                ("c", "Depends on b through y"),
            ],
        ),
        (
            {"provider": "x = 1", "a": "del x; y = 1", "b": "z = x + y"},
            [("a", "Depends on b through x"), ("b", "Depends on a through y")],
        ),
    ],
)
def test_cycles_report_the_dependency_chain_on_every_participant(
    codes, dependencies, reverse
):
    if reverse:
        codes = dict(reversed(list(codes.items())))
    analyses = analyze(codes)
    expected = protocol.Error(
        kind="cycle-dependencies",
        message="This cell is in a cycle",
        source="marimo",
        severity="error",
        range=None,
        name=None,
        traceback=None,
        related=tuple(
            protocol.Related(cell_id=cid, range=None, message=message)
            for cid, message in dependencies
        ),
    )
    participants = {cid for cid, _ in dependencies}
    assert {cid: cell.errors for cid, cell in analyses.items()} == {
        cid: (expected,) if cid in participants else () for cid in codes
    }


def test_cycles_and_multiple_definitions_are_reported_together() -> None:
    codes = {"a": "x, z = y, 0", "b": "y, z = x, 0"}
    assert render_diagnostics(codes, analyze(codes)) == snapshot("""\
-- a --
1 | x, z = y, 0
  |    ^ error[multiple-definitions]: Multiple cells define z
  |    ^ related[a]: Defines z
  |    ^ related[b]: Defines z
  = error[cycle-dependencies]: This cell is in a cycle (no range)
  = related[a]: Depends on b through y (no range)
  = related[b]: Depends on b through y (no range)
-- b --
1 | y, z = x, 0
  |    ^ error[multiple-definitions]: Multiple cells define z
  |    ^ related[a]: Defines z
  |    ^ related[b]: Defines z
  = error[cycle-dependencies]: This cell is in a cycle (no range)
  = related[a]: Depends on a through x (no range)
  = related[b]: Depends on a through x (no range)\
""")


def test_definition_ranges_cover_the_bound_name() -> None:
    codes = {
        "a": "def x():\n    pass",
        "b": "import numpy as x",
        "c": "for x in range(3):\n    def y():\n        x = 1",
        "d": "mo.sql('CREATE TABLE x (id INT)')",
    }
    assert render_diagnostics(codes, analyze(codes)) == snapshot("""\
-- a --
1 | def x():
  |     ^ error[multiple-definitions]: Multiple cells define x
  |     ^ related[a]: Defines x
  |     ^ related[b]: Defines x
  |     ^ related[c]: Defines x
  |     ^ related[d]: Defines x
2 |     pass
-- b --
1 | import numpy as x
  |                 ^ error[multiple-definitions]: Multiple cells define x
  |                 ^ related[a]: Defines x
  |                 ^ related[b]: Defines x
  |                 ^ related[c]: Defines x
  |                 ^ related[d]: Defines x
-- c --
1 | for x in range(3):
  |     ^ error[multiple-definitions]: Multiple cells define x
  |     ^ related[a]: Defines x
  |     ^ related[b]: Defines x
  |     ^ related[c]: Defines x
  |     ^ related[d]: Defines x
2 |     def y():
3 |         x = 1
-- d --
1 | mo.sql('CREATE TABLE x (id INT)')
  = error[multiple-definitions]: Multiple cells define x (no range)
  = related[a]: Defines x (no range)
  = related[b]: Defines x (no range)
  = related[c]: Defines x (no range)
  = related[d]: Defines x (no range)\
""")


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
        {"b": "y = x\nw = z"},
        {"b": "def (:", "c": "z = y"},
    ]
    for codes in steps:
        assert analyzer(document_snapshot(codes)) == analyze(codes), codes


def test_analyzer_retries_after_an_unexpected_compiler_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analyzer = CellAnalyzer()
    analyzer(document_snapshot({"a": "x = 1"}))
    codes = {"a": "y = 2", "b": "z = y"}

    def fail(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("compiler failed")

    with monkeypatch.context() as patch:
        patch.setattr("marimo._server.host.analysis.compile_cell", fail)
        with pytest.raises(RuntimeError, match="compiler failed"):
            analyzer(document_snapshot(codes))

    assert analyzer(document_snapshot(codes)) == analyze(codes)


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
    reported = asyncio.create_task(analyzer.analyze(document_snapshot(codes)))
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
        await analyzer.analyze(document_snapshot({"a": "x = 1"}))


def test_compilation_cache_uses_identity_and_code_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    compiler = Mock(wraps=compile_cell)
    monkeypatch.setattr("marimo._server.host.analysis.compile_cell", compiler)
    analyzer = CellAnalyzer()
    document = Document(
        protocol.NotebookId("n1"),
        [
            CellSource("a", "x = 1"),
            CellSource("b", "y = x"),
            CellSource("bad", "def (:"),
        ],
        {},
    )
    analyzer(document.snapshot())
    assert compiler.call_count == 3

    # Names, configuration, and order are visible without recompiling code.
    document.replace(
        [
            CellSource("b", "y = x", name="renamed"),
            CellSource("a", "x = 1"),
            CellSource("bad", "def (:"),
        ],
        {"width": "full"},
    )
    analyzer(document.snapshot())
    assert compiler.call_count == 3

    # An unchanged cell loses its reference when its provider changes.
    document.replace([CellSource("a", "z = 1"), CellSource("b", "y = x")], {})
    assert analyzer(document.snapshot())[protocol.CellId("b")].refs == ()
    assert compiler.call_count == 4

    document.replace([CellSource("b", "y = x")], {})
    analyzer(document.snapshot())
    document.replace([CellSource("a", "z = 1"), CellSource("c", "y = x")], {})
    analyzer(document.snapshot())
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
