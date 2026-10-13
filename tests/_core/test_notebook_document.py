# Copyright 2026 Marimo. All rights reserved.
"""The document's etags, change reporting, and publication order."""

from __future__ import annotations

from typing import TYPE_CHECKING

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
)
from marimo._core.errors import EditConflict, Invalid
from marimo._core.host import Host
from marimo._core.notebook import Notebook
from marimo._core.stream import Event
from tests._core.conftest import make_notebook, names, project, record

if TYPE_CHECKING:
    from collections.abc import Mapping

NOTEBOOK = protocol.NotebookId("n1")


def source(cell_id: str, code: str, **fields: object) -> CellSource:
    return CellSource(protocol.CellId(cell_id), code, **fields)  # type: ignore[arg-type]


HIDDEN = protocol.CellConfig(
    column=None, disabled=False, hide_code=True, expand_output=False
)


def fixture_cells() -> list[CellSource]:
    """The cells in pair's `notebook-events.sse` fixture."""
    return [
        source("c1", "import marimo as mo"),
        source("c3", "x = 21"),
        source("k7f2", "y = x * 2", config=HIDDEN),
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

    def test_normalizes_line_endings_before_hashing(self) -> None:
        document = Document(NOTEBOOK, [source("a", "x = 1\r\ny = 2")], {})
        (cell,) = document
        assert cell.code == "x = 1\ny = 2"
        assert cell.code_hash == code_hash("x = 1\ny = 2")


class TestReplace:
    def test_reports_new_changed_and_removed_cells(self) -> None:
        document = Document(NOTEBOOK, fixture_cells(), {"width": "full"})
        before = document._record

        changed = document.replace(
            [
                source("c1", "import marimo as mo"),
                source("new", "z = 3"),
                source("k7f2", "y = x * 3", config=HIDDEN),
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
            Document(NOTEBOOK, [source("a", "1"), source("a", "2")], {})

    def test_marks_saved_state_separately(self) -> None:
        document = Document(NOTEBOOK, fixture_cells(), {}, saved=False)
        assert document._record.saved_etag is None

        document.replace([source("c1", "1")], {})
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
            [source("a", "x = 1"), source("b", "y = 2")],
            {},
            analyzer=defs_only,
        )
        a, _ = document
        assert a.analysis == protocol.Analysis(defs=["x"], refs=[], errors=[])

        changed = document.replace(
            [source("a", "x = 1"), source("b", "x = 2")], {}
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
        assert all(cell.analysis is None for cell in document)


class TestFromRecords:
    def test_preserves_imported_analysis_and_saved_revision(self) -> None:
        source = Document(
            NOTEBOOK,
            fixture_cells(),
            {"width": "full"},
            policy="lazy",
            analyzer=lambda codes: {
                cell_id: protocol.Analysis(defs=(), refs=(), errors=())
                for cell_id in codes
            },
        )
        # The saved revision precedes the current one; both survive.
        source.replace([CellSource("c1", "import marimo")], {"width": "full"})
        restored = Document.from_records(source._record, list(source))
        assert restored._record == source._record
        assert list(restored) == list(source)
        assert next(iter(restored)).analysis is not None

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

    def test_analyzer_is_injected_for_restoration_and_later_edits(
        self,
    ) -> None:
        observed: list[dict[str, str]] = []

        def analyze(codes: Mapping[str, str]) -> dict[str, protocol.Analysis]:
            observed.append(dict(codes))
            return {
                cell_id: protocol.Analysis(defs=(), refs=(), errors=())
                for cell_id in codes
            }

        source = Document(NOTEBOOK, [CellSource("c1", "42")], {})
        document = Document.from_records(
            source._record, list(source), analyzer=analyze
        )
        document.replace([CellSource("c1", "43")], {})
        assert observed == [{"c1": "42"}, {"c1": "43"}]
        assert next(iter(document)).analysis is not None


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
                source("c1", "import marimo as mo"),
                source("c3", "x = 22"),
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

        changed = notebook.replace([source("c1", "x = 22")], {}, saved=True)

        assert changed.document is not None
        assert changed.document.saved_etag == changed.document.etag
        assert names(log) == [
            "cell",
            "cell.removed",
            "cell.removed",
            "document",
        ]
        assert log[-1].data.document == changed.document  # type: ignore[union-attr]


def put(
    cell_id: str,
    code: str,
    base_etag: str | None,
    *,
    after: str | None = None,
    before: str | None = None,
    name: str = "_",
) -> protocol.PutCell:
    return protocol.PutCell(
        base_etag=base_etag,
        cell=protocol.CellInput(id=cell_id, code=code, name=name),
        after=UNSET if after is None else after,
        before=UNSET if before is None else before,
    )


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
                protocol.DeleteCell(id="k7f2", base_etag=k7f2.etag),
                protocol.SetOrder(
                    base_etag=before.order_etag, order=["c3", "c2", "c1"]
                ),
                protocol.SetAppConfig(
                    base_etag=before.app_config_etag, app_config={}
                ),
            ]
        )

        assert document.order == ["c3", "c2", "c1"]
        assert [c.id for c in applied.changed.cells] == ["c3", "c2"]
        assert applied.changed.removed == ["k7f2"]
        assert applied.changed.document is not None
        assert applied.changed.document.app_config == {}
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

        with pytest.raises(EditConflict) as raised:
            document.apply([put("c3", "x = 1", None)])
        assert raised.value.cell == document.cell("c3")

        with pytest.raises(EditConflict) as raised:
            document.apply([put("nope", "x = 1", "*")])
        assert raised.value.cell is None

    def test_star_skips_the_check(self) -> None:
        document = Document(NOTEBOOK, fixture_cells(), {})

        document.apply(
            [
                put("c3", "x = 23", "*"),
                protocol.SetOrder(base_etag="*", order=["k7f2", "c3", "c1"]),
                protocol.SetAppConfig(base_etag="*", app_config={"a": 1}),
            ]
        )

        assert document.order == ["k7f2", "c3", "c1"]
        assert document._record.app_config == {"a": 1}

    def test_an_edit_app_config_is_normalized_before_hashing(self) -> None:
        def normalize(config: Mapping[str, object]) -> dict[str, object]:
            if "bad" in config:
                raise Invalid("'bad' is not an app config key")
            return {k: v for k, v in config.items() if v is not None}

        document = Document(
            NOTEBOOK, fixture_cells(), {}, normalizer=normalize
        )
        applied = document.apply(
            [
                protocol.SetAppConfig(
                    base_etag="*", app_config={"width": None, "a": 1}
                )
            ]
        )

        assert applied.changed.document is not None
        assert applied.changed.document.app_config == {"a": 1}
        assert applied.changed.document.app_config_etag == app_config_etag(
            {"a": 1}
        )
        with pytest.raises(Invalid):
            document.apply(
                [protocol.SetAppConfig(base_etag="*", app_config={"bad": 1})]
            )
        assert document._record.app_config == {"a": 1}
        # Configs that arrive from a store are kept as they are.
        assert Document(NOTEBOOK, [], {"width": None})._record.app_config == {
            "width": None
        }

    def test_placement_has_no_precondition(self) -> None:
        document = Document(NOTEBOOK, fixture_cells(), {})

        document.apply([put("a", "1", None, before="c1")])
        document.apply([put("b", "2", None, after="c1")])
        document.apply([put("c", "3", None)])

        assert document.order == ["a", "c1", "b", "c3", "k7f2", "c"]

    def test_malformed_changes_are_invalid(self) -> None:
        document = Document(NOTEBOOK, fixture_cells(), {})

        with pytest.raises(Invalid):
            document.apply(
                [protocol.SetOrder(base_etag="*", order=["c1", "c3"])]
            )
        with pytest.raises(Invalid):
            document.apply(
                [protocol.SetOrder(base_etag="*", order=["c1", "c3", "c3"])]
            )
        with pytest.raises(Invalid):
            document.apply([put("a", "1", None, after="nope")])
        with pytest.raises(Invalid):
            document.apply([put("a", "1", None, after="c1", before="c3")])

    def test_an_edit_that_changes_nothing_reports_nothing(self) -> None:
        document = Document(NOTEBOOK, fixture_cells(), {})
        c3 = document.cell("c3")
        assert c3 is not None

        applied = document.apply([put("c3", "x = 21", c3.etag)])

        assert not applied.changed
        assert applied.cells["c3"] == protocol.CellEtags(
            etag=c3.etag, code_hash=c3.code_hash
        )

    def test_the_notebook_publishes_an_edit_as_one_unit(
        self, notebook: Notebook, log: list[Event]
    ) -> None:
        notebook.replace(fixture_cells(), {})
        log.clear()
        k7f2 = notebook.document.cell("k7f2")
        assert k7f2 is not None

        response = notebook.edit(
            [
                put("c2", "print('hi')", None, after="c1"),
                protocol.DeleteCell(id="k7f2", base_etag=k7f2.etag),
            ],
            request_id="edit-1",
        )

        assert names(log) == ["cell", "cell.removed", "document"]
        assert all(e.data.request_id == "edit-1" for e in log)  # type: ignore[union-attr]
        assert response.document == log[-1].data.document  # type: ignore[union-attr]
        assert set(response.cells) == {"c2", "k7f2"}
