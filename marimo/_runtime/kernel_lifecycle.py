# Copyright 2026 Marimo. All rights reserved.
"""Kernel-startup primitives that don't depend on the hosting environment.

Environment-specific concerns (stream construction, signal handlers,
subprocess bootstrap, the outer task driver) stay at the call site.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, TypeVar

from marimo import _loggers
from marimo._runtime import patches
from marimo._runtime.commands import (
    ModelCommand,
    StopKernelCommand,
    UpdateUIElementCommand,
)
from marimo._runtime.context.kernel_context import (
    KernelRuntimeContext,
    initialize_kernel_context,
)
from marimo._runtime.context.types import teardown_context
from marimo._runtime.input_override import input_override
from marimo._runtime.runner.hooks import (
    NotebookCellHooks,
    Priority,
    create_default_hooks,
)
from marimo._runtime.utils.set_ui_element_request_manager import (
    SetUIElementRequestManager,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from marimo._ast.cell import CellConfig
    from marimo._config.config import MarimoConfig
    from marimo._messaging.types import Stderr, Stdin, Stdout, Stream
    from marimo._runtime import marimo_pdb
    from marimo._runtime.commands import (
        AppMetadata,
        BatchableCommand,
        CommandMessage,
    )
    from marimo._runtime.runtime import Kernel
    from marimo._runtime.virtual_file import VirtualFileStorageType
    from marimo._session.model import SessionMode
    from marimo._session.queue import QueueType
    from marimo._types.ids import CellId_t

    ControlQueue = QueueType[CommandMessage] | asyncio.Queue[CommandMessage]
    UIElementQueue = (
        QueueType[BatchableCommand] | asyncio.Queue[BatchableCommand]
    )

LOGGER = _loggers.marimo_logger()

# Lets each caller pin listen_messages and its reader to the same queue type
# (threading vs asyncio).
_Q = TypeVar("_Q")


def _build_hooks(
    is_edit_mode: bool, user_config: MarimoConfig
) -> NotebookCellHooks:
    from marimo._runtime.runner.hooks_post_execution import (
        attempt_pytest,
        broadcast_storage_backends,
        render_toplevel_defs,
    )

    hooks = create_default_hooks()
    if is_edit_mode and user_config["runtime"].get("reactive_tests", False):
        hooks.add_post_execution(attempt_pytest, Priority.LATE)
    if is_edit_mode:
        hooks.add_post_execution(render_toplevel_defs, Priority.LATE)
        hooks.add_post_execution(broadcast_storage_backends, Priority.LATE)
    return hooks


def create_kernel(
    *,
    stream: Stream,
    stdout: Stdout | None,
    stderr: Stderr | None,
    stdin: Stdin | None,
    debugger: marimo_pdb.MarimoPdb | None,
    configs: dict[CellId_t, CellConfig],
    app_metadata: AppMetadata,
    user_config: MarimoConfig,
    is_edit_mode: bool,
    control_queue: ControlQueue,
    set_ui_element_queue: UIElementQueue,
    virtual_file_storage: VirtualFileStorageType | None,
    mode: SessionMode,
    print_override_fn: Callable[[Any], None] | None,
) -> tuple[Kernel, KernelRuntimeContext]:
    # Run mode forces autorun and disables the module autoreloader.
    if not is_edit_mode:
        user_config = user_config.copy()
        user_config["runtime"]["on_cell_change"] = "autorun"
        user_config["runtime"]["auto_reload"] = "off"

    def _enqueue_control_request(req: CommandMessage) -> None:
        control_queue.put_nowait(req)
        if isinstance(req, (UpdateUIElementCommand, ModelCommand)):
            set_ui_element_queue.put_nowait(req)

    # Deferred to break the runtime.py <-> kernel_lifecycle.py import cycle.
    from marimo._runtime.runtime import Kernel

    kernel = Kernel(
        cell_configs=configs,
        app_metadata=app_metadata,
        stream=stream,
        stdout=stdout,
        stderr=stderr,
        stdin=stdin,
        module=patches.patch_main_module(
            file=app_metadata.filename,
            input_override=input_override,
            print_override=print_override_fn,
            doc=app_metadata.docstring,
        ),
        debugger_override=debugger,
        user_config=user_config,
        enqueue_control_request=_enqueue_control_request,
        hooks=_build_hooks(is_edit_mode, user_config),
    )
    ctx = initialize_kernel_context(
        kernel=kernel,
        stream=stream,
        stdout=stdout,
        stderr=stderr,
        virtual_file_storage=virtual_file_storage,
        mode=mode,
    )
    return kernel, ctx


async def threaded_queue_reader(
    queue: QueueType[CommandMessage],
) -> CommandMessage | None:
    # Offload the blocking get() so background asyncio tasks aren't starved.
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, queue.get)


async def asyncio_queue_reader(
    queue: asyncio.Queue[CommandMessage],
) -> CommandMessage | None:
    return await queue.get()


async def listen_messages(
    kernel: Kernel,
    control_queue: _Q,
    set_ui_element_queue: UIElementQueue,
    get_request: Callable[[_Q], Awaitable[CommandMessage | None]],
) -> None:
    """Run the kernel's control loop until `StopKernelCommand` is received.

    `get_request` adapts the queue-read mechanism so this loop can drive
    either a threading/multiprocessing queue or an `asyncio.Queue`.
    """
    ui_request_mgr = SetUIElementRequestManager(set_ui_element_queue)

    while True:
        try:
            request = await get_request(control_queue)
        except Exception as e:
            # triggered on Windows when quit with Ctrl+C
            LOGGER.debug("kernel queue.get() failed %s", e)
            return

        if request is None:
            continue
        LOGGER.debug("Received control request: %s", type(request).__name__)
        if isinstance(request, StopKernelCommand):
            return

        merged: list[CommandMessage]
        if isinstance(request, (UpdateUIElementCommand, ModelCommand)):
            merged = list(ui_request_mgr.process_request(request))
        else:
            merged = [request]

        for r in merged:
            try:
                await kernel.handle_message(r)
            except Exception:
                LOGGER.exception(
                    "Failed to handle control request: %s",
                    type(r).__name__,
                )


def teardown_kernel(kernel: Kernel, ctx: KernelRuntimeContext) -> None:
    # Defensively shut down registries in case a leak prevents context
    # destruction from cleaning them up.
    ctx.virtual_file_registry.shutdown()
    ctx.app_kernel_runner_registry.shutdown()
    teardown_context()
    kernel.teardown()
