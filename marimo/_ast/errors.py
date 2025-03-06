# Copyright 2024 Marimo. All rights reserved.
class CycleError(Exception):
    pass


class ImportStarError(SyntaxError):
    pass


class MultipleDefinitionError(Exception):
    pass


class DeleteNonlocalError(Exception):
    pass


class UnparsableError(Exception):
    pass
