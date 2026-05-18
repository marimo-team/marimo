# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from marimo._runtime.request_router import RequestRouter


@runtime_checkable
class KernelCallback(Protocol):
    """A bundle of kernel command handlers that registers itself with a router."""

    def register(self, router: RequestRouter) -> None: ...


class GlobalsView(Protocol):
    """A view onto user-defined variables (kernel globals)."""

    @property
    def globals(self) -> dict[Any, Any]: ...
