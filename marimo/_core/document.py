# Copyright 2026 Marimo. All rights reserved.
"""Notebook cells, order, configuration, and revisions."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from msgspec import UNSET
from msgspec.structs import replace

from marimo._core import protocol
from marimo._core.errors import EditConflict, Invalid

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Sequence

Analyzer = Callable[[Mapping[str, str]], Mapping[str, protocol.Analysis]]
"""Derives every cell's analysis from the cells' code, keyed by id in document order."""

Normalizer = Callable[[Mapping[str, Any]], Mapping[str, Any]]
"""Puts an app config in the form the store keeps, so equal configs have equal etags.

Raises `Invalid` for a config no notebook can have.
"""

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


def dependents(
    cells: Sequence[protocol.Cell], roots: Iterable[protocol.CellId]
) -> set[protocol.CellId]:
    """Ids of cells reading a name a root defines, directly or through others.

    Edges come from the cells' analyses; a cell without one has none.
    """
    by_id = {cell.id: cell for cell in cells}
    readers: dict[str, list[protocol.CellId]] = {}
    for cell in cells:
        if cell.analysis is not None:
            for name in cell.analysis.refs:
                readers.setdefault(name, []).append(cell.id)
    found: set[protocol.CellId] = set()
    pending = list(roots)
    while pending:
        root = by_id.get(pending.pop())
        if root is None or root.analysis is None:
            continue
        for name in root.analysis.defs:
            for reader in readers.get(name, ()):
                if reader not in found:
                    found.add(reader)
                    pending.append(reader)
    return found


def default_config() -> protocol.CellConfig:
    return protocol.CellConfig(
        column=None, disabled=False, hide_code=False, expand_output=False
    )


@dataclass(frozen=True)
class CellSource:
    """Cell source and metadata with an ID supplied by its creator."""

    id: protocol.CellId
    code: str
    name: str = "_"
    config: protocol.CellConfig = field(default_factory=default_config)


@dataclass(frozen=True)
class Changed:
    """Changed cells, removed cell IDs, and the updated document."""

    cells: list[protocol.Cell]
    """New cells, and cells whose etag or analysis changed."""
    removed: list[protocol.CellId]
    """Ids of cells that no longer exist."""
    document: protocol.Document | None
    """The document, when any of its fields changed."""

    def __bool__(self) -> bool:
        return bool(self.cells or self.removed or self.document)


@dataclass(frozen=True)
class Applied:
    """An edit's effects and the etags of the cells it touched."""

    changed: Changed
    cells: dict[str, protocol.CellEtags | None]
    """By id, for each cell the edit put, and `None` for each it deleted."""


class Document:
    """A notebook document with content-derived revisions.

    Cell source uses newline line endings. Analysis covers all cells.
    Edits normalize app config before hashing. Loaded config must already
    be normalized.
    """

    def __init__(
        self,
        notebook_id: protocol.NotebookId,
        cells: Sequence[CellSource],
        app_config: Mapping[str, Any],
        *,
        policy: Policy = "autorun",
        analyzer: Analyzer | None = None,
        normalizer: Normalizer | None = None,
        saved: bool = True,
    ) -> None:
        self._id = notebook_id
        self._analyzer = analyzer
        self._normalizer = normalizer
        self._policy: Policy = policy
        self._cells: dict[protocol.CellId, protocol.Cell] = {}
        self._order: list[protocol.CellId] = []
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
        normalizer: Normalizer | None = None,
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
            normalizer=normalizer,
            saved=False,
        )
        for cell in restored:
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
        current = restored._record
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
    def notebook_id(self) -> protocol.NotebookId:
        """The notebook this document belongs to."""
        return self._id

    @property
    def _record(self) -> protocol.Document:
        assert self._document is not None
        return self._document

    def __iter__(self) -> Iterator[protocol.Cell]:
        """Iterate over cells in document order."""
        for cell_id in self._order:
            yield self._cells[cell_id]

    @property
    def order(self) -> list[protocol.CellId]:
        return list(self._order)

    def cell(self, cell_id: str) -> protocol.Cell | None:
        return self._cells.get(protocol.CellId(cell_id))

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

    def apply(self, changes: Sequence[protocol.Change]) -> Applied:
        """Apply `changes` in order as one unit, or none of them.

        Every precondition is compared with the document as it was when
        the request arrived, so one request can create a cell and then
        place it with the order etag the client read.

        Raises:
            EditConflict: If a precondition names a state the document no
                longer has. Nothing is applied.
            Invalid: If a change could not apply to any state.
        """
        staged: dict[protocol.CellId, CellSource] = {
            cell.id: CellSource(cell.id, cell.code, cell.name, cell.config)
            for cell in self
        }
        order = list(self._order)
        app_config = dict(self._app_config)
        touched: dict[protocol.CellId, bool] = {}

        before = self._record

        def matches(base: str, cell_id: protocol.CellId) -> bool:
            if base == "*":
                return True
            current = self._cells.get(cell_id)
            return current is not None and base == current.etag

        def stale(index: int, cell_id: protocol.CellId | None) -> EditConflict:
            return EditConflict(
                f"change {index} names a state the document no longer has",
                change=index,
                cell=None if cell_id is None else self._cells.get(cell_id),
                document=self._record,
            )

        for index, change in enumerate(changes):
            if isinstance(change, protocol.PutCell):
                source = _source(change.cell)
                cell_id = source.id
                if change.base_etag is None:
                    if cell_id in staged:
                        raise stale(index, cell_id)
                    order.insert(_slot(order, change, index), cell_id)
                elif cell_id not in staged or not matches(
                    change.base_etag, cell_id
                ):
                    raise stale(index, cell_id)
                staged[cell_id] = source
                touched[cell_id] = True
            elif isinstance(change, protocol.DeleteCell):
                if change.id not in staged or not matches(
                    change.base_etag, change.id
                ):
                    raise stale(index, change.id)
                del staged[change.id]
                order.remove(change.id)
                touched[change.id] = False
            elif isinstance(change, protocol.SetOrder):
                if change.base_etag not in ("*", before.order_etag):
                    raise stale(index, None)
                if sorted(change.order) != sorted(order) or len(
                    set(change.order)
                ) != len(change.order):
                    raise Invalid(
                        f"change {index} must name every cell exactly once"
                    )
                order = list(change.order)
            elif isinstance(change, protocol.SetAppConfig):
                if change.base_etag not in ("*", before.app_config_etag):
                    raise stale(index, None)
                app_config = dict(change.app_config)
                if self._normalizer is not None:
                    app_config = dict(self._normalizer(app_config))
            else:
                raise Invalid(f"change {index} has an unknown kind")

        changed = self.replace(
            [staged[cell_id] for cell_id in order], app_config
        )
        cells: dict[str, protocol.CellEtags | None] = {}
        for cell_id, put in touched.items():
            if put:
                cell = self._cells[cell_id]
                cells[cell_id] = protocol.CellEtags(
                    etag=cell.etag, code_hash=cell.code_hash
                )
            else:
                cells[cell_id] = None
        return Applied(changed, cells)

    def mark_saved(
        self, etag: protocol.Etag | None = None
    ) -> protocol.Document | None:
        """Record the persisted revision, which may precede the current one."""
        self._saved_etag = self._record.etag if etag is None else etag
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


def _source(cell: protocol.CellInput) -> CellSource:
    name = "_" if cell.name is UNSET else cell.name
    config = cell.config
    if config is UNSET:
        return CellSource(cell.id, cell.code, name)
    return CellSource(
        cell.id,
        cell.code,
        name,
        protocol.CellConfig(
            column=None if config.column is UNSET else config.column,
            disabled=False if config.disabled is UNSET else config.disabled,
            hide_code=False if config.hide_code is UNSET else config.hide_code,
            expand_output=False
            if config.expand_output is UNSET
            else config.expand_output,
        ),
    )


def _slot(
    order: list[protocol.CellId], change: protocol.PutCell, index: int
) -> int:
    """Where a created cell goes: after or before an anchor, or at the end."""
    after = None if change.after is UNSET else change.after
    before = None if change.before is UNSET else change.before
    if after is not None and before is not None:
        raise Invalid(f"change {index} names both after and before")
    anchor = after if after is not None else before
    if anchor is None:
        return len(order)
    if anchor not in order:
        raise Invalid(
            f"change {index} places a cell by {anchor}, which does not exist"
        )
    return order.index(anchor) + (1 if after is not None else 0)
