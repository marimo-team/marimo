# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from typing import Callable, Generic, TypeVar

from marimo._output.rich_help import mddoc
from marimo._runtime.context import get_context

T = TypeVar("T")


class State(Generic[T]):
    """Mutable reactive state"""

    def __init__(self, value: T) -> None:
        self._value = value

    @property
    def value(self) -> T:
        return self._value

    def _set_value(self, value: T) -> None:
        """Update the state and register the update with the kernel"""
        self._value = value
        ctx = get_context()
        if not ctx.initialized:
            return
        kernel = ctx.kernel
        assert kernel is not None
        kernel.register_state_update(self)


@mddoc
def state(value: T) -> tuple[State[T], Callable[[T], None]]:
    """Mutable reactive state

    This function takes an initial value and returns:

    - a state object with a value attribute
    - a setter function to set the state's value

    When you call the setter function and update the state value in one cell,
    all other cells that read any global variables assigned to the state
    object will automatically run.

    You can use this function in conjunction with `UIElement` `on_change`
    handlers to trigger side-effects when an element's value is updated. For
    example, you can tie multiple UI elements to derive their values from
    shared state.

    **Basic Usage.**


    Create state:

    ```python
    count, set_count = mo.state(0)
    ```

    Read the value:

    ```python
    count.value
    ```

    Update the state:

    ```
    set_count(1)
    ```

    Update the state based on the current value:

    ```
    set_count(count.value + 1)
    ```

    *Note: Never mutate the state object directly. You should only change its
    value through its setter.*

    **Synchronizing multiple UI elements.**

    ```python
    state, set_state = mo.state(0)
    ```

    ```python
    # updating the state through the slider will recreate the number (below)
    slider = mo.ui.slider(0, 100, value=state.value, on_change=set_state)
    ```

    ```python
    # updating the state through the number will recreate the slider (above)
    number = mo.ui.number(0, 100, value=state.value, on_change=set_state)
    ```

    ```python
    # slider and number are synchronized to have the same value (try it!)
    [slider, number]
    ```

    **Args**:

    - `value`: initial value of the state

    **Returns**:

    - `State` object
    - setter function that takes a new value, or a callable taking the current
      value and returning a new value, as its argument
    """
    state_instance = State(value)
    return state_instance, state_instance._set_value
