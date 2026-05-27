# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo import _loggers
from marimo._messaging.context import http_request_context
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
from marimo._types.ids import UIElementId

if TYPE_CHECKING:
    from marimo._runtime.request_router import RequestRouter
    from marimo._runtime.runtime import Kernel

LOGGER = _loggers.marimo_logger()


class KernelRequestHandlers:
    """Kernel-owned command handlers.

    These handlers wrap kernel methods with cross-cutting concerns
    (request context, completion notifications) before delegating.
    """

    def __init__(self, kernel: Kernel) -> None:
        self._kernel = kernel

    def register(self, router: RequestRouter) -> None:
        k = self._kernel
        router.register(CreateNotebookCommand, self._handle_instantiate)
        router.register(DeleteCellCommand, k.delete_cell)
        router.register(ExecuteCellsCommand, self._handle_execute_multiple)
        router.register(SyncGraphCommand, self._handle_sync_graph)
        router.register(
            ExecuteScratchpadCommand, self._handle_execute_scratchpad
        )
        router.register(ExecuteStaleCellsCommand, self._handle_execute_stale)
        router.register(InvokeFunctionCommand, self._handle_function_call)
        router.register(DebugCellCommand, self._handle_pdb_request)
        router.register(RenameNotebookCommand, self._handle_rename)
        router.register(UpdateCellConfigCommand, k.set_cell_config)
        router.register(
            UpdateUIElementCommand, self._handle_set_ui_element_value
        )
        router.register(ModelCommand, self._handle_receive_model_message)
        router.register(UpdateUserConfigCommand, self._handle_set_user_config)
        router.register(StopKernelCommand, self._handle_stop)

    async def _handle_instantiate(
        self, request: CreateNotebookCommand
    ) -> None:
        with http_request_context(request.request):
            await self._kernel.instantiate(request)
        broadcast_notification(CompletedRunNotification())

    async def _handle_execute_multiple(
        self, request: ExecuteCellsCommand
    ) -> None:
        with http_request_context(request.request):
            await self._kernel.run(request.execution_requests)
        broadcast_notification(CompletedRunNotification())

    async def _handle_sync_graph(self, request: SyncGraphCommand) -> None:
        with http_request_context(None):
            await self._kernel.sync_graph(
                request.cells, request.run_ids, request.delete_ids
            )
        broadcast_notification(CompletedRunNotification())

    async def _handle_execute_scratchpad(
        self, request: ExecuteScratchpadCommand
    ) -> None:
        doc = (
            NotebookDocument(list(request.notebook_cells))
            if request.notebook_cells is not None
            else None
        )
        try:
            with (
                notebook_document_context(doc),
                notebook_outputs_context(request.cell_outputs),
                http_request_context(request.request),
            ):
                await self._kernel.run_scratchpad(request.code)
        finally:
            # Always emit completion so a waiting ``ScratchCellListener``
            # doesn't block forever if ``run_scratchpad`` raises.
            broadcast_notification(
                CompletedRunNotification(run_id=request.run_id)
            )

    async def _handle_execute_stale(
        self, request: ExecuteStaleCellsCommand
    ) -> None:
        with http_request_context(request.request):
            await self._kernel.run_stale_cells()
        broadcast_notification(CompletedRunNotification())

    async def _handle_set_ui_element_value(
        self, request: UpdateUIElementCommand
    ) -> None:
        with http_request_context(request.request):
            await self._kernel.set_ui_element_value(
                request, notify_frontend=False
            )
        broadcast_notification(CompletedRunNotification())

    async def _handle_pdb_request(self, request: DebugCellCommand) -> None:
        await self._kernel.pdb_request(request.cell_id)

    async def _handle_rename(self, request: RenameNotebookCommand) -> None:
        await self._kernel.rename_file(request.filename)

    async def _handle_receive_model_message(
        self, request: ModelCommand
    ) -> None:
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
            broadcast_notification(CompletedRunNotification())
        elif self._kernel.state_updates:
            # Callbacks during message processing (e.g. widget observe
            # handlers) may have called mo.state setters. Process
            # those pending state updates now.
            await self._kernel._run_cells(set())
            broadcast_notification(CompletedRunNotification())

    async def _handle_function_call(
        self, request: InvokeFunctionCommand
    ) -> None:
        status, ret, _ = await self._kernel.function_call_request(request)
        LOGGER.debug("Function returned with status %s", status)
        broadcast_notification(
            FunctionCallResultNotification(
                function_call_id=request.function_call_id,
                return_value=ret,
                status=status,
            ),
        )

    async def _handle_set_user_config(
        self, request: UpdateUserConfigCommand
    ) -> None:
        self._kernel.set_user_config(request)

    async def _handle_stop(self, request: StopKernelCommand) -> None:
        del request
        return
