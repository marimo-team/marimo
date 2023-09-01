# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from typing import Callable, Final, Optional, Union

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

    - `value`: The time in seconds since the refresh has been activated.

    **Initialization Args.**

    - `options`: The options for the refresh interval, as a list of
    human-readable strings or numbers (int or float) in seconds.
    If no options are provided and default_interval is provided,
    the options will be generated automatically.
    If no options are provided and default_interval is not provided,
    the refresh button will not be displayed with a dropdown for auto-refresh.
    - `default_interval`: The default value of the refresh interval.
    - `label`: optional text label for the element
    - `on_change`: optional callback to run when this element's value changes
    """

    name: Final[str] = "marimo-refresh"

    def __init__(
        self,
        options: Optional[list[Union[int, float, str]]] = None,
        default_interval: Optional[Union[int, float, str]] = None,
        *,
        label: str = "",
        on_change: Optional[Callable[[int], None]] = None,
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
            resolved_options = [default_interval] if default_interval else []
        else:
            resolved_options = options

        if not isinstance(resolved_options, list):
            raise ValueError(
                "Invalid type: `options` must be a list, not %s"
                % type(resolved_options)
            )

        # If has options and default_interval is provided,
        # check that default_interval is in options.
        if (
            default_interval
            and len(resolved_options) > 0
            and (default_interval not in resolved_options)
        ):
            raise ValueError(
                "Invalid value: `default_interval` must be "
                + "one of the options, not %s" % default_interval
            )

        super().__init__(
            component_name=refresh.name,
            initial_value=0,
            label=label,
            args={
                "options": resolved_options,
                "default-interval": default_interval,
            },
            on_change=on_change,
        )

    def _convert_value(self, value: int) -> int:
        return value
