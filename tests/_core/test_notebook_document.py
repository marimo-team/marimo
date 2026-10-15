# Copyright 2026 Marimo. All rights reserved.
"""The document's etags, change reporting, and publication order."""

from __future__ import annotations

import asyncio

import pytest
from msgspec import UNSET
from msgspec.structs import replace

from marimo._core import protocol
from marimo._core.document import (
    CellSource,
    Document,
    app_config_etag,
    cell_etag,
    code_hash,
    document_etag,
    order_etag,
    revision,
)
from marimo._core.errors import EditConflict, Invalid
from marimo._core.executions import Executions
from marimo._core.host import Host
from marimo._core.notebook import Notebook
from marimo._core.stream import Event
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


def fixture_cells() -> list[CellSource]:
    """The cells in pair's `notebook-events.sse` fixture."""
    return [
        CellSource("c1", "import marimo as mo"),
        CellSource("c3", "x = 21"),
        CellSource("k7f2", "y = x * 2", config=HIDDEN),
    ]


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


class TestEtags:
    def test_reordering_cell_ids_with_newlines_changes_the_revision(
        self,
    ) -> None:
        cells = [CellSource("a", "x = 1"), CellSource("a\na", "x = 1")]
        document = Document(NOTEBOOK, cells, {})
        before = document._record

        document.replace(list(reversed(cells)), {})

        assert [cell.id for cell in document] == ["a\na", "a"]
        assert document._record.order_etag != before.order_etag
        assert document._record.etag != before.etag
        assert document._record.saved_etag == before.etag

    def test_match_the_values_pinned_in_the_fixtures(self) -> None:
        document = Document(NOTEBOOK, fixture_cells(), {"width": "full"})

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
        assert document._record.order_etag == "b9c412c2d7d63161"
        assert document._record.app_config_etag == "283513048dfeb45b"
        assert document._record.etag == "e59d9c2af02f5814"
        assert document._record.saved_etag == "e59d9c2af02f5814"

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

    def test_revision_matches_the_document_built_from_the_same_sources(
        self,
    ) -> None:
        cells = [*fixture_cells(), CellSource("crlf", "x = 1\r\ny = 2")]
        app_config = {"width": "full"}
        document = Document(NOTEBOOK, cells, app_config)
        assert revision(cells, app_config) == document._record.etag

    def test_normalizes_line_endings_before_hashing(self) -> None:
        document = Document(NOTEBOOK, [CellSource("a", "x = 1\r\ny = 2")], {})
        (cell,) = document
        assert cell.code == "x = 1\ny = 2"
        assert cell.code_hash == code_hash("x = 1\ny = 2")


class TestReplace:
    def test_reports_new_changed_and_removed_cells(self) -> None:
        document = Document(NOTEBOOK, fixture_cells(), {"width": "full"})
        before = document._record

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
        before = document._record

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
        assert document._record.saved_etag is None

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


class TestApply:
    def test_creates_replaces_deletes_and_reorders_as_one_unit(self) -> None:
        document = Document(NOTEBOOK, fixture_cells(), {"width": "full"})
        before = document._record
        c3 = document.cell("c3")
        k7f2 = document.cell("k7f2")
        assert c3 is not None
        assert k7f2 is not None

        applied = document.apply(
            [
                put("c2", "print('hi')", None, after="c1"),
                put("c3", "x = 22", c3.etag),
                delete("k7f2", k7f2.etag),
                set_order(before.order_etag, "c3", "c2", "c1"),
            ]
        )

        assert document.order == ["c3", "c2", "c1"]
        assert [c.id for c in applied.changed.cells] == ["c3", "c2"]
        assert applied.changed.removed == ["k7f2"]
        assert applied.changed.document is not None
        assert applied.changed.document.app_config == {"width": "full"}
        assert set(applied.cells) == {"c2", "c3", "k7f2"}
        assert applied.cells["k7f2"] is None
        new_c3 = document.cell("c3")
        assert new_c3 is not None
        assert applied.cells["c3"] == protocol.CellEtags(
            etag=new_c3.etag, code_hash=new_c3.code_hash
        )
        assert new_c3.etag != c3.etag

    def test_a_stale_etag_applies_nothing_and_names_the_change(self) -> None:
        document = Document(NOTEBOOK, fixture_cells(), {})
        before = document._record

        with pytest.raises(EditConflict) as raised:
            document.apply(
                [
                    put("new", "z = 1", None),
                    put("c3", "x = 22", "0000000000000000"),
                ]
            )

        assert raised.value.change == 1
        assert raised.value.cell == document.cell("c3")
        assert raised.value.document == before
        assert document._record == before
        assert document.cell("new") is None

    def test_creating_an_existing_cell_or_replacing_a_missing_one_conflicts(
        self,
    ) -> None:
        document = Document(NOTEBOOK, fixture_cells(), {})
        c3 = document.cell("c3")
        assert c3 is not None

        with pytest.raises(EditConflict) as raised:
            document.apply([put("c3", "x = 1", None)])
        assert raised.value.cell == c3

        with pytest.raises(EditConflict) as raised:
            document.apply([put("nope", "x = 1", "*")])
        assert raised.value.cell is None

        # The cell existed when the client read, even if the same batch
        # deletes it first.
        with pytest.raises(EditConflict) as raised:
            document.apply([delete("c3", c3.etag), put("c3", "x = 1", None)])
        assert raised.value.change == 1
        assert document.cell("c3") == c3

    def test_star_skips_the_check(self) -> None:
        document = Document(NOTEBOOK, fixture_cells(), {})

        document.apply(
            [put("c3", "x = 23", "*"), set_order("*", "k7f2", "c3", "c1")]
        )

        assert document.order == ["k7f2", "c3", "c1"]

    def test_placement_has_no_precondition(self) -> None:
        document = Document(NOTEBOOK, fixture_cells(), {})

        document.apply([put("a", "1", None, before="c1")])
        document.apply([put("b", "2", None, after="c1")])
        document.apply([put("c", "3", None)])

        assert document.order == ["a", "c1", "b", "c3", "k7f2", "c"]

    def test_malformed_changes_are_invalid(self) -> None:
        document = Document(NOTEBOOK, fixture_cells(), {})
        before = document._record

        with pytest.raises(Invalid):
            document.apply([set_order("*", "c1", "c3")])
        with pytest.raises(Invalid):
            document.apply([set_order("*", "c1", "c3", "c3")])
        with pytest.raises(Invalid):
            document.apply([put("a", "1", None, after="nope")])
        with pytest.raises(Invalid):
            document.apply([put("a", "1", None, after="c1", before="c3")])
        assert document._record == before

    def test_an_edit_that_changes_nothing_reports_nothing(self) -> None:
        document = Document(NOTEBOOK, fixture_cells(), {})
        c3 = document.cell("c3")
        assert c3 is not None

        applied = document.apply([put("c3", "x = 21", c3.etag)])

        assert not applied.changed
        assert applied.cells["c3"] == protocol.CellEtags(
            etag=c3.etag, code_hash=c3.code_hash
        )


class TestFromRecords:
    def test_preserves_the_saved_revision(self) -> None:
        source = Document(
            NOTEBOOK, fixture_cells(), {"width": "full"}, policy="lazy"
        )
        # The saved revision precedes the current one; both survive.
        source.replace([CellSource("c1", "import marimo")], {"width": "full"})
        restored = Document.from_records(source._record, list(source))
        assert restored._record == source._record
        assert list(restored) == list(source)

    @pytest.mark.parametrize(
        "invalid", ["order", "notebook-id", "cell-etag", "document-etag"]
    )
    def test_rejects_inconsistent_records(self, invalid: str) -> None:
        source = Document(NOTEBOOK, fixture_cells(), {})
        document, cells = source._record, list(source)
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
            Document.from_records(document, cells)


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

    def test_replace_can_record_the_saved_revision(
        self, notebook: Notebook, log: list[Event]
    ) -> None:
        notebook.replace(fixture_cells(), {})
        log.clear()

        changed = notebook.replace(
            [CellSource("c1", "x = 22")], {}, saved=True
        )

        assert changed.document is not None
        assert changed.document.saved_etag == changed.document.etag
        assert names(log) == [
            "cell",
            "cell.removed",
            "cell.removed",
            "document",
        ]
        assert log[-1].data.document == changed.document  # type: ignore[union-attr]

    def test_mark_saved_records_the_revision_that_was_written(
        self, notebook: Notebook, log: list[Event]
    ) -> None:
        notebook.replace(fixture_cells(), {})
        written = notebook.document._record.etag
        notebook.replace([CellSource("c1", "x = 22")], {})
        log.clear()

        document = notebook.mark_saved(written, request_id="save-1")

        assert document.saved_etag == written
        assert document.etag != written
        assert names(log) == ["document"]
        assert request_ids(log) == ["save-1"]
        assert log[0].data.document == document  # type: ignore[union-attr]
        # Marking the same revision again publishes nothing.
        assert notebook.mark_saved(written) == document
        assert names(log) == ["document"]

    def test_edit_publishes_as_one_unit_with_the_request_key(
        self, notebook: Notebook, log: list[Event]
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
        assert response.document == log[-1].data.document  # type: ignore[union-attr]
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
        self, host: Host, log: list[Event]
    ) -> None:
        host.update_project(project())
        analyzer = ScriptedAnalyzer()
        document = Document(NOTEBOOK, fixture_cells(), {"width": "full"})
        notebook = await add_notebook(
            host,
            record(),
            ScriptedBackend(),
            document=document,
            analyzer=analyzer,
        )
        snapshot, result = await analyzer.next_request()
        assert snapshot == document.snapshot()
        assert notebook.analysis is None

        log.clear()
        result.set_result(cell_analyses(document))
        await asyncio.sleep(0)

        assert names(log) == ["analysis"]
        assert request_ids(log) == [UNSET]
        assert notebook.analysis == protocol.Analysis(
            notebook_id=NOTEBOOK,
            document_etag=snapshot.document.etag,
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
        self, host: Host, log: list[Event]
    ) -> None:
        host.update_project(project())
        analyzer = ScriptedAnalyzer()
        document = Document(NOTEBOOK, fixture_cells(), {})
        notebook = await add_notebook(
            host,
            record(),
            ScriptedBackend(),
            document=document,
            analyzer=analyzer,
        )
        first, result = await analyzer.next_request()
        first_analysis = cell_analyses(document)
        notebook.replace([CellSource("c1", "1")], {}, request_id="edit-1")
        notebook.replace(
            [CellSource("c1", "2", name="named", config=HIDDEN)],
            {"width": "full"},
            request_id="edit-2",
        )
        assert len(analyzer.requests) == 1
        assert first.document.etag != document._record.etag
        assert first.cells[0].code == "import marimo as mo"

        log.clear()
        result.set_result(first_analysis)
        latest, result = await analyzer.next_request()
        assert names(log) == []
        assert latest == document.snapshot()

        result.set_result(cell_analyses(document))
        await asyncio.sleep(0)
        assert names(log) == ["analysis"]
        assert request_ids(log) == ["edit-2"]
        assert notebook.analysis is not None
        assert notebook.analysis.document_etag == latest.document.etag

    async def test_an_edit_is_analyzed_under_its_request_key(
        self, host: Host, log: list[Event]
    ) -> None:
        host.update_project(project())
        analyzer = ScriptedAnalyzer()
        document = Document(NOTEBOOK, fixture_cells(), {})
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
        snapshot, result = await analyzer.next_request()
        assert snapshot == document.snapshot()
        assert [c.id for c in snapshot.cells] == ["c1", "c3", "k7f2", "c9"]

        result.set_result(cell_analyses(document))
        await asyncio.sleep(0)
        assert names(log) == ["cell", "document", "analysis"]
        assert request_ids(log) == ["edit-1"] * 3

    async def test_the_previous_analysis_stays_until_the_next_arrives(
        self, host: Host
    ) -> None:
        host.update_project(project())
        analyzer = ScriptedAnalyzer()
        document = Document(NOTEBOOK, fixture_cells(), {})
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
        notebook.replace([CellSource("c1", "1")], {})
        _, result = await analyzer.next_request()

        assert notebook.analysis is not None
        assert (
            notebook.analysis.document_etag
            == first.document.etag
            != document._record.etag
        )
        assert names(host.events(notebook_id="n1")) == [
            "notebook",
            "cell",
            "document",
            "analysis",
            "ready",
        ]
        result.set_result(cell_analyses(document))
        await asyncio.sleep(0)

    @pytest.mark.parametrize("edit_while_running", [False, True])
    async def test_a_failed_analysis_leaves_the_notebook_ready_for_the_next(
        self, host: Host, log: list[Event], edit_while_running: bool
    ) -> None:
        host.update_project(project())
        analyzer = ScriptedAnalyzer()
        document = Document(NOTEBOOK, fixture_cells(), {})
        notebook = await add_notebook(
            host,
            record(),
            ScriptedBackend(),
            document=document,
            analyzer=analyzer,
        )
        _, result = await analyzer.next_request()
        if edit_while_running:
            notebook.replace([CellSource("c1", "1")], {})
        log.clear()
        result.set_exception(RuntimeError("compiler failed"))
        await asyncio.sleep(0)
        assert names(log) == []
        assert notebook.analysis is None
        if not edit_while_running:
            notebook.replace([CellSource("c1", "1")], {})
        snapshot, result = await analyzer.next_request()
        assert snapshot == document.snapshot()
        log.clear()
        result.set_result(cell_analyses(document))
        await asyncio.sleep(0)
        assert names(log) == ["analysis"]

    async def test_removal_discards_a_result_even_if_cancellation_is_suppressed(
        self, host: Host, log: list[Event]
    ) -> None:
        started, cancelled = asyncio.Event(), asyncio.Event()
        result = asyncio.get_running_loop().create_future()
        document = Document(NOTEBOOK, fixture_cells(), {})

        class Analyzer:
            async def analyze(self, _snapshot):
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
                document,
                Executions(),
                ScriptedBackend(),
                sink,
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


def test_snapshot_preserves_order_metadata_and_nested_configuration() -> None:
    document = Document(NOTEBOOK, fixture_cells(), {"nested": {"items": [1]}})
    snapshot = document.snapshot()
    assert snapshot.cells == tuple(document)
    assert snapshot.document == document._record
    document._record.app_config["nested"]["items"].append(2)
    document.replace([CellSource("c1", "42", name="renamed")], {})
    assert snapshot.document.app_config == {"nested": {"items": [1]}}
    assert snapshot.cells[0].code == "import marimo as mo"
    assert snapshot.cells[-1].config == HIDDEN
    snapshot.document.app_config["another"] = True
    assert document._record.app_config == {}
