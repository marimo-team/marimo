# Copyright 2026 Marimo. All rights reserved.
"""The document's etags, change reporting, and publication order."""

from __future__ import annotations

import asyncio

import pytest
from msgspec import UNSET
from msgspec.structs import replace

from marimo._core import protocol
from marimo._core.document import (
    Document,
    DocumentCell,
    Stale,
    app_config_etag,
    cell_etag,
    code_hash,
    document_etag,
    order_etag,
)
from marimo._core.errors import EditConflict, Invalid
from marimo._core.executions import Executions
from marimo._core.host import Host
from marimo._core.notebook import Notebook
from marimo._core.stream import RoutedEvent, Stream
from tests._core.conftest import (
    ScriptedAnalyzer,
    ScriptedBackend,
    add_notebook,
    make_notebook,
    names,
    project,
    record,
    request_ids,
)

NOTEBOOK = protocol.NotebookId("n1")
HIDDEN = protocol.CellConfig(
    column=None, disabled=False, hide_code=True, expand_output=False
)


def fixture_cells() -> list[DocumentCell]:
    """The cells in pair's `notebook-events.sse` fixture."""
    return [
        DocumentCell(protocol.CellId("c1"), "import marimo as mo"),
        DocumentCell(protocol.CellId("c3"), "x = 21"),
        DocumentCell(protocol.CellId("k7f2"), "y = x * 2", config=HIDDEN),
    ]


def cell(cell_id: str, code: str, **kwargs: object) -> DocumentCell:
    return DocumentCell(protocol.CellId(cell_id), code, **kwargs)  # type: ignore[arg-type]


def ids(document: Document) -> list[str]:
    return [c.id for c in document]


def put(
    cell_id: str,
    code: str,
    base_etag: str | None,
    *,
    after: str | None = None,
    before: str | None = None,
) -> protocol.PutCell:
    return protocol.PutCell(
        base_etag=base_etag,
        cell=protocol.CellInput(id=protocol.CellId(cell_id), code=code),
        after=UNSET if after is None else protocol.CellId(after),
        before=UNSET if before is None else protocol.CellId(before),
    )


def delete(cell_id: str, base_etag: str) -> protocol.DeleteCell:
    return protocol.DeleteCell(
        id=protocol.CellId(cell_id), base_etag=base_etag
    )


def set_order(base_etag: str, *cell_ids: str) -> protocol.SetOrder:
    return protocol.SetOrder(
        base_etag=base_etag, order=tuple(protocol.CellId(c) for c in cell_ids)
    )


def hosted(document: Document) -> Notebook:
    """A notebook around `document` with the revision saved."""
    return Notebook(
        NOTEBOOK,
        document,
        Executions(),
        ScriptedBackend(),
        Stream(history=0),
        saved_etag=document.etag,
    )


def records(
    notebook: Notebook,
) -> tuple[protocol.Document, list[protocol.Cell]]:
    """The document and cell records the notebook publishes."""
    events = notebook._snapshot()
    (document,) = [
        e.event.data.document
        for e in events
        if isinstance(e.event, protocol.DocumentEvent)
    ]
    cells = [
        e.event.data.cell
        for e in events
        if isinstance(e.event, protocol.CellEvent)
    ]
    return document, cells


class TestCells:
    def test_normalizes_line_endings_and_compares_by_content(self) -> None:
        c = cell("a", "x = 1\r\ny = 2", name="named", config=HIDDEN)
        assert c.code == "x = 1\ny = 2"
        assert c == cell("a", "x = 1\ny = 2", name="named", config=HIDDEN)
        assert c != cell("a", "x = 1\ny = 2", name="other", config=HIDDEN)


class TestEtags:
    def test_reordering_cell_ids_with_newlines_changes_the_revision(
        self,
    ) -> None:
        cells = [cell("a", "x = 1"), cell("a\na", "x = 1")]
        before = Document(cells, {})

        document, _ = before.replace(list(reversed(cells)), {})

        assert ids(document) == ["a\na", "a"]
        assert document.order_etag != before.order_etag
        assert document.etag != before.etag

    def test_match_the_values_pinned_in_the_fixtures(self) -> None:
        document = Document(fixture_cells(), {"width": "full"})

        c1, c3, k7f2 = document
        assert (c3.code_hash, c3.etag) == (
            "0f71456db2ea83f4",
            "5cf78587dcf22d8d",
        )
        assert (k7f2.code_hash, k7f2.etag) == (
            "db2b9ee97e1ecf4c",
            "f199b5f48ae0aabb",
        )
        assert c1.etag == "48d6363150d6281c"
        assert document.order_etag == "b9c412c2d7d63161"
        assert document.app_config_etag == "283513048dfeb45b"
        assert document.etag == "e59d9c2af02f5814"
        assert hosted(document).saved_etag == document.etag

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


class TestValue:
    def test_config_is_detached_from_inputs_and_published_records(
        self,
    ) -> None:
        config = {"auto_download": ["html"]}
        document = Document(fixture_cells(), config)
        notebook = hosted(document)
        before, _ = records(notebook)

        config["auto_download"].append("markdown")
        published, _ = records(notebook)
        published.app_config["auto_download"].clear()

        assert document.app_config == {"auto_download": ["html"]}
        assert records(notebook)[0] == before

    def test_documents_with_the_same_content_are_equal(self) -> None:
        assert Document(fixture_cells(), {"a": 1}) == Document(
            fixture_cells(), {"a": 1}
        )
        assert Document(fixture_cells(), {}) != Document(
            fixture_cells()[:2], {}
        )

    def test_changing_produces_a_new_document_and_keeps_the_old(self) -> None:
        before = Document(fixture_cells(), {"nested": {"items": [1]}})

        after, _ = before.replace([cell("c1", "42", name="renamed")], {})

        assert ids(before) == ["c1", "c3", "k7f2"]
        assert before.app_config == {"nested": {"items": [1]}}
        assert ids(after) == ["c1"]
        assert after.app_config == {}

    def test_rejects_duplicate_ids(self) -> None:
        with pytest.raises(ValueError, match="unique"):
            Document([cell("a", "1"), cell("a", "2")], {})


class TestReplace:
    def test_reports_new_changed_and_removed_cells(self) -> None:
        before = Document(fixture_cells(), {"width": "full"})

        document, changed = before.replace(
            [
                cell("c1", "import marimo as mo"),
                cell("new", "z = 3"),
                cell("k7f2", "y = x * 3", config=HIDDEN),
            ],
            {"width": "full"},
        )

        assert [c.id for c in changed.cells] == ["new", "k7f2"]
        assert changed.removed == ["c3"]
        assert changed.etag == document.etag != before.etag
        assert ids(document) == ["c1", "new", "k7f2"]
        assert document.order_etag != before.order_etag
        assert document.app_config_etag == before.app_config_etag

    def test_a_change_that_changes_nothing_reports_nothing(self) -> None:
        before = Document(fixture_cells(), {"width": "full"})

        document, changed = before.replace(fixture_cells(), {"width": "full"})

        assert not changed
        assert document == before

    def test_an_app_config_change_moves_only_its_etag(self) -> None:
        before = Document(fixture_cells(), {})

        document, changed = before.replace(fixture_cells(), {"width": "full"})

        assert changed.cells == []
        assert changed.removed == []
        assert changed.etag == document.etag
        assert document.order_etag == before.order_etag
        assert document.app_config_etag != before.app_config_etag
        assert document.etag != before.etag


class TestApply:
    def test_creates_replaces_deletes_and_reorders_as_one_unit(self) -> None:
        before = Document(fixture_cells(), {"width": "full"})
        c3 = before.cell("c3")
        k7f2 = before.cell("k7f2")
        assert c3 is not None
        assert k7f2 is not None

        result = before.apply(
            [
                put("c2", "print('hi')", None, after="c1"),
                put("c3", "x = 22", c3.etag),
                delete("k7f2", k7f2.etag),
                set_order(before.order_etag, "c3", "c2", "c1"),
            ]
        )

        assert not isinstance(result, Stale)
        document, applied = result
        assert ids(document) == ["c3", "c2", "c1"]
        assert [c.id for c in applied.changed.cells] == ["c3", "c2"]
        assert applied.changed.removed == ["k7f2"]
        assert applied.changed.etag == document.etag
        assert document.app_config == {"width": "full"}
        assert set(applied.cells) == {"c2", "c3", "k7f2"}
        assert applied.cells["k7f2"] is None
        new_c3 = document.cell("c3")
        assert new_c3 is not None
        assert applied.cells["c3"] == new_c3
        assert new_c3.etag != c3.etag

    def test_a_stale_etag_applies_nothing_and_names_the_change(self) -> None:
        document = Document(fixture_cells(), {})

        result = document.apply(
            [
                put("new", "z = 1", None),
                put("c3", "x = 22", "0000000000000000"),
            ]
        )

        assert result == Stale(change=1, cell_id="c3")

    def test_creating_an_existing_cell_or_replacing_a_missing_one_conflicts(
        self,
    ) -> None:
        document = Document(fixture_cells(), {})
        c3 = document.cell("c3")
        assert c3 is not None

        assert document.apply([put("c3", "x = 1", None)]) == Stale(0, "c3")
        assert document.apply([put("nope", "x = 1", "*")]) == Stale(0, "nope")
        # The cell existed when the client read, even if the same batch
        # deletes it first.
        assert document.apply(
            [delete("c3", c3.etag), put("c3", "x = 1", None)]
        ) == Stale(1, "c3")

    def test_star_skips_the_check(self) -> None:
        result = Document(fixture_cells(), {}).apply(
            [put("c3", "x = 23", "*"), set_order("*", "k7f2", "c3", "c1")]
        )

        assert not isinstance(result, Stale)
        assert ids(result[0]) == ["k7f2", "c3", "c1"]

    def test_placement_has_no_precondition(self) -> None:
        document = Document(fixture_cells(), {})
        for change in (
            put("a", "1", None, before="c1"),
            put("b", "2", None, after="c1"),
            put("c", "3", None),
        ):
            result = document.apply([change])
            assert not isinstance(result, Stale)
            document = result[0]

        assert ids(document) == ["a", "c1", "b", "c3", "k7f2", "c"]

    def test_malformed_changes_are_invalid(self) -> None:
        document = Document(fixture_cells(), {})

        with pytest.raises(Invalid):
            document.apply([set_order("*", "c1", "c3")])
        with pytest.raises(Invalid):
            document.apply([set_order("*", "c1", "c3", "c3")])
        with pytest.raises(Invalid):
            document.apply([put("a", "1", None, after="nope")])
        with pytest.raises(Invalid):
            document.apply([put("a", "1", None, after="c1", before="c3")])

    def test_an_edit_that_changes_nothing_reports_nothing(self) -> None:
        before = Document(fixture_cells(), {})
        c3 = before.cell("c3")
        assert c3 is not None

        result = before.apply([put("c3", "x = 21", c3.etag)])

        assert not isinstance(result, Stale)
        document, applied = result
        assert document == before
        assert not applied.changed
        assert applied.cells["c3"] == c3


class TestFromRecords:
    def test_restores_the_content(self) -> None:
        notebook = hosted(Document(fixture_cells(), {"width": "full"}))
        # The saved revision precedes the current one. The content is
        # what is restored, and the notebook carries the rest.
        notebook.replace([cell("c1", "import marimo")], {"width": "full"})
        document, cells = records(notebook)

        restored = Document.restore(document, cells)

        assert restored == notebook.document
        assert document.saved_etag != restored.etag

    @pytest.mark.parametrize(
        "invalid", ["order", "notebook-id", "cell-etag", "document-etag"]
    )
    def test_rejects_inconsistent_records(self, invalid: str) -> None:
        document, cells = records(hosted(Document(fixture_cells(), {})))
        if invalid == "order":
            document = replace(document, order=())
        elif invalid == "notebook-id":
            cells[0] = replace(
                cells[0], notebook_id=protocol.NotebookId("other")
            )
        elif invalid == "cell-etag":
            cells[0] = replace(cells[0], code="different source")
        else:
            document = replace(document, app_config={"width": "full"})
        with pytest.raises(ValueError):
            Document.restore(document, cells)


class TestNotebookRecords:
    def test_stamps_the_notebook_id_and_carries_the_saved_state(
        self,
    ) -> None:
        document = Document(fixture_cells(), {"width": "full"})
        notebook = Notebook(
            NOTEBOOK,
            document,
            Executions(),
            ScriptedBackend(),
            Stream(history=0),
        )
        record, cells = records(notebook)
        assert record.notebook_id == NOTEBOOK
        assert record.saved_etag is None
        assert record.etag == document.etag
        assert record.order == ("c1", "c3", "k7f2")
        assert record.app_config == {"width": "full"}
        assert [c.notebook_id for c in cells] == [NOTEBOOK] * 3
        assert [(c.id, c.etag) for c in cells] == [
            (c.id, c.etag) for c in document
        ]

    def test_marks_saved_state_separately(self) -> None:
        notebook = Notebook(
            NOTEBOOK,
            Document(fixture_cells(), {}),
            Executions(),
            ScriptedBackend(),
            Stream(history=0),
        )
        assert notebook.saved_etag is None

        notebook.replace([cell("c1", "1")], {})
        saved = notebook.mark_saved(notebook.document.etag)

        assert saved.saved_etag == saved.etag
        assert notebook.saved_etag == saved.etag

        # A store may hold a revision other than the live one.
        other = Notebook(
            NOTEBOOK,
            Document(fixture_cells(), {}),
            Executions(),
            ScriptedBackend(),
            Stream(history=0),
        )
        behind = other.mark_saved(saved.etag)
        assert behind.saved_etag == saved.etag != behind.etag

    def test_versions_order_changes_and_stamp_the_cells_they_touch(
        self,
    ) -> None:
        notebook = hosted(Document(fixture_cells(), {}))
        record, cells = records(notebook)
        assert record.version == 1
        assert [c.version for c in cells] == [1, 1, 1]
        (_, c3, k7f2) = cells

        response = notebook.edit(
            [put("c3", "x = 22", c3.etag), delete("k7f2", k7f2.etag)],
            request_id="e",
        )

        # Changed cells take the new document version; others keep theirs.
        assert response.document.version == 2
        assert response.cells["k7f2"] is None
        assert response.cells["c3"].version == 2  # type: ignore[union-attr]
        record, cells = records(notebook)
        assert record.version == 2
        assert [(c.id, c.version) for c in cells] == [("c1", 1), ("c3", 2)]

        # Saving moves `saved_etag` only; a no-op edit changes nothing.
        assert notebook.mark_saved(record.etag).version == 2
        same = notebook.edit(
            [put("c1", "import marimo as mo", cells[0].etag)], request_id="n"
        )
        assert same.document.version == 2
        assert same.cells["c1"] == protocol.CellVersion(
            etag=cells[0].etag, code_hash=cells[0].code_hash, version=1
        )

        # A reload changes content like any edit.
        notebook.replace([cell("c1", "1")], {})
        record, cells = records(notebook)
        assert record.version == 3
        assert [(c.id, c.version) for c in cells] == [("c1", 3)]

    def test_a_stale_edit_names_the_cell_and_document_as_they_are(
        self,
    ) -> None:
        document = Document(fixture_cells(), {})
        notebook = hosted(document)
        before, cells = records(notebook)
        (_, c3, _) = cells

        with pytest.raises(EditConflict) as raised:
            notebook.edit(
                [put("c3", "x = 22", "0000000000000000")], request_id="e"
            )

        assert raised.value.change == 0
        assert raised.value.cell == c3
        assert raised.value.document == before
        assert notebook.document is document


class TestNotebook:
    @pytest.mark.parametrize("method", ["edit", "replace"])
    @pytest.mark.parametrize("remove", [False, True])
    def test_response_preserves_revision_before_subscriber_changes(
        self,
        host: Host,
        notebook: Notebook,
        log: list[RoutedEvent],
        method: str,
        remove: bool,
    ) -> None:
        notebook.replace([cell("c1", "0")], {})
        log.clear()

        def change_again(event: RoutedEvent) -> None:
            if (
                isinstance(event.event, protocol.CellEvent)
                and event.event.data.request_id == "first"
            ):
                change = delete("c1", "*") if remove else put("c1", "2", "*")
                notebook.edit([change], request_id="second")

        host.subscribe(change_again, notebook_id=notebook.id)
        if method == "edit":
            response = notebook.edit([put("c1", "1", "*")], request_id="first")
        else:
            response = notebook.replace(
                [cell("c1", "1")], {}, request_id="first"
            )

        first_cell, first_document = log[:2]
        assert isinstance(first_cell.event, protocol.CellEvent)
        assert isinstance(first_document.event, protocol.DocumentEvent)
        published = first_cell.event.data.cell
        assert response == protocol.EditResponse(
            document=first_document.event.data.document,
            cells={
                "c1": protocol.CellVersion(
                    etag=published.etag,
                    code_hash=published.code_hash,
                    version=published.version,
                )
            },
        )
        assert notebook.document.cell("c1") == (
            None if remove else cell("c1", "2")
        )

    async def test_initialization_publishes_cells_then_the_document(
        self, host: Host, log: list[RoutedEvent]
    ) -> None:
        host.update_project(project())
        host.add_notebook(
            record(),
            lambda record, sink: make_notebook(
                record,
                sink,
                document=Document(fixture_cells(), {"width": "full"}),
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
        self, notebook: Notebook, log: list[RoutedEvent]
    ) -> None:
        notebook.replace(fixture_cells(), {})
        log.clear()

        notebook.replace(
            [
                cell("c1", "import marimo as mo"),
                cell("c3", "x = 22"),
            ],
            {},
            request_id="edit-1",
        )

        assert names(log) == ["cell", "cell.removed", "document"]
        assert all(e.event.data.request_id == "edit-1" for e in log)  # type: ignore[union-attr]
        assert log[1].event.data.id == "k7f2"  # type: ignore[union-attr]

    def test_replace_can_record_the_saved_revision(
        self, notebook: Notebook, log: list[RoutedEvent]
    ) -> None:
        notebook.replace(fixture_cells(), {})
        log.clear()

        response = notebook.replace([cell("c1", "x = 22")], {}, saved=True)

        assert response.document.saved_etag == response.document.etag
        assert set(response.cells) == {"c1", "c3", "k7f2"}
        assert response.cells["c3"] is None
        assert names(log) == [
            "cell",
            "cell.removed",
            "cell.removed",
            "document",
        ]
        assert log[-1].event.data.document == response.document  # type: ignore[union-attr]

    def test_mark_saved_records_the_revision_that_was_written(
        self, notebook: Notebook, log: list[RoutedEvent]
    ) -> None:
        notebook.replace(fixture_cells(), {})
        written = notebook.document.etag
        notebook.replace([cell("c1", "x = 22")], {})
        log.clear()

        document = notebook.mark_saved(written, request_id="save-1")

        assert document.saved_etag == written
        assert document.etag != written
        assert names(log) == ["document"]
        assert request_ids(log) == ["save-1"]
        assert log[0].event.data.document == document  # type: ignore[union-attr]
        # Marking the same revision again publishes nothing.
        assert notebook.mark_saved(written) == document
        assert names(log) == ["document"]

    def test_edit_publishes_as_one_unit_with_the_request_key(
        self, notebook: Notebook, log: list[RoutedEvent]
    ) -> None:
        notebook.replace(fixture_cells(), {})
        log.clear()
        k7f2 = notebook.document.cell("k7f2")
        assert k7f2 is not None

        response = notebook.edit(
            [
                put("c2", "print('hi')", None, after="c1"),
                delete("k7f2", k7f2.etag),
            ],
            request_id="edit-1",
        )

        assert names(log) == ["cell", "cell.removed", "document"]
        assert request_ids(log) == ["edit-1"] * 3
        assert response.document == log[-1].event.data.document  # type: ignore[union-attr]
        assert set(response.cells) == {"c2", "k7f2"}


def cell_analyses(
    document: Document,
) -> dict[protocol.CellId, protocol.CellAnalysis]:
    """A placeholder analysis of every cell in the document."""
    return {
        cell.id: protocol.CellAnalysis(defs=(), refs=(), errors=())
        for cell in document
    }


class TestAnalysis:
    async def test_the_initial_revision_is_analyzed_and_published_after_the_document(
        self, host: Host, log: list[RoutedEvent]
    ) -> None:
        host.update_project(project())
        analyzer = ScriptedAnalyzer()
        document = Document(fixture_cells(), {"width": "full"})
        notebook = await add_notebook(
            host,
            record(),
            ScriptedBackend(),
            document=document,
            analyzer=analyzer,
        )
        analyzed, result = await analyzer.next_request()
        assert analyzed is document
        assert notebook.analysis is None

        log.clear()
        result.set_result(cell_analyses(document))
        await asyncio.sleep(0)

        assert names(log) == ["analysis"]
        assert request_ids(log) == [UNSET]
        assert notebook.analysis == protocol.Analysis(
            notebook_id=NOTEBOOK,
            document_etag=document.etag,
            cells=cell_analyses(document),
        )
        assert names(host.events(notebook_id="n1")) == [
            "notebook",
            "cell",
            "cell",
            "cell",
            "document",
            "analysis",
            "ready",
        ]

    async def test_edits_during_analysis_are_analyzed_once_afterwards(
        self, host: Host, log: list[RoutedEvent]
    ) -> None:
        host.update_project(project())
        analyzer = ScriptedAnalyzer()
        document = Document(fixture_cells(), {})
        notebook = await add_notebook(
            host,
            record(),
            ScriptedBackend(),
            document=document,
            analyzer=analyzer,
        )
        first, result = await analyzer.next_request()
        first_analysis = cell_analyses(document)
        notebook.replace([cell("c1", "1")], {}, request_id="edit-1")
        notebook.replace(
            [cell("c1", "2", name="named", config=HIDDEN)],
            {"width": "full"},
            request_id="edit-2",
        )
        assert len(analyzer.requests) == 1
        # The analyzer holds the revision it was given.
        assert first is document
        assert first.etag != notebook.document.etag
        assert next(iter(first)).code == "import marimo as mo"

        log.clear()
        result.set_result(first_analysis)
        latest, result = await analyzer.next_request()
        assert names(log) == []
        assert latest is notebook.document

        result.set_result(cell_analyses(latest))
        await asyncio.sleep(0)
        assert names(log) == ["analysis"]
        assert request_ids(log) == ["edit-2"]
        assert notebook.analysis is not None
        assert notebook.analysis.document_etag == latest.etag

    async def test_an_edit_is_analyzed_under_its_request_key(
        self, host: Host, log: list[RoutedEvent]
    ) -> None:
        host.update_project(project())
        analyzer = ScriptedAnalyzer()
        document = Document(fixture_cells(), {})
        notebook = await add_notebook(
            host,
            record(),
            ScriptedBackend(),
            document=document,
            analyzer=analyzer,
        )
        _, result = await analyzer.next_request()
        result.set_result(cell_analyses(document))
        await asyncio.sleep(0)

        log.clear()
        notebook.edit([put("c9", "z = 1", None)], request_id="edit-1")
        analyzed, result = await analyzer.next_request()
        assert analyzed is notebook.document
        assert ids(analyzed) == ["c1", "c3", "k7f2", "c9"]

        result.set_result(cell_analyses(analyzed))
        await asyncio.sleep(0)
        assert names(log) == ["cell", "document", "analysis"]
        assert request_ids(log) == ["edit-1"] * 3

    async def test_the_previous_analysis_stays_until_the_next_arrives(
        self, host: Host
    ) -> None:
        host.update_project(project())
        analyzer = ScriptedAnalyzer()
        document = Document(fixture_cells(), {})
        notebook = await add_notebook(
            host,
            record(),
            ScriptedBackend(),
            document=document,
            analyzer=analyzer,
        )
        first, result = await analyzer.next_request()
        result.set_result(cell_analyses(document))
        await asyncio.sleep(0)
        notebook.replace([cell("c1", "1")], {})
        _, result = await analyzer.next_request()

        assert notebook.analysis is not None
        assert (
            notebook.analysis.document_etag
            == first.etag
            != notebook.document.etag
        )
        assert names(host.events(notebook_id="n1")) == [
            "notebook",
            "cell",
            "document",
            "analysis",
            "ready",
        ]
        result.set_result(cell_analyses(notebook.document))
        await asyncio.sleep(0)

    @pytest.mark.parametrize("edit_while_running", [False, True])
    async def test_a_failed_analysis_leaves_the_notebook_ready_for_the_next(
        self, host: Host, log: list[RoutedEvent], edit_while_running: bool
    ) -> None:
        host.update_project(project())
        analyzer = ScriptedAnalyzer()
        document = Document(fixture_cells(), {})
        notebook = await add_notebook(
            host,
            record(),
            ScriptedBackend(),
            document=document,
            analyzer=analyzer,
        )
        _, result = await analyzer.next_request()
        if edit_while_running:
            notebook.replace([cell("c1", "1")], {})
        log.clear()
        result.set_exception(RuntimeError("compiler failed"))
        await asyncio.sleep(0)
        assert names(log) == []
        assert notebook.analysis is None
        if not edit_while_running:
            notebook.replace([cell("c1", "1")], {})
        analyzed, result = await analyzer.next_request()
        assert analyzed is notebook.document
        log.clear()
        result.set_result(cell_analyses(analyzed))
        await asyncio.sleep(0)
        assert names(log) == ["analysis"]

    async def test_removal_discards_a_result_even_if_cancellation_is_suppressed(
        self, host: Host, log: list[RoutedEvent]
    ) -> None:
        started, cancelled = asyncio.Event(), asyncio.Event()
        result = asyncio.get_running_loop().create_future()
        document = Document(fixture_cells(), {})

        class Analyzer:
            async def analyze(self, _document):
                started.set()
                try:
                    return await asyncio.shield(result)
                except asyncio.CancelledError:
                    cancelled.set()
                    return await result

        host.update_project(project())
        host.add_notebook(
            record(),
            lambda _, sink: Notebook(
                NOTEBOOK,
                document,
                Executions(),
                ScriptedBackend(),
                sink,
                saved_etag=document.etag,
                analyzer=Analyzer(),
            ),
        )
        await host.notebook("n1")
        await asyncio.wait_for(started.wait(), timeout=5)
        host.remove_notebook("n1")
        await asyncio.wait_for(cancelled.wait(), timeout=5)
        log.clear()
        result.set_result(cell_analyses(document))
        await asyncio.sleep(0)
        assert names(log) == []
        assert "n1" not in host.notebooks
