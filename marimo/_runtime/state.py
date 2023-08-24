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

    def __call__(self, value: object) -> object:
        self.state.value = value
        ctx = get_context()
        if not ctx.initialized:
            return
        # TODO: need to handle case when triggered by UI element (runner will
        # be None, need to communciate directly with kernel)
        runner = ctx.kernel.runner
        assert runner is not None
        runner.register_state_update(self.state)


class State:
    def __init__(self, value: object) -> None:
        self.value = value
        self.get_value = GetState(self)
        self.set_value = SetState(self)


def state(value: Optional[object] = None) -> tuple[GetState, SetState]:
    state_instance = State(value)
    return state_instance.get_value, state_instance.set_value
