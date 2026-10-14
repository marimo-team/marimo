# Copyright 2026 Marimo. All rights reserved.
"""Notebook cells, order, configuration, and revisions."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from msgspec.structs import replace

from marimo._core import protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

Analyzer = Callable[[Mapping[str, str]], Mapping[str, protocol.Analysis]]
"""Derives every cell's analysis from the cells' code, keyed by id in document order."""

Policy = Literal["autorun", "lazy"]


def etag(text: str) -> protocol.Etag:
    """The first 16 hex characters of SHA-256 over the UTF-8 text."""
    return protocol.Etag(hashlib.sha256(text.encode()).hexdigest()[:16])


def code_hash(code: str) -> protocol.Etag:
    return etag(code)


def cell_etag(
    code_hash: protocol.Etag, name: str, config: protocol.CellConfig
) -> protocol.Etag:
    """Over the code hash, the name, and the config values as JSON scalars."""
    values = (
        config.column,
        config.disabled,
        config.hide_code,
        config.expand_output,
    )
    return etag("\n".join([code_hash, name, *(json.dumps(v) for v in values)]))


def order_etag(order: Sequence[str]) -> protocol.Etag:
    return etag(json.dumps(order, separators=(",", ":"), ensure_ascii=False))


def app_config_etag(app_config: Mapping[str, Any]) -> protocol.Etag:
    """Over the app config as canonical JSON."""
    return etag(
        json.dumps(
            app_config,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    )


def document_etag(
    order_etag: protocol.Etag,
    app_config_etag: protocol.Etag,
    cell_etags: Sequence[protocol.Etag],
) -> protocol.Etag:
    return etag("\n".join([order_etag, app_config_etag, *cell_etags]))


def default_config() -> protocol.CellConfig:
    return protocol.CellConfig(
        column=None, disabled=False, hide_code=False, expand_output=False
    )


@dataclass(frozen=True)
class CellSource:
    """Cell source and metadata supplied by a file or editor."""

    id: str
    code: str
    name: str = "_"
    config: protocol.CellConfig = field(default_factory=default_config)


@dataclass(frozen=True)
class Changed:
    """Changed cells, removed cell IDs, and the updated document."""

    cells: list[protocol.Cell]
    """New cells, and cells whose etag or analysis changed."""
    removed: list[str]
    """Ids of cells that no longer exist."""
    document: protocol.Document | None
    """The document, when any of its fields changed."""

    def __bool__(self) -> bool:
        return bool(self.cells or self.removed or self.document)


class Document:
    """A notebook document with content-derived revisions.

    Cell source uses newline line endings. Analysis covers all cells.
    """

    def __init__(
        self,
        notebook_id: protocol.NotebookId,
        cells: Sequence[CellSource],
        app_config: Mapping[str, Any],
        *,
        policy: Policy = "autorun",
        analyzer: Analyzer | None = None,
        saved: bool = True,
    ) -> None:
        self._id = notebook_id
        self._analyzer = analyzer
        self._policy: Policy = policy
        self._cells: dict[str, protocol.Cell] = {}
        self._order: list[str] = []
        self._app_config: dict[str, Any] = {}
        self._saved_etag: protocol.Etag | None = None
        self._document: protocol.Document | None = None
        self.replace(cells, app_config)
        if saved:
            self.mark_saved()

    @classmethod
    def from_records(
        cls,
        document: protocol.Document,
        cells: Sequence[protocol.Cell],
        *,
        analyzer: Analyzer | None = None,
    ) -> Document:
        """Restore a document from its protocol records.

        Cell identities, order, and revisions must agree. Analysis is kept
        unless an analyzer is supplied. The saved revision is preserved.
        """
        document, cells = deepcopy((document, cells))
        by_id = {cell.id: cell for cell in cells}
        if len(by_id) != len(cells) or (
            len(set(document.order)) != len(document.order)
            or set(document.order) != set(by_id)
        ):
            raise ValueError(
                "document order must contain every cell exactly once"
            )
        if any(cell.notebook_id != document.id for cell in cells):
            raise ValueError("cells must belong to the document")
        restored = cls(
            document.id,
            [
                CellSource(cell.id, cell.code, cell.name, cell.config)
                for cell in (by_id[cell_id] for cell_id in document.order)
            ],
            document.app_config,
            policy=document.policy,
            analyzer=analyzer,
            saved=False,
        )
        for cell in restored.cells:
            original = by_id[cell.id]
            if (
                cell.etag != original.etag
                or cell.code_hash != original.code_hash
            ):
                raise ValueError("cell revisions must match their content")
            if analyzer is None:
                restored._cells[cell.id] = replace(
                    cell, analysis=original.analysis
                )
        current = restored.document
        if (
            current.etag != document.etag
            or current.order_etag != document.order_etag
            or current.app_config_etag != document.app_config_etag
        ):
            raise ValueError("document revisions must match its content")
        if document.saved_etag is not None:
            restored.mark_saved(document.saved_etag)
        return restored

    @property
    def document(self) -> protocol.Document:
        assert self._document is not None
        return self._document

    @property
    def cells(self) -> list[protocol.Cell]:
        """The cells in document order."""
        return [self._cells[cell_id] for cell_id in self._order]

    @property
    def order(self) -> list[str]:
        return list(self._order)

    def cell(self, cell_id: str) -> protocol.Cell | None:
        return self._cells.get(cell_id)

    def replace(
        self, cells: Sequence[CellSource], app_config: Mapping[str, Any]
    ) -> Changed:
        """Replace cells and configuration and return what changed.

        Cell IDs must be unique.
        """
        order = [source.id for source in cells]
        if len(set(order)) != len(order):
            raise ValueError("cell ids must be unique within the notebook")
        built = {source.id: self._build(source) for source in cells}
        if self._analyzer is not None:
            analyses = self._analyzer(
                {cell_id: built[cell_id].code for cell_id in order}
            )
            for cell_id in order:
                analysis = analyses.get(cell_id)
                if analysis is not None:
                    built[cell_id] = replace(built[cell_id], analysis=analysis)
        changed = [
            built[cell_id]
            for cell_id in order
            if self._cells.get(cell_id) != built[cell_id]
        ]
        removed = [cell_id for cell_id in self._order if cell_id not in built]
        self._cells = built
        self._order = order
        self._app_config = dict(app_config)
        return Changed(changed, removed, self._refresh())

    def mark_saved(
        self, etag: protocol.Etag | None = None
    ) -> protocol.Document | None:
        """Record the persisted revision, which may precede the current one."""
        self._saved_etag = self.document.etag if etag is None else etag
        return self._refresh()

    def set_policy(self, policy: Policy) -> protocol.Document | None:
        self._policy = policy
        return self._refresh()

    def _build(self, source: CellSource) -> protocol.Cell:
        code = source.code.replace("\r\n", "\n").replace("\r", "\n")
        hashed = code_hash(code)
        return protocol.Cell(
            id=protocol.CellId(source.id),
            notebook_id=self._id,
            code=code,
            name=source.name,
            config=source.config,
            etag=cell_etag(hashed, source.name, source.config),
            code_hash=hashed,
            analysis=None,
        )

    def _refresh(self) -> protocol.Document | None:
        """Recompute the document and return it when it changed."""
        order = order_etag(self._order)
        app_config = app_config_etag(self._app_config)
        document = protocol.Document(
            id=self._id,
            order=tuple(protocol.CellId(c) for c in self._order),
            app_config=dict(self._app_config),
            policy=self._policy,
            etag=document_etag(
                order,
                app_config,
                [self._cells[cell_id].etag for cell_id in self._order],
            ),
            saved_etag=self._saved_etag,
            order_etag=order,
            app_config_etag=app_config,
        )
        if document == self._document:
            return None
        self._document = document
        return document
