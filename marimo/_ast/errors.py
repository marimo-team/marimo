# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations


class SetupRootError(Exception):
    pass


class CycleError(Exception):
    pass


class ImportStarError(SyntaxError):
    pass


class MultipleDefinitionError(Exception):
    pass


class UnparsableError(Exception):
    pass


class IncompleteRefsError(Exception):
    pass
