# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations


class SetupRootError(Exception):
    """Raised when a setup cell appears as a non-root node in the dependency graph."""


class CycleError(Exception):
    """Raised when the cell dependency graph contains a cycle."""


class ImportStarError(SyntaxError):
    """Raised when a cell uses a wildcard import (``from module import *``)."""


class MultipleDefinitionError(Exception):
    """Raised when the same variable is defined in more than one cell."""


class UnparsableError(Exception):
    """Raised when a cell's code cannot be parsed by the AST parser."""


class IncompleteRefsError(Exception):
    """Raised when a cell references variables that have not been fully resolved."""
