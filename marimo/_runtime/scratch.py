# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING

from marimo._core.document import Document
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from collections.abc import Iterator

SCRATCH_CELL_ID = CellId_t("__scratch__")


@dataclass
class ScratchpadDocument:
    """Latest accepted source, shared by contexts in one scratch execution."""

    document: Document


_current_document: ContextVar[ScratchpadDocument | None] = ContextVar(
    "_current_document", default=None
)


def get_current_document() -> ScratchpadDocument | None:
    return _current_document.get()


@contextmanager
def notebook_document_context(document: Document | None) -> Iterator[None]:
    token = _current_document.set(
        ScratchpadDocument(document) if document is not None else None
    )
    try:
        yield
    finally:
        _current_document.reset(token)
