# Copyright 2024 Marimo. All rights reserved.
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
