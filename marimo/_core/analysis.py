# Copyright 2026 Marimo. All rights reserved.
"""Document analysis for the host API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from marimo._core import protocol

if TYPE_CHECKING:
    from collections.abc import Mapping

    from marimo._core.document import Document


class Analyzer(Protocol):
    """Analysis of a document's cells.

    One instance belongs to one notebook. Calls are serialized, allowing
    implementations to cache compilation by cell ID and code hash.
    Results cover every cell in the document, including syntax errors.
    Unexpected failures raise; they are not document diagnostics.

    Implementations must keep the event loop responsive. After cancelling
    a call, the notebook retires the instance: worker code may still run.
    """

    async def analyze(
        self, document: Document
    ) -> Mapping[protocol.CellId, protocol.CellAnalysis]:
        """Analyze one revision of the document."""
