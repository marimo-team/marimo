# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import json
from typing import Any, Union

from marimo._output import formatting
from marimo._output.formatters.formatter_factory import FormatterFactory
from marimo._utils.flatten import CyclicStructureError, flatten


def _leaf_formatter(value: object) -> str:
    formatter = formatting.get_formatter(value)
    if formatter is None:
        try:
            return f"text/plain:{json.dumps(value)}"
        except TypeError:
            return f"text/plain:{value}"
    return ":".join(formatter(value))


def format_structure(
    t: Union[tuple[Any, ...], list[Any], dict[str, Any]]
) -> Union[tuple[Any, ...], list[Any], dict[str, Any]]:
    """Format the leaves of a structure.

    Returns a structure of the same shape as `t` with formatted
    leaves.
    """
    flattened, repacker = flatten(t, json_compat_keys=True)
    return repacker([_leaf_formatter(v) for v in flattened])


class StructuresFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> None:
        return None

    def register(self) -> None:
        @formatting.formatter(list)
        @formatting.formatter(tuple)
        @formatting.formatter(dict)
        def _format_structure(
            t: Union[tuple[Any, ...], list[Any], dict[str, Any]]
        ) -> tuple[str, str]:
            try:
                formatted_structure = format_structure(t)
            except CyclicStructureError:
                return ("text/plain", str(t))

            return ("application/json", json.dumps(formatted_structure))
