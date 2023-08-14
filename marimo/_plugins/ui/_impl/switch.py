# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from typing import Final

from marimo._output.rich_help import mddoc
from marimo._plugins.ui._core.ui_element import UIElement


@mddoc
class switch(UIElement[bool, bool]):
    """
    A boolean switch.

    **Example.**

    ```python
    switch = mo.ui.switch()
    ```

    **Attributes.**

    - `value`: A boolean, `True` if checked.

    **Initialization Args.**

    - `value`: default value, True or False
    - `label`: text label for the element
    """

    _name: Final[str] = "marimo-switch"

    def __init__(self, value: bool = False, label: str = "") -> None:
        if not isinstance(value, bool):
            raise ValueError(
                "Invalid type: `value` must be a bool, but got %s"
                % type(value)
            )
        if not isinstance(label, str):
            raise ValueError(
                "Invalid type: `label` must be a str, but got %s" % type(label)
            )

        super().__init__(
            component_name=switch._name,
            initial_value=value,
            label=label,
            args={},
        )

    def _convert_value(self, value: bool) -> bool:
        return value
