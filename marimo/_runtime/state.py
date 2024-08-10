# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import types
import weakref
from dataclasses import dataclass
from typing import Any, Callable, Generic, Optional, TypeVar

from marimo._output.rich_help import mddoc
from marimo._runtime.context import ContextNotInitializedError, get_context

T = TypeVar("T")


@dataclass
class StateItem(Generic[T]):
    id: int
    ref: weakref.ref[State[T]]


class StateRegistry:
    _states: dict[str, StateItem[Any]] = {}
    _inv_states: dict[int, set[str]] = {}

    @staticmethod
    def register(name: str, state: State[T]) -> None:
        if id(state) in StateRegistry._inv_states:
            ref = next(iter(StateRegistry._inv_states[id(state)]))
            if StateRegistry._states[ref].id != id(state):
                for ref in StateRegistry._inv_states[id(state)]:
                    del StateRegistry._states[ref]
                StateRegistry._inv_states[id(state)].clear()
        StateRegistry._states[name] = StateItem(id(state), weakref.ref(state))
        id_to_ref = StateRegistry._inv_states.get(id(state), set())
        id_to_ref.add(name)
        StateRegistry._inv_states[id(state)] = id_to_ref

    @staticmethod
    def retain_active_states(active_variables: set[str]) -> None:
        """Retains only the active states in the registry."""
        # Remove all non-active states by name
        active_state_ids = set()
        for state_name in list(StateRegistry._states.keys()):
            if state_name not in active_variables:
                StateRegistry._inv_states.pop(
                    id(StateRegistry._states[state_name]), None
                )
                del StateRegistry._states[state_name]
            else:
                active_state_ids.add(id(StateRegistry._states[state_name]))

        # Remove all non-active states by id
        for state_id in list(StateRegistry._inv_states.keys()):
            if state_id not in active_state_ids:
                del StateRegistry._inv_states[state_id]

    @staticmethod
    def lookup(name: str) -> Optional[State[T]]:
        if name in StateRegistry._states:
            return StateRegistry._states[name].ref()
        return None


class State(Generic[T]):
    """Mutable reactive state"""

    def __init__(self, value: T, allow_self_loops: bool = False) -> None:
        self._value = value
        self.allow_self_loops = allow_self_loops
        self._set_value = SetFunctor(self)

    def __call__(self) -> T:
        return self._value


class SetFunctor(Generic[T]):
    """Typed function tied to a state instance"""

    def __init__(self, state: State[T]):
        self._state = state

    def __call__(self, update: T | Callable[[T], T]) -> None:
        self._state._value = (
            update(self._state._value)
            if isinstance(update, (types.MethodType, types.FunctionType))
            else update
        )
        try:
            ctx = get_context()
        except ContextNotInitializedError:
            return
        ctx.register_state_update(self._state)


@mddoc
def state(
    value: T, allow_self_loops: bool = False
) -> tuple[State[T], Callable[[T], None]]:
    """Mutable reactive state

    This function takes an initial value and returns:

    - a getter function that reads the state value
    - a setter function to set the state's value

    When you call the setter function and update the state value in one cell,
    all *other* cells that read any global variables assigned to the getter
    will automatically run. By default, the cell that called the setter
    function won't be re-run, even if it references the getter; to allow a
    state setter to possibly run the caller cell, use the keyword argument
    `allow_self_loops=True`.

    You can use this function in conjunction with `UIElement` `on_change`
    handlers to trigger side-effects when an element's value is updated. For
    example, you can tie multiple UI elements to derive their values from
    shared state.

    **Basic Usage.**


    Create state:

    ```python
    get_count, set_count = mo.state(0)
    ```

    Read the value:

    ```python
    get_count()
    ```

    Update the state:

    ```
    set_count(1)
    ```

    Update the state based on the current value:

    ```
    set_count(lambda value: value + 1)
    ```

    *Note: Never mutate the state directly. You should only change its
    value through its setter.*

    **Synchronizing multiple UI elements.**

    ```python
    get_state, set_state = mo.state(0)
    ```

    ```python
    # updating the state through the slider will recreate the number (below)
    slider = mo.ui.slider(0, 100, value=get_state(), on_change=set_state)
    ```

    ```python
    # updating the state through the number will recreate the slider (above)
    number = mo.ui.number(0, 100, value=get_state(), on_change=set_state)
    ```

    ```python
    # slider and number are synchronized to have the same value (try it!)
    [slider, number]
    ```

    **Warning.** Do not store `marimo.ui` elements in state; doing so can
    lead to hard-to-diagnose bugs.

    **Args**:

    - `value`: initial value of the state
    - `allow_self_loops`: if True, if a cell calls a state setter
      and also references its getter, the caller cell will be re-run;
      defaults to `False`.



    **Returns**:

    - getter function that retrieves the state value
    - setter function that takes a new value, or a function taking the current
      value as its argument and returning a new value
    """
    state_instance = State(value, allow_self_loops=allow_self_loops)
    return state_instance, state_instance._set_value
