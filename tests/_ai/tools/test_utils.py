# Copyright 2025 Marimo. All rights reserved.
"""Shared fixtures and mocks for AI tools tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class MockSessionView:
    """Mock session view for testing."""

    cell_notifications: dict | None = None
    last_execution_time: dict | None = None
    variable_values: dict | None = None
    data_connectors: Any = None

    def __post_init__(self) -> None:
        if self.cell_notifications is None:
            self.cell_notifications = {}
        if self.last_execution_time is None:
            self.last_execution_time = {}
        if self.variable_values is None:
            self.variable_values = {}


@dataclass
class MockSession:
    """Mock session for testing."""

    _session_view: MockSessionView

    @property
    def session_view(self) -> MockSessionView:
        return self._session_view
