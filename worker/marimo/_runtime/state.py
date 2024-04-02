# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import types
from typing import Callable, Generic, TypeVar

from marimo._output.rich_help import mddoc
from marimo._runtime.context import ContextNotInitializedError, get_context

T = TypeVar("T")


class State(Generic[T]):
    """Mutable reactive state"""

    def __init__(self, value: T, allow_self_loops: bool = False) -> None:
        self._value = value
        self.allow_self_loops = allow_self_loops

    def __call__(self) -> T:
        return self._value

    def _set_value(self, update: T | Callable[[T], T]) -> None:
        """Update the state and register the update with the kernel"""
        self._value = (
            update(self._value)
            if isinstance(update, (types.MethodType, types.FunctionType))
            else update
        )
        try:
            ctx = get_context()
        except ContextNotInitializedError:
            return
        kernel = ctx.kernel
        assert kernel is not None
        kernel.register_state_update(self)


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
