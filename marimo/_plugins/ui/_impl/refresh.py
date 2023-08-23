# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from typing import Final, Optional, Union

from marimo._output.rich_help import mddoc
from marimo._plugins.ui._core.ui_element import UIElement


@mddoc
class refresh(UIElement[int, int]):
    """
    A refresh button that will auto-refresh its descendants for a
    given interval.
    Each option value can either be a number (int or float) in seconds or a
    human-readable string (e.g. "1s", "10s", "1m").

    You can also combine multiple time units (e.g. "1m 30s").

    **Example.**
    ```python
    refresh_button = mo.ui.refresh_button(
        options=["1m", "5m 30s", "10m"],
        default_interval="10m",
    )
    ```
    **Attributes.**
    - `options`: The options for the refresh interval, as a list of
    human-readable strings or numbers (int or float) in seconds.
    - `default_interval`: The default value of the refresh interval.
    - `value`: The time in seconds since the refresh has been activated.

    **Initialization Args.**
    - `options`: The options for the refresh interval, as a list of
    human-readable strings or numbers (int or float) in seconds.
    If no options are provided and default_interval is provided,
    the options will be generated automatically.
    If no options are provided and default_interval is not provided,
    the refresh button will not be displayed with a dropdown for auto-refresh.
    - `default_interval`: The default value of the refresh interval.
    """

    name: Final[str] = "marimo-refresh"

    def __init__(
        self,
        options: Optional[list[Union[int, float, str]]] = None,
        default_interval: Optional[Union[int, float, str]] = None,
    ) -> None:
        if default_interval and not isinstance(
            default_interval, (int, float, str)
        ):
            raise ValueError(
                "Invalid type: `default_interval` must be "
                + "an int, float or str, not %s" % type(default_interval)
            )

        # If no options are provided and default_interval is provided,
        if options is None:
            self.options = [default_interval] if default_interval else []
        else:
            self.options = options

        if not isinstance(self.options, list):
            raise ValueError(
                "Invalid type: `options` must be a list, not %s"
                % type(self.options)
            )

        super().__init__(
            component_name=refresh.name,
            initial_value=0,
            label=None,
            args={
                "options": self.options,
                "default-interval": default_interval,
            },
        )
        self.default_interval = default_interval

    def _convert_value(self, value: int) -> int:
        return value
