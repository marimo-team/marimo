# Copyright 2026 Marimo. All rights reserved.
"""Retry receipts and problems shared by every transport."""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from time import monotonic
from typing import TYPE_CHECKING, Protocol

import msgspec

from marimo._core import protocol
from marimo._core.errors import (
    Conflict,
    DecisionRequired,
    EditConflict,
    Forbidden,
    HostError,
    Invalid,
    NoRuntime,
    NotFound,
    Unsupported,
)
from marimo._core.host import Host
from marimo._core.stream import RoutedEvent

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping, Sequence

Reply = tuple[int, msgspec.Struct | None]
"""A status and body, for a transport to encode."""


class NotebookBridge(Protocol):
    @property
    def host(self) -> Host: ...

    async def edit(
        self,
        notebook_id: str,
        changes: Sequence[protocol.Change],
        *,
        request_id: str,
    ) -> protocol.EditResponse: ...

    async def save(
        self,
        notebook_id: str,
        *,
        if_match: Sequence[str] | None,
        decisions: Mapping[str, str],
        request_id: str,
    ) -> protocol.EditResponse: ...


_TITLES = {
    "invalid-request": "Invalid request",
    "unauthorized": "Unauthorized",
    "forbidden": "Forbidden",
    "not-found": "Not found",
    "method-not-allowed": "Method not allowed",
    "conflict": "Conflict",
    "no-runtime": "No runtime",
    "decision-required": "Decision required",
    "unsupported-operation": "Unsupported operation",
    "internal": "Internal error",
}


def problem(
    status: int,
    kind: str,
    detail: str | None = None,
    *,
    edit: protocol.EditConflict | None = None,
    decisions: tuple[protocol.Decision, ...] | None = None,
) -> protocol.Problem:
    return protocol.Problem(
        type="tag:marimo.io,2026:host/" + kind,
        title=_TITLES[kind],
        status=status,
        detail=msgspec.UNSET if detail is None else detail,
        edit=msgspec.UNSET if edit is None else edit,
        decisions=msgspec.UNSET if decisions is None else decisions,
    )


def problem_for(error: HostError) -> protocol.Problem:
    """Describe a failed command the same way on every transport."""
    detail = str(error)
    match error:
        case NoRuntime():
            return problem(409, "no-runtime", detail)
        case DecisionRequired():
            return problem(
                409, "decision-required", detail, decisions=error.decisions
            )
        case EditConflict():
            return problem(
                409,
                "conflict",
                detail,
                edit=protocol.EditConflict(
                    change=error.change,
                    cell=error.cell,
                    document=error.document,
                ),
            )
        case Conflict():
            return problem(409, "conflict", detail)
        case Invalid():
            return problem(400, "invalid-request", detail)
        case NotFound():
            return problem(404, "not-found", detail)
        case Forbidden():
            return problem(403, "forbidden", detail)
        case Unsupported():
            return problem(501, "unsupported-operation", detail)
    return problem(500, "internal", "The host failed")


@dataclass
class CachedMutation:
    """An accepted request, including its in-flight or completed result."""

    fingerprint: str
    task: asyncio.Future[Reply]
    run: protocol.Run | None = None
    expires_at: float | None = None


class Mutations:
    """Share capability checks and retry semantics across all host mutations."""

    def __init__(
        self,
        host: Host,
        *,
        receipt_seconds: float = 300.0,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self.host = host
        # A receipt covers a client's retry loop after a lost response, so it
        # outlasts retry backoff rather than a person's absence.
        self.receipt_seconds = receipt_seconds
        self.clock = clock
        self.replies: dict[str, CachedMutation] = {}

    def remembered(self, key: str) -> CachedMutation | None:
        """Return the receipt for a key, dropping it if it has expired."""
        reply = self.replies.get(key)
        if reply is not None and self._expired(reply):
            del self.replies[key]
            return None
        return reply

    def settle(self, mutation: CachedMutation) -> None:
        """Start the receipt's retention window once its work is complete."""
        mutation.expires_at = self.clock() + self.receipt_seconds

    def expire(self) -> None:
        """Sweep expired receipts and the host's results."""
        self.host.expire()
        for key, reply in list(self.replies.items()):
            if self._expired(reply):
                del self.replies[key]

    def _expired(self, reply: CachedMutation) -> bool:
        return (
            reply.expires_at is not None and self.clock() >= reply.expires_at
        )

    async def execute(
        self,
        operation: str,
        *,
        notebook_id: str | None,
        key: str,
        payload: object,
        call: Callable[[], Awaitable[Reply]],
    ) -> Reply:
        """Run `call` once per idempotency key, and answer retries with its reply."""
        capability = (
            "runtime.run" if operation == "runtime.interrupt" else operation
        )
        if capability not in self.host.operations:
            raise Unsupported(f"This host does not offer {capability}")
        record = self.host.notebooks.get(notebook_id) if notebook_id else None
        if record is not None and capability not in record.operations:
            raise Forbidden(f"This notebook does not allow {capability}")
        if not key:
            raise Invalid("Idempotency-Key is required")
        fingerprint = hashlib.sha256(
            msgspec.json.encode((operation, notebook_id, payload))
        ).hexdigest()
        remembered = self.remembered(key)
        if remembered is not None:
            if remembered.fingerprint != fingerprint:
                raise Conflict(
                    f"Idempotency-Key {key} was used for another request"
                )
            reply = await asyncio.shield(remembered.task)
            # A retried run answers with the run as it is now.
            return reply if remembered.run is None else (202, remembered.run)

        task = asyncio.ensure_future(call())
        mutation = CachedMutation(fingerprint, task)
        self.replies[key] = mutation
        unsubscribe: Callable[[], None] | None = None
        lifecycle_accepted: Callable[[Reply], None] | None = None
        if operation == "runtime.run":
            # Retain the latest run without retaining its output payloads.
            def updated(event: RoutedEvent) -> None:
                if isinstance(event.event, protocol.RunEvent):
                    run = event.event.data.run
                    if event.event.data.request_id == key:
                        mutation.run = run
                        if (
                            run.status == "completed"
                            and unsubscribe is not None
                        ):
                            self.settle(mutation)
                            unsubscribe()

            unsubscribe = self.host.subscribe(
                updated, notebook_id=notebook_id, types={"run"}
            )
        elif operation in {"runtime.start", "runtime.stop", "runtime.restart"}:
            if notebook_id is None:
                raise RuntimeError("Notebook ID is required")
            lifecycle_accepted, unsubscribe = _watch_lifecycle(
                self,
                mutation,
                operation=operation,
                notebook_id=notebook_id,
                request_id=key,
            )

        def completed(task: asyncio.Future[Reply]) -> None:
            if task.cancelled() or task.exception() is not None:
                self.replies.pop(key, None)
                if unsubscribe is not None:
                    unsubscribe()
            elif lifecycle_accepted is not None:
                lifecycle_accepted(task.result())
            elif mutation.expires_at is None and (
                mutation.run is None or mutation.run.status == "completed"
            ):
                self.settle(mutation)

        task.add_done_callback(completed)
        # A disconnected waiter must not cancel a shared mutation.
        return await asyncio.shield(task)


def _watch_lifecycle(
    context: Mutations,
    mutation: CachedMutation,
    *,
    operation: str,
    notebook_id: str,
    request_id: str,
) -> tuple[Callable[[Reply], None], Callable[[], None]]:
    runtime_id: protocol.RuntimeId | None = None
    previous_id: protocol.RuntimeId | None = None
    early: list[RoutedEvent] = []

    def settle() -> None:
        context.settle(mutation)
        unsubscribe()

    def updated(event: RoutedEvent) -> None:
        nonlocal previous_id
        if mutation.expires_at is not None:
            return
        if runtime_id is None:
            # A backend can finish synchronously, before the response exists.
            early.append(event)
            return
        if isinstance(event.event, protocol.NotebookRemovedEvent):
            settle()
        elif isinstance(event.event, protocol.RuntimeEvent):
            runtime = event.event.data.runtime
            if (
                operation == "runtime.restart"
                and event.event.data.request_id == request_id
                and runtime.status == "terminating"
                and runtime.id != runtime_id
            ):
                previous_id = runtime.id
            if (
                operation != "runtime.stop"
                and runtime.id == runtime_id
                and runtime.status in ("running", "failed")
            ):
                settle()
        elif isinstance(event.event, protocol.RuntimeRemovedEvent):
            if event.event.data.id == runtime_id or (
                event.event.data.id == previous_id
                and event.event.data.request_id != request_id
            ):
                # A later stop can cancel a restart before its replacement starts.
                settle()

    unsubscribe = context.host.subscribe(
        updated, notebook_id=notebook_id, types={"runtime", "notebook"}
    )

    def accepted(reply: Reply) -> None:
        nonlocal runtime_id
        match reply:
            # A 202 changes a runtime, and a 200 found the one already running.
            case (202, protocol.Runtime(id=accepted_id)):
                runtime_id = accepted_id
                for event in early:
                    updated(event)
            case _:
                settle()
        early.clear()

    return accepted, unsubscribe
