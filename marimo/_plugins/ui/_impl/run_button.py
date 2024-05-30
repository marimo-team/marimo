# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Callable, Final, Literal, Optional

from marimo._output.rich_help import mddoc
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._plugins.ui._impl.input import button
from marimo._runtime.context.types import ContextNotInitializedError


@mddoc
class run_button(UIElement[Any, Any]):
    """
    A button that can be used to trigger computation.

    **Example.**

    ```python
    # a button that when clicked will have its value set to True;
    # any cells referencing that button will automatically run.
    button = mo.ui.run_button()
    button
    ```

    ```python
    slider = mo.ui.slider(1, 10)
    slider
    ```

    ```python
    # if the button hasn't been clicked, don't run.
    mo.stop(not button.value)

    slider.value
    ```

    When clicked, `run_button`'s value is set to `True`, and any cells
    referencing it are run. After those cells are run, `run_button`'s
    value will automatically be set back to `False` as long as automatic
    execution is enabled.

    **Attributes.**

    - `value`: the value of the button; `True` when clicked, and reset to
      `False` after cells referencing the button finish running (when
      automatic execution is enabled).

    **Initialization Args.**

    - `kind`: 'neutral', 'success', 'warn', or 'danger'
    - `disabled`: whether the button is disabled
    - `tooltip`: a tooltip to display for the button
    - `label`: text label for the element
    - `on_change`: optional callback to run when this element's value changes
    - `full_width`: whether the input should take up the full width of its
        container
    """

    # We reuse the button plugin on the frontend, UI/logic are the same
    _name: Final[str] = button._name

    def __init__(
        self,
        kind: Literal["neutral", "success", "warn", "danger"] = "neutral",
        disabled: bool = False,
        tooltip: Optional[str] = None,
        *,
        label: str = "click to run",
        on_change: Optional[Callable[[Any], None]] = None,
        full_width: bool = False,
    ) -> None:
        self._initial_value = False
        super().__init__(
            component_name=button._name,
            # frontend's value is a counter
            initial_value=0,
            label=label,
            args={
                "kind": kind,
                "disabled": disabled,
                "tooltip": tooltip,
                "full-width": full_width,
            },
            on_change=on_change,
        )

    def _convert_value(self, value: Any) -> Any:
        if value == 0:
            # frontend's value == 0 only during initialization; first value
            # frontend will send is 1
            return False
        else:
            return True

    def _on_update_completion(self) -> None:
        from marimo._runtime.context import get_context
        from marimo._runtime.context.kernel_context import KernelRuntimeContext

        try:
            ctx = get_context()
        except ContextNotInitializedError:
            self._value = False
            return

        if isinstance(ctx, KernelRuntimeContext) and ctx.lazy:
            # Resetting to False in lazy kernels makes the button pointless,
            # since its value hasn't been read by downstream cells on update
            # completion.
            #
            # The right thing to do would be to somehow set to False after
            # all cells that were marked stale because of the update were run,
            # but that's too complicated.
            return
        else:
            self._value = False
