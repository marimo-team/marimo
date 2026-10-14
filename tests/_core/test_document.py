# Copyright 2026 Marimo. All rights reserved.
"""The document's etags, change reporting, and publication order."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from marimo._core import protocol
from marimo._core.document import (
    CellSource,
    Document,
    app_config_etag,
    cell_etag,
    code_hash,
    document_etag,
    order_etag,
)
from marimo._core.host import Host
from marimo._core.notebook import Notebook
from marimo._core.stream import Event
from tests._core.conftest import make_notebook, names, project, record

if TYPE_CHECKING:
    from collections.abc import Mapping

NOTEBOOK = protocol.NotebookId("n1")
HIDDEN = protocol.CellConfig(
    column=None, disabled=False, hide_code=True, expand_output=False
)


def fixture_cells() -> list[CellSource]:
    """The cells in pair's `notebook-events.sse` fixture."""
    return [
        CellSource("c1", "import marimo as mo"),
        CellSource("c3", "x = 21"),
        CellSource("k7f2", "y = x * 2", config=HIDDEN),
    ]


def defs_only(codes: Mapping[str, str]) -> dict[str, protocol.Analysis]:
    """An analyzer that reports an error on every cell defining `x`."""
    out = {}
    definers = [cell_id for cell_id, code in codes.items() if "x =" in code]
    for cell_id, code in codes.items():
        errors = []
        if cell_id in definers and len(definers) > 1:
            errors.append(
                protocol.Error(
                    kind="multiple-definitions",
                    message="x is defined twice",
                    source="marimo",
                    severity="error",
                    range=None,
                    name=None,
                    traceback=None,
                    related=[],
                )
            )
        out[cell_id] = protocol.Analysis(
            defs=[code.split(" =")[0]] if " =" in code else [],
            refs=[],
            errors=errors,
        )
    return out


class TestEtags:
    def test_match_the_values_pinned_in_the_fixtures(self) -> None:
        document = Document(NOTEBOOK, fixture_cells(), {"width": "full"})

        c1, c3, k7f2 = document.cells
        assert (c3.code_hash, c3.etag) == (
            "0f71456db2ea83f4",
            "5cf78587dcf22d8d",
        )
        assert (k7f2.code_hash, k7f2.etag) == (
            "db2b9ee97e1ecf4c",
            "f199b5f48ae0aabb",
        )
        assert c1.etag == "48d6363150d6281c"
        assert document.document.order_etag == "b205774f616b44e3"
        assert document.document.app_config_etag == "283513048dfeb45b"
        assert document.document.etag == "0129d119bfb96bf9"
        assert document.document.saved_etag == "0129d119bfb96bf9"

    def test_are_derived_from_their_parts(self) -> None:
        hashed = code_hash("x = 21")
        assert cell_etag(hashed, "_", HIDDEN) != cell_etag(
            hashed,
            "_",
            protocol.CellConfig(
                column=None,
                disabled=False,
                hide_code=False,
                expand_output=False,
            ),
        )
        assert cell_etag(hashed, "named", HIDDEN) != cell_etag(
            hashed, "_", HIDDEN
        )
        assert order_etag(["a", "b"]) != order_etag(["b", "a"])
        assert app_config_etag({"b": 1, "a": 2}) == app_config_etag(
            {"a": 2, "b": 1}
        )
        assert document_etag(
            order_etag(["a"]), app_config_etag({}), [hashed]
        ) != (document_etag(order_etag(["a"]), app_config_etag({}), []))

    def test_normalizes_line_endings_before_hashing(self) -> None:
        document = Document(NOTEBOOK, [CellSource("a", "x = 1\r\ny = 2")], {})
        (cell,) = document.cells
        assert cell.code == "x = 1\ny = 2"
        assert cell.code_hash == code_hash("x = 1\ny = 2")


class TestReplace:
    def test_reports_new_changed_and_removed_cells(self) -> None:
        document = Document(NOTEBOOK, fixture_cells(), {"width": "full"})
        before = document.document

        changed = document.replace(
            [
                CellSource("c1", "import marimo as mo"),
                CellSource("new", "z = 3"),
                CellSource("k7f2", "y = x * 3", config=HIDDEN),
            ],
            {"width": "full"},
        )

        assert [cell.id for cell in changed.cells] == ["new", "k7f2"]
        assert changed.removed == ["c3"]
        assert changed.document is not None
        assert changed.document.order == ("c1", "new", "k7f2")
        assert changed.document.order_etag != before.order_etag
        assert changed.document.app_config_etag == before.app_config_etag
        assert changed.document.saved_etag == before.etag

    def test_a_change_that_changes_nothing_reports_nothing(self) -> None:
        document = Document(NOTEBOOK, fixture_cells(), {"width": "full"})

        assert not document.replace(fixture_cells(), {"width": "full"})

    def test_an_app_config_change_moves_only_its_etag(self) -> None:
        document = Document(NOTEBOOK, fixture_cells(), {})
        before = document.document

        changed = document.replace(fixture_cells(), {"width": "full"})

        assert changed.cells == []
        assert changed.removed == []
        assert changed.document is not None
        assert changed.document.order_etag == before.order_etag
        assert changed.document.app_config_etag != before.app_config_etag
        assert changed.document.etag != before.etag

    def test_rejects_duplicate_ids(self) -> None:
        with pytest.raises(ValueError, match="unique"):
            Document(
                NOTEBOOK, [CellSource("a", "1"), CellSource("a", "2")], {}
            )

    def test_marks_saved_state_separately(self) -> None:
        document = Document(NOTEBOOK, fixture_cells(), {}, saved=False)
        assert document.document.saved_etag is None

        document.replace([CellSource("c1", "1")], {})
        saved = document.mark_saved()

        assert saved is not None
        assert saved.saved_etag == saved.etag
        assert document.mark_saved() is None

        # A store may hold a revision other than the live one.
        other = Document(NOTEBOOK, fixture_cells(), {}, saved=False)
        behind = other.mark_saved(saved.etag)
        assert behind is not None
        assert behind.saved_etag == saved.etag != behind.etag


class TestAnalysis:
    def test_reruns_over_the_whole_document(self) -> None:
        document = Document(
            NOTEBOOK,
            [CellSource("a", "x = 1"), CellSource("b", "y = 2")],
            {},
            analyzer=defs_only,
        )
        a, _ = document.cells
        assert a.analysis == protocol.Analysis(defs=["x"], refs=[], errors=[])

        changed = document.replace(
            [CellSource("a", "x = 1"), CellSource("b", "x = 2")], {}
        )

        # Both cells re-emit: b because its code changed, a because its
        # analysis gained an error while its etag stayed put.
        assert [cell.id for cell in changed.cells] == ["a", "b"]
        new_a = changed.cells[0]
        assert new_a.etag == a.etag
        assert new_a.analysis is not None
        assert [e.kind for e in new_a.analysis.errors] == [
            "multiple-definitions"
        ]

    def test_is_null_without_an_analyzer(self) -> None:
        document = Document(NOTEBOOK, fixture_cells(), {})
        assert all(cell.analysis is None for cell in document.cells)


class TestNotebook:
    async def test_initialization_publishes_cells_then_the_document(
        self, host: Host, log: list[Event]
    ) -> None:
        host.update_project(project())
        host.add_notebook(
            record(),
            lambda record, sink: make_notebook(
                record,
                sink,
                document=Document(
                    NOTEBOOK, fixture_cells(), {"width": "full"}
                ),
            ),
        )
        log.clear()
        await host.notebook(NOTEBOOK)

        assert names(log) == ["cell", "cell", "cell", "document"]
        snapshot = host.events(notebook_id="n1")
        assert names(snapshot) == [
            "notebook",
            "cell",
            "cell",
            "cell",
            "document",
            "ready",
        ]
        assert names(host.events(notebook_id="n1", types={"document"})) == [
            "document",
            "ready",
        ]
        # The catalog does not carry the document.
        assert "cell" not in names(host.events())

    def test_replace_publishes_what_changed(
        self, notebook: Notebook, log: list[Event]
    ) -> None:
        notebook.replace(fixture_cells(), {})
        log.clear()

        notebook.replace(
            [
                CellSource("c1", "import marimo as mo"),
                CellSource("c3", "x = 22"),
            ],
            {},
            request_id="edit-1",
        )

        assert names(log) == ["cell", "cell.removed", "document"]
        assert all(e.data.request_id == "edit-1" for e in log)  # type: ignore[union-attr]
        assert log[1].data.id == "k7f2"  # type: ignore[union-attr]
