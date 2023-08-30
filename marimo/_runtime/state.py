# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from typing import Callable, Generic, TypeVar

from marimo._runtime.context import get_context

T = TypeVar("T")


class State(Generic[T]):
    def __init__(self, value: T) -> None:
        self._value = value

    @property
    def value(self) -> T:
        return self._value

    def _set_value(self, update: T | Callable[[T], T]) -> None:
        if callable(update):
            self._value = update(self.value)
        else:
            self._value = update
        ctx = get_context()
        if not ctx.initialized:
            return
        kernel = ctx.kernel
        assert kernel is not None
        kernel.register_state_update(self)


def state(value: T) -> tuple[State[T], Callable[[T | Callable[[T], T]], None]]:
    state_instance = State(value)
    return state_instance, state_instance._set_value
