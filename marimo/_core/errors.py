# Copyright 2026 Marimo. All rights reserved.
"""Errors of host and notebook commands."""

from __future__ import annotations

from marimo._core import protocol


class HostError(Exception):
    """Base exception for host and notebook commands."""

    def problem(self) -> protocol.Problem:
        """The protocol's problem for this error."""
        return protocol.InternalProblem(detail="The host failed")


class NotFound(HostError):
    """The requested object does not exist."""

    def problem(self) -> protocol.NotFoundProblem:
        return protocol.NotFoundProblem(detail=str(self))


class Conflict(HostError):
    """The command cannot run in the current state."""

    def problem(self) -> protocol.ConflictProblem:
        return protocol.ConflictProblem(detail=str(self))


class NoRuntime(HostError):
    """The command requires a runtime, but the notebook has none."""

    def problem(self) -> protocol.NoRuntimeProblem:
        return protocol.NoRuntimeProblem(detail=str(self))


class Invalid(HostError):
    """The request could not apply to any state."""

    def problem(self) -> protocol.InvalidRequestProblem:
        return protocol.InvalidRequestProblem(detail=str(self))


class Forbidden(HostError):
    """The notebook does not allow the command."""

    def problem(self) -> protocol.ForbiddenProblem:
        return protocol.ForbiddenProblem(detail=str(self))


class Unsupported(HostError):
    """The host does not offer the command."""

    def problem(self) -> protocol.UnsupportedOperationProblem:
        return protocol.UnsupportedOperationProblem(detail=str(self))


class PreconditionFailed(HostError):
    """The request named a state the document no longer has.

    Carries the position of the first stale entry in the request, the
    cell it named as it now is, and the document as it now is.
    """

    def __init__(
        self,
        message: str,
        *,
        index: int,
        cell: protocol.Cell | None,
        document: protocol.Document,
    ) -> None:
        super().__init__(message)
        self.index = index
        self.cell = cell
        self.document = document

    def problem(self) -> protocol.PreconditionFailedProblem:
        return protocol.PreconditionFailedProblem(
            detail=str(self),
            index=self.index,
            cell=self.cell,
            document=self.document,
        )


class DecisionRequired(HostError):
    """The command needs a choice from the client before it can proceed.

    Carries the decisions to put to the client, which repeats the
    request with its answers.
    """

    def __init__(
        self, message: str, *, decisions: tuple[protocol.Decision, ...]
    ) -> None:
        super().__init__(message)
        self.decisions = decisions

    def problem(self) -> protocol.DecisionRequiredProblem:
        return protocol.DecisionRequiredProblem(
            detail=str(self), decisions=self.decisions
        )
