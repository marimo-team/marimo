# Copyright 2026 Marimo. All rights reserved.
"""The host's analyzer reports each cell's names and syntax errors."""

from __future__ import annotations

from marimo._core import protocol
from marimo._server.host.analysis import Analyzer, analyze


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
    assert analyses["b"] == protocol.Analysis(defs=("x",), refs=(), errors=())
    assert analyses["c"].refs == ("x",)


def test_a_name_defined_twice_is_a_ref_for_neither_definer() -> None:
    analyses = analyze({"a": "x = 1", "b": "x = 2\ny = x", "c": "z = x"})
    assert analyses["b"].refs == ()
    assert analyses["c"].refs == ("x",)
    # Cross-cell errors come from the kernel at run time for now.
    assert all(analyses[cell_id].errors == () for cell_id in "abc")


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
    analyzer = Analyzer()
    steps = [
        {"a": "x = 1", "b": "y = x"},
        {"a": "x = 1", "b": "y = x", "c": "x = 2"},
        {"a": "x = 1", "b": "y = x", "c": "z = y"},
        {"a": "x = 1", "b": "y = x\nw = z", "c": "z = y"},
        {"b": "y = x\nw = z", "c": "z = y"},
        {"b": "def (:", "c": "z = y"},
    ]
    for codes in steps:
        assert analyzer(codes) == analyze(codes), codes
