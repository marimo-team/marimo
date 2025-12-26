# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Literal, Optional, Union

from marimo._loggers import marimo_logger
from marimo._output.formatting import as_html
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import build_stateless_plugin
from marimo._plugins.utils import remove_none_values

Logger = marimo_logger()


@mddoc
def stat(
    value: Union[str, int, float],
    label: Optional[str] = None,
    caption: Optional[str] = None,
    direction: Optional[Literal["increase", "decrease"]] = None,
    bordered: bool = False,
    target_direction: Optional[Literal["increase", "decrease"]] = "increase",
    slot: Optional[Html] = None,
) -> Html:
    """Display a statistic.

    Optionally include a label, caption, and direction.

    Args:
        value: the value to display
        label: the label to display
        caption: the caption to display
        direction: the direction of the statistic,
            either `increase` or `decrease`
        bordered: whether to display a border around the statistic
        target_direction: the direction of the statistic
            corresponding to a positive or desirable outcome. Set to
            `increase` when higher values are better, or `decrease`
            when lower values are better. By default the target
            direction is `increase`.
        slot: an optional Html object to place beside the widget


    Returns:
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
                    "target_direction": target_direction,
                    "slot": try_convert_to_html(slot),
                }
            ),
        )
    )


def try_convert_to_html(slot: Any) -> Optional[Html]:
    if slot is None:
        return None

    try:
        return as_html(slot)
    except Exception as e:
        Logger.error(
            f"Error converting slot to Html: {e}. Please ensure it is a valid Html object."
        )
        return None
