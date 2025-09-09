# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from abc import ABC, abstractmethod

from marimo._ast.parse import NotebookSerialization
from marimo._lint.diagnostic import Diagnostic, Severity


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
    def check(self, notebook: NotebookSerialization) -> list[Diagnostic]:
        """Check notebook for violations of this rule."""
        pass
