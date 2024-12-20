# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Optional


class MarimoRuntimeException(BaseException):
    """Wrapper for all marimo runtime exceptions."""


class MarimoNameError(NameError):
    """Wrap a name error to rethrow later."""

    def __init__(self, msg: str, ref: str) -> None:
        super().__init__(msg)
        self.ref = ref


class MarimoMissingRefError(BaseException):
    def __init__(
        self, ref: str, name_error: Optional[NameError] = None
    ) -> None:
        super(MarimoMissingRefError, self).__init__(ref)
        self.ref = ref
        self.name_error = name_error
