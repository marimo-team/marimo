# Copyright 2026 Marimo. All rights reserved.
"""Test-flavored wrapper around production `kernel_session()`.

Tests use `mocked_kernel_session()` as a context manager to get a fully wired
kernel with mock streams, sensible default config, and automatic teardown.
"""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import sys
from typing import TYPE_CHECKING

from marimo._config.config import DEFAULT_CONFIG
from marimo._messaging.print_override import print_override
from marimo._runtime.kernel_lifecycle import KernelArgs, kernel_session
from marimo._runtime.marimo_pdb import MarimoPdb
from marimo._runtime.virtual_file import VirtualFileStorageType
from marimo._session.model import SessionMode
from tests._runtime._helpers.factories import default_app_metadata
from tests._runtime._helpers.streams import (
    MockStderr,
    MockStdin,
    MockStdout,
    MockStream,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from marimo._ast.cell import CellConfig
    from marimo._config.config import ExecutionType, MarimoConfig
    from marimo._runtime.commands import AppMetadata
    from marimo._runtime.context.kernel_context import KernelRuntimeContext
    from marimo._runtime.runtime import Kernel
    from marimo._types.ids import CellId_t


@dataclasses.dataclass
class TestKernel:
    """A live kernel + its mocked I/O surface, bound for the test's lifetime."""

    kernel: Kernel
    ctx: KernelRuntimeContext
    stream: MockStream
    stdout: MockStdout
    stderr: MockStderr
    stdin: MockStdin


@contextlib.contextmanager
def mocked_kernel_session(
    *,
    app_metadata: AppMetadata | None = None,
    user_config: MarimoConfig | None = None,
    configs: dict[CellId_t, CellConfig] | None = None,
    mode: SessionMode = SessionMode.EDIT,
    execution_type: ExecutionType | None = None,
    reactive_mode: str | None = None,
    with_debugger: bool = True,
) -> Iterator[TestKernel]:
    """Yield a fully wired `TestKernel`; tear it down on exit.

    Wraps production `kernel_session()` and supplies test defaults: mock
    streams, dummy queues (the kernel doesn't drive a real loop here), an
    optional in-process debugger, and edit-mode by default. Restores
    `sys.modules["__main__"]` on exit since `patch_main_module` swaps it.
    """
    stream = MockStream()
    stdout = MockStdout(stream)
    stderr = MockStderr(stream)
    stdin = MockStdin(stream)
    debugger = MarimoPdb(stdout=stdout, stdin=stdin) if with_debugger else None

    saved_main = sys.modules.get("__main__")
    # Kernel.teardown() clears the kernel module's __dict__, which breaks
    # any sys.meta_path entries installed by patches.patch_micropip (their
    # closures reference module globals) for subsequent tests.
    saved_meta_path = sys.meta_path[:]
    virtual_file_storage: VirtualFileStorageType = (
        "shared_memory" if mode == SessionMode.EDIT else "in_memory"
    )

    args = KernelArgs(
        stream=stream,
        stdout=stdout,
        stderr=stderr,
        stdin=stdin,
        debugger=debugger,
        configs=configs or {},
        app_metadata=app_metadata or default_app_metadata(),
        user_config=user_config or DEFAULT_CONFIG,
        mode=mode,
        control_queue=asyncio.Queue(),
        set_ui_element_queue=asyncio.Queue(),
        virtual_file_storage=virtual_file_storage,
        print_override_fn=print_override,
    )

    try:
        with kernel_session(args) as (kernel, ctx):
            if execution_type is not None:
                kernel.execution_type = execution_type
            if reactive_mode is not None:
                kernel.reactive_execution_mode = reactive_mode  # type: ignore[assignment]
            yield TestKernel(
                kernel=kernel,
                ctx=ctx,
                stream=stream,
                stdout=stdout,
                stderr=stderr,
                stdin=stdin,
            )
    finally:
        sys.meta_path[:] = saved_meta_path
        if saved_main is not None:
            sys.modules["__main__"] = saved_main
