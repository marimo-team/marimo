# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypeVar

if TYPE_CHECKING:
    from marimo._runtime import commands

T = TypeVar("T")


class QueueType(Protocol[T]):
    """
    Minimal queue protocol used by Marimo.

    Defines the common subset of methods shared by `multiprocessing.Queue` and
    `queue.Queue` that Marimo depends on. Keeping this protocol minimal makes it
    straightforward to stub in `marimo-lsp` and to substitute alternative queue
    implementations (e.g., wrapping a ZeroMQ socket).

    If additional queue behavior becomes necessary, expand this protocol so that
    stubs and implementations stay aligned.
    """

    def get(self, block: bool = True, timeout: float | None = None) -> T: ...
    def put(
        self, obj: T, /, block: bool = True, timeout: float | None = None
    ) -> None: ...
    def get_nowait(self) -> T: ...
    def put_nowait(self, item: T, /) -> None: ...
    def empty(self) -> bool: ...


def route_control_request(
    request: commands.CommandMessage,
    control_queue: QueueType[commands.CommandMessage],
    completion_queue: QueueType[commands.CodeCompletionCommand],
    ui_element_queue: QueueType[commands.BatchableCommand],
) -> None:
    """Route a control request to the appropriate queue(s).

    - CodeCompletionCommand → completion_queue only
    - UpdateUIElementCommand / ModelCommand → control_queue + ui_element_queue
    - Everything else → control_queue only
    """
    from marimo._runtime import commands

    if isinstance(request, commands.CodeCompletionCommand):
        completion_queue.put(request)
        return

    control_queue.put(request)
    if isinstance(
        request,
        (commands.UpdateUIElementCommand, commands.ModelCommand),
    ):
        ui_element_queue.put(request)


class ProcessLike(Protocol):
    """Protocol for process-like objects."""

    @property
    def pid(self) -> int | None: ...

    def is_alive(self) -> bool: ...

    def terminate(self) -> None: ...

    def join(self, timeout: float | None = None) -> None: ...
