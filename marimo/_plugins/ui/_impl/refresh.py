# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from typing import Final, Optional, Union

from marimo._output.rich_help import mddoc
from marimo._plugins.ui._core.ui_element import UIElement

InternalValue = Union[int, float, str]


@mddoc
class refresh(UIElement[int, int]):
    """
    A refresh button that will auto-refresh its descendants for a
    give interval.

    **Example.**
    ```python
    refresh_button = mo.ui.refresh_button(
        options=["1m", "15m", "30m"],
        default_value="15m",
    )
    ```
    **Attributes.**
    - `default_value`: The default value of the refresh interval.
    - `options`: The options for the refresh interval.
    - `value`: The time in seconds since the refresh has been activated.

    **Initialization Args.**
    - `default_value`: The default value of the refresh interval.
    - `options`: The options for the refresh interval.
    """

    name: Final[str] = "marimo-refresh"

    def __init__(
        self,
        options: list[InternalValue],
        default_value: Optional[InternalValue] = None,
    ) -> None:
        if default_value and not isinstance(default_value, (int, float, str)):
            raise ValueError(
                "Invalid type: `default_value` must be "
                + "an int, float or str, not %s" % type(default_value)
            )

        if not isinstance(options, list):
            raise ValueError(
                "Invalid type: `options` must be a list, not %s"
                % type(options)
            )

        super().__init__(
            component_name=refresh.name,
            initial_value=0,
            label=None,
            args={
                "options": options,
                "default-value": default_value,
            },
        )
        self.options = options
        self.default_value = default_value

    def _convert_value(self, value: int) -> int:
        return value
