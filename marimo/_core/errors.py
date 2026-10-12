# Copyright 2026 Marimo. All rights reserved.
"""Exceptions raised by host and notebook commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from marimo._core import protocol


class HostError(Exception):
    """Base exception for host and notebook commands."""


class NotFound(HostError):
    """The requested object does not exist."""


class Conflict(HostError):
    """The command cannot run in the current state."""


class NoRuntime(Conflict):
    """The command requires a runtime, but the notebook has none."""


class Invalid(HostError):
    """The request could not apply to any state."""


class EditConflict(Conflict):
    """A change named a state the document no longer has.

    Carries the index of the first stale change, the cell it named as it
    now is, and the document as it now is.
    """

    def __init__(
        self,
        message: str,
        *,
        change: int,
        cell: protocol.Cell | None,
        document: protocol.Document,
    ) -> None:
        super().__init__(message)
        self.change = change
        self.cell = cell
        self.document = document
