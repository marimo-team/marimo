# Copyright 2026 Marimo. All rights reserved.
"""Document analysis for the host API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from marimo._core import protocol

if TYPE_CHECKING:
    from collections.abc import Mapping


class Analyzer(Protocol):
    """Analysis of a document's cells.

    `analyze` returns without waiting. The implementation reports the
    result through `Notebook.observe` as an `Analyzed` naming the same
    revision. The notebook requests one revision at a time.
    """

    def analyze(
        self, document_etag: protocol.Etag, codes: Mapping[str, str]
    ) -> None:
        """Analyze the cells' code, keyed by id in document order."""


@dataclass(frozen=True)
class Analyzed:
    """The analysis of one document revision.

    `cells` is null when the analyzer could not analyze the revision.
    """

    document_etag: protocol.Etag
    cells: Mapping[str, protocol.CellAnalysis] | None
