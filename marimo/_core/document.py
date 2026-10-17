# Copyright 2026 Marimo. All rights reserved.
"""Notebook cells, order, configuration, and revisions.

A document is the notebook's content at one revision. It does not
change. Editing it returns the next document. The notebook holds the
current one.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from msgspec import UNSET

from marimo._core import protocol
from marimo._core.errors import Invalid

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping, Sequence


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


def normalize_code(code: str) -> str:
    """Convert line endings to newlines."""
    return code.replace("\r\n", "\n").replace("\r", "\n")


def default_config() -> protocol.CellConfig:
    return protocol.CellConfig(
        column=None, disabled=False, hide_code=False, expand_output=False
    )


@dataclass(frozen=True)
class DocumentCell:
    """A cell and the hashes of its content.

    Line endings are normalized to newlines and the hashes computed when
    the cell is built, so they always match the content.
    """

    id: protocol.CellId
    code: str
    name: str = "_"
    config: protocol.CellConfig = field(default_factory=default_config)
    etag: protocol.Etag = field(init=False)
    """Identifies code, name, and config together."""
    code_hash: protocol.Etag = field(init=False)
    """Identifies the code alone."""

    def __post_init__(self) -> None:
        code = normalize_code(self.code)
        hashed = code_hash(code)
        object.__setattr__(self, "code", code)
        object.__setattr__(self, "code_hash", hashed)
        object.__setattr__(
            self, "etag", cell_etag(hashed, self.name, self.config)
        )


@dataclass(frozen=True)
class Changed:
    """Changed cells, removed cell IDs, and the new revision."""

    cells: list[DocumentCell]
    """New cells, and cells whose etag changed."""
    removed: list[protocol.CellId]
    """Ids of cells that no longer exist."""
    etag: protocol.Etag | None
    """The document's etag, when it changed."""

    def __bool__(self) -> bool:
        return bool(self.cells or self.removed or self.etag)


@dataclass(frozen=True)
class Applied:
    """An edit's effects and the etags of the cells it touched."""

    changed: Changed
    cells: dict[protocol.CellId, protocol.CellEtags | None]
    """By id, for each cell the edit put, and `None` for each it deleted."""


@dataclass(frozen=True)
class Stale:
    """An edit named a state the document no longer has. Nothing applied."""

    change: int
    """The index of the first stale change."""
    cell_id: protocol.CellId | None
    """The cell that change named, if it named one."""


class Document:
    """The notebook's content at one revision.

    Documents with the same etag are equal. Cell IDs must be unique.
    """

    __slots__ = (
        "_app_config",
        "_app_config_etag",
        "_cells",
        "_etag",
        "_order_etag",
    )

    def __init__(
        self, cells: Iterable[DocumentCell], app_config: Mapping[str, Any]
    ) -> None:
        held: dict[protocol.CellId, DocumentCell] = {}
        for cell in cells:
            if cell.id in held:
                raise ValueError("cell ids must be unique within the notebook")
            held[cell.id] = cell
        plain = deepcopy(dict(app_config))
        self._cells = held
        self._app_config: Mapping[str, Any] = plain
        self._order_etag = order_etag(list(held))
        self._app_config_etag = app_config_etag(plain)
        self._etag = document_etag(
            self._order_etag,
            self._app_config_etag,
            [cell.etag for cell in held.values()],
        )

    @classmethod
    def restore(
        cls,
        document: protocol.Document,
        cells: Sequence[protocol.Cell],
    ) -> Document:
        """Rebuild a document from the records the notebook published.

        Cell identities, order, and revisions must agree.
        """
        by_id = {cell.id: cell for cell in cells}
        if len(by_id) != len(cells) or (
            len(set(document.order)) != len(document.order)
            or set(document.order) != set(by_id)
        ):
            raise ValueError(
                "document order must contain every cell exactly once"
            )
        if any(cell.notebook_id != document.notebook_id for cell in cells):
            raise ValueError("cells must belong to the document")
        restored = cls(
            [
                DocumentCell(cell.id, cell.code, cell.name, cell.config)
                for cell in (by_id[cell_id] for cell_id in document.order)
            ],
            document.app_config,
        )
        for cell in restored:
            original = by_id[cell.id]
            if (
                cell.etag != original.etag
                or cell.code_hash != original.code_hash
            ):
                raise ValueError("cell revisions must match their content")
        if (
            restored.etag != document.etag
            or restored.order_etag != document.order_etag
            or restored.app_config_etag != document.app_config_etag
        ):
            raise ValueError("document revisions must match its content")
        return restored

    # ---- reading --------------------------------------------------------

    def __iter__(self) -> Iterator[DocumentCell]:
        """Iterate over cells in document order."""
        return iter(self._cells.values())

    def cell(self, cell_id: protocol.CellId) -> DocumentCell | None:
        return self._cells.get(cell_id)

    @property
    def etag(self) -> protocol.Etag:
        """Identifies cells, order, and app config together."""
        return self._etag

    @property
    def order_etag(self) -> protocol.Etag:
        return self._order_etag

    @property
    def app_config_etag(self) -> protocol.Etag:
        return self._app_config_etag

    @property
    def app_config(self) -> Mapping[str, Any]:
        """The app config. Treat this mapping and nested values as read-only."""
        return self._app_config

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Document) and other._etag == self._etag

    def __hash__(self) -> int:
        return hash(self._etag)

    def __repr__(self) -> str:
        return f"Document(etag={self._etag!r}, cells={len(self._cells)})"

    # ---- producing the next revision ------------------------------------

    def replace(
        self, cells: Iterable[DocumentCell], app_config: Mapping[str, Any]
    ) -> tuple[Document, Changed]:
        """The document with these cells and config, and what changed."""
        document = Document(cells, app_config)
        changed = [
            cell for cell in document if self._cells.get(cell.id) != cell
        ]
        removed = [
            cell_id
            for cell_id in self._cells
            if cell_id not in document._cells
        ]
        revised = None if document._etag == self._etag else document._etag
        return document, Changed(changed, removed, revised)

    def apply(
        self, changes: Sequence[protocol.Change]
    ) -> tuple[Document, Applied] | Stale:
        """Apply `changes` in order as one unit, or none of them.

        Preconditions are checked against this document, so one request
        can create a cell and then place it with the order etag the
        client read. A stale precondition returns `Stale`.

        Raises:
            Invalid: If a change could not apply to any state.
        """
        staged: dict[protocol.CellId, DocumentCell] = dict(self._cells)
        order: list[protocol.CellId] = list(self._cells)
        touched: dict[protocol.CellId, bool] = {}

        def matches(base: str, cell_id: protocol.CellId) -> bool:
            if base == "*":
                return True
            current = self._cells.get(cell_id)
            return current is not None and base == current.etag

        for index, change in enumerate(changes):
            if isinstance(change, protocol.PutCell):
                cell = _cell(change.cell)
                if change.base_etag is None:
                    # A cell deleted earlier in the batch still existed
                    # when the client read, so creating it is a conflict.
                    if cell.id in self._cells or cell.id in staged:
                        return Stale(index, cell.id)
                    order.insert(_slot(order, change, index), cell.id)
                elif cell.id not in staged or not matches(
                    change.base_etag, cell.id
                ):
                    return Stale(index, cell.id)
                staged[cell.id] = cell
                touched[cell.id] = True
            elif isinstance(change, protocol.DeleteCell):
                if change.id not in staged or not matches(
                    change.base_etag, change.id
                ):
                    return Stale(index, change.id)
                del staged[change.id]
                order.remove(change.id)
                touched[change.id] = False
            elif isinstance(change, protocol.SetOrder):
                if change.base_etag not in ("*", self._order_etag):
                    return Stale(index, None)
                if sorted(change.order) != sorted(order) or len(
                    set(change.order)
                ) != len(change.order):
                    raise Invalid(
                        f"change {index} must name every cell exactly once"
                    )
                order = [*change.order]
            else:
                raise Invalid(f"change {index} has an unknown kind")

        document, changed = self.replace(
            [staged[cell_id] for cell_id in order], self._app_config
        )
        cells: dict[protocol.CellId, protocol.CellEtags | None] = {}
        for cell_id, put in touched.items():
            if put:
                cell = document._cells[cell_id]
                cells[cell_id] = protocol.CellEtags(
                    etag=cell.etag, code_hash=cell.code_hash
                )
            else:
                cells[cell_id] = None
        return document, Applied(changed, cells)


def _cell(cell: protocol.CellInput) -> DocumentCell:
    """The cell a client's input describes, with unset fields defaulted."""
    name = "_" if cell.name is UNSET else cell.name
    config = cell.config
    if config is UNSET:
        return DocumentCell(cell.id, cell.code, name)
    return DocumentCell(
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
