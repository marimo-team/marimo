# Copyright 2023 Marimo. All rights reserved.
class CycleError(Exception):
    pass


class MultipleDefinitionError(Exception):
    pass


class DeleteNonlocalError(Exception):
    pass


class UnparsableError(Exception):
    pass
