# Copyright 2026 Marimo. All rights reserved.
"""Document requests exchanged by a kernel and its host."""

from __future__ import annotations

from typing import Any, ClassVar

import msgspec

from marimo._core import protocol
from marimo._core.document import Document, DocumentCell


class DocumentSnapshot(msgspec.Struct, frozen=True):
    cells: tuple[DocumentCell, ...]
    app_config: dict[str, Any]

    def document(self) -> Document:
        return Document(self.cells, self.app_config)


class DocumentRequest(
    msgspec.Struct, frozen=True, tag_field="op", tag="host-document-request"
):
    """Read or edit the notebook bound to a scratchpad execution.

    `for_run` checks pending updates before committing an edit-and-run batch.
    `applied_edits` names queued updates already applied inline by the kernel.
    """

    name: ClassVar[str] = "host-document-request"
    request_id: str
    changes: tuple[protocol.Change, ...] | None = None
    cells: tuple[protocol.RequestedCell, ...] = ()
    for_run: bool = False
    applied_edits: tuple[str, ...] = ()
