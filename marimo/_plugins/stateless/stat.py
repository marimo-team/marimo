# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Literal, Optional, Union

from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import build_stateless_plugin
from marimo._plugins.utils import remove_none_values


@mddoc
def stat(
    value: Union[str, int, float],
    label: Optional[str] = None,
    caption: Optional[str] = None,
    direction: Optional[Literal["increase", "decrease"]] = None,
    bordered: bool = False,
) -> Html:
    """Display a statistic.

    Optionally include a label, caption, and direction.

    **Args.**

    - `value`: the value to display
    - `label`: the label to display
    - `caption`: the caption to display
    - `direction`: the direction of the statistic,
        either `increase` or `decrease`
    - `bordered`: whether to display a border around the statistic

    **Returns.**

    An `Html` object representing the statistic.
    """
    return Html(
        build_stateless_plugin(
            component_name="marimo-stat",
            args=remove_none_values(
                {
                    "value": value,
                    "label": label,
                    "caption": caption,
                    "direction": direction,
                    "bordered": bordered,
                }
            ),
        )
    )
