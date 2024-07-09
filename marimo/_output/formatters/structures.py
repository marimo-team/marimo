# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import json
import sys
from typing import Any, Union

from marimo._messaging.mimetypes import KnownMimeType
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
    t: Union[tuple[Any, ...], list[Any], dict[str, Any]],
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
            t: Union[tuple[Any, ...], list[Any], dict[str, Any]],
        ) -> tuple[KnownMimeType, str]:
            if t and "matplotlib" in sys.modules:
                # Special case for matplotlib:
                #
                # plt.plot() returns a list of lines 2D objects, one for each
                # line, which typically have identical figures. Without this
                # special case, if a plot had (say) 5 lines, it would be shown
                # 5 times.
                import matplotlib.artist  # type: ignore

                if all(isinstance(i, matplotlib.artist.Artist) for i in t):
                    figs = [getattr(i, "figure", None) for i in t]
                    if all(f is not None and f == figs[0] for f in figs):
                        matplotlib_formatter = formatting.get_formatter(
                            figs[0]
                        )
                        if matplotlib_formatter is not None:
                            return matplotlib_formatter(figs[0])
            try:
                formatted_structure = format_structure(t)
            except CyclicStructureError:
                return ("text/plain", str(t))

            return ("application/json", json.dumps(formatted_structure))
