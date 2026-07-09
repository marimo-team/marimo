# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import typing
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
    CodeCompletionCommand,
    CommandMessage,
    SetBreakpointsCommand,
    StopKernelCommand,
)
from marimo._runtime.kernel_request_handlers import KernelRequestHandlers
from marimo._runtime.request_router import RequestRouter

if TYPE_CHECKING:
    from tests.conftest import MockedKernel


# All callback bundles that self-register against a router. Order doesn't
# matter — tests only iterate this list, never index into it.
ALL_CALLBACKS: list[type] = [
    SecretsCallbacks,
    DatasetCallbacks,
    SqlCallbacks,
    CacheCallbacks,
    ExternalStorageCallbacks,
    PackagesCallbacks,
]

# Commands that are part of the CommandMessage dispatch surface but are
# intentionally not handled by the kernel's RequestRouter. These are delivered
# on the off-main-loop completion queue and processed by
# start_out_of_band_worker: CodeCompletionCommand (autocomplete) and
# SetBreakpointsCommand (live-debugger breakpoints, so they apply mid-run).
NOT_ROUTED: set[type] = {CodeCompletionCommand, SetBreakpointsCommand}


def _all_command_classes() -> set[type]:
    """Every concrete command type in the CommandMessage discriminated union."""
    return set(typing.get_args(CommandMessage))


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


@pytest.mark.parametrize(
    "callback_cls", ALL_CALLBACKS, ids=lambda c: c.__name__
)
def test_callback_implements_kernel_callback_protocol(
    callback_cls: type,
    mocked_kernel: MockedKernel,
) -> None:
    assert isinstance(callback_cls(mocked_kernel.k), KernelCallback)


def test_no_two_callbacks_claim_the_same_command(
    mocked_kernel: MockedKernel,
) -> None:
    """Each callback bundle must own a disjoint slice of the command surface."""
    owner: dict[type, str] = {}
    for cb_cls in ALL_CALLBACKS:
        router = RequestRouter()
        cb_cls(mocked_kernel.k).register(router)
        for cmd in router._handlers:
            assert cmd not in owner, (
                f"{cmd.__name__} is registered by both "
                f"{owner[cmd]} and {cb_cls.__name__}"
            )
            owner[cmd] = cb_cls.__name__


def test_kernel_handlers_and_callbacks_partition_the_command_surface(
    mocked_kernel: MockedKernel,
) -> None:
    """Kernel-owned handlers and callback-owned handlers must not overlap."""
    kernel_router = RequestRouter()
    KernelRequestHandlers(mocked_kernel.k).register(kernel_router)
    kernel_bound = set(kernel_router._handlers)

    callback_bound: set[type] = set()
    for cb_cls in ALL_CALLBACKS:
        router = RequestRouter()
        cb_cls(mocked_kernel.k).register(router)
        callback_bound |= set(router._handlers)

    overlap = kernel_bound & callback_bound
    assert not overlap, (
        f"commands handled by both KernelRequestHandlers and a callback: "
        f"{sorted(c.__name__ for c in overlap)}"
    )


def test_kernel_router_covers_every_dispatchable_command(
    mocked_kernel: MockedKernel,
) -> None:
    """Every CommandMessage member (minus NOT_ROUTED) has a handler."""
    bound = set(mocked_kernel.k.router._handlers)
    expected = _all_command_classes() - NOT_ROUTED

    missing = expected - bound
    extra = bound - expected
    assert not missing, (
        f"commands with no handler on the kernel router: "
        f"{sorted(c.__name__ for c in missing)}"
    )
    assert not extra, (
        f"handlers bound for commands not in CommandMessage: "
        f"{sorted(c.__name__ for c in extra)}"
    )
