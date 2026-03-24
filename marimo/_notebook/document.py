# Copyright 2026 Marimo. All rights reserved.
"""Canonical notebook document model.

``NotebookDocument`` maintains an ordered list of ``CellMeta`` entries and
a ``LoroDoc`` that owns all cell source text as ``LoroText`` containers.
``NotebookCell`` is a read-only snapshot materialized on access.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

from marimo._utils.assert_never import assert_never

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable, Iterator

import msgspec
from msgspec.structs import replace as structs_replace

from marimo._ast.cell import CellConfig
from marimo._notebook._loro import create_doc, create_text, unwrap_text
from marimo._messaging.notebook.changes import (
    CreateCell,
    DeleteCell,
    DocumentChange,
    MoveCell,
    ReorderCells,
    SetCode,
    SetConfig,
    SetName,
    Transaction,
)
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from loro import LoroDoc, LoroText


class NotebookCell(msgspec.Struct, frozen=True):
    """Read-only snapshot of a cell, materialized from CellMeta + LoroText.

    This is never stored by the document — ``get_cell()`` and ``.cells``
    construct fresh instances each time.
    """

    id: CellId_t
    code: str
    name: str
    config: CellConfig


class CellMeta(msgspec.Struct):
    """Mutable metadata for a cell. Owned by the document internally.

    Does *not* hold code — that lives in the ``LoroDoc``.
    """

    id: CellId_t
    name: str
    config: CellConfig


class NotebookDocument:
    """Ordered collection of cells with transactional updates.

    Cell text is owned by a ``LoroDoc`` (one ``LoroText`` per cell under
    ``LoroMap("codes")``).  Structural metadata (name, config, ordering)
    is stored in ``_cell_metas``.

    Usage::

        from loro import LoroDoc

        doc = NotebookDocument(LoroDoc())
        doc.add_cell(
            CellId_t("a"), code="x = 1", name="__", config=CellConfig()
        )
        tx = Transaction(
            changes=(SetCode(CellId_t("a"), "x = 2"),), source="kernel"
        )
        applied = doc.apply(tx)
        assert applied.version == 1
        assert doc.get_cell(CellId_t("a")).code == "x = 2"
    """

    def __init__(self, loro_doc: LoroDoc) -> None:
        self._loro_doc = loro_doc
        self._codes_map = loro_doc.get_map("codes")
        self._cell_metas: list[CellMeta] = []
        self._version: int = 0

    @classmethod
    def from_cells(cls, cells: Iterable[NotebookCell]) -> NotebookDocument:
        """Build a document from ``NotebookCell`` snapshots.

        Creates a fresh ``LoroDoc`` populated from the snapshot data.
        Used at the kernel-process boundary where cells arrive as
        serialized structs and need to be reconstructed into a live
        document.
        """
        doc = cls(create_doc())
        for c in cells:
            doc.add_cell(
                cell_id=c.id, code=c.code, name=c.name, config=c.config
            )
        doc._loro_doc.commit()
        return doc

    @property
    def loro_doc(self) -> LoroDoc:
        """The underlying Loro document owning cell text."""
        return self._loro_doc

    # ------------------------------------------------------------------
    # Bootstrap — populate the document from an external source
    # ------------------------------------------------------------------

    def add_cell(
        self,
        cell_id: CellId_t,
        code: str,
        name: str,
        config: CellConfig,
    ) -> None:
        """Append a cell during initial document construction.

        This is *not* a transaction — it is used at session init to
        populate the document from a ``CellManager``.
        """
        text = create_text()
        text.insert(0, code)
        self._codes_map.insert_container(cell_id, text)
        self._cell_metas.append(CellMeta(id=cell_id, name=name, config=config))

    # ------------------------------------------------------------------
    # Read-only accessors
    # ------------------------------------------------------------------

    @property
    def cells(self) -> list[NotebookCell]:
        """Materialize and return a snapshot list of all cells."""
        return [self._snapshot(m) for m in self._cell_metas]

    @property
    def cell_ids(self) -> list[CellId_t]:
        """Cell IDs in document order."""
        return [m.id for m in self._cell_metas]

    @property
    def version(self) -> int:
        return self._version

    def get_cell(self, cell_id: CellId_t) -> NotebookCell:
        """Lookup by ID. Raises ``KeyError`` if not found."""
        return self._snapshot(self._find_meta(cell_id))

    def get(self, cell_id: CellId_t) -> NotebookCell | None:
        """Lookup by ID, returning ``None`` if not found."""
        for m in self._cell_metas:
            if m.id == cell_id:
                return self._snapshot(m)
        return None

    def __contains__(self, cell_id: object) -> bool:
        return any(m.id == cell_id for m in self._cell_metas)

    def __len__(self) -> int:
        return len(self._cell_metas)

    def __iter__(self) -> Iterator[CellId_t]:
        return (m.id for m in self._cell_metas)

    # ------------------------------------------------------------------
    # Transaction application
    # ------------------------------------------------------------------

    def apply(self, tx: Transaction) -> Transaction:
        """Validate and apply *tx*, return it with ``version`` assigned.

        Raises ``ValueError`` for validation failures and ``KeyError``
        when a change references a non-existent cell.
        """
        if not tx.changes:
            return structs_replace(tx, version=self._version)

        _validate(tx.changes, self._cell_metas)

        for change in tx.changes:
            self._apply_change(change)

        # Commit all Loro mutations from this transaction as a single
        # batch.  This triggers one ``subscribe_local_update`` callback
        # so RTC clients receive one update per transaction.
        self._loro_doc.commit()

        self._version += 1
        return structs_replace(tx, version=self._version)

    def _apply_change(self, change: DocumentChange) -> None:
        # TODO: refactor to use match/case (min Python is 3.10) once
        # ruff target-version is bumped from py39.
        if isinstance(change, CreateCell):
            # Create LoroText in the shared doc
            text = create_text()
            text.insert(0, change.code)
            self._codes_map.insert_container(change.cell_id, text)

            meta = CellMeta(id=change.cell_id, name=change.name, config=change.config)
            if change.after is not None:
                idx = self._find_index(change.after)
                self._cell_metas.insert(idx + 1, meta)
            elif change.before is not None:
                idx = self._find_index(change.before)
                self._cell_metas.insert(idx, meta)
            else:
                self._cell_metas.append(meta)

        elif isinstance(change, DeleteCell):
            idx = self._find_index(change.cell_id)
            del self._cell_metas[idx]
            self._codes_map.delete(change.cell_id)

        elif isinstance(change, MoveCell):
            idx = self._find_index(change.cell_id)
            meta = self._cell_metas.pop(idx)
            if change.after is not None:
                target = self._find_index(change.after)
                self._cell_metas.insert(target + 1, meta)
            elif change.before is not None:
                target = self._find_index(change.before)
                self._cell_metas.insert(target, meta)
            else:
                raise ValueError("MoveCell requires 'before' or 'after'")

        elif isinstance(change, ReorderCells):
            by_id = {m.id: m for m in self._cell_metas}
            seen: set[CellId_t] = set()
            reordered: list[CellMeta] = []
            for cid in change.cell_ids:
                if cid in by_id and cid not in seen:
                    reordered.append(by_id[cid])
                    seen.add(cid)
            for m in self._cell_metas:
                if m.id not in seen:
                    reordered.append(m)
            self._cell_metas = reordered

        elif isinstance(change, SetCode):
            self._find_meta(change.cell_id)
            text = self._get_loro_text(change.cell_id)
            if text.len_unicode > 0:
                text.delete(0, text.len_unicode)
            if change.code:
                text.insert(0, change.code)

        elif isinstance(change, SetName):
            self._find_meta(change.cell_id).name = change.name

        elif isinstance(change, SetConfig):
            meta = self._find_meta(change.cell_id)
            meta.config = CellConfig(
                column=change.column
                if change.column is not None
                else meta.config.column,
                disabled=change.disabled
                if change.disabled is not None
                else meta.config.disabled,
                hide_code=change.hide_code
                if change.hide_code is not None
                else meta.config.hide_code,
            )
        else:
            assert_never(change)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _snapshot(self, meta: CellMeta) -> NotebookCell:
        """Build a read-only ``NotebookCell`` from metadata + Loro text."""
        code = self._get_loro_text(meta.id).to_string()
        return NotebookCell(
            id=meta.id, code=code, name=meta.name, config=meta.config
        )

    def _get_loro_text(self, cell_id: CellId_t) -> LoroText:
        """Return the ``LoroText`` for *cell_id*."""
        val = self._codes_map.get(cell_id)
        if val is None:
            raise KeyError(f"No LoroText for cell {cell_id!r}")
        return unwrap_text(val)

    def _find_index(self, cell_id: CellId_t) -> int:
        for i, m in enumerate(self._cell_metas):
            if m.id == cell_id:
                return i
        raise KeyError(f"Cell {cell_id!r} not found in document")

    def _find_meta(self, cell_id: CellId_t) -> CellMeta:
        for m in self._cell_metas:
            if m.id == cell_id:
                return m
        raise KeyError(f"Cell {cell_id!r} not found in document")

    def __repr__(self) -> str:
        lines = [f"NotebookDocument({len(self._cell_metas)} cells):"]
        for i, m in enumerate(self._cell_metas):
            code_preview = (
                self._get_loro_text(m.id).to_string()[:40].replace("\n", "\\n")
            )
            lines.append(f"  {i}: {m.id} {code_preview!r}")
        return "\n".join(lines)


# ------------------------------------------------------------------
# Context variable
# ------------------------------------------------------------------

#: Document snapshot for the current scratchpad execution. Set by the
#: kernel before running code_mode so ``AsyncCodeModeContext`` can read
#: cell ordering, code, names, and configs without the kernel carrying
#: mutable document state.
_current_document: ContextVar[NotebookDocument | None] = ContextVar(
    "_current_document", default=None
)


def get_current_document() -> NotebookDocument | None:
    """Return the document for the current execution, if any."""
    return _current_document.get()


@contextmanager
def notebook_document_context(
    doc: NotebookDocument | None,
) -> Generator[None, None, None]:
    """Context manager for setting and resetting the current document."""
    token = _current_document.set(doc)
    try:
        yield
    finally:
        _current_document.reset(token)


# ------------------------------------------------------------------
# Validation
# ------------------------------------------------------------------


def _validate(
    changes: tuple[DocumentChange, ...], metas: list[CellMeta]
) -> None:
    """Check for conflicting changes. Raises ``ValueError``."""
    existing_ids = {m.id for m in metas}
    created: set[CellId_t] = set()
    deleted: set[CellId_t] = set()
    updated: set[CellId_t] = set()
    moved: set[CellId_t] = set()

    for change in changes:
        if isinstance(change, CreateCell):
            if change.cell_id in existing_ids or change.cell_id in created:
                raise ValueError(f"Cell {change.cell_id!r} already exists")
            if change.before is not None and change.after is not None:
                raise ValueError(
                    "CreateCell cannot specify both 'before' and 'after'"
                )
            created.add(change.cell_id)

        elif isinstance(change, DeleteCell):
            if change.cell_id in deleted:
                raise ValueError(
                    f"Cell {change.cell_id!r} is deleted more than once"
                )
            if change.cell_id in updated:
                raise ValueError(
                    f"Cannot delete cell {change.cell_id!r} that is also "
                    f"updated in the same transaction"
                )
            if change.cell_id in moved:
                raise ValueError(
                    f"Cannot delete cell {change.cell_id!r} that is also "
                    f"moved in the same transaction"
                )
            deleted.add(change.cell_id)

        elif isinstance(change, MoveCell):
            if change.cell_id in deleted:
                raise ValueError(
                    f"Cannot move cell {change.cell_id!r} that is also "
                    f"deleted in the same transaction"
                )
            if change.before is not None and change.after is not None:
                raise ValueError(
                    "MoveCell cannot specify both 'before' and 'after'"
                )
            if change.before is None and change.after is None:
                raise ValueError("MoveCell requires 'before' or 'after'")
            moved.add(change.cell_id)

        elif isinstance(change, ReorderCells):
            pass  # No conflicts — replaces full ordering

        elif isinstance(change, (SetCode, SetName, SetConfig)):
            if change.cell_id in deleted:
                raise ValueError(
                    f"Cannot update cell {change.cell_id!r} that is also "
                    f"deleted in the same transaction"
                )
            updated.add(change.cell_id)

        else:
            raise TypeError(f"Unknown change type: {type(change)!r}")
