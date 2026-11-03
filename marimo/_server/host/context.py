# Copyright 2026 Marimo. All rights reserved.
"""Shared state for host API routes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from marimo._core.operations import Mutations

if TYPE_CHECKING:
    from marimo._server.host.bridge import SessionBridge


@dataclass
class HostContext:
    """Host API token, address, session bridge, and retry receipts."""

    bridge: SessionBridge
    token: str
    port: int
    mutations: Mutations = field(init=False)

    def __post_init__(self) -> None:
        self.mutations = Mutations(self.bridge.host)
