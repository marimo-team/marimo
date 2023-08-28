from __future__ import annotations

from typing import Optional

from marimo._runtime.context import get_context


# TODO(akshayka): consider refactoring to remove reference cycles ...
class GetState:
    def __init__(self, state: State) -> None:
        self.state = state

    def __call__(self) -> object:
        return self.state.value


class SetState:
    def __init__(self, state: State) -> None:
        self.state = state

    def __call__(self, update: object) -> object:
        if callable(update):
            self.state.value = update(self.state.value)
        else:
            self.state.value = update
        ctx = get_context()
        if not ctx.initialized:
            return
        kernel = ctx.kernel
        assert kernel is not None
        kernel.register_state_update(self.state)


class State:
    def __init__(self, value: object) -> None:
        self.value = value
        self.get_value = GetState(self)
        self.set_value = SetState(self)


def state(value: Optional[object] = None) -> tuple[GetState, SetState]:
    state_instance = State(value)
    return state_instance.get_value, state_instance.set_value
