# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping

    from marimo._runtime.request_router import RequestRouter


@runtime_checkable
class KernelCallback(Protocol):
    """A bundle of kernel command handlers that registers itself with a router."""

    def register(self, router: RequestRouter) -> None: ...


@runtime_checkable
class SupportsTeardown(Protocol):
    """A callback that releases resources when the kernel tears down.

    Optional capability: `Kernel.teardown_callbacks` narrows to it with
    `isinstance`, so only callbacks that implement `teardown` are invoked.
    """

    def teardown(self) -> None: ...


class GlobalsView(Protocol):
    """A view onto user-defined variables (kernel globals)."""

    @property
    def globals(self) -> Mapping[str, Any]: ...
