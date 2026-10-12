# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import contextlib
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from marimo import _loggers
from marimo._messaging.context import (
    http_request_context,
    run_id_context,
)
from marimo._messaging.notebook.document import (
    NotebookDocument,
    notebook_document_context,
)
from marimo._messaging.notebook.outputs import notebook_outputs_context
from marimo._messaging.notification import (
    CompletedRunNotification,
    FunctionCallResultNotification,
)
from marimo._messaging.notification_utils import broadcast_notification
from marimo._plugins.ui._impl.anywidget.init import WIDGET_COMM_MANAGER
from marimo._runtime.commands import (
    CreateNotebookCommand,
    DebugCellCommand,
    DeleteCellCommand,
    ExecuteCellsCommand,
    ExecuteScratchpadCommand,
    ExecuteStaleCellsCommand,
    InvokeFunctionCommand,
    ModelCommand,
    RenameNotebookCommand,
    StopKernelCommand,
    SyncGraphCommand,
    UpdateCellConfigCommand,
    UpdateUIElementCommand,
    UpdateUserConfigCommand,
)
from marimo._runtime.context import safe_get_context
from marimo._runtime.context.kernel_context import KernelRuntimeContext
from marimo._runtime.redirect_streams import stdin_context
from marimo._types.ids import UIElementId

if TYPE_CHECKING:
    from collections.abc import Iterator

    from marimo._runtime.request_router import RequestRouter
    from marimo._runtime.runtime import Kernel

LOGGER = _loggers.marimo_logger()


@dataclass
class _CommandCycle:
    run_id: str
    owner: asyncio.Task[object] | None
    active: bool = True
    outcome: Literal["succeeded", "failed", "interrupted"] = "succeeded"
    error: str | None = None


_COMMAND_CYCLE: ContextVar[_CommandCycle | None] = ContextVar(
    "command_cycle", default=None
)


class KernelRequestHandlers:
    """Kernel-owned command handlers.

    These handlers wrap kernel methods with cross-cutting concerns
    (request context, completion notifications) before delegating.
    """

    def __init__(self, kernel: Kernel) -> None:
        self._kernel = kernel

    def register(self, router: RequestRouter) -> None:
        router.register(CreateNotebookCommand, self._handle_instantiate)
        router.register(DeleteCellCommand, self._handle_delete_cell)
        router.register(ExecuteCellsCommand, self._handle_execute_multiple)
        router.register(SyncGraphCommand, self._handle_sync_graph)
        router.register(
            ExecuteScratchpadCommand, self._handle_execute_scratchpad
        )
        router.register(ExecuteStaleCellsCommand, self._handle_execute_stale)
        router.register(InvokeFunctionCommand, self._handle_function_call)
        router.register(DebugCellCommand, self._handle_pdb_request)
        router.register(RenameNotebookCommand, self._handle_rename)
        router.register(UpdateCellConfigCommand, self._handle_cell_config)
        router.register(
            UpdateUIElementCommand, self._handle_set_ui_element_value
        )
        router.register(ModelCommand, self._handle_receive_model_message)
        router.register(UpdateUserConfigCommand, self._handle_set_user_config)
        router.register(StopKernelCommand, self._handle_stop)

    @contextlib.contextmanager
    def _run_context(self, run_id: str | None = None) -> Iterator[None]:
        """Own one command's propagation through its final notification."""
        parent = _COMMAND_CYCLE.get()
        owner = asyncio.current_task()
        runtime_context = safe_get_context()
        scheduler = (
            runtime_context.active_scheduler
            if isinstance(runtime_context, KernelRuntimeContext)
            else None
        )
        # Copied context is provenance, not ownership. Only this task and
        # evaluations awaited by the reactive scheduler can extend the cycle.
        if (
            parent is not None
            and parent.active
            and (
                parent.owner is owner
                or scheduler is not None
                and scheduler.owns_task(owner)
            )
        ):
            cycle, nested = parent, True
            context = run_id_context(parent.run_id)
        else:
            context = run_id_context(run_id)
            cycle, nested = _CommandCycle(context.run_id, owner), False
        token = _COMMAND_CYCLE.set(cycle)
        try:
            with context:
                try:
                    yield
                except BaseException as exc:
                    if isinstance(
                        exc, (KeyboardInterrupt, asyncio.CancelledError)
                    ):
                        cycle.outcome = "interrupted"
                    elif cycle.outcome != "interrupted":
                        cycle.outcome = "failed"
                    cycle.error = str(exc) or type(exc).__name__
                    raise
                finally:
                    if not nested:
                        cycle.active = False
                        self._kernel.stream.flush_console()
                        broadcast_notification(
                            CompletedRunNotification(
                                run_id=cycle.run_id,
                                outcome=cycle.outcome,
                                error=cycle.error,
                            )
                        )
        finally:
            _COMMAND_CYCLE.reset(token)

    async def _handle_delete_cell(self, request: DeleteCellCommand) -> None:
        with self._run_context():
            await self._kernel.delete_cell(request)

    async def _handle_cell_config(
        self, request: UpdateCellConfigCommand
    ) -> None:
        with self._run_context():
            await self._kernel.set_cell_config(request)

    async def _handle_instantiate(
        self, request: CreateNotebookCommand
    ) -> None:
        with self._run_context(), http_request_context(request.request):
            await self._kernel.instantiate(request)

    async def _handle_execute_multiple(
        self, request: ExecuteCellsCommand
    ) -> None:
        with (
            self._run_context(request.run_id),
            http_request_context(request.request),
        ):
            await self._kernel.run(request.execution_requests)

    async def _handle_sync_graph(self, request: SyncGraphCommand) -> None:
        with self._run_context(), http_request_context(None):
            await self._kernel.sync_graph(
                request.cells, request.run_ids, request.delete_ids
            )

    async def _handle_execute_scratchpad(
        self, request: ExecuteScratchpadCommand
    ) -> None:
        doc = (
            NotebookDocument(list(request.notebook_cells))
            if request.notebook_cells is not None
            else None
        )
        with (
            self._run_context(request.run_id),
            stdin_context(request.allow_stdin),
            notebook_document_context(doc),
            notebook_outputs_context(request.cell_outputs),
            http_request_context(request.request),
        ):
            await self._kernel.run_scratchpad(request.code)

    async def _handle_execute_stale(
        self, request: ExecuteStaleCellsCommand
    ) -> None:
        with self._run_context(), http_request_context(request.request):
            await self._kernel.run_stale_cells()

    async def _handle_set_ui_element_value(
        self, request: UpdateUIElementCommand
    ) -> None:
        with self._run_context(), http_request_context(request.request):
            await self._kernel.set_ui_element_value(
                request, notify_frontend=False
            )

    async def _handle_pdb_request(self, request: DebugCellCommand) -> None:
        await self._kernel.pdb_request(request.cell_id)

    async def _handle_rename(self, request: RenameNotebookCommand) -> None:
        with self._run_context():
            await self._kernel.rename_file(request.filename)

    async def _handle_receive_model_message(
        self, request: ModelCommand
    ) -> None:
        with self._run_context():
            ui_element_id, state = WIDGET_COMM_MANAGER.receive_comm_message(
                request
            )

            # Directly handle the UI element update instead of
            # re-enqueuing it as a separate command. Re-enqueuing
            # caused Model+UI interleaving that the batch merger
            # couldn't collapse (different types), leading to every
            # drag tick getting its own full cell re-execution.
            if ui_element_id and state:
                await self._kernel.set_ui_element_value(
                    UpdateUIElementCommand.from_ids_and_values(
                        [(UIElementId(ui_element_id), state)]
                    ),
                    notify_frontend=False,
                )
            elif self._kernel.state_updates:
                # Callbacks during message processing (e.g. widget observe
                # handlers) may have called mo.state setters. Process
                # those pending state updates now.
                await self._kernel._run_cells(set())

    async def _handle_function_call(
        self, request: InvokeFunctionCommand
    ) -> None:
        with self._run_context():
            status, ret, found = await self._kernel.function_call_request(
                request
            )
            LOGGER.debug("Function returned with status %s", status)
            broadcast_notification(
                FunctionCallResultNotification(
                    function_call_id=request.function_call_id,
                    return_value=ret,
                    status=status,
                    found=found,
                ),
            )

    async def _handle_set_user_config(
        self, request: UpdateUserConfigCommand
    ) -> None:
        self._kernel.set_user_config(request)

    async def _handle_stop(self, request: StopKernelCommand) -> None:
        del request
        return
