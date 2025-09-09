# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from marimo._lint.diagnostic import Severity

if TYPE_CHECKING:
    from marimo._lint.context import LintContext


class LintRule(ABC):
    """Base class for lint rules."""

    def __init__(
        self,
        code: str,
        name: str,
        description: str,
        severity: Severity,
        fixable: bool,
    ):
        self.code = code
        self.name = name
        self.description = description
        self.severity = severity
        self.fixable = fixable

    @abstractmethod
    async def check(self, ctx: LintContext) -> None:
        """Check notebook for violations of this rule using the provided context."""
        pass
