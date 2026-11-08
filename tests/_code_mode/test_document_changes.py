# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import replace

import pytest

from marimo._ast.cell import CellConfig
from marimo._code_mode._plan import (
    _AddOp,
    _build_plan,
    _DeleteOp,
    _document_changes,
    _MoveOp,
    _Op,
    _UpdateOp,
)
from marimo._core import protocol
from marimo._core.document import Document, DocumentCell, Stale
from marimo._types.ids import CellId_t


def changes(document: Document, ops: list[_Op]) -> list[protocol.Change]:
    return _document_changes(
        document, _build_plan([CellId_t(cell.id) for cell in document], ops)
    )


A = DocumentCell(
    protocol.CellId("a"),
    "x = 1",
    "named",
    protocol.CellConfig(
        column=2, disabled=True, hide_code=True, expand_output=True
    ),
)
B = DocumentCell(protocol.CellId("b"), "y = x + 1")


def test_source_edit_preserves_name_config_and_app_config() -> None:
    document = Document([A, B], {"width": "full"})
    batch = changes(document, [_UpdateOp(CellId_t("a"), code="x = 2")])
    assert len(batch) == 1
    result = document.apply(batch)
    assert not isinstance(result, Stale)
    assert result[0] == Document(
        [replace(A, code="x = 2"), B], {"width": "full"}
    )


def test_chained_creates_updates_deletes_and_moves() -> None:
    document = Document([A, B], {})
    batch = changes(
        document,
        [
            _AddOp(
                CellId_t("c"),
                "z = 1",
                CellConfig(hide_code=True),
                before=CellId_t("a"),
            ),
            _AddOp(CellId_t("d"), "w = 2", CellConfig(), after=CellId_t("c")),
            _UpdateOp(CellId_t("c"), code="z = 3", name="created"),
            _MoveOp(CellId_t("a"), before=CellId_t("d")),
            _DeleteOp(CellId_t("b")),
        ],
    )
    result = document.apply(batch)
    assert not isinstance(result, Stale)
    assert list(result[0]) == [
        DocumentCell(
            protocol.CellId("c"),
            "z = 3",
            "created",
            protocol.CellConfig(
                column=None,
                disabled=False,
                hide_code=True,
                expand_output=False,
            ),
        ),
        A,
        DocumentCell(protocol.CellId("d"), "w = 2", ""),
    ]


@pytest.mark.parametrize("delete", [False, True])
@pytest.mark.parametrize("field", ["code", "name", "config"])
def test_changed_cell_rejects_whole_batch(field: str, delete: bool) -> None:
    document = Document([A, B], {})
    batch = changes(
        document,
        [
            _UpdateOp(CellId_t("b"), code="y = 2"),
            _DeleteOp(CellId_t("a"))
            if delete
            else _UpdateOp(CellId_t("a"), code="x = 3"),
        ],
    )
    edited = (
        replace(A, config=B.config)
        if field == "config"
        else replace(A, code="x = 4")
        if field == "code"
        else replace(A, name="renamed")
    )
    current = Document([edited, B], {})
    assert isinstance(current.apply(batch), Stale)
    assert list(current) == [edited, B]


def test_order_conflict_rejects_source_changes_too() -> None:
    document = Document([A, B], {})
    batch = changes(
        document,
        [
            _UpdateOp(CellId_t("a"), code="x = 2"),
            _MoveOp(CellId_t("b"), before=CellId_t("a")),
        ],
    )
    added = DocumentCell(protocol.CellId("c"), "z = 3")
    current = Document([A, B, added], {})
    assert isinstance(current.apply(batch), Stale)
    assert list(current) == [A, B, added]


def test_source_edit_allows_unrelated_content_and_order_changes() -> None:
    document = Document([A, B], {})
    batch = changes(document, [_UpdateOp(CellId_t("a"), code="x = 2")])
    other = replace(B, code="y = 7")
    current = Document([other, A], {})
    result = current.apply(batch)
    assert not isinstance(result, Stale)
    assert list(result[0]) == [other, replace(A, code="x = 2")]


def test_create_after_last_cell_conflicts_with_a_concurrent_append() -> None:
    document = Document([A, B], {})
    batch = changes(
        document,
        [_AddOp(CellId_t("c"), "z = 3", CellConfig(), after=CellId_t("b"))],
    )
    appended = DocumentCell(protocol.CellId("d"), "w = 4")
    current = Document([A, B, appended], {})
    assert isinstance(current.apply(batch), Stale)
    assert list(current) == [A, B, appended]


def test_setup_conversion_replaces_the_cell_identity() -> None:
    document = Document([A, B], {})
    batch = changes(
        document,
        [
            _UpdateOp(
                CellId_t("a"),
                code="import math",
                new_cell_id=CellId_t("setup"),
            )
        ],
    )
    result = document.apply(batch)
    assert not isinstance(result, Stale)
    assert list(result[0]) == [
        DocumentCell(
            protocol.CellId("setup"),
            "import math",
            "",
            protocol.CellConfig(
                column=None,
                disabled=False,
                hide_code=True,
                expand_output=False,
            ),
        ),
        B,
    ]


def test_normalized_unchanged_source_produces_no_changes() -> None:
    document = Document([replace(A, code="x = 1\n"), B], {})
    assert (
        changes(document, [_UpdateOp(CellId_t("a"), code="x = 1\r\n")]) == []
    )
