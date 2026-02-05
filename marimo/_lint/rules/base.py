# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Literal

from marimo._lint.diagnostic import Severity

if TYPE_CHECKING:
    from marimo._lint.context import RuleContext
    from marimo._lint.diagnostic import Diagnostic
    from marimo._schemas.serialization import NotebookSerialization


class LintRule(ABC):
    """Base class for lint rules."""

    # Class attributes that must be set by subclasses
    code: str
    name: str
    description: str
    severity: Severity
    fixable: bool | Literal["unsafe"]

    @abstractmethod
    async def check(self, ctx: RuleContext) -> None:
        """Check notebook for violations of this rule using the provided context."""
        pass


class UnsafeFixRule(LintRule):
    """Base class for rules that can apply unsafe fixes to notebook IR."""

    @abstractmethod
    def apply_unsafe_fix(
        self, notebook: NotebookSerialization, diagnostics: list[Diagnostic]
    ) -> NotebookSerialization:
        """Apply unsafe fix to notebook IR.

        Args:
            notebook: The notebook to modify
            diagnostics: List of diagnostics that triggered this fix

        Returns:
            Modified notebook serialization
        """
        pass
