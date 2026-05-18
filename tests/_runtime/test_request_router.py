# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from marimo._runtime.callbacks import (
    CacheCallbacks,
    DatasetCallbacks,
    ExternalStorageCallbacks,
    KernelCallback,
    PackagesCallbacks,
    SecretsCallbacks,
    SqlCallbacks,
)
from marimo._runtime.commands import (
    ClearCacheCommand,
    CreateNotebookCommand,
    DebugCellCommand,
    DeleteCellCommand,
    ExecuteCellsCommand,
    ExecuteScratchpadCommand,
    ExecuteStaleCellsCommand,
    GetCacheInfoCommand,
    InstallPackagesCommand,
    InvokeFunctionCommand,
    ListDataSourceConnectionCommand,
    ListSecretKeysCommand,
    ListSQLSchemasCommand,
    ListSQLTablesCommand,
    ModelCommand,
    PreviewDatasetColumnCommand,
    PreviewSQLTableCommand,
    RefreshSecretsCommand,
    RenameNotebookCommand,
    StopKernelCommand,
    StorageDownloadCommand,
    StorageListEntriesCommand,
    SyncGraphCommand,
    UpdateCellConfigCommand,
    UpdateUIElementCommand,
    UpdateUserConfigCommand,
    ValidateSQLCommand,
)
from marimo._runtime.kernel_request_handlers import KernelRequestHandlers
from marimo._runtime.request_router import RequestRouter

if TYPE_CHECKING:
    from tests.conftest import MockedKernel


class TestRequestRouter:
    async def test_dispatch_invokes_registered_handler(self) -> None:
        router = RequestRouter()
        seen: list[Any] = []

        async def handler(request: StopKernelCommand) -> None:
            seen.append(request)

        router.register(StopKernelCommand, handler)
        cmd = StopKernelCommand()
        await router.dispatch(cmd)
        assert seen == [cmd]

    async def test_dispatch_unknown_command_raises(self) -> None:
        router = RequestRouter()
        with pytest.raises(ValueError, match="Unknown request"):
            await router.dispatch(StopKernelCommand())

    async def test_register_overwrites_prior_binding(self) -> None:
        router = RequestRouter()
        calls: list[str] = []

        async def first(_: StopKernelCommand) -> None:
            calls.append("first")

        async def second(_: StopKernelCommand) -> None:
            calls.append("second")

        router.register(StopKernelCommand, first)
        router.register(StopKernelCommand, second)
        await router.dispatch(StopKernelCommand())
        assert calls == ["second"]

    async def test_dispatch_routes_by_exact_type(self) -> None:
        router = RequestRouter()
        seen: list[str] = []

        async def stop_handler(_: StopKernelCommand) -> None:
            seen.append("stop")

        async def clear_handler(_: ClearCacheCommand) -> None:
            seen.append("clear")

        router.register(StopKernelCommand, stop_handler)
        router.register(ClearCacheCommand, clear_handler)
        await router.dispatch(ClearCacheCommand())
        await router.dispatch(StopKernelCommand())
        assert seen == ["clear", "stop"]


# ---------------------------------------------------------------------------
# Callback registration contracts
# ---------------------------------------------------------------------------

# Each callback class is expected to bind exactly these command types onto a
# fresh router.
_CALLBACK_BINDINGS: list[tuple[type, set[type]]] = [
    (SecretsCallbacks, {ListSecretKeysCommand, RefreshSecretsCommand}),
    (
        DatasetCallbacks,
        {
            PreviewDatasetColumnCommand,
            PreviewSQLTableCommand,
            ListSQLTablesCommand,
            ListSQLSchemasCommand,
            ListDataSourceConnectionCommand,
        },
    ),
    (SqlCallbacks, {ValidateSQLCommand}),
    (CacheCallbacks, {ClearCacheCommand, GetCacheInfoCommand}),
    (
        ExternalStorageCallbacks,
        {StorageListEntriesCommand, StorageDownloadCommand},
    ),
    (PackagesCallbacks, {InstallPackagesCommand}),
]


@pytest.mark.parametrize(
    ("callback_cls", "expected_commands"),
    _CALLBACK_BINDINGS,
    ids=lambda v: v.__name__ if isinstance(v, type) else "",
)
def test_callback_implements_kernel_callback_protocol(
    callback_cls: type,
    expected_commands: set[type],
    mocked_kernel: MockedKernel,
) -> None:
    del expected_commands
    callback = callback_cls(mocked_kernel.k)
    # Runtime-checkable Protocol membership.
    assert isinstance(callback, KernelCallback)


@pytest.mark.parametrize(
    ("callback_cls", "expected_commands"),
    _CALLBACK_BINDINGS,
    ids=lambda v: v.__name__ if isinstance(v, type) else "",
)
def test_callback_register_binds_expected_commands(
    callback_cls: type,
    expected_commands: set[type],
    mocked_kernel: MockedKernel,
) -> None:
    router = RequestRouter()
    callback_cls(mocked_kernel.k).register(router)
    assert set(router._handlers.keys()) == expected_commands


def test_kernel_request_handlers_binds_kernel_owned_commands(
    mocked_kernel: MockedKernel,
) -> None:
    router = RequestRouter()
    KernelRequestHandlers(mocked_kernel.k).register(router)
    # The kernel-owned set: anything that requires a request-context wrap, a
    # completion notification, or directly delegates to a Kernel method.
    expected = {
        CreateNotebookCommand,
        DeleteCellCommand,
        ExecuteCellsCommand,
        SyncGraphCommand,
        ExecuteScratchpadCommand,
        ExecuteStaleCellsCommand,
        InvokeFunctionCommand,
        DebugCellCommand,
        RenameNotebookCommand,
        UpdateCellConfigCommand,
        UpdateUIElementCommand,
        ModelCommand,
        UpdateUserConfigCommand,
        StopKernelCommand,
    }
    assert set(router._handlers.keys()) == expected


def test_kernel_router_has_full_dispatch_table(
    mocked_kernel: MockedKernel,
) -> None:
    """All 27 commands the kernel knows about are bound exactly once."""
    handlers = mocked_kernel.k.router._handlers
    expected = (
        # Kernel-owned
        {
            CreateNotebookCommand,
            DeleteCellCommand,
            ExecuteCellsCommand,
            SyncGraphCommand,
            ExecuteScratchpadCommand,
            ExecuteStaleCellsCommand,
            InvokeFunctionCommand,
            DebugCellCommand,
            RenameNotebookCommand,
            UpdateCellConfigCommand,
            UpdateUIElementCommand,
            ModelCommand,
            UpdateUserConfigCommand,
            StopKernelCommand,
        }
        # Callback-owned
        | {ListSecretKeysCommand, RefreshSecretsCommand}
        | {
            PreviewDatasetColumnCommand,
            PreviewSQLTableCommand,
            ListSQLTablesCommand,
            ListSQLSchemasCommand,
            ListDataSourceConnectionCommand,
        }
        | {ValidateSQLCommand}
        | {ClearCacheCommand, GetCacheInfoCommand}
        | {StorageListEntriesCommand, StorageDownloadCommand}
        | {InstallPackagesCommand}
    )
    assert set(handlers.keys()) == expected
    assert len(handlers) == 27
