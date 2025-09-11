# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from marimo._lint.diagnostic import Severity

if TYPE_CHECKING:
    from marimo._lint.context import RuleContext


class LintRule(ABC):
    """Base class for lint rules."""

    # Class attributes that must be set by subclasses
    code: str
    name: str
    description: str
    severity: Severity
    fixable: bool

    @abstractmethod
    async def check(self, ctx: RuleContext) -> None:
        """Check notebook for violations of this rule using the provided context."""
        pass
