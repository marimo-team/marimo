# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Callable, Final, Optional

from marimo._output.rich_help import mddoc
from marimo._plugins.ui._core.ui_element import UIElement


@mddoc
class switch(UIElement[bool, bool]):
    """A boolean switch.

    Examples:
        ```python
        switch = mo.ui.switch()
        ```

    Attributes:
        value (bool): A boolean, `True` if checked.

    Args:
        value (bool, optional): Default value, True or False. Defaults to False.
        label (str, optional): Markdown label for the element. Defaults to "".
        on_change (Optional[Callable[[bool], None]], optional): Optional callback to run
            when this element's value changes.
    """

    _name: Final[str] = "marimo-switch"

    def __init__(
        self,
        value: bool = False,
        *,
        label: str = "",
        on_change: Optional[Callable[[bool], None]] = None,
    ) -> None:
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
            on_change=on_change,
        )

    def _convert_value(self, value: bool) -> bool:
        return value
