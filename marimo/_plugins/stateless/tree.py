# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Optional

from marimo._output.formatters.structures import format_structure
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import JSONType
from marimo._plugins.stateless import json_output
from marimo._utils.flatten import CyclicStructureError


@mddoc
def tree(
    items: list[Any] | tuple[Any] | dict[Any, Any],
    label: Optional[str] = None,
    as_json: bool = False,
) -> Html:
    """Render a nested structure of lists, tuples, or dicts as a tree.

    This function can be used to visualize objects structures in JSON format,
    the as_json argument is used to control the output format (and Copy).

    Example:
        ```python3
        mo.tree(
            ["entry", "another entry", {"key": [0, 1, 2]}], label="A tree."
        )
        ```

    Notes:
        - The enabled `as_json` argument will format the output in JSON format,
        which means that the floats will be displayed as numbers, and sets and
        tuples will be displayed as lists. JavaScript can handle these types
        of values with some changes.

    Args:
        items: nested structure of lists, tuples, or dicts
        label: optional text label for the tree
        as_json: if True, the output will be in JSON format
            (and Copy), otherwise it will be in Python format

    Returns:
        Html: `Html` object
    """
    if not isinstance(items, (list, tuple, dict)):
        raise ValueError(
            "Argument `items` must be a list, tuple, or dict, "
            + f"but got: {type(items)}"
        )

    json_data: JSONType
    try:
        json_data = format_structure(items, json_compat_values=as_json)
    except CyclicStructureError:
        json_data = str(items)
    return json_output.json_output(
        json_data=json_data,
        name=label,
        value_types="json" if as_json else "python",
    )
